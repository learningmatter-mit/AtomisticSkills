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

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../mat-electrochemical-window/scripts')))
try:
    from calculate_ecw import get_electrochemical_window
except ImportError:
    get_electrochemical_window = None


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
    loaded_dirs = set()
    
    # 1. Load the structures specifically requested from the hull manifest
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
            continue
            
        entry = _load_single_entry(material_dir, material_id)
        if entry:
            entries.append(entry)
            loaded_dirs.add(material_dir)
            print(f"✓ Loaded from manifest: {material_id:<15} {formula:<20} E = {entry.energy:.4f} eV")
            
    # 2. Load ANY OTHER STRUCTURES present in relaxed_dir for self-competition screening
    for material_dir in relaxed_dir.iterdir():
        if material_dir.is_dir() and material_dir not in loaded_dirs:
            entry_id = material_dir.name
            entry = _load_single_entry(material_dir, entry_id)
            if entry:
                entries.append(entry)
                loaded_dirs.add(material_dir)
                formula = entry.composition.reduced_formula
                print(f"✓ Loaded for self-competition: {entry_id:<15} {formula:<20} E = {entry.energy:.4f} eV")
                
    return entries

def _load_single_entry(material_dir: Path, entry_id: str) -> ComputedEntry:
    # Look for relaxed_structure.cif or similar
    possible_files = [
        material_dir / "relaxed_structure.cif",
        material_dir / "final_structure.cif",
        material_dir / f"{entry_id}.cif"
    ]
    
    structure_file = None
    for f in possible_files:
        if f.exists():
            structure_file = f
            break
    
    if not structure_file:
        return None
    
    # Read structure and get energy
    # Assuming relaxed_energy is stored alongside or can be read from trajectory
    energy_file = material_dir / "relaxed_energy.txt"
    energy = None
    
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
    
    if energy is None:
        return None
    
    # Read structure to get composition
    atoms = read(structure_file)
    pmg_structure = AseAtomsAdaptor.get_structure(atoms)
    composition = pmg_structure.composition
    
    # Create ComputedEntry
    return ComputedEntry(
        composition=composition,
        energy=energy,
        entry_id=entry_id
    )


def compute_hull_analysis(
    entries: List[ComputedEntry],
    target_formula: str,
    calculate_ecw: bool = False,
    mobile_ion: str = "Li"
) -> Dict:
    """
    Construct phase diagram and compute E_hull for target material.
    
    Args:
        entries: List of ComputedEntry objects
        target_formula: Chemical formula of target material
        calculate_ecw: Whether to calculate electrochemical window
        mobile_ion: The mobile ion for ECW calculation
        
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
    
    # Calculate ECW if requested
    if calculate_ecw and get_electrochemical_window is not None:
        print(f"\nCalculating Electrochemical Window vs {mobile_ion}/{mobile_ion}+...")
        # If metastable, force onto hull for pseudo-stability calculations
        ecw_entry = target_entry
        hull_e = pd.get_hull_energy(target_entry.composition)
        if target_entry.energy > hull_e:
            ecw_entry = ComputedEntry(target_entry.composition, hull_e - 1e-5)
            
        v_red, v_ox = get_electrochemical_window(ecw_entry, pd, mobile_ion)
        results["v_red"] = v_red
        results["v_ox"] = v_ox
        results["ecw"] = f"[{v_red:.2f} V, {v_ox:.2f} V]"
        print(f"V_red: {v_red:.2f} V")
        print(f"V_ox:  {v_ox:.2f} V")
        print(f"ECW:   [{v_red:.2f} V, {v_ox:.2f} V]")
    
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
    parser.add_argument(
        "--calculate_ecw",
        action="store_true",
        help="Calculate the intrinsic electrochemical stability window"
    )
    parser.add_argument(
        "--mobile_ion",
        default="Li",
        help="Mobile ion for ECW calculation (default: Li)"
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
        results = compute_hull_analysis(
            entries, 
            args.target_material,
            calculate_ecw=args.calculate_ecw,
            mobile_ion=args.mobile_ion
        )
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
    
    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)

    return 0


if __name__ == "__main__":
    exit(main())
