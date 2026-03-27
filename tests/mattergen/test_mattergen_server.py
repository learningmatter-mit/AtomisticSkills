import pytest
from src.mcp_server import mattergen_server

@pytest.mark.mattergen
def test_generate_structures(skip_if_wrong_env):
    res = mattergen_server.generate_structures(
        num_structures=1
    )
    assert "error" not in res
    assert "num_generated" in res
