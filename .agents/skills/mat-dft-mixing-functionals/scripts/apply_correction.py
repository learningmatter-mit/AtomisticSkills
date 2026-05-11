"""
Apply Materials Project 2020 Compatibility corrections to a structure's energy.

Usage:
    python apply_correction.py structure.cif --energy -123.45

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen
"""

import argparse
import sys
import os

# Add src to sys.path to allow importing utils
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../src")))
except Exception:
    pass

from pymatgen.core import Structure
from pymatgen.entries.computed_entries import ComputedStructureEntry
from pymatgen.entries.compatibility import MaterialsProject2020Compatibility
try:
    from pymatgen.entries.compatibility import needs_u_correction
except ImportError:
    # Fallback for older pymatgen versions if needed, or define it locally
    # But user claimed it exists. strict dependency.
    print("Error: needs_u_correction not found in pymatgen.entries.compatibility")
    sys.exit(1)

from utils.structure_utils import load_structures
from typing import Union

def apply_mp2020_correction(structure_input: Union[str, Structure], energy: float):
    """
    Apply MP2020 corrections to a structure and energy.
    Also returns structure label (formula) if filename not available.

    Args:
        structure_input: Path to structure file OR pymatgen Structure object.
        energy: Total energy in eV.
    """
    # Load single structure using utility if path, or use object
    if isinstance(structure_input, (str, os.PathLike)):
        try:
            structure = Structure.from_file(str(structure_input))
        except Exception as e:
            print(f"Error loading structure: {e}")
            return None
    elif isinstance(structure_input, Structure):
        structure = structure_input
    else:
        print("Invalid input type")
        return None

    compat = MaterialsProject2020Compatibility(check_potcar=False)
    
    hubbards = {}
    is_hubbard = False

    # Check if MP2020 considers this composition to need U corrections
    if needs_u_correction(structure.composition):
        is_hubbard = True
        
        # Find most electronegative element to determine U settings (MP2020 logic)
        # We need to populate the expected hubbards so the Entry effectively mimics a MP calculation
        elements = sorted([el for el in structure.composition.elements if structure.composition[el] > 0], key=lambda el: el.X)
        most_electro_neg = elements[-1].symbol
        
        u_block = compat.u_settings.get(most_electro_neg, {})
        
        for el in structure.composition.elements:
            sym = el.symbol
            if sym in u_block:
                u_val = u_block[sym]
                if u_val > 0:
                    hubbards[sym] = u_val
            
    parameters = {
        "hubbards": hubbards,
        "is_hubbard": is_hubbard,
        "run_type": "GGA+U" if is_hubbard else "GGA"
    }
    
    entry = ComputedStructureEntry(
        structure=structure,
        energy=energy,
        correction=0.0,
        parameters=parameters,
        data={}
    )
    
    entry = compat.process_entry(entry)

    if entry is None:
        print("Warning: MaterialsProject2020Compatibility failed to process the entry.")
        return None

    result = {
        "original_energy": energy,
        "corrected_energy": entry.energy,
        "correction": entry.correction,
        "corrections_dict": {adj.name: adj.value for adj in entry.energy_adjustments},
        "formula": structure.composition.reduced_formula
    }
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply MP2020 Compatibility corrections.")
    parser.add_argument("structure_path", help="Path to structure file or directory or glob pattern")
    parser.add_argument("--energy", type=float, default=0.0, help="Total uncorrected energy in eV")
    parser.add_argument("--verbose", action="store_true", help="Print detailed breakdown")
    
    args = parser.parse_args()

    # Use universal loader
    # Argument is a string (path/glob), so load_structures will handle it.
    structures = load_structures(args.structure_path)
    
    if not structures:
        print(f"No structures found in {args.structure_path}")
        sys.exit(1)
        
    if len(structures) > 1:
        print(f"Found {len(structures)} structures. Processing batch...")
        print(f"{'Structure':<40} {'Original':<12} {'Corrected':<12} {'Correction':<12}")
        print("-" * 80)
        
    for s in structures:
        try:
            result = apply_mp2020_correction(s, args.energy)
            if not result:
                print(f"{s.composition.reduced_formula:<40} {'FAILED':<12}")
                continue
                
            label = result["formula"]
            # If valid result
            if len(structures) > 1:
                 print(f"{label:<40} {result['original_energy']:<12.3f} {result['corrected_energy']:<12.3f} {result['correction']:<12.3f}")
            else:
                print(f"Structure Formula: {label}")
                print(f"Original Energy: {result['original_energy']:.4f} eV")
                print(f"Corrected Energy: {result['corrected_energy']:.4f} eV")
                print(f"Total Correction: {result['correction']:.4f} eV")
                print(f"Corrections Details: {result['corrections_dict']}")
                
        except Exception as e:
            print(f"Error processing {s.composition.reduced_formula}: {e}")


