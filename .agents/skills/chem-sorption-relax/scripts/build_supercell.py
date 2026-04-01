"""
Checks if a structure needs to be expanded into a supercell to satisfy a minimum 
interplanar distance requirement for sorption calculations, and writes the resulting structure.

Usage:
    python build_supercell.py --structure input.cif --min-plane-dist 12.0 --output-cif supercell.cif

Requirements:
    - Conda environment: base-agent
    - Required packages: ase
"""
import argparse
import sys
from pathlib import Path
import numpy as np
from ase.io import read, write

def get_supercell_dimensions(cell, min_dist: float) -> tuple[int, int, int]:
    """
    Calculate the supercell expansion (nx, ny, nz) required so the distance 
    between parallel crystal planes is at least `min_dist`.
    """
    # Calculate reciprocal lattice vectors
    volume = np.abs(np.dot(cell[0], np.cross(cell[1], cell[2])))
    b1 = np.cross(cell[1], cell[2]) / volume
    b2 = np.cross(cell[2], cell[0]) / volume
    b3 = np.cross(cell[0], cell[1]) / volume

    # The distance between planes is 1 / |b_i|
    d1 = 1.0 / np.linalg.norm(b1)
    d2 = 1.0 / np.linalg.norm(b2)
    d3 = 1.0 / np.linalg.norm(b3)

    return (
        int(np.ceil(min_dist / d1)),
        int(np.ceil(min_dist / d2)),
        int(np.ceil(min_dist / d3)),
    )

def main():
    parser = argparse.ArgumentParser(description="Build a supercell based on a minimum interplanar distance.")
    parser.add_argument("--structure", type=Path, required=True, help="Path to input structure (.cif or .xyz)")
    parser.add_argument("--min-plane-dist", type=float, default=12.0, help="Minimum interplanar distance (Å) before building supercell")
    parser.add_argument("--output-cif", type=Path, required=True, help="Path to save the generated supercell CIF")
    
    args = parser.parse_args()
    
    atoms = read(args.structure)
    if not all(atoms.pbc):
        print("Warning: Input structure does not have PBC in all directions. Adding PBC.")
        atoms.pbc = [True, True, True]

    sc_dims = get_supercell_dimensions(atoms.cell, args.min_plane_dist)
    
    print(f"Original cell volume: {atoms.get_volume():.2f} A^3")
    print(f"Calculated supercell dimensions: {sc_dims[0]}x{sc_dims[1]}x{sc_dims[2]}")
    
    if sc_dims == (1, 1, 1):
        print("No supercell expansion is necessary.")
        supercell_atoms = atoms
    else:
        supercell_atoms = atoms.repeat(sc_dims)
        print(f"Generated supercell with {len(supercell_atoms)} atoms.")
        
    # Ensure output directory exists
    args.output_cif.parent.mkdir(parents=True, exist_ok=True)
    write(args.output_cif, supercell_atoms)
    print(f"Saved structure to {args.output_cif}")

if __name__ == "__main__":
    sys.exit(main())
