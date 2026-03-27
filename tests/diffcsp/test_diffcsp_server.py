import pytest
from src.mcp_server import diffcsp_server

@pytest.mark.diffcsp
def test_generate_structures_with_symmetry(skip_if_wrong_env):
    res = diffcsp_server.generate_structures_with_symmetry(
        spacegroup=225,
        wyckoff_letters="a,c",
        atom_types="Na,Cl",
        num_samples=1
    )
    assert "error" not in res
    assert "num_generated" in res
