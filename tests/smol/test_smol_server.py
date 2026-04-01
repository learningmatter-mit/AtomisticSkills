import pytest
from src.mcp_server import smol_server
from pymatgen.core import Structure, Lattice

@pytest.mark.smol
def test_sample_ordered_structures(skip_if_wrong_env, tmp_research_dir):
    lattice = Lattice.cubic(3.5)
    struct = Structure(lattice, [{"Li": 0.5, "Ag": 0.5}], [[0, 0, 0]]).as_dict()
    res = smol_server.sample_ordered_structures(
        disordered_structure=struct,
        cutoffs={2: 5.0},
        num_structures=1,
        target_num_sites=2
    )
    assert "error" not in res

@pytest.mark.smol
def test_train_cluster_expansion(skip_if_wrong_env, tmp_research_dir):
    lattice = Lattice.cubic(3.5)
    struct = Structure(lattice, [{"Li": 0.5, "Ag": 0.5}], [[0, 0, 0]]).as_dict()
    # Provide a minimal mock training data list
    training_data = []
    res = smol_server.train_cluster_expansion(
        disordered_structure=struct,
        training_data=training_data,
        cutoffs={"2": 5.0}
    )
    assert "error" in res # Because training data is empty, it shouldn't crash but will return error cleanly

@pytest.mark.smol
def test_run_monte_carlo(skip_if_wrong_env, tmp_research_dir):
    # Just need simple test
    res = smol_server.run_monte_carlo(
        supercell_matrix=[[2,0,0],[0,2,0],[0,0,2]],
        temperature=300,
        steps=100
    )
    assert "error" in res # No CE loaded
    
@pytest.mark.smol
def test_compute_feature_vectors(skip_if_wrong_env):
    res = smol_server.compute_feature_vectors(structures=[])
    assert "error" in res # Empty structures or CE not loaded
    
@pytest.mark.smol
def test_get_feature_matrix(skip_if_wrong_env):
    res = smol_server.get_feature_matrix(ce_file="dummy.json")
    assert "error" in res

@pytest.mark.smol
def test_fit_feature_matrix(skip_if_wrong_env):
    res = smol_server.fit_feature_matrix(feature_matrix_path="dummy.npy", energies_path="dummy.npy")
    assert "error" in res

@pytest.mark.smol
def test_check_mapping(skip_if_wrong_env):
    lattice = Lattice.cubic(3.5)
    struct = Structure(lattice, [{"Li": 0.5, "Ag": 0.5}], [[0, 0, 0]]).as_dict()
    res = smol_server.check_mapping(initial_structure=struct, relaxed_structure=struct)
    assert "error" in res # Because CE isn't initialized or similar, but it tests function execution
