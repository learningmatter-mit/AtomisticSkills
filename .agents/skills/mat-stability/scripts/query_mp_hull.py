"""
Query Materials Project for all structures on the convex hull in a chemical space.

Usage:
    python query_mp_hull.py --formula "Li-Fe-P-O" --target "LiFePO4" --output hull_structures/

Requirements:
    - Conda environment: base-agent
    - Required packages: mp-api, pymatgen, ase
    - MP_API_KEY environment variable must be set
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict

from mp_api.client import MPRester
from pymatgen.io.ase import AseAtomsAdaptor


def query_hull_structures(
    chemsys: str,
    target_formula: str,
    output_dir: Path,
    api_key: str,
    thermo_type: str = "R2SCAN"
) -> Dict:
    """
    Query Materials Project for all structures on the convex hull.
    
    Args:
        chemsys: Chemical system (e.g., "Li-Fe-P-O")
        target_formula: Target material formula (e.g., "LiFePO4")
        output_dir: Directory to save structures
        api_key: Materials Project API key
        thermo_type: Level of theory ("GGA_GGA+U" or "R2SCAN", default: "R2SCAN")
        
    Returns:
        Dictionary containing hull entries metadata
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"Querying Materials Project Hull: {chemsys}")
    print(f"Target Material: {target_formula}")
    print(f"Level of Theory: {thermo_type}")
    print(f"{'='*70}\n")
    
    hull_entries = []
    
    with MPRester(api_key) as mpr:
        # get_entries_in_chemsys retrieves all stable entries in the chemical system and all its subsystems
        # This includes terminal elements, binaries, ternaries, etc.
        entries = mpr.get_entries_in_chemsys(
            elements=chemsys.split('-'),
            additional_criteria={
                "is_stable": True,
                "thermo_types": [thermo_type]
            }
        )
        
        if not entries:
            print(f"⚠️  No stable structures found in {chemsys} chemical space with {thermo_type}.")
            return {"error": "No structures found", "hull_entries": []}
        
        print(f"✓ Found {len(entries)} structures on the convex hull:\n")
        print(f"{'Material ID':<15} {'Formula':<20} {'E/atom (eV)':<15}")
        print("-" * 70)
        
        target_found = False
        
        for entry in entries:
            # Extract structure and save
            structure = entry.structure
            material_id = entry.entry_id
            formula = structure.composition.reduced_formula
            energy_per_atom = entry.energy / len(structure)
            
            # Save structure as CIF
            structure_file = output_dir / f"{material_id}.cif"
            structure.to(filename=str(structure_file), fmt="cif")
            
            # Check if this is the target material
            is_target = formula == target_formula
            if is_target:
                target_found = True
                marker = "← TARGET"
                # Also save a copy with friendly name
                target_file = output_dir / f"{target_formula}.cif"
                structure.to(filename=str(target_file), fmt="cif")
            else:
                marker = ""
            
            print(f"{material_id:<15} {formula:<20} {energy_per_atom:<15.4f} {marker}")
            
            # Store metadata
            hull_entries.append({
                "material_id": str(material_id),
                "formula": formula,
                "composition": structure.composition.as_dict(),
                "energy_per_atom_eV": energy_per_atom,
                "is_target": is_target,
                "structure_file": str(structure_file.name),
                "num_atoms": len(structure)
            })
        
        print(f"\n{'='*70}")
        if target_found:
            print(f"✓ Target material {target_formula} found on the hull")
        else:
            print(f"⚠️  Target material {target_formula} NOT on the hull")
            print(f"   (It may be metastable or unstable)")
        print(f"{'='*70}\n")
    
    # Save manifest
    manifest = {
        "chemical_system": chemsys,
        "target_formula": target_formula,
        "target_on_hull": target_found,
        "num_hull_structures": len(hull_entries),
        "hull_entries": hull_entries,
        "output_directory": str(output_dir)
    }
    
    manifest_file = Path("hull_entries.json")
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✓ Saved {len(hull_entries)} structures to {output_dir}")
    print(f"✓ Saved manifest to {manifest_file}")
    
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Query Materials Project for convex hull structures"
    )
    parser.add_argument(
        "--formula",
        required=True,
        help='Chemical system (e.g., "Li-Fe-P-O")'
    )
    parser.add_argument(
        "--target",
        required=True,
        help='Target material formula (e.g., "LiFePO4")'
    )
    parser.add_argument(
        "--output",
        default="hull_structures",
        help="Output directory for structures (default: hull_structures)"
    )
    parser.add_argument(
        "--thermo_type",
        default="R2SCAN",
        choices=["GGA_GGA+U", "R2SCAN"],
        help="Level of theory (default: R2SCAN)"
    )
    
    args = parser.parse_args()
    
    # Check for API key
    api_key = os.getenv("MP_API_KEY")
    if not api_key:
        print("\n⚠️  ERROR: MP_API_KEY environment variable not set")
        print("   Get your API key from: https://next-gen.materialsproject.org/api")
        print("   Set it with: export MP_API_KEY='your_api_key_here'")
        return 1
    
    output_dir = Path(args.output)
    
    try:
        manifest = query_hull_structures(
            args.formula,
            args.target,
            output_dir,
            api_key,
            thermo_type=args.thermo_type
        )
        
        if "error" in manifest:
            return 1
            
        return 0
        
    except Exception as e:
        print(f"\n⚠️  Error querying Materials Project: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    exit(main())
