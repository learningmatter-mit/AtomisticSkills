import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import ase.units

from src.utils.dft.atomate2_utils import Atomate2Handler

# Fake document resembling jobflow VASP TaskDoc
MOCK_TASK_DOC = {
    "uuid": "fake-uuid-1234",
    "flow_id": "fake-flow-uuid-5678",
    "output": {
        "chemsys": "Te-S-T",
        "formula_pretty": "TeST",
        "structure": {"fake_key": "fake_structure"},
        "output": {
            "energy": -123.456,
            "forces": [[0.1, -0.2, 0.3]],
            "stress": [
                [1.0, 0.0, 0.0],
                [0.0, 2.0, 0.0],
                [0.0, 0.0, 3.0]
            ]
        }
    }
}

class TestAtomate2Handler(unittest.TestCase):
    
    @patch("jobflow_remote.jobs.jobcontroller.JobController")
    def test_get_results_by_formula(self, mock_jc_class):
        """Test fetching deeply nested MLIP data using pure MongoDB querying"""
        mock_jc = MagicMock()
        mock_jc_class.from_project_name.return_value = mock_jc
        
        # Mock MongoDB chaining: find(query).sort().limit()
        mock_cursor = MagicMock()
        mock_sort = MagicMock()
        mock_limit = MagicMock()
        
        mock_jc.jobstore.docs_store._collection.find.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_sort
        mock_sort.limit.return_value = mock_limit
        
        # Make the iterable return our fake document
        mock_limit.__iter__.return_value = [MOCK_TASK_DOC]
        
        handler = Atomate2Handler()
        results = handler.get_results_by_formula(
            chemsys="Te-S-T", formula="TeST", project_name="mock_proj", limit=10
        )
        
        # Verify JC Instantiation
        mock_jc_class.from_project_name.assert_called_once_with("mock_proj")
        
        # Verify MongoDB query parameters
        find_args = mock_jc.jobstore.docs_store._collection.find.call_args[0][0]
        assert find_args == {"output.formula_pretty": "TeST", "output.chemsys": "Te-S-T"}
        mock_cursor.sort.assert_called_once_with("output.last_updated", -1)
        mock_sort.limit.assert_called_once_with(10)
        
        # Verify extracted properties
        assert len(results) == 1
        res = results[0]
        assert res["energy"] == -123.456
        assert res["forces"] == [[0.1, -0.2, 0.3]]
        
        # Verify converted stress from kB to GPa (and sign convention)
        expected_stress = (-np.array(MOCK_TASK_DOC["output"]["output"]["stress"]) * 0.1 * ase.units.GPa).tolist()
        np.testing.assert_almost_equal(res["stress"], expected_stress)
        
        assert res["structure"] == {"fake_key": "fake_structure"}
        assert res["job_uuid"] == "fake-uuid-1234"
        assert res["formula"] == "TeST"
        assert res["chemsys"] == "Te-S-T"

    @patch("jobflow_remote.jobs.jobcontroller.JobController")
    def test_get_results_by_id(self, mock_jc_class):
        """Test fallback extraction via job UUIDs / flow mapping"""
        mock_jc = MagicMock()
        mock_jc_class.from_project_name.return_value = mock_jc
        
        class FakeFlowInfo:
            def __init__(self, flow_id, job_ids):
                self.flow_id = flow_id
                self.job_ids = job_ids
        
        # Mock flow info resolution
        mock_jc.get_flows_info.return_value = [
            FakeFlowInfo(flow_id="flow_1", job_ids=["job_A"])
        ]
        
        # Mock actual jobstore output
        mock_jc.jobstore.get_output.return_value = MOCK_TASK_DOC
        
        handler = Atomate2Handler()
        # Non-digits are treated as uuids and handled with flow expansion
        results = handler.get_results_by_id(
            flow_ids=["flow_1"], project_name="mock_proj"
        )
        
        # Should correctly iterate over the flow's job_ids to grab jobs
        mock_jc.jobstore.get_output.assert_called_with("job_A")
        
        assert len(results) == 1
        assert results[0]["energy"] == -123.456
        assert results[0]["forces"] == [[0.1, -0.2, 0.3]]
