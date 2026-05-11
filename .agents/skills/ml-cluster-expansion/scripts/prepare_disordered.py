#!/usr/bin/env python
"""
Prepare a primordial disordered structure for smol CE training.

This script:
1. Loads a structure from Materials Project or file
2. Refines the symmetry (required by smol)
3. Creates disorder on specified sites with partial occupancies

Usage:
    python prepare_primordial.py input.cif Li 0.5 -o primordial.cif
"""
import argparse
from pymatgen.core import Structure, Species
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

def prepare_primordial(
    input_structure,
    disorder_species,
    occupancy,
    output_file="primordial.cif"
):
    """
    Prepare a primordial structure with disorder for CE training.
    
    Args:
        input_structure: Path to input structure or Structure object
        disorder_species: Element symbol to make disordered (e.g., "Li")
        occupancy: Occupancy fraction (e.g., 0.5 for 50% Li / 50% vacancy)
        output_file: Output CIF filename
        
    Returns:
        Refined disordered Structure
    """
    # Load structure
    if isinstance(input_structure, str):
        s = Structure.from_file(input_structure)
    else:
        s = input_structure
    
    print(f"Original structure: {s.formula}")
    print(f"Space group: {s.get_space_group_info()}")
    
    # Refine symmetry (CRITICAL for smol)
    sga = SpacegroupAnalyzer(s)
    s_refined = sga.get_refined_structure()
    print(f"Refined structure: {s_refined.formula}")
    print(f"Refined space group: {s_refined.get_space_group_info()}")
    
    # Create disorder on specified sites
    disorder_indices = [
        i for i, site in enumerate(s_refined) 
        if site.specie.symbol == disorder_species
    ]
    
    print(f"\nCreating disorder on {len(disorder_indices)} {disorder_species} sites")
    print(f"Occupancy: {occupancy} {disorder_species} + {1-occupancy} vacancy")
    
    for i in disorder_indices:
        # Smol automatically interprets occupancy < 1.0 as Li/vacancy disorder
        s_refined[i].species = {Species(disorder_species): occupancy}
    
    print(f"Disordered formula: {s_refined.formula}")
    
    # Save
    s_refined.to(filename=output_file)
    print(f"\n✓ Saved to {output_file}")
    
    return s_refined

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare a primordial disordered structure for smol CE training"
    )
    parser.add_argument(
        "input_structure", 
        help="Input structure file (CIF, POSCAR, etc.)"
    )
    parser.add_argument(
        "element",
        help="Element to make disordered (e.g., Li)"
    )
    parser.add_argument(
        "occupancy",
        type=float,
        help="Occupancy fraction (0.0 to 1.0, e.g., 0.5 for 50%%)"
    )
    parser.add_argument(
        "-o", "--output",
        default="primordial.cif",
        help="Output filename (default: primordial.cif)"
    )
    
    args = parser.parse_args()
    
    if not (0.0 < args.occupancy < 1.0):
        raise ValueError("Occupancy must be between 0.0 and 1.0 (exclusive)")
    
    prepare_primordial(
        args.input_structure,
        args.element,
        args.occupancy,
        args.output
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)
