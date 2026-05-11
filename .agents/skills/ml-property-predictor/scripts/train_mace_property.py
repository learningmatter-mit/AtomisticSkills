#!/usr/bin/env python3
import sys
import os
import argparse
import tempfile
import subprocess
import logging
from pathlib import Path
import json
import torch
import numpy as np
from ase.io import read, write

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Train a property predictor using MACE.")
    parser.add_argument("--data_path", type=str, required=True, help="Path to JSON or XYZ file containing structures and properties.")
    parser.add_argument("--model_name", type=str, required=True, help="MACE foundation model to use (e.g., MACE-MP-medium).")
    parser.add_argument("--target_property", type=str, default="target_property", help="Key name for the target property in the data file.")
    parser.add_argument("--property_type", type=str, choices=["intensive", "extensive"], default="intensive", help="Type of property.")
    parser.add_argument("--output_dir", type=str, default=None, help="Directory to save the trained model.")
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs.")
    parser.add_argument("--batch_size", type=int, default=2, help="Batch size.")
    parser.add_argument("--lr", type=float, default=0.01, help="Learning rate.")
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"], help="Device to use.")
    return parser.parse_args()

def prepare_data(data_path, target_property, property_type):
    if data_path.endswith('.json'):
        with open(data_path, 'r') as f:
            data = json.load(f)
            
        from pymatgen.core import Structure
        from pymatgen.io.ase import AseAtomsAdaptor
        converter = AseAtomsAdaptor()
        
        atoms_list = []
        for item in data:
            struct = Structure.from_dict(item['structure'])
            atoms = converter.get_atoms(struct)
            
            if target_property in item:
                prop_val = float(item[target_property])
            elif 'property' in item:
                prop_val = float(item['property'])
            else:
                 raise ValueError("Could not find property in JSON item.")
                 
            if property_type == "intensive":
                 prop_val *= len(atoms)
                 
            atoms.info[target_property] = float(prop_val)
            
            atoms.info["energy"] = 0.0
            atoms.arrays["forces"] = np.zeros((len(atoms), 3))
            atoms_list.append(atoms)
        return atoms_list
    elif data_path.endswith('.xyz') or data_path.endswith('.extxyz'):
        atoms_list = read(data_path, index=':')
        for atoms in atoms_list:
            if target_property not in atoms.info:
                raise ValueError(f"Property key '{target_property}' not found in XYZ file info.")
            
            # Ensure scalar
            prop_val = atoms.info[target_property]
            if isinstance(prop_val, np.ndarray):
                 atoms.info[target_property] = float(prop_val[0])
            
            if property_type == "intensive":
                 atoms.info[target_property] = float(atoms.info[target_property]) * len(atoms)
                 
            atoms.info["energy"] = 0.0
            atoms.arrays["forces"] = np.zeros((len(atoms), 3))
        return atoms_list
    else:
        raise ValueError("Unsupported data format. Please provide .json or .xyz files.")

def main():
    args = parse_args()
    
    atoms_list = prepare_data(args.data_path, args.target_property, args.property_type)
    logger.info(f"Loaded {len(atoms_list)} structures.")
    
    output_dir = args.output_dir or tempfile.mkdtemp(prefix="mace_property_")
    output_path = Path(output_dir).absolute()
    output_path.mkdir(parents=True, exist_ok=True)
    
    train_xyz_path = output_path / "train_prop.xyz"
    write(str(train_xyz_path), atoms_list, format="extxyz")
    
    batch_size = min(args.batch_size, len(atoms_list))
    
    # Gather atomic numbers for dummy E0s map
    all_atomic_numbers = set()
    for atoms in atoms_list:
        all_atomic_numbers.update(atoms.get_atomic_numbers())
    
    dummy_e0s = "{" + ", ".join([f"{int(z)}: 0.0" for z in sorted(all_atomic_numbers)]) + "}"
    
    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
    cmd = [
        sys.executable, "-m", "mace.cli.run_train",
        "--name", f"{args.model_name.lower()}_prop_predictor",
        "--train_file", str(train_xyz_path),
        "--max_num_epochs", str(args.epochs),
        "--lr", str(args.lr),
        "--batch_size", str(batch_size),
        "--valid_batch_size", str(batch_size),
        "--device", device,
        "--compute_forces", "False",
        "--loss", "universal", # universal supports energy target
        "--energy_weight", "1.0",
        "--forces_weight", "0.0",
        "--energy_key", args.target_property,
        "--compute_forces", "False",
        "--E0s", dummy_e0s,
        "--checkpoints_dir", str(output_path / "checkpoints"),
        "--results_dir", str(output_path / "results"),
        "--log_dir", str(output_path / "logs")
    ]
    
    model_name_upper = args.model_name.upper()
    foundation_model_name = "medium"
    if "MATPES-R2SCAN" in model_name_upper:
        foundation_model_name = "mace-matpes-r2scan-0"
    elif "MATPES-PBE" in model_name_upper:
        foundation_model_name = "mace-matpes-pbe-0"
    elif "OMAT" in model_name_upper:
        foundation_model_name = "medium-omat-0" if "MEDIUM" in model_name_upper else "small-omat-0"
        
    cmd.extend(["--foundation_model", foundation_model_name])
    
    # ALWAYS inject the backbone freeze patch
    wrapper_script_path = output_path / "mace_prop_train_wrapper.py"
    
    # Locate freeze_patch.py (it lives in src/utils/mlips/mace/freeze_patch.py)
    # Assuming script is run from project root, this path is correct.
    project_root = Path(__file__).parent.parent.parent.parent.absolute()
    patch_script_path = project_root / "src" / "utils" / "mlips" / "mace" / "freeze_patch.py"
    
    if not patch_script_path.exists():
         # Fallback search path if not found relative to script
         patch_script_path = Path("/home/bdeng/projects/AtomisticSkills/src/utils/mlips/mace/freeze_patch.py")
         
    with open(wrapper_script_path, "w") as f:
         f.write(f'''

    try:
        # Save input configs for reproducibility
        import yaml as _yaml
        _cfg = {k: str(v) if hasattr(v, '__fspath__') else v for k, v in vars(args).items()}
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(args.output_dir) / "input_configs.yaml", 'w') as _f:
            _yaml.dump(_cfg, _f, default_flow_style=False, sort_keys=False)
    except Exception as _e:
        print(f"Warning: Failed to save input_configs.yaml: {_e}")
import sys
sys.path.append(r"{str(patch_script_path.parent)}")
import freeze_patch
import mace.cli.run_train
if __name__ == "__main__":
    freeze_patch.apply_patch(["readouts"])
    mace.cli.run_train.main()
''')
    cmd.insert(1, str(wrapper_script_path))
    cmd.remove("-m")
    cmd.remove("mace.cli.run_train")
    
    logger.info(f"Training MACE property predictor: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(output_path), capture_output=True, text=True)
    if result.returncode != 0:
         logger.error(f"MACE Property Predictor training failed: {result.stderr}")
         sys.exit(1)
         
    logger.info("MACE Property Predictor training finished.")
    logger.info(f"Output saved to {output_path}")
    
if __name__ == "__main__":
    main()
