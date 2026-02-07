
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

def test_fine_tune_model(loaded_server):
    # Construct dummy training data
    atoms = bulk("Cu")
    struct_dict = AseAtomsAdaptor.get_structure(atoms).as_dict()
    
    # 1. Initial Prediction
    res_pre = loaded_server.predict_structure(struct_dict)
    assert "error" not in res_pre
    e_pre = res_pre["energy"]
    
    # Create training data with VERY different energy to force large update
    training_data = [
        {
            "structure": struct_dict,
            "energy": -100.0, # Large shift from typical Cu energy (~-3.5 eV)
            "forces": [[0.0, 0.0, 0.0]] * len(atoms),
            "stress": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        },
        {
             "structure": struct_dict,
             "energy": -100.1, 
             "forces": [[0.1, 0.0, 0.0]] * len(atoms),
             "stress": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        }
    ]
    
    output_dir = os.path.abspath("./results/mace_test/finetune")
    os.makedirs(output_dir, exist_ok=True)
    
    # Save training data to json file
    training_data_path = os.path.join(output_dir, "training_data.json")
    with open(training_data_path, "w") as f:
        json.dump(training_data, f)
    
    # 2. Fine-tune
    res = loaded_server.fine_tune_model(
        training_data_path=training_data_path,
        epochs=1, # Just one epoch needed to move weights
        learning_rate=0.1, # High LR to ensure move
        output_dir=output_dir,
        training_config={
            "use_foundation_model": False,
            "batch_size": 1
        }
    )
    
    if "error" in res:
         # Fail if fine-tuning itself fails
         pytest.fail(f"Fine-tuning failed: {res['error']}")
        
    assert res.get("is_fine_tuned") is True
    
    # 3. Verify Checkpoints
    assert os.path.exists(output_dir)
    # Check for MACE specific output files
    files = os.listdir(output_dir)
    model_files = [f for f in files if f.endswith(".model") or f.endswith(".pt")]
    assert len(model_files) > 0, f"No model files found in {output_dir}. Files: {files}"
    
    # 4. Reload Model
    # Use the model ending in .model (usually model_swa.model or similar)
    model_path = os.path.join(output_dir, model_files[0])
    
    load_res = loaded_server.load_model(model_name=model_path) 
    
    assert "Successfully loaded" in load_res or "error" not in load_res
    
    # 5. Predict Again
    res_post = loaded_server.predict_structure(struct_dict)
    assert "error" not in res_post
    e_post = res_post["energy"]
    
    # 6. Compare
    print(f"Pre-train Energy: {e_pre}, Post-train Energy: {e_post}")
    assert e_pre != e_post, "Energy should change after fine-tuning"

