"""
Get structures for Pourbaix diagram calculation.

This script queries Materials Project for:
1. All solid phases in the chemical system (for the hull)
2. Elemental reference structures (for formation energy calculation)
3. Aqueous ion data (saved for later use)

Usage:
    python get_pourbaix_structures.py --chemsys "Zn-O-H" --output_dir "pourbaix_inputs"
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict

from mp_api.client import MPRester
from pymatgen.core import Structure
from pymatgen.analysis.pourbaix_diagram import PourbaixEntry
from pymatgen.io.cif import CifWriter


def get_structures(chemsys: str, api_key: str, output_dir: Path):
    """Query MP and save structures."""
    print(f"\n{'='*70}")
    print(f" getting structures for {chemsys}")
    print(f"{'='*70}\n")
    
    elements = chemsys.split('-')
    output_dir.mkdir(parents=True, exist_ok=True)
    structures_dir = output_dir / "structures"
    structures_dir.mkdir(exist_ok=True)
    
    with MPRester(api_key) as mpr:
        # 1. Get Pourbaix Entries (Solids + Ions)
        print("Querying Pourbaix entries...")
        pb_entries = mpr.get_pourbaix_entries(elements)
        
        # Separate ions and solids
        ions = [e for e in pb_entries if e.phase_type == "Ion"]
        solids = [e for e in pb_entries if e.phase_type == "Solid"]
        
        print(f"Found {len(ions)} ions and {len(solids)} solid phases.")
        
        # Save Ions for later
        ion_data = []
        for ion in ions:
            ion_data.append({
                "formula": ion.name,
                "energy": ion.energy,  # Formation energy per atom (usually)
                "charge": ion.charge,
                "entry_id": ion.entry_id,
                "composition": ion.composition.as_dict()
            })
        
        with open(output_dir / "ions.json", 'w') as f:
            json.dump(ion_data, f, indent=2)
        print(f"✓ Saved {len(ions)} ions to ions.json")

        # 2. Get Structures for Solids
        # PourbaixEntry.entry is a ComputedEntry, it doesn't have the structure always.
        # We need to query structures for these entry_ids.
        # FIX: Strip suffixes like "-GGA" from entry_ids (e.g. "mp-1178680-GGA" -> "mp-1178680")
        solid_ids = [e.entry_id.split('-')[0] + '-' + e.entry_id.split('-')[1] for e in solids]
        # Better robust way:
        clean_ids = []
        original_map = {} # Map clean ID back to entry if needed, but we just need structures
        for e in solids:
            eid = e.entry_id
            # Handle "mp-123", "mp-123-GGA", "mvc-123"
            parts = eid.split('-')
            if len(parts) >= 2:
                clean_id = f"{parts[0]}-{parts[1]}"
                clean_ids.append(clean_id)
            else:
                print(f"Warning: Unusual ID format {eid}")
        
        # Remove duplicates
        solid_ids = list(set(clean_ids))
        
        # Also need elemental references if not in the solids list
        # Usually they are included, but let's be safe.
        
        print(f"Retrieving structures for {len(solid_ids)} solids...")
        # Batch query structures
        docs = mpr.materials.summary.search(material_ids=solid_ids, fields=["material_id", "structure", "formula_pretty", "energy_per_atom"])
        
        # Filter for lowest energy polymorph per formula
        best_docs = {}
        for doc in docs:
            formula = doc.formula_pretty
            if formula not in best_docs or doc.energy_per_atom < best_docs[formula].energy_per_atom:
                best_docs[formula] = doc
        
        print(f"Filtered to {len(best_docs)} lowest energy polymorphs (from {len(docs)} retrieved).")

        saved_count = 0
        for doc in best_docs.values():
            struct = doc.structure
            name = f"{doc.formula_pretty}_{doc.material_id}"
            filename = structures_dir / f"{name}.cif"
            struct.to(filename=str(filename), fmt="cif")
            saved_count += 1
            
        print(f"✓ Saved {saved_count} solid structures to {structures_dir}")
        
        # 3. Ensure Elemental References exist
        # We need simple elemental structures for calculating chemical potentials
        # e.g. Zn (hcp), O2 (gas/molecule), H2 (gas/molecule)
        # Note: MP "Solid" entries usually include ground state elements.
        # But for O and H, we typically need molecules for formation energy if assuming standard states.
        # However, for MLIP consistency, we usually define formation energy relative to the 
        # *MLIP energy of the most stable elemental form*.
        # For O and H, this might be an isolated molecule in a box if the MLIP handles it,
        # or a solid phase if valid.
        
        # Let's save explicit elemental reference structures to be sure.
        print("\nChecking elemental references...")
        ref_dir = output_dir / "references"
        ref_dir.mkdir(exist_ok=True)
        
        # 3. Handle Elemental References
        print("\nHandling elemental references...")
        ref_dir = output_dir / "references"
        ref_dir.mkdir(exist_ok=True)
        
        # Define local resources map
        # Assumes this script is in .agents/skills/mat-pourbaix-diagram/scripts/
        # and resources are in .agents/skills/mat-pourbaix-diagram/resources/
        script_dir = Path(__file__).parent
        resources_dir = script_dir.parent / "resources"
        
        local_refs = {
            "H": "H2.cif",
            "O": "O2.cif",
            "H2O": "H2O.cif",
            "H2": "H2.cif",
            "O2": "O2.cif"
        }
        
        import shutil

        for el in elements:
            # Handle special molecular references from local resources
            if el in ["H", "O"]:
                ref_file = resources_dir / local_refs[el]
                if ref_file.exists():
                    target_file = ref_dir / ref_file.name
                    shutil.copy(ref_file, target_file)
                    print(f"  Copied local reference for {el}: {ref_file.name}")
                    
                    # Also copy H2O if not already (useful for water correction)
                    h2o_src = resources_dir / "H2O.cif"
                    if h2o_src.exists():
                        h2o_dst = ref_dir / "H2O.cif"
                        if not h2o_dst.exists():
                            shutil.copy(h2o_src, h2o_dst)
                            print(f"  Copied local reference: H2O.cif")
                    continue
            
            # For metallic elements (e.g. Zn, Ta), query MP for ground state
            docs = mpr.materials.summary.search(
                chemsys=el, 
                fields=["structure", "formula_pretty", "material_id", "energy_per_atom"]
            )
            
            if docs:
                # Sort by energy per atom to find ground state
                docs.sort(key=lambda x: x.energy_per_atom)
                ref = docs[0]
                
                filename = ref_dir / f"{ref.formula_pretty}_{ref.material_id}.cif"
                ref.structure.to(filename=str(filename), fmt="cif")
                print(f"  Saved reference for {el}: {filename.name} (Energy: {ref.energy_per_atom:.4f} eV/atom)")
            else:
                print(f"⚠️  Warning: No reference found for {el}")

        print(f"\nNext Steps:")
        print(f"1. Relax structures in '{structures_dir}' AND '{ref_dir}' using MLIP.")
        print(f"2. Run calculate_formation_energies.py")


def main():
    parser = argparse.ArgumentParser(description="Get structures for Pourbaix diagram")
    parser.add_argument("--chemsys", required=True, help="e.g. Zn-O-H")
    parser.add_argument("--output_dir", required=True, help="Output directory")
    
    args = parser.parse_args()
    api_key = os.getenv("MP_API_KEY")
    if not api_key:
        print("Error: MP_API_KEY not set")
        return 1
        
    get_structures(args.chemsys, api_key, Path(args.output_dir))
    return 0

if __name__ == "__main__":
    main()
