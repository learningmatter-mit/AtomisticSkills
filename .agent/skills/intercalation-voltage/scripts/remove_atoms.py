"""
Remove specified atoms from a structure to create a de-intercalated state.

This script removes all atoms of a given element from a structure file,
which is useful for creating the empty (de-intercalated) cathode structure
from the full (intercalated) structure.

Usage:
    python remove_atoms.py LiFePO4.cif --remove Li --output FePO4.cif

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, argparse
"""

import argparse
from pathlib import Path
from pymatgen.core import Structure
from collections import Counter


def remove_atoms(
    input_file: str,
    elements_to_remove: list,
    output_file: str = None
) -> Structure:
    """
    Remove all atoms of specified elements from a structure.
    
    Args:
        input_file: Path to input structure file
        elements_to_remove: List of element symbols to remove (e.g., ['Li', 'Na'])
        output_file: Optional path to save the modified structure
        
    Returns:
        Pymatgen Structure object with specified atoms removed
    """
    # Read structure
    structure = Structure.from_file(input_file)
    n_atoms_initial = len(structure)
    
    # Get initial composition
    initial_composition = Counter(structure.symbol_set)
    for species in structure:
        initial_composition[species.specie.symbol] = initial_composition.get(species.specie.symbol, 0) + 1
    
    # Count atoms to be removed
    n_atoms_removed = sum(
        1 for site in structure
        if site.specie.symbol in elements_to_remove
    )
    
    # Remove specified species (modifies structure in place)
    structure.remove_species(elements_to_remove)
    
    # Get final composition
    final_composition = Counter()
    for site in structure:
        final_composition[site.specie.symbol] = final_composition.get(site.specie.symbol, 0) + 1
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Removing atoms from structure")
    print(f"{'='*60}")
    print(f"Input file:       {input_file}")
    print(f"Elements removed: {', '.join(elements_to_remove)}")
    print(f"Initial atoms:    {n_atoms_initial}")
    print(f"Atoms removed:    {n_atoms_removed}")
    print(f"Final atoms:      {len(structure)}")
    
    # Show composition change
    print(f"\nComposition change:")
    all_elements = sorted(set(list(initial_composition.keys()) + list(final_composition.keys())))
    for element in all_elements:
        n_initial = initial_composition.get(element, 0)
        n_final = final_composition.get(element, 0)
        print(f"  {element:2s}: {n_initial:3d} → {n_final:3d}")
    
    # Save if output file specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        structure.to(filename=str(output_path))
        print(f"\nOutput saved to:  {output_file}")
    
    print(f"{'='*60}\n")
    
    return structure


def main():
    parser = argparse.ArgumentParser(
        description="Remove specified atoms from a structure using pymatgen"
    )
    parser.add_argument("input", type=str,
                       help="Input structure file (CIF, POSCAR, etc.)")
    parser.add_argument("--remove", type=str, nargs='+', required=True,
                       help="Element symbol(s) to remove (e.g., Li Na)")
    parser.add_argument("--output", type=str, default=None,
                       help="Output structure file (optional)")
    
    args = parser.parse_args()
    
    # Auto-generate output filename if not provided
    if args.output is None:
        input_path = Path(args.input)
        elements_str = '_'.join(args.remove)
        args.output = str(input_path.parent / f"{input_path.stem}_no{elements_str}{input_path.suffix}")
    
    remove_atoms(
        input_file=args.input,
        elements_to_remove=args.remove,
        output_file=args.output
    )


if __name__ == "__main__":
    main()
