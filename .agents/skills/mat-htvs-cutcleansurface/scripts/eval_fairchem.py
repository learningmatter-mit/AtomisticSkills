import os
import sys
import json
import argparse
import numpy as np
from ase.io import read

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper

def get_surface_area(atoms):
    """Calculate the area of the a-b plane."""
    cell = atoms.get_cell()
    cross = np.cross(cell[0], cell[1])
    return np.linalg.norm(cross)

def main():
    parser = argparse.ArgumentParser(description="Evaluate surface energies with FAIRChem UMA")
    parser.add_argument("temp_dir", type=str, help="Directory containing bulk.cif and slab_*.cif files")
    parser.add_argument("--top_n", type=int, default=2, help="Number of top terminations to keep")
    args = parser.parse_args()

    bulk_path = os.path.join(args.temp_dir, "bulk.cif")
    if not os.path.exists(bulk_path):
        print(f"Error: {bulk_path} not found")
        sys.exit(1)

    # Load bulk
    bulk_atoms = read(bulk_path)
    n_bulk = len(bulk_atoms)
    
    # Find all slab files
    slab_files = []
    for f in os.listdir(args.temp_dir):
        if f.startswith("slab_") and f.endswith(".cif"):
            slab_files.append(f)
            
    if not slab_files:
        print("No slabs found")
        sys.exit(0)

    print(f"EVAL_FAIRCHEM: Loading uma-s-1p1 model...")
    wrapper = FAIRCHEMWrapper(model_name="uma-s-1p1", device="cuda")
    wrapper.load()

    print(f"EVAL_FAIRCHEM: Evaluating bulk ({n_bulk} atoms)...")
    bulk_results = wrapper.static_calculation([bulk_path])
    if "error" in bulk_results:
        print(f"Error evaluating bulk: {bulk_results['error']}")
        sys.exit(1)
        
    e_bulk = bulk_results["results"][0]["energy"]
    e_per_atom_bulk = e_bulk / n_bulk
    print(f"EVAL_FAIRCHEM: Bulk energy = {e_bulk:.4f} eV ({e_per_atom_bulk:.4f} eV/atom)")

    slab_paths = [os.path.join(args.temp_dir, f) for f in slab_files]
    print(f"EVAL_FAIRCHEM: Evaluating {len(slab_paths)} slabs...")
    slab_results = wrapper.static_calculation(slab_paths)
    
    if "error" in slab_results:
        print(f"Error evaluating slabs: {slab_results['error']}")
        sys.exit(1)

    ranking = []
    for f, res in zip(slab_files, slab_results["results"]):
        slab_atoms = read(os.path.join(args.temp_dir, f))
        n_slab = len(slab_atoms)
        e_slab = res["energy"]
        area = get_surface_area(slab_atoms)
        
        # Calculate pseudo-surface energy
        # Gamma = (E_slab - N_slab * E_per_atom_bulk) / (2 * A)
        pseudo_gamma = (e_slab - n_slab * e_per_atom_bulk) / (2 * area)
        
        ranking.append({
            "filename": f,
            "energy": e_slab,
            "pseudo_gamma": pseudo_gamma,
            "n_atoms": n_slab,
            "area": area
        })
        print(f"EVAL_FAIRCHEM: {f} -> E_slab={e_slab:.4f} eV, N={n_slab}, Gamma={pseudo_gamma:.4f} eV/A^2")

    # Sort by pseudo_gamma ascending (most stable first)
    ranking.sort(key=lambda x: x["pseudo_gamma"])
    
    top_n = ranking[:args.top_n]
    
    output_path = os.path.join(args.temp_dir, "ranking.json")
    with open(output_path, "w") as f:
        json.dump(top_n, f, indent=2)
        
    print(f"EVAL_FAIRCHEM: Selected top {len(top_n)} slabs. Wrote ranking to {output_path}")

if __name__ == "__main__":
    main()
