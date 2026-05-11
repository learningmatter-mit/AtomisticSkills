#!/usr/bin/env python
"""
Convert fine-tuning JSON data into Fairchem LMDB training files and generate a configuration YAML.

Usage:
    python prepare_fairchem_data.py --data path/to/data.json --model uma-s-1p1 \
        --epochs 10 --lr 4e-4 --batch-size 2 --output-dir ./finetune_dir
"""

import argparse
import json
import logging
import os
import random
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import lmdb

import numpy as np
import yaml
import torch
from ase import Atoms
from ase.db import connect
from ase.io import read
from ase.io import write as ase_write
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def _to_atoms(data_dict):
    """Convert a data dict to ASE Atoms with info/arrays labels."""
    s_obj = data_dict["structure"]
    if isinstance(s_obj, dict):
        struct = Structure.from_dict(s_obj)
        atoms = AseAtomsAdaptor.get_atoms(struct)
    elif isinstance(s_obj, Atoms):
        atoms = s_obj.copy()
    else:
        atoms = AseAtomsAdaptor.get_atoms(s_obj)
    
    # Attach labels as info/arrays (extxyz format)
    if "energy" in data_dict and data_dict["energy"] is not None:
        atoms.info["energy"] = float(data_dict["energy"])
    if "forces" in data_dict and data_dict["forces"] is not None:
        atoms.arrays["forces"] = np.array(data_dict["forces"], dtype=np.float64)
    if "stress" in data_dict and data_dict["stress"] is not None:
        stress = np.array(data_dict["stress"], dtype=np.float64)
        # Ensure 3x3 format
        if stress.shape == (6,):
            # Voigt: xx, yy, zz, yz, xz, xy → 3x3
            v = stress.flatten()
            stress = np.array([
                [v[0], v[5], v[4]],
                [v[5], v[1], v[3]],
                [v[4], v[3], v[2]]
            ])
        elif stress.size == 9:
            stress = stress.reshape(3, 3)
        atoms.info["stress"] = stress
    return atoms

def _create_lmdb_sequential(data_dir, output_dir):
    """Create LMDB dataset sequentially."""
    import glob
    os.makedirs(output_dir, exist_ok=True)
    input_files = [f for f in glob.glob(os.path.join(str(data_dir), "**/*"), recursive=True) if os.path.isfile(f)]
    db_file = Path(output_dir) / "data.0000.aselmdb"
    natoms = []
    successful = []
    failed = []
    
    with connect(str(db_file)) as db:
        for file in tqdm(input_files, desc="Creating LMDB"):
            atoms_list = read(file, ":")
            for i, atoms in enumerate(atoms_list):
                if atoms.calc is not None and "energy" in atoms.calc.results and "forces" in atoms.calc.results:
                    db.write(atoms, data=atoms.info)
                    natoms.append(len(atoms))
                    successful.append(f"{file},{i}")
                else:
                    failed.append(f"{file},{i}: missing calc/energy/forces")
    
    np.savez_compressed(Path(output_dir) / "metadata.npz", natoms=natoms)
    logging.info(f"Created LMDB with {len(successful)} entries at {output_dir}")

def _compute_normalizer_sequential(train_lmdb_path):
    """Compute normalizer and linear reference sequentially."""
    from fairchem.core.datasets import AseDBDataset
    from fairchem.core.scripts.create_finetune_dataset import compute_lin_ref
    
    dataset = AseDBDataset({"src": str(train_lmdb_path)})
    sample_indices = random.sample(range(len(dataset)), min(100000, len(dataset)))
    
    atomic_numbers_list = []
    energies = []
    all_forces = []
    
    for idx in tqdm(sample_indices, desc="Computing normalizer values"):
        atoms = dataset.get_atoms(idx)
        atomic_numbers_list.append(atoms.get_atomic_numbers())
        energies.append(atoms.get_potential_energy())
        forces = atoms.get_forces()
        
        n_atoms = len(atoms)
        fixed_idx = np.zeros(n_atoms)
        if hasattr(atoms, "constraints"):
            from ase.constraints import FixAtoms
            for constraint in atoms.constraints:
                if isinstance(constraint, FixAtoms):
                    fixed_idx[constraint.index] = 1
        mask = fixed_idx == 0
        all_forces.extend(forces[mask].tolist())
    
    forces_arr = np.array(all_forces)
    force_rms = np.sqrt(np.mean(np.square(forces_arr)))
    coeff = compute_lin_ref(atomic_numbers_list, energies)
    
    logging.info(f"force_rms={force_rms:.4f}, linref has {len(coeff)} coeffs")
    return force_rms, coeff

def main():
    parser = argparse.ArgumentParser(description="Prepare custom data for Fairchem training into LMDBs.")
    parser.add_argument("--data", required=True, help="Path to JSON file containing training split")
    parser.add_argument("--val-data", help="Path to JSON file containing validation split. (Optional, otherwise 90/10 split)")
    parser.add_argument("--val-split", type=float, default=0.1, help="Validation split if --val-data is not provided")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--linref-coeff", type=str, help="Comma separated linear reference coefficients or JSON list string. Overrides auto compute.")
    parser.add_argument("--vasp-stress-conversion", action="store_true", help="If flag is present, multiplies stress arrays by -1/1602.1766208 to convert from kB to eV/Å³")
    parser.add_argument("--output-dir", default="./fairchem_finetuning", help="Directory to save the configuration and data")

    args = parser.parse_args()

    # Load data
    logging.info(f"Loading data from {args.data}...")
    with open(args.data, 'r') as f:
        loaded = json.load(f)
        all_data = []
        if isinstance(loaded, dict):
            # Flatten dicts
            for k, v in loaded.items():
                if isinstance(v, dict):
                    if "structure" in v:
                        all_data.append(v)
                    else:
                        for sub_k, sub_v in v.items():
                            if isinstance(sub_v, dict) and "structure" in sub_v:
                                all_data.append(sub_v)
        elif isinstance(loaded, list):
            all_data = loaded
            
        # Adapt keys (vasp_e -> energy, etc)
        for d in all_data:
            if "energy" not in d and "vasp_e" in d:
                d["energy"] = d["vasp_e"]
            if "forces" not in d and "vasp_f" in d:
                d["forces"] = d["vasp_f"]
            if "stress" not in d and "vasp_s" in d:
                d["stress"] = d["vasp_s"]
            if d.get("stress") is not None and args.vasp_stress_conversion:
                d["stress"] = (np.array(d["stress"]) * (-1.0 / 1602.1766208)).tolist()
    
    if args.val_data:
        logging.info(f"Loading validation from {args.val_data}...")
        with open(args.val_data, 'r') as f:
            loaded_val = json.load(f)
            val_data = []
            if isinstance(loaded_val, dict):
                for k, v in loaded_val.items():
                    if isinstance(v, dict):
                        if "structure" in v:
                            val_data.append(v)
                        else:
                            for sub_k, sub_v in v.items():
                                if isinstance(sub_v, dict) and "structure" in sub_v:
                                    val_data.append(sub_v)
            elif isinstance(loaded_val, list):
                val_data = loaded_val
                
            for d in val_data:
                if "energy" not in d and "vasp_e" in d: d["energy"] = d["vasp_e"]
                if "forces" not in d and "vasp_f" in d: d["forces"] = d["vasp_f"]
                if "stress" not in d and "vasp_s" in d: d["stress"] = d["vasp_s"]
                if d.get("stress") is not None and args.vasp_stress_conversion:
                    d["stress"] = (np.array(d["stress"]) * (-1.0 / 1602.1766208)).tolist()
                
        train_data = all_data
    else:
        if args.val_split > 0:
            random.seed(args.seed)
            random.shuffle(all_data)
            split_idx = int(len(all_data) * (1.0 - args.val_split))
            train_data = all_data[:split_idx]
            val_data = all_data[split_idx:]
            if not val_data:
                val_data = train_data[-1:]
        else:
            train_data = all_data
            val_data = train_data[-1:]
    
    logging.info(f"Using {len(train_data)} train samples and {len(val_data)} validation samples.")
    
    save_dir = Path(args.output_dir).absolute()
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Convert to EXTXYZ
    train_extxyz_dir = save_dir / "extxyz" / "train"
    val_extxyz_dir = save_dir / "extxyz" / "val"
    train_extxyz_dir.mkdir(parents=True, exist_ok=True)
    val_extxyz_dir.mkdir(parents=True, exist_ok=True)
    
    logging.info("Converting structures to EXTXYZ...")
    has_forces = False
    has_stress = False
    for i, d in enumerate(train_data):
        if d.get("forces") is not None: has_forces = True
        if d.get("stress") is not None: has_stress = True
        atoms = _to_atoms(d)
        ase_write(str(train_extxyz_dir / f"train_{i:04d}.extxyz"), atoms, format="extxyz")
        
    for i, d in enumerate(val_data):
        atoms = _to_atoms(d)
        ase_write(str(val_extxyz_dir / f"val_{i:04d}.extxyz"), atoms, format="extxyz")
    
    if has_stress:
        regression_tasks = "efs"
    elif has_forces:
        regression_tasks = "ef"
    else:
        regression_tasks = "e"
    
    logging.info(f"Detected regression tasks: {regression_tasks}")
    
    # 2. Create LMDB
    lmdb_dir = save_dir / "lmdb_output"
    if lmdb_dir.exists():
        shutil.rmtree(lmdb_dir)
        
    train_lmdb_path = lmdb_dir / "train"
    val_lmdb_path = lmdb_dir / "val"
    
    logging.info("Creating LMDB datasets...")
    _create_lmdb_sequential(train_extxyz_dir, train_lmdb_path)
    
    if args.linref_coeff:
        force_rms = 1.0
        try:
            linref_coeff = json.loads(args.linref_coeff)
        except:
            linref_coeff = [float(x) for x in args.linref_coeff.split(",")]
        logging.info("Using provided linref_coeff from config.")
        
        if regression_tasks == "e":
            force_rms = 1.0
    else:
        force_rms, linref_coeff = _compute_normalizer_sequential(train_lmdb_path)
        if regression_tasks == "e":
            force_rms = 1.0
        
    _create_lmdb_sequential(val_extxyz_dir, val_lmdb_path)
    
    # 3. Save metadata JSON
    metadata = {
        "train_lmdb_path": str(train_lmdb_path.absolute()),
        "val_lmdb_path": str(val_lmdb_path.absolute()),
        "force_rms": float(force_rms),
        "linref_coeff": linref_coeff,
        "regression_tasks": regression_tasks
    }
    
    metadata_path = save_dir / "dataset_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print("\n=======================================================")
    print("Data successfully prepared!")
    print(f"LMDB datasets created at: {lmdb_dir}")
    print(f"Dataset metadata written to: {metadata_path}")
    print("=======================================================\n")
    print("To generate training configs and start training, run:")
    print(f"  conda activate fairchem-agent")
    print(f"  python generate_fairchem_config.py --data-metadata {metadata_path.absolute()} --output-dir {save_dir.absolute()}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

if __name__ == "__main__":
    main()
