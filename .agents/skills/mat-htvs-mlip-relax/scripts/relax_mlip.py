"""
Relax exported CIFs using MLIP and save relaxed geometries and energies.

Usage:
    python relax_mlip.py --input_dir <dir> --model_name <name> --fmax <val>

Requirements:
    - Conda environment: fairchem-agent (or mace-agent, matgl-agent)
"""
import os
import sys
import json
import argparse
import glob
from tqdm import tqdm
from ase.io import read, write
from ase.constraints import FixAtoms
from ase.optimize import BFGS

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", type=str, required=True)
    parser.add_argument("--model_type", type=str, required=True, choices=["fairchem", "mace", "matgl"])
    parser.add_argument("--model_name", type=str, required=True)
    parser.add_argument("--fmax", type=float, default=0.03)
    parser.add_argument("--steps", type=int, default=200)
    args = parser.parse_args()
    
    meta_path = os.path.join(args.input_dir, "metadata.json")
    with open(meta_path, "r") as f:
        metadata = json.load(f)
        
    device = "cuda" if glob.glob("/dev/nvidia*") else "cpu"
    
    if args.model_type == "fairchem":
        from fairchem.core import FAIRChemCalculator, pretrained_mlip
        model = pretrained_mlip.get_predict_unit(args.model_name, device=device)
        calc = FAIRChemCalculator(predict_unit=model, task_name="omat")
    elif args.model_type == "mace":
        from mace.calculators import mace_mp
        calc = mace_mp(model=args.model_name, device=device, default_dtype="float32")
    else:
        raise NotImplementedError("matgl not yet implemented in this wrapper")

    results = []
    
    for item in tqdm(metadata):
        cif_path = item["cif_path"]
        atoms = read(cif_path)
        atoms.calc = calc
        
        fixed_indices = item.get("fixed_indices", [])
        if fixed_indices:
            atoms.set_constraint(FixAtoms(indices=fixed_indices))
            
        opt = BFGS(atoms, logfile=None)
        opt.run(fmax=args.fmax, steps=args.steps)
        
        energy = float(atoms.get_potential_energy())
        
        out_cif = cif_path.replace(".cif", "_relaxed.cif")
        atoms.write(out_cif)
        
        xyz = [[int(a.number), float(p[0]), float(p[1]), float(p[2])] for a, p in zip(atoms, atoms.positions)]
        
        results.append({
            "id": item["id"],
            "energy": energy,
            "xyz": xyz,
            "relaxed_cif": out_cif
        })
        
    with open(os.path.join(args.input_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    print(json.dumps({"status": "success", "count": len(results)}))

if __name__ == "__main__":
    main()
