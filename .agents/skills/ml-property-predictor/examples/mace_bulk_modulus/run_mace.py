import os
import sys
import subprocess
import glob
from pathlib import Path

def run_mace():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    sys.path.insert(0, base_dir)
    
    script_path = os.path.join(base_dir, ".agents", "skills", "ml-property-predictor", "scripts", "train_mace_property.py")
    data_path = os.path.join(base_dir, ".agents", "test", "mp_bulk_modulus.json")
    out_dir = os.path.join(os.path.dirname(__file__), "mace_results")
    
    cmd = [
         "python", script_path,
         "--data_path", data_path,
         "--model_name", "MACE-OMAT-0-small",
         "--target_property", "bulk_modulus",
         "--property_type", "intensive",
         "--epochs", "25",
         "--batch_size", "16",
         "--output_dir", out_dir
    ]
    
    print(f"Running MACE training: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    # Reload validation script
    print("\n--- MACE Inference Prediction Accuracy ---")
    from src.utils.mlips.mace.mace_wrapper import MACEWrapper
    import json
    from pymatgen.core import Structure
    import numpy as np
    
    data = json.load(open(data_path))
    atoms = [Structure.from_dict(d["structure"]) for d in data[:5]]
    props = [d["bulk_modulus"] for d in data[:5]]
    
    chkpt_dir = os.path.join(out_dir, "checkpoints")
    models = sorted(os.listdir(chkpt_dir))
    model_path = os.path.join(chkpt_dir, models[-1])
    
    wrapper = MACEWrapper(model_name="MACE-OMAT-0-small", device="cpu")
    wrapper.load(model_path=model_path)
    
    for i, struct in enumerate(atoms):
        res = wrapper.static_calculation(struct)
        val = res.get("bulk_modulus", res.get("energy", 0.0))
        if isinstance(val, (list, np.ndarray)):
            val = val[0]
            
        pred_intensive = float(val) / len(struct)
        print(f"Sample {i}: Target = {props[i]:.2f}, Prediction = {pred_intensive:.2f}")

    # Cleanup large checkpoint binaries
    print("\nCleaning up all models to save space as MACE checkpoints are large...")
    import shutil
    if os.path.exists(chkpt_dir):
        shutil.rmtree(chkpt_dir)
    for file in glob.glob(os.path.join(out_dir, "*.model")):
        os.remove(file)
    print("MACE evaluation fully complete.")

if __name__ == "__main__":
    if "mace-agent" not in os.environ.get("CONDA_DEFAULT_ENV", ""):
        print("Restarting MACE test in mace-agent environment...")
        subprocess.run(["conda", "run", "-n", "mace-agent", "python", __file__], check=True)
    else:
        run_mace()
