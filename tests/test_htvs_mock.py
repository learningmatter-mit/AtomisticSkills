
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath("src"))


# Mock mcp.server.fastmcp BEFORE importing htvs_server
sys.modules["mcp.server.fastmcp"] = MagicMock()
mock_mcp = MagicMock()
# Make .tool() a decorator that returns the function as-is
def tool_decorator():
    def decorator(func):
        return func
    return decorator
mock_mcp.return_value.tool.side_effect = tool_decorator
sys.modules["mcp.server.fastmcp"].FastMCP = mock_mcp

from mcp_server import htvs_server

def test_list_configs():
    print("Testing list_htvs_configs...")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '[{"name": "test_config", "parent_class_name": "TestClass"}]'
        
        result = htvs_server.list_htvs_configs()
        print(f"Result: {result}")
        
        # Verify subprocess was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        print(f"Command called: {call_args}")
        assert call_args[0] == "python"
        assert call_args[1].endswith(".py")

def test_get_status():
    print("\nTesting get_htvs_job_status...")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"uuid1": "done"}'
        
        result = htvs_server.get_htvs_job_status(job_uuids=["uuid1"])
        print(f"Result: {result}")
        
        mock_run.assert_called_once()
        
def test_query_structures():
    print("\nTesting query_htvs_structures...")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '[{"id": 1, "type": "Crystal", "formula": "CaTiO3"}]'
        
        result = htvs_server.query_htvs_structures(group_name="perovskite")
        print(f"Result: {result}")
        mock_run.assert_called_once()

if __name__ == "__main__":
    test_list_configs()
    test_get_status()
    test_query_structures()
    print("\nTests Passed!")
