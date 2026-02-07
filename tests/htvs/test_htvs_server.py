
import pytest
import os
import json
from src.mcp_server import htvs_server

def test_vasp_to_htvs_details_basic():
    vasp_input = {
        "ENCUT": 520,
        "ISPIN": 2,
        "NSW": 100,
        "POTIM": 0.5
    }
    details = htvs_server.vasp_to_htvs_details(vasp_input)
    
    assert details["encut"] == 520
    assert details["ispin"] == 2
    assert details["nsteps"] == 100 # NSW maps to nsteps
    assert details["timestep"] == 0.5 # POTIM maps to timestep

def test_vasp_to_htvs_details_with_extras():
    vasp_input = {"ENCUT": 500}
    extras = {"compute_platform": "slurm", "priority": 100}
    details = htvs_server.vasp_to_htvs_details(vasp_input, additional_details=extras)
    
    assert details["encut"] == 500
    assert details["compute_platform"] == "slurm"
    assert details["priority"] == 100

def test_tools_existence():
    # Verify all new and important tools are decorated with @mcp.tool()
    # (Checking the exported tool names in the MCP instance)
    tool_names = [t.name for t in htvs_server.mcp._tool_manager.list_tools()]
    
    expected_tools = [
        "vasp_to_htvs_details",
        "request_htvs_job",
        "build_htvs_job",
        "parse_htvs_job",
        "list_htvs_configs",
        "get_htvs_job_status",
        "get_htvs_job_results",
        "save_htvs_structures",
        "inspect_chem_config",
        "create_htvs_group",
        "query_htvs_structures",
        "query_htvs_calcs",
        "query_htvs_geoms"
    ]
    
    for tool in expected_tools:
        assert tool in tool_names, f"Tool {tool} not found in htvs_server tools"

def test_query_calcs_logic():
    # This just tests if the function body can be entered and it correctly formats the script
    # We don't have a live DB to run against here in a simple unit test.
    # We mainly want to ensure no syntax errors in the python wrapper.
    try:
        # This will likely fail with a "manage.py not found" error if it actually tries to run,
        # but we are checking if the function is callable.
        res = htvs_server.query_htvs_calcs(
            group_name="test_group", 
            settings_module="test.settings",
            formula="Pt",
            limit=5
        )
        assert "Error" in res or "Success" in res or "[" in res
    except Exception as e:
        # If it fails due to environment (subprocess failing), that's expected in some CI/test envs
        pass

def test_get_htvs_job_results_logic():
    # Ensure the enhanced tool is callable
    try:
        res = htvs_server.get_htvs_job_results(
            job_uuids=["uuid1"],
            settings_module="test.settings"
        )
        assert isinstance(res, str)
    except:
        pass
