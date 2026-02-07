
import sys
import os
import json
import logging
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Mock mcp.server.fastmcp
sys.modules["mcp.server.fastmcp"] = MagicMock()
mock_mcp = MagicMock()
# Make .tool() a decorator that returns the function as-is
def tool_decorator():
    def decorator(func):
        return func
    return decorator
mock_mcp.return_value.tool.side_effect = tool_decorator
sys.modules["mcp.server.fastmcp"].FastMCP = mock_mcp

from src.mcp_server import htvs_server

def test_workflow():
    print("Testing HTVS Workflow Integration...")

    # 1. Mock VASP Input -> HTVS Details
    vasp_input = {"ENCUT": 500, "ISPIN": 2, "LREAL": "Auto"}
    details = htvs_server.vasp_to_htvs_details(vasp_input)
    print(f"1. Details generated: {details}")

    # 2. Request Job
    with patch("os.path.exists", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Requested job 123"
            
            project = "test_workflow"
            config = "pbe_d3_paw_bomd_vasp"
            
            output = htvs_server.request_htvs_job(
                project, config, details, settings_module="dummy", djangochem_dir="/dummy/path"
            )
            print(f"2. Request Output: {output}")
            
            # Verify call
            args = mock_run.call_args[0][0]
            assert "requestjobs" in args
            assert project in args
            print("   -> request_htvs_job call verified")

        # 3. Build Job
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Built job 123 to inbox/"
            
            output = htvs_server.build_htvs_job(
                project, settings_module="dummy", inbox_path="inbox_path", djangochem_dir="/dummy/path"
            )
            print(f"3. Build Output: {output}")
            
            args = mock_run.call_args[0][0]
            assert "buildjobs" in args
            assert project in args
            print("   -> build_htvs_job call verified")

if __name__ == "__main__":
    test_workflow()
    print("\nWorkflow Test Passed!")
