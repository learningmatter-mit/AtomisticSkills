"""
Script to generate oriented slabs from a bulk structure using pymatgen.

Usage:
    python create_slabs.py --bulk bulk.cif --max_index 1 --min_thickness 10.0 --vacuum 15.0 --output slabs/

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, ase
"""

import argparse
import os
from pymatgen.core import Structure
from pymatgen.core.surface import SlabGenerator, generate_all_slabs
from pymatgen.io.ase import AseAtomsAdaptor

def main():
    parser = argparse.ArgumentParser(description="Generate oriented slabs for surface energy calculations.")
    parser.add_argument("--bulk", required=True, help="Path to bulk structure file (CIF, POSCAR, etc.)")
    parser.add_argument("--max_index", type=int, default=1, help="Maximum Miller index to consider (default: 1)")
    parser.add_argument("--min_thickness", type=float, default=10.0, help="Minimum slab thickness in Angstroms (default: 10.0)")
    parser.add_argument("--vacuum", type=float, default=15.0, help="Vacuum thickness in Angstroms (default: 15.0)")
    parser.add_argument("--output", default="slabs", help="Directory to save generated slabs (default: slabs)")
    parser.add_argument("--primitive", action="store_true", help="Use primitive cell for generation")

    args = parser.parse_args()

    # Load structure
    bulk = Structure.from_file(args.bulk)
    if args.primitive:
        bulk = bulk.get_primitive_structure()

    os.makedirs(args.output, exist_ok=True)

    # Generate all slabs up to max_index
    # generate_all_slabs yields slabs with unique orientations
    slabs = generate_all_slabs(
        bulk,
        max_index=args.max_index,
        min_slab_size=args.min_thickness,
        min_vacuum_size=args.vacuum,
        center_slab=True,
        lll_reduce=True,
        bonds=None,  # Standard bonds
        ftol=0.1
    )

    print(f"Generating slabs for {bulk.composition.reduced_formula} up to index {args.max_index}...")
    count = 0
    for i, slab in enumerate(slabs):
        hkl = "".join(map(str, slab.miller_index))
        # Handle cases where multiple terminations exist for the same hkl
        # We'll save all of them, the user/MLIP will find the lowest energy one
        filename = f"slab_{hkl}_{count}.cif"
        path = os.path.join(args.output, filename)
        slab.to(fmt="cif", filename=path)
        print(f"  Saved {hkl} plane to {path}")
        count += 1

    print(f"Total slabs generated: {count}")

if __name__ == "__main__":
    main()
