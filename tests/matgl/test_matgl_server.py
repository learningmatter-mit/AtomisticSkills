
import pytest
import os
import shutil
from ase.build import bulk
from pymatgen.io.ase import AseAtomsAdaptor
from src.mcp_server import matgl_server

@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    if os.path.exists("./results/matgl_test"):
        shutil.rmtree("./results/matgl_test")

@pytest.fixture(scope="module")
def loaded_server():
    # Use M3GNet as it is usually fastest/easiest
    res = matgl_server.load_model("M3GNet", device="cpu")
    if "error" in res:
        pytest.fail(f"Failed to load model: {res}")
    return matgl_server

@pytest.fixture
def cu_structure():
    atoms = bulk("Cu")
    return AseAtomsAdaptor.get_structure(atoms).as_dict()

def test_predict_structure(loaded_server, cu_structure):
    res = loaded_server.predict_structure(cu_structure)
    assert "energy" in res
    assert "forces" in res

def test_relax_structure(loaded_server, cu_structure):
    output_dir = os.path.abspath("./results/matgl_test/relax")
    res = loaded_server.relax_structure(
        cu_structure, 
        steps=5, 
        output_dir=output_dir
    )
    assert "error" not in res
    assert "cif_path" in res

def test_run_md(loaded_server, cu_structure):
    output_dir = os.path.abspath("./results/matgl_test/md")
    res = loaded_server.run_md(
        cu_structure,
        steps=5,
        output_dir=output_dir
    )
    assert "error" not in res # Trajectory path handled
    assert "trajectory_path" in res

def test_run_md_batch(loaded_server, cu_structure):
    output_dir = os.path.abspath("./results/matgl_test/md_batch")
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


    
    res = loaded_server.load_model("M3GNet", device="cpu")
    assert "error" not in res
    assert "Successfully loaded" in res

def test_predict_atomic_features(loaded_server, cu_structure):
    res = loaded_server.predict_atomic_features(cu_structure)
    assert "error" not in res
    assert "atomic_features" in res
    assert "feature_dim" in res

@pytest.mark.xfail(reason="MEGNet DGL FloatTensor type error in embedding layer")
def test_predict_bandgap(loaded_server, cu_structure):
    res = loaded_server.predict_bandgap(cu_structure)
    assert "error" not in res
    assert "bandgap" in res
