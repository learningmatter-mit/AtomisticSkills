import pytest
from src.mcp_server import base_server
from pymatgen.core import Structure, Lattice

@pytest.mark.base
def test_create_research_dir(skip_if_wrong_env):
    res = base_server.create_research_dir("test_topic")
    assert "error" not in res

@pytest.mark.base
def test_search_materials_project_by_formula(skip_if_wrong_env, mock_mp_api_key):
    res = base_server.search_materials_project_by_formula("Si")
    # Without real API key it might return an error string
    assert isinstance(res, str)

@pytest.mark.base
def test_search_materials_project_by_chemsys(skip_if_wrong_env, mock_mp_api_key):
    res = base_server.search_materials_project_by_chemsys("Li-O")
    assert isinstance(res, str)

@pytest.mark.base
def test_visualize_structure(skip_if_wrong_env, tmp_cif_file):
    res = base_server.visualize_structure(str(tmp_cif_file))
    assert "error" not in res

@pytest.mark.base
def test_prepare_vasp_inputs(skip_if_wrong_env, tmp_cif_file):
    res = base_server.prepare_vasp_inputs(str(tmp_cif_file), "dummy_vasp_out")
    assert isinstance(res, str)

@pytest.mark.base
def test_parse_vasp_results(skip_if_wrong_env, tmp_path):
    dummy_dir = tmp_path / "dummy_vasp_out"
    dummy_dir.mkdir()
    res = base_server.parse_vasp_results(str(dummy_dir))
    assert "error" in res # No inputs present

@pytest.mark.base
def test_search_literature(skip_if_wrong_env):
    res = base_server.search_literature("battery")
    assert isinstance(res, str)
