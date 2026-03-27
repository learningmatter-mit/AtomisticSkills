
import pytest
import os
import shutil
import json
from ase.build import bulk
from pymatgen.io.ase import AseAtomsAdaptor
from src.mcp_server import mace_server

# Helper to clean up output
@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    if os.path.exists("./results/mace_test"):
        shutil.rmtree("./results/mace_test")

@pytest.fixture(scope="module")
def loaded_server():
    # Use small model for speed
    res = mace_server.load_model("MACE-MP-small", device="cpu")
    if "error" in res:
        pytest.fail(f"Failed to load model: {res}")
    return mace_server

@pytest.fixture
def cu_structure():
    atoms = bulk("Cu")
    return AseAtomsAdaptor.get_structure(atoms).as_dict()

def test_get_info(loaded_server):
    info = loaded_server.get_info()
    assert info.get("model_name") == "MACE-MP-small"

def test_predict_structure(loaded_server, cu_structure):
    res = loaded_server.predict_structure(cu_structure)
    assert "energy" in res
    assert "forces" in res
    assert "stress" in res # MACE usually returns stress

def test_relax_structure(loaded_server, cu_structure):
    # Perturb
    import numpy as np
    atoms_obj = bulk("Cu")
    atoms_obj.positions[0] += 0.1
    struct_dict = AseAtomsAdaptor.get_structure(atoms_obj).as_dict()
    
    output_dir = os.path.abspath("./results/mace_test/relax")
    res = loaded_server.relax_structure(
        struct_dict, 
        steps=5, 
        fmax=0.1, 
        output_dir=output_dir
    )
    
    assert "error" not in res
    assert "cif_path" in res
    assert "energy" in res
    assert os.path.exists(output_dir)

def test_run_md(loaded_server, cu_structure):
    output_dir = os.path.abspath("./results/mace_test/md")
    res = loaded_server.run_md(
        cu_structure,
        temperature=300,
        steps=5,
        log_interval=1,
        output_dir=output_dir
    )
    assert "error" not in res
    assert "trajectory_path" in res
    # Depending on the wrapper, it might return 'trajectory_path' or check existence
    if "trajectory_path" in res:
        assert os.path.exists(res["trajectory_path"])

def test_run_md_batch(loaded_server, cu_structure):
    output_dir = os.path.abspath("./results/mace_test/md_batch")
    res = loaded_server.run_md(
        [cu_structure, cu_structure],
        temperature=300,
        steps=5,
        log_interval=1,
        output_dir=output_dir
    )
    assert "error" not in res
    assert res.get("mode") == "batch"
    assert res.get("total_jobs") == 2
    assert res.get("successful") == 2


def test_load_model(loaded_server):
    res = loaded_server.load_model("MACE-MP-small", device="cpu")
    assert "error" not in res
    assert "Successfully loaded" in res

def test_predict_atomic_features(loaded_server, cu_structure):
    res = loaded_server.predict_atomic_features(cu_structure)
    assert "error" not in res
    assert "saved_path" in res
    assert "feature_dim" in res
