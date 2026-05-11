import pytest
import json
from unittest.mock import patch, MagicMock
from src.mcp_server import atomate2_server

@pytest.fixture
def mock_handler():
    with patch('src.mcp_server.atomate2_server.Atomate2Handler') as mock:
        instance = mock.return_value
        instance.check_environment.return_value = {"atomate2": True, "vasp": True, "potcar": True}
        instance.get_project_name.return_value = "mock_project"
        yield instance

@pytest.mark.atomate2
def test_run_atomate2_vasp_calculation(skip_if_wrong_env, mock_handler):
    res = atomate2_server.run_atomate2_vasp_calculation(
        structures_path="dummy.cif",
        output_dir="dummy_out",
        check_only=True
    )
    assert "Environment is ready" in res

@pytest.mark.atomate2
def test_run_atomate2_vasp_calculation_optics_check_only(skip_if_wrong_env):
    res = atomate2_server.run_atomate2_vasp_calculation(
        structures_path="dummy.cif",
        output_dir="dummy_out",
        calculation_type="optics",
        check_only=True
    )
    assert "error" not in res

@pytest.mark.atomate2
def test_run_atomate2_vasp_calculation_lobster_check_only(skip_if_wrong_env):
    res = atomate2_server.run_atomate2_vasp_calculation(
        structures_path="dummy.cif",
        output_dir="dummy_out",
        calculation_type="lobster",
        check_only=True
    )
    assert "error" not in res

@pytest.mark.atomate2
def test_get_atomate2_results_by_id(skip_if_wrong_env, mock_handler):
    mock_handler.get_results_by_id.return_value = [{"energy": -5.0}]
    res = atomate2_server.get_atomate2_results_by_id(job_ids=["dummy"])
    assert res["count"] == 1
    assert res["results"][0]["energy"] == -5.0

@pytest.mark.atomate2
def test_get_atomate2_results_by_formula(skip_if_wrong_env, mock_handler):
    mock_handler.get_results_by_formula.return_value = [{"energy": -10.0}]
    res = atomate2_server.get_atomate2_results_by_formula(formula="Si")
    assert res["count"] == 1
    assert res["results"][0]["energy"] == -10.0

@pytest.mark.atomate2
def test_get_atomate2_summary(skip_if_wrong_env, mock_handler):
    mock_handler.get_database_summary.return_value = {"total_jobs": 100}
    res = atomate2_server.get_atomate2_summary()
    assert "error" not in res
    assert res["total_jobs"] == 100

@pytest.mark.atomate2
def test_get_atomate2_recent_jobs(skip_if_wrong_env, mock_handler):
    mock_handler.get_recent_jobs.return_value = [{"job_id": "job_123", "status": "COMPLETED"}]
    res = atomate2_server.get_atomate2_recent_jobs(limit=1)
    assert len(res) == 1
    assert res[0]["job_id"] == "job_123"

@pytest.mark.atomate2
def test_get_atomate2_job_status(skip_if_wrong_env, mock_handler):
    mock_handler.check_status.return_value = {"status": "RUNNING"}
    res = atomate2_server.get_atomate2_job_status(job_id="dummy")
    assert res["status"] == "RUNNING"
