import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from pymatgen.core import Structure

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.mcp_server.atomate2_server import run_atomate2_vasp_calculation

@patch('jobflow.Flow')
@patch('src.mcp_server.atomate2_server.Atomate2Handler')
def test_remote_submission(mock_handler_class, mock_flow_class):
    # Setup mock returns
    mock_instance = mock_handler_class.return_value
    mock_instance.check_environment.return_value = {"atomate2": True}
    mock_instance.get_project_name.return_value = "mock_project"
    mock_instance.run_remote.return_value = "fake-job-id"
    mock_instance.check_status.return_value = {"status": "COMPLETED"}
    mock_instance.extract_results.return_value = {"results": [{"energy": -12.34}]}
    
    # ensure multiple flows return distinct mocks
    mock_instance.get_flow_maker.return_value.make.side_effect = lambda x: MagicMock()

    # load_structures logic
    si = Structure(
        lattice=[[0, 2.715, 2.715], [2.715, 0, 2.715], [2.715, 2.715, 0]],
        species=["Si", "Si"],
        coords=[[0, 0, 0], [0.25, 0.25, 0.25]],
    )
    mock_instance.load_structures.return_value = [si]

    output_dir = ".agents/test/remote_test_si_mock"
    os.makedirs(output_dir, exist_ok=True)
    si_path = os.path.join(output_dir, "Si.cif")
    si.to(filename=si_path)
    
    # 1. Submit remotely
    response = run_atomate2_vasp_calculation(
        structures_path=si_path,
        output_dir=output_dir,
        preset_type="omat",
        calculation_type="static",
        config={"NELM": 1},
        execution_mode="remote"
    )
    assert "fake-job-id" in response

    # 2. Check status
    status_response = run_atomate2_vasp_calculation(
        structures_path=si_path,
        output_dir=output_dir,
        check_only=True,
        job_id="fake-job-id"
    )
    status = json.loads(status_response)
    assert status['status'] == "COMPLETED"
    
    # 3. Extract results
    results_response = run_atomate2_vasp_calculation(
        structures_path=si_path,
        output_dir=output_dir,
        job_id="fake-job-id"
    )
    assert "Successfully extracted results" in results_response

    # Cleanup
    import shutil
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
