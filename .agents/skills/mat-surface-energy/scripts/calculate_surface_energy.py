"""
Script to calculate surface energies from relaxed slab and bulk energies.

Usage:
    python calculate_surface_energy.py --bulk_energy_per_atom -4.567 --slab_dir slab_relaxations/ --output surface_energies.json

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, ase
"""

import argparse
import json
import os
from pathlib import Path
from ase.io import read
from pymatgen.io.ase import AseAtomsAdaptor

def get_energy(material_dir: Path):
    """Try to read energy from relaxed_energy.txt or result.json."""
    energy_file = material_dir / "relaxed_energy.txt"
    if energy_file.exists():
        with open(energy_file) as f:
            return float(f.read().strip())
    
    result_file = material_dir / "result.json"
    if result_file.exists():
        with open(result_file) as f:
            result = json.load(f)
            return result.get("relaxed_energy") or result.get("energy")
    
    return None

def main():
    parser = argparse.ArgumentParser(description="Calculate surface energies from relaxed slabs.")
    parser.add_argument("--bulk_energy_per_atom", type=float, required=True, help="Bulk energy per atom (eV/atom)")
    parser.add_argument("--slab_dir", required=True, help="Directory containing relaxed slab subdirectories")
    parser.add_argument("--output", default="surface_energies.json", help="Output JSON file for surface energies")
    
    args = parser.parse_args()
    slab_dir = Path(args.slab_dir)
    bulk_e_per_atom = args.bulk_energy_per_atom

    results = []
    
    # Iterate through each slab relaxation directory
    # MCP batch relaxation creates subdirectories named after the input file (e.g., slab_111_0)
    for subdir in slab_dir.iterdir():
        if not subdir.is_dir():
            continue
        
        energy = get_energy(subdir)
        if energy is None:
            print(f"⚠️  Warning: No energy found for {subdir.name}")
            continue
            
        # Find the relaxed structure
        structure_file = None
        for f in ["relaxed_structure.cif", "final_structure.cif"]:
            if (subdir / f).exists():
                structure_file = subdir / f
                break
        
        if not structure_file:
            # Fallback: check if there's any CIF in the directory
            cifs = list(subdir.glob("*.cif"))
            if cifs:
                structure_file = cifs[0]
        
        if not structure_file:
            print(f"⚠️  Warning: No structure found for {subdir.name}")
            continue
            
        atoms = read(str(structure_file))
        num_atoms = len(atoms)
        
        # Calculate surface area (perpendicular to standard slab vector)
        # Pymatgen slabs are oriented such that the surface is in the a-b plane
        # Area = |a x b|
        pmg_structure = AseAtomsAdaptor.get_structure(atoms)
        area = pmg_structure.lattice.matrix[0][0] * pmg_structure.lattice.matrix[1][1] - \
               pmg_structure.lattice.matrix[0][1] * pmg_structure.lattice.matrix[1][0]
        # Actually, simpler:
        a = pmg_structure.lattice.matrix[0]
        b = pmg_structure.lattice.matrix[1]
        import numpy as np
        area = np.linalg.norm(np.cross(a, b))

        # Surface energy calculation (eV/A^2)
        # Gamma = (E_slab - N * E_bulk) / (2 * Area)
        # Factor of 2 because there are two surfaces (top and bottom)
        gamma_ev_ang2 = (energy - num_atoms * bulk_e_per_atom) / (2 * area)
        
        # Convert to J/m^2 (1 eV/A^2 = 16.0218 J/m^2)
        gamma_j_m2 = gamma_ev_ang2 * 16.0218

        # Try to parse miller index from dirname (slab_111_0 -> 1 1 1)
        name_parts = subdir.name.split("_")
        miller_index = None
        if len(name_parts) >= 2:
            hkl_str = name_parts[1]
            try:
                # Handle negative indices like 11-1 or 10-1
                # Format is usually 'hkl' where '-' precedes the digit
                idx = []
                j = 0
                while j < len(hkl_str):
                    if hkl_str[j] == '-':
                        idx.append(-int(hkl_str[j+1]))
                        j += 2
                    else:
                        idx.append(int(hkl_str[j]))
                        j += 1
                miller_index = tuple(idx)
            except:
                pass

        results.append({
            "name": subdir.name,
            "miller_index": miller_index,
            "energy": energy,
            "num_atoms": num_atoms,
            "area": area,
            "gamma_ev_ang2": gamma_ev_ang2,
            "gamma_j_m2": gamma_j_m2
        })
        
        print(f"✓ Calculated {subdir.name}: gamma = {gamma_j_m2:.4f} J/m^2")

    # Sort results by miller index if possible, then by energy (to pick lowest termination)
    # Group by miller index
    grouped = {}
    for r in results:
        hkl = r["miller_index"]
        if hkl not in grouped or r["gamma_j_m2"] < grouped[hkl]["gamma_j_m2"]:
            grouped[hkl] = r

    final_results = {
        "bulk_energy_per_atom": bulk_e_per_atom,
        "all_slabs": results,
        "unique_min_slabs": [v for k, v in grouped.items() if k is not None]
    }

    with open(args.output, "w") as f:
        json.dump(final_results, f, indent=2)
    
    print(f"\n✓ Saved results for {len(final_results['unique_min_slabs'])} unique planes to {args.output}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)

if __name__ == "__main__":
    main()
