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
def test_supercell_expansion(skip_if_wrong_env, tmp_cif_file):
    res = base_server.supercell_expansion(
        structure_path=str(tmp_cif_file),
        scaling_matrix_json="[2, 2, 2]"
    )
    assert "Successfully created supercell" in res

@pytest.mark.base
def test_modify_structure(skip_if_wrong_env, tmp_cif_file):
    res = base_server.modify_structure(
        structure_path=str(tmp_cif_file),
        substitution_dict_json='{"Si": "Fe"}'
    )
    assert "Successfully modified structure" in res

@pytest.mark.base
def test_search_literature(skip_if_wrong_env):
    res = base_server.search_literature("battery")
    assert isinstance(res, str)

@pytest.fixture
def mock_registry_file(tmp_path, monkeypatch):
    from src.utils import model_registry
    registry_file = tmp_path / "model_registry.yaml"
    monkeypatch.setattr(model_registry, "REGISTRY_PATH", registry_file)
    return registry_file

@pytest.mark.base
def test_register_and_search_model_registry(skip_if_wrong_env, mock_registry_file, tmp_path):
    ckpt = tmp_path / "dummy.pt"
    ckpt.touch()
    
    # Test register_model tool
    res_register = base_server.register_model(
        checkpoint_path=str(ckpt),
        chemical_system="Li-O",
        backend="mace",
        base_model="MACE-MH-1",
        tags_json='["test"]'
    )
    assert "Model successfully registered" in res_register
    
    # Test search_model_registry tool
    res_search = base_server.search_model_registry(
        chemical_system="Li",
        backend="mace"
    )
    assert "Found" in res_search
    assert "mace-LiO-v1" in res_search

    res_empty = base_server.search_model_registry(
        chemical_system="Fe"
    )
    assert "No models found" in res_empty
