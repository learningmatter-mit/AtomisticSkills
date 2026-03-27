import os
import sys
import subprocess
import glob
from pathlib import Path
import shutil

def run_matgl():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    sys.path.insert(0, base_dir)
    
    script_path = os.path.join(base_dir, ".agents", "skills", "ml-property-predictor", "scripts", "train_matgl_property.py")
    data_path = os.path.join(base_dir, ".agents", "test", "mp_bulk_modulus.json")
    out_dir = os.path.join(os.path.dirname(__file__), "matgl_results")
    
    cmd = [
         "python", script_path,
         "--data_path", data_path,
         "--target_property", "bulk_modulus",
         "--epochs", "25",
         "--batch_size", "16",
         "--output_dir", out_dir
    ]
    
    print(f"Running MatGL training: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    # Reload validation script
    print("\n--- MatGL Inference Prediction Accuracy ---")
    from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
    import json
    from pymatgen.core import Structure
    import numpy as np
    
    data = json.load(open(data_path))
    atoms = [Structure.from_dict(d["structure"]) for d in data[:5]]
    props = [d["bulk_modulus"] for d in data[:5]]
    
    wrapper = MatGLWrapper(model_name="custom", device="cpu")
    wrapper.load(model_path=os.path.join(out_dir, "matgl_model"))
    
    for i, struct in enumerate(atoms):
        res = wrapper.static_calculation(struct)
        val = res.get("bulk_modulus", res.get("energy", 0.0))
        if isinstance(val, (list, np.ndarray)):
            val = val[0]
            
        # MatGL MEGNet explicitly trains to raw target inputs
        pred = float(val)
        print(f"Sample {i}: Target = {props[i]:.2f}, Prediction = {pred:.2f}")

    # Cleanup large checkpoint binaries
    print("\nCleaning up intermediate PyTorch Lightning checkpoint files...")
    ckpt_dir = os.path.join(out_dir, "checkpoints")
    if os.path.exists(ckpt_dir):
        shutil.rmtree(ckpt_dir)
        
    log_dir = os.path.join(out_dir, "lightning_logs")
    if os.path.exists(log_dir):
         shutil.rmtree(log_dir)
    print("MatGL evaluation fully complete.")

if __name__ == "__main__":
    if "matgl-agent" not in os.environ.get("CONDA_DEFAULT_ENV", ""):
        print("Restarting MatGL test in matgl-agent environment...")
        subprocess.run(["conda", "run", "-n", "matgl-agent", "python", __file__], check=True)
    else:
        run_matgl()
