#!/usr/bin/env python3
"""
Retrieve a crystal structure from Materials Project by material ID.

This script queries Materials Project for a specific material ID and saves the structure
to a CIF file. This is useful for retrieving reference structures for validation,
comparison, or as starting points for simulations.

Usage:
    python get_structure_by_id.py mp-149 --output Si_diamond.cif
    python get_structure_by_id.py mp-19017 --output LiFePO4.cif
    python get_structure_by_id.py mp-1234 mp-5678 mp-9012 --output_dir structures/

Requirements:
    - Conda environment: base-agent
    - Required packages: mp-api, pymatgen, ase
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

def get_mp_api_key() -> Optional[str]:
    """Get Materials Project API key from environment."""
    return os.environ.get("MP_API_KEY")


def get_structure_by_id(material_id: str, mprester) -> Optional[object]:
    """
    Retrieve structure from Materials Project by material ID.
    
    Args:
        material_id: Materials Project ID (e.g., "mp-149")
        mprester: MPRester instance
        
    Returns:
        ASE Atoms object or None if not found
    """
    try:
        structure = mprester.materials.get_structure_by_material_id(material_id)
        if not structure:
            return None
        
        # Convert pymatgen Structure to ASE Atoms
        from pymatgen.io.ase import AseAtomsAdaptor
        atoms = AseAtomsAdaptor.get_atoms(structure)
        return atoms
    except Exception as e:
        print(f"Error retrieving structure for {material_id}: {e}", file=sys.stderr)
        return None


def save_structure(atoms, output_path: Path) -> None:
    """
    Save ASE Atoms object to file.
    
    Args:
        atoms: ASE Atoms object
        output_path: Path to save the structure
    """
    from ase.io import write
    write(str(output_path), atoms, format='cif')


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve crystal structures from Materials Project by material ID"
    )
    parser.add_argument(
        "material_ids",
        nargs="+",
        help="Material ID(s) to retrieve (e.g., mp-149, mp-19017)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output CIF file path (only for single material ID)"
    )
    parser.add_argument(
        "--output_dir",
        "-d",
        help="Output directory for multiple material IDs (default: current directory)"
    )
    parser.add_argument(
        "--api_key",
        help="Materials Project API key (defaults to MP_API_KEY environment variable)"
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or get_mp_api_key()
    if not api_key:
        print("Error: Materials Project API key not found.", file=sys.stderr)
        print("Set MP_API_KEY environment variable or use --api_key argument.", file=sys.stderr)
        sys.exit(1)
    
    # Validate arguments
    if len(args.material_ids) > 1 and args.output:
        print("Error: --output can only be used with a single material ID.", file=sys.stderr)
        print("Use --output_dir for multiple IDs.", file=sys.stderr)
        sys.exit(1)
    
    # Setup output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = Path.cwd()
    
    # Import MPRester
    from mp_api.client import MPRester
    
    # Process material IDs
    with MPRester(api_key) as mpr:
        for material_id in args.material_ids:
            print(f"Retrieving structure for {material_id}...")
            
            atoms = get_structure_by_id(material_id, mpr)
            
            if atoms is None:
                print(f"  ❌ No structure found for {material_id}", file=sys.stderr)
                continue
            
            # Determine output path
            if args.output:
                output_path = Path(args.output)
            else:
                # Create safe filename from material ID
                safe_name = material_id.replace("*", "_star")
                output_path = output_dir / f"{safe_name}.cif"
            
            # Save structure
            try:
                save_structure(atoms, output_path)
                print(f"  ✓ Saved to {output_path.absolute()}")
            except Exception as e:
                print(f"  ❌ Error saving structure: {e}", file=sys.stderr)
                continue
    
    print("\nDone!")


if __name__ == "__main__":
    main()
