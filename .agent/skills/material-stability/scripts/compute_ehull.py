"""
Compute energy above hull (E_hull) using pymatgen phase diagram analysis.

Usage:
    python compute_ehull.py --hull_manifest hull_entries.json --relaxed_dir relaxed/ --target_material LiFePO4

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, ase, matplotlib
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List

from ase.io import read
from pymatgen.core import Composition
from pymatgen.entries.computed_entries import ComputedEntry
from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.io.ase import AseAtomsAdaptor


def load_relaxed_energies(
    hull_manifest: Dict,
    relaxed_dir: Path
) -> List[ComputedEntry]:
    """
    Load relaxed energies from directory structure.
    
    Args:
        hull_manifest: Manifest from query_mp_hull.py
        relaxed_dir: Directory containing relaxed/<material_id>/ subdirectories
        
    Returns:
        List of ComputedEntry objects for pymatgen
    """
    entries = []
    
    for hull_entry in hull_manifest["hull_entries"]:
        material_id = hull_entry["material_id"]
        formula = hull_entry["formula"]
        
        # Look for relaxed structure in subdirectory
        material_dir = relaxed_dir / material_id
        
        if not material_dir.exists():
            # Try with formula name for target material
            material_dir = relaxed_dir / formula
        
        if not material_dir.exists():
            print(f"⚠️  Warning: No relaxed directory found for {material_id} ({formula})")
            print(f"   Expected: {relaxed_dir / material_id} or {relaxed_dir / formula}")
            continue
        
        # Look for relaxed_structure.cif or similar
        possible_files = [
            material_dir / "relaxed_structure.cif",
            material_dir / "final_structure.cif",
            material_dir / f"{material_id}.cif"
        ]
        
        structure_file = None
        for f in possible_files:
            if f.exists():
                structure_file = f
                break
        
        if not structure_file:
            print(f"⚠️  Warning: No structure file found in {material_dir}")
            continue
        
        # Read structure and get energy
        # Assuming relaxed_energy is stored alongside or can be read from trajectory
        energy_file = material_dir / "relaxed_energy.txt"
        
        if energy_file.exists():
            with open(energy_file) as f:
                energy = float(f.read().strip())
        else:
            # Try to read from a JSON result file
            result_file = material_dir / "result.json"
            if result_file.exists():
                with open(result_file) as f:
                    result = json.load(f)
                    energy = result.get("relaxed_energy", None)
            else:
                print(f"⚠️  Warning: No energy file found for {material_id}")
                print(f"   Expected: {energy_file} or {result_file}")
                continue
        
        # Read structure to get composition
        atoms = read(structure_file)
        pmg_structure = AseAtomsAdaptor.get_structure(atoms)
        composition = pmg_structure.composition
        
        # Create ComputedEntry
        entry = ComputedEntry(
            composition=composition,
            energy=energy,
            entry_id=material_id
        )
        
        entries.append(entry)
        print(f"✓ Loaded: {material_id:<15} {formula:<20} E = {energy:.4f} eV")
    
    return entries


def compute_hull_analysis(
    entries: List[ComputedEntry],
    target_formula: str
) -> Dict:
    """
    Construct phase diagram and compute E_hull for target material.
    
    Args:
        entries: List of ComputedEntry objects
        target_formula: Chemical formula of target material
        
    Returns:
        Dictionary with stability analysis results
    """
    
    print(f"\n{'='*70}")
    print(f"Constructing Convex Hull Phase Diagram")
    print(f"{'='*70}\n")
    
    # Build phase diagram
    pd = PhaseDiagram(entries)
    
    # Find target entry
    target_comp = Composition(target_formula)
    target_entry = None
    
    for entry in entries:
        if entry.composition.reduced_formula == target_comp.reduced_formula:
            target_entry = entry
            break
    
    if not target_entry:
        raise ValueError(f"Target material {target_formula} not found in entries")
    
    # Calculate E_hull
    e_hull = pd.get_e_above_hull(target_entry) * 1000  # Convert to meV/atom
    decomp = pd.get_decomposition(target_entry.composition)
    
    # Get stability assessment
    if e_hull < 1e-6:  # Numerically zero
        stability = "STABLE"
        assessment = "On the convex hull - thermodynamically stable"
    elif e_hull <= 50:
        stability = "METASTABLE"
        assessment = "May be synthesizable under kinetic control"
    else:
        stability = "UNSTABLE"
        assessment = "Likely to decompose into competing phases"
    
    # Format decomposition products
    decomp_products = []
    for phase, amount in decomp.items():
        decomp_products.append({
            "phase": phase.reduced_formula,
            "fraction": amount
        })
    
    results = {
        "target_formula": target_formula,
        "energy_above_hull_meV": e_hull,
        "stability": stability,
        "assessment": assessment,
        "decomposition_products": decomp_products,
        "num_phases_on_hull": len(pd.stable_entries)
    }
    
    # Print results
    print(f"Target Material: {target_formula}")
    print(f"E_hull: {e_hull:.2f} meV/atom")
    print(f"Stability: {stability}")
    print(f"Assessment: {assessment}")
    
    if e_hull > 1e-6:
        print(f"\nDecomposition Products:")
        for prod in decomp_products:
            print(f"  - {prod['phase']:<15} ({prod['fraction']:.3f})")
    
    print(f"\n{'='*70}\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Compute E_hull using pymatgen phase diagram"
    )
    parser.add_argument(
        "--hull_manifest",
        required=True,
        help="Path to hull_entries.json from query_mp_hull.py"
    )
    parser.add_argument(
        "--relaxed_dir",
        required=True,
        help="Directory containing relaxed/<material_id>/ subdirectories"
    )
    parser.add_argument(
        "--target_material",
        required=True,
        help="Chemical formula of target material"
    )
    parser.add_argument(
        "--output",
        default="stability_analysis.json",
        help="Output JSON file"
    )
    
    args = parser.parse_args()
    
    # Load hull manifest
    with open(args.hull_manifest) as f:
        hull_manifest = json.load(f)
    
    relaxed_dir = Path(args.relaxed_dir)
    
    print(f"\n{'='*70}")
    print(f"Loading Relaxed Structures")
    print(f"{'='*70}\n")
    
    # Load relaxed energies
    entries = load_relaxed_energies(hull_manifest, relaxed_dir)
    
    if not entries:
        print("\n⚠️  ERROR: No relaxed structures loaded")
        return 1
    
    print(f"\n✓ Loaded {len(entries)} structures")
    
    # Compute hull analysis
    try:
        results = compute_hull_analysis(entries, args.target_material)
    except Exception as e:
        print(f"\n⚠️  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Save results
    output_file = Path(args.output)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✓ Results saved to {output_file}")
    
    return 0


if __name__ == "__main__":
    exit(main())
