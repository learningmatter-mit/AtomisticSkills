import pytest
from src.mcp_server import adit_server

@pytest.mark.adit
def test_generate_structures(skip_if_wrong_env):
    res = adit_server.generate_structures(
        generation_type="crystals",
        num_structures=1
    )
    assert "error" not in res
    assert "num_generated" in res
