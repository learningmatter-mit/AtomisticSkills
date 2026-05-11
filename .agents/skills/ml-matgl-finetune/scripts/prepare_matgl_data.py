#!/usr/bin/env python
"""
Convert fine-tuning JSON data into MatGL compatible format (MGLDataset).

Usage:
    python prepare_matgl_data.py --data path/to/data.json --model CHGNet-MatPES-PBE-2025.2.10-2.7M-PES \
        --val-split 0.1 --output-dir ./fine_tuning
"""

import argparse
import json
import os
import random
from pathlib import Path
import numpy as np

def main():
    parser = argparse.ArgumentParser(description="Prepare custom data for MatGL training")
    # Basic arguments
    parser.add_argument("--data", required=True, help="Path to JSON file containing ASE/pymatgen structure dictionaries with 'energy', 'forces', 'stress' keys")
    parser.add_argument("--model", default="CHGNet-MatPES-PBE-2025.2.10-2.7M-PES", help="Base model name or path to a checkpoint")
    parser.add_argument("--output-dir", default="./fine_tuning", help="Directory to save the processed data")
    
    # Validation and Regularization
    parser.add_argument("--val-split", type=float, default=0.1, help="Fraction of data to set aside for validation (0.0 to use everything for training)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for splitting validation data")
    parser.add_argument("--vasp-stress-conversion", action="store_true", help="If flag is present, multiplies stress arrays by -1/160.21766208 to convert from kB to eV/Å³")
    
    args = parser.parse_args()

    print(f"Loading data from {args.data}...")
    with open(args.data, 'r') as f:
        raw_data = json.load(f)

    all_data = []
    
    def _extract_item(data_dict):
        item = {"structure": data_dict.get("structure") or data_dict.get("atoms")}
        if "vasp_e" in data_dict: item["energy"] = data_dict["vasp_e"]
        elif "energy" in data_dict: item["energy"] = data_dict["energy"]
        if "vasp_f" in data_dict: item["forces"] = data_dict["vasp_f"]
        elif "forces" in data_dict: item["forces"] = data_dict["forces"]
        
        stress = data_dict.get("vasp_s") or data_dict.get("stress")
        if stress is not None:
            if args.vasp_stress_conversion:
                import numpy as np
                item["stress"] = (np.array(stress) * (-1.0 / 1602.1766208)).tolist()
            else:
                item["stress"] = stress
        return item

    # Handle dictionary of subsets (WBM formats) or flat lists
    if isinstance(raw_data, dict):
        processed_raw_data = []
        for key, items in raw_data.items():
            if isinstance(items, list):
                processed_raw_data.extend(items)
            elif isinstance(items, dict):
                if 'atoms' in items or 'structure' in items:
                    processed_raw_data.append(items)
                else:
                    # Handle 3-tier deep dicts (e.g., dict of dicts of structures)
                    for subkey, subvalue in items.items():
                        if isinstance(subvalue, dict) and ('atoms' in subvalue or 'structure' in subvalue):
                            processed_raw_data.append(subvalue)
                        elif isinstance(subvalue, list): # Handle dict of lists of structures
                            processed_raw_data.extend(subvalue)
            else:
                processed_raw_data.append(items)
        raw_data = processed_raw_data
    
    # Now raw_data should be a list of structure dictionaries (or a flat list if it was originally)
    for item in raw_data:
        all_data.append(_extract_item(item))

    if args.val_split > 0.0:
        random.seed(args.seed)
        random.shuffle(all_data)
        split_idx = int(len(all_data) * (1.0 - args.val_split))
        train_data = all_data[:split_idx]
        val_data = all_data[split_idx:]
        print(f"Split data into {len(train_data)} training and {len(val_data)} validation samples.")
    else:
        train_data = all_data
        val_data = None
        print(f"Using all {len(train_data)} samples for training.")

    output_path = Path(args.output_dir).absolute()
    output_path.mkdir(parents=True, exist_ok=True)
    
    train_path = output_path / "train_data.json"
    val_path = output_path / "val_data.json"
    
    with open(train_path, "w") as f:
        json.dump(train_data, f)
        
    if val_data:
        with open(val_path, "w") as f:
            json.dump(val_data, f)

    print("\n=======================================================")
    print("Data successfully prepared!")
    print(f"Training structures: {len(train_data)}")
    if val_data:
        print(f"Validation structures: {len(val_data)}")
    print(f"Data written to: {output_path}")
    print("=======================================================\n")
    print("To generate training config and start training, run:")
    print(f"  conda activate matgl-agent")
    print(f"  python generate_matgl_config.py --train-data {train_path.absolute()} " + (f"--val-data {val_path.absolute()} " if val_data else "") + f"--model {args.model} --output-dir {output_path.absolute()}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

if __name__ == "__main__":
    main()
