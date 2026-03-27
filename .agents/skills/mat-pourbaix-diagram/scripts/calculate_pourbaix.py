
import argparse
import json
import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import matplotlib.pyplot as plt

from pymatgen.core import Composition, Element, Structure
from pymatgen.entries.computed_entries import ComputedEntry
from pymatgen.analysis.pourbaix_diagram import PourbaixDiagram, PourbaixEntry, PourbaixPlotter
from pymatgen.entries.compatibility import MaterialsProjectAqueousCompatibility, MaterialsProject2020Compatibility
from pymatgen.analysis.phase_diagram import PhaseDiagram
from mp_api.client import MPRester

def load_relaxed_solids(relaxed_dir: Path, exclude_formulas: List[str] = None) -> Dict[str, Dict]:
    """Load total energies from relaxed structure result files."""
    energies = {}
    exclude_formulas = exclude_formulas or []
    
    for subdir in relaxed_dir.iterdir():
        if not subdir.is_dir():
            continue
            
        energy_file = subdir / "relaxed_energy.txt"
        struct_file = subdir / "relaxed_structure.cif"
        if not energy_file.exists():
            continue
            
        with open(energy_file) as f:
            total_energy = float(f.read().strip())
            
        # Extract formula and subdir name
        name_parts = subdir.name.split('_')
        formula = name_parts[0]
        if formula in exclude_formulas or subdir.name in exclude_formulas:
            continue
            
        from pymatgen.core import Structure
        struct = Structure.from_file(str(struct_file)) if struct_file.exists() else None
        comp = struct.composition if struct else Composition(formula)
        
        energies[subdir.name] = {
            'energy': total_energy,
            'composition': comp,
            'formula': formula
        }
    return energies

def main():
    parser = argparse.ArgumentParser(description='Strict Pymatgen Pourbaix Diagram Script')
    parser.add_argument('--relaxed_solids', type=Path, required=True, help='Dir containing relaxed solid results')
    parser.add_argument('--target', type=str, help='Target metal element (required if comp_dict not provided)')
    parser.add_argument('--output', type=Path, required=True, help='Output directory')
    parser.add_argument('--ion_concentration', type=float, default=1e-6, help='Ion concentration in M')
    parser.add_argument('--exclude_phases', nargs='*', help='Formulas to exclude (e.g. Zn(HO)2)')
    parser.add_argument('--comp_dict', type=str, help='Composition dictionary, e.g. "Li=1,Fe=1"')
    parser.add_argument('--conc_dict', type=str, help='Concentration dictionary, e.g. "Li=1e-6,Fe=1e-6"')
    parser.add_argument('--mlip_name', type=str, default="MLIP", help='MLIP name for plot title')
    parser.add_argument('--mlip_head', type=str, default=None, help='MLIP head name (optional, for compatibility check)')
    parser.add_argument('--apply_solid_compat', action='store_true', help='Apply MP2020 solid compatibility (for MP-trained MLIPs)')
    
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    # Parse comp_dict and conc_dict
    comp_dict = {}
    if args.comp_dict:
        for item in args.comp_dict.split(','):
            el, amt = item.split('=')
            comp_dict[el.strip()] = float(amt)
    else:
        # Default: target element = 1.0
        comp_dict = {args.target: 1.0}
        
    elements_of_interest = list(comp_dict.keys())
    
    conc_dict = {}
    if args.conc_dict:
        for item in args.conc_dict.split(','):
             el, val = item.split('=')
             conc_dict[el.strip()] = float(val)
    else:
        # Default: Apply global ion_concentration to all elements of interest
        for el in elements_of_interest:
            conc_dict[el] = args.ion_concentration

    # ... (Compatibility Check Logic - Unchanged) ...
    # Determine if solid compatibility is needed based on MLIP name/head
    if not args.apply_solid_compat:
        try:
            # Locate the YAML file relative to this script
            yaml_path = Path(__file__).parent.parent.parent / "mp2020-compatibility" / "resources" / "gga-ggau-mixed-mlips.yaml"
            if yaml_path.exists():
                with open(yaml_path, 'r') as f:
                    compat_data = yaml.safe_load(f)
                
                checkpoints = compat_data.get("checkpoints_requiring_mp2020_compatibility", [])
                for ckpt in checkpoints:
                    if ckpt.get("name") == args.mlip_name:
                        config_head = ckpt.get("head")
                        if config_head:
                            if args.mlip_head == config_head:
                                args.apply_solid_compat = True
                                print(f"Auto-detected need for MP2020 compatibility for {args.mlip_name} (head: {args.mlip_head})")
                                break
                        else:
                            # applies to all heads if not specified
                            args.apply_solid_compat = True
                            print(f"Auto-detected need for MP2020 compatibility for {args.mlip_name}")
                            break
        except Exception as e:
            print(f"Warning: Failed to check compatibility config: {e}")
    
    # 1. Determine Chemical Potentials

    # 1. Fetch Elemental Energies (for references)
    print("Fetching elemental energies...")
    ee_path = Path(__file__).parent.parent.parent / "elemental-energies" / "resources" / f"{args.mlip_name}_energies.json"

    if not ee_path.exists():
        print(f"Warning: {ee_path} not found. Ensure elemental-energies skill is run for {args.mlip_name}.")
        # Fallback empty dict, will fail if H/O missing unless found in relaxations
        ee_data = {}
    else:
        with open(ee_path, 'r') as f:
            ee_data = json.load(f)

    def get_ref_energy_per_atom(element_symbol: str) -> float:
        if element_symbol in ee_data:
            return ee_data[element_symbol]
        # Fallback to local relaxation
        candidates = list(args.relaxed_solids.glob(f"{element_symbol}_*"))
        if not candidates:
            # Try just element symbol
            candidates = list(args.relaxed_solids.glob(f"{element_symbol}"))

        if not candidates:
             raise ValueError(f"Could not find reference energy for {element_symbol}")

        # Find min energy per atom
        min_e = float('inf')
        for p in candidates:
            try:
                # Try reading relaxed_energy.txt
                if (p / 'relaxed_energy.txt').exists():
                   e_total = float((p / 'relaxed_energy.txt').read_text().strip())
                   # Need num atoms... assume we can parse structure or assume it matches symbol?
                   # Better to parse structure
                   if (p / 'relaxed_structure.cif').exists():
                       s = Structure.from_file(p / 'relaxed_structure.cif')
                       e_pa = e_total / len(s)
                       if e_pa < min_e: min_e = e_pa
            except Exception:
                continue
        if min_e == float('inf'):
            raise ValueError(f"Could not determine energy for {element_symbol}")
        return min_e

    # Get references
    try:
        mu_H = get_ref_energy_per_atom("H") # H2 gas per atom
        mu_O = get_ref_energy_per_atom("O") # O2 gas per atom
        # Check references for all elements of interest to fail early if missing
        for el in elements_of_interest:
            get_ref_energy_per_atom(el)
    except ValueError as e:
        print(f"Error: {e}")
        return 1


    # Get H2O energy
    h2o_energy_per_atom = None
    
    # Try loading from H2O energies JSON first
    try:
        h2o_json_path = Path(__file__).parent.parent / "resources" / "h2o_energies.json"
        if h2o_json_path.exists():
            with open(h2o_json_path, 'r') as f:
                h2o_data = json.load(f)
            
            # Construct possible keys
            keys_to_try = []
            if args.mlip_head:
                keys_to_try.append(f"{args.mlip_name}_{args.mlip_head}")
            keys_to_try.append(args.mlip_name)
            
            for k in keys_to_try:
                if k in h2o_data:
                    h2o_energy_per_atom = h2o_data[k]
                    print(f"Loaded H2O energy for {k} from JSON: {h2o_energy_per_atom:.4f} eV/atom")
                    break
    except Exception as e:
        print(f"Warning: Failed to load pre-calculated H2O energy: {e}")

    # Fallback to local relaxation if not found
    if h2o_energy_per_atom is None:
        h2o_candidates = list(args.relaxed_solids.glob("H2O*"))
        if not h2o_candidates:
             print("Error: No H2O relaxation found in relaxed_solids. Required for aqueous compatibility (and not found in pre-calculated JSON).")
             return 1
    
        e_h2o_min = float('inf')
        best_h2o_path = None
        h2o_atoms = 0
    
        for p in h2o_candidates:
            if (p / 'relaxed_energy.txt').exists() and (p / 'relaxed_structure.cif').exists():
                e = float((p / 'relaxed_energy.txt').read_text().strip())
                s = Structure.from_file(p / 'relaxed_structure.cif')
                if e < e_h2o_min:
                    e_h2o_min = e
                    best_h2o_path = p
                    h2o_atoms = len(s)
    
        if best_h2o_path is None:
             print("Error: Could not parse H2O energy from relaxation directory.")
             return 1
    
        h2o_energy_per_atom = e_h2o_min / h2o_atoms


    # 2. Setup Compatibility
    print(f"Setting up MaterialsProjectAqueousCompatibility...")
    print(f"  O2 energy: {mu_O:.4f} eV/atom")
    print(f"  H2O energy: {h2o_energy_per_atom:.4f} eV/atom")



    # Disable POTCAR checks for MLIP data
    solid_compat = MaterialsProject2020Compatibility(check_potcar=False, check_potcar_hash=False) if args.apply_solid_compat else None

    # We pass o2_energy and h2o_energy (per atom) to init
    # Set h2o_adjustments=0.0 to satisfy check (assuming our H2O energy is final)
    compat = MaterialsProjectAqueousCompatibility(
        solid_compat=solid_compat,
        o2_energy=mu_O,
        h2o_energy=h2o_energy_per_atom,
        h2o_adjustments=0.0
    )

    # 3. Load All Solids as ComputedEntry
    print("Loading solids and creating PhaseDiagram...")
    mlip_solids_data = load_relaxed_solids(args.relaxed_solids, args.exclude_phases)

    computed_entries = []
    for eid, data in mlip_solids_data.items():
        # Create ComputedEntry. We use default parameters.
        # Note: If solid_compat is MP2020, it might expect 'run_type'='GGA'/'GGA+U' and 'hubbards'.
        # Since we are MLIP, we probably don't have these.
        # If args.apply_solid_compat is True, this might fail or warn if metadata missing.
        # User said "treat MLIP predicted energy as DFT energies".
        parameters = {"run_type": "GGA"} # Fake it for compatibility if needed
        entry = ComputedEntry(data['composition'], data['energy'], entry_id=eid, parameters=parameters)
        computed_entries.append(entry)

    # Ensure references are present. If not in relaxed_solids, add them manually from elementary-energies
    # Identify all elements in the system from loaded solids
    all_elements = set()
    for entry in computed_entries:
        all_elements.update(entry.composition.elements)
    
    # Always include H and O if they might be part of the Pourbaix diagram (usually yes)
    # But strictly, we should only add them if we expect them. 
    # The aqueous compatibility usually requires H and O.
    all_elements.add(Element("H"))
    all_elements.add(Element("O"))

    for el in all_elements:
        # Check if we have a pure entry for this element
        # Note: "Li" entry composition is Li1. "H2" is H2.
        # We check if any entry has composition strictly equal to the element (or integer multiple)
        has_element = False
        for entry in computed_entries:
            if len(entry.composition.elements) == 1 and entry.composition.elements[0] == el:
                has_element = True
                break
        
        if not has_element:
            try:
                # Try to get energy from pre-calculated data or local search
                # get_ref_energy_per_atom raises ValueError if not found
                e_per_atom = get_ref_energy_per_atom(el.symbol)
                
                # Create entry. For gases (H, O, N, F, Cl), convention often uses diatomic.
                # But PhaseDiagram handles normalization.
                # However, our H2/O2 specific H/O handling might prefer H2/O2 names.
                # Let's stick to simple "Element" name unless it's H/O where we used "H2"/"O2" before.
                
                label = el.symbol
                formula_size = 1
                if el.symbol in ["H", "O", "N", "F", "Cl"]:
                     label = f"{el.symbol}2"
                     formula_size = 2
                
                total_energy = e_per_atom * formula_size
                print(f"Auto-adding missing terminal entry: {label} (E={total_energy:.4f} eV)")
                
                computed_entries.append(ComputedEntry(label, total_energy, entry_id=f"{label}_ref_ee", parameters={"run_type": "GGA"}))
            except ValueError:
                print(f"Warning: Missing terminal entry for {el} and could not find reference energy. Phase Diagram construction may fail.")

    # 4. Process Entries
    print("Processing entries with Aqueous Compatibility...")
    processed_entries = compat.process_entries(computed_entries)

    # 5. Calculate Formation Energies
    # We utilize PhaseDiagram to get formation energies relative to stable inputs (elements)
    # The processed_entries now have energies adjusted to be compatible with Aqueous scale (H2 / H2O shifted)
    pd = PhaseDiagram(processed_entries)

    pourbaix_entries = []

    print("Constructing Pourbaix Entries...")
    for entry in processed_entries:
        # Calculate Formation Energy relative to elements in PhaseDiagram
        # Note: PhaseDiagram uses the energies *in* the entries.
        # If compat modified them, PD uses modified energies.
        form_e = pd.get_form_energy(entry)

        # Check for Pure H/O entries (H2, O2, H2O)
        # Pymatgen PourbaixEntry throws ZeroDivisionError if normalization factor (non-OH atoms) is 0.
        # These entries are needed for PhaseDiagram (above) but should NOT be passed to PourbaixDiagram as solids.
        n_non_oh = entry.composition.num_atoms - entry.composition.get("H", 0) - entry.composition.get("O", 0)
        if n_non_oh < 1e-3:
            continue

        # Create new ComputedEntry with this formation energy
        # Ref: MPRester.get_pourbaix_entries
        new_entry = ComputedEntry(entry.composition, form_e, entry_id=entry.entry_id)

        # Wrap in PourbaixEntry
        pb_entry = PourbaixEntry(new_entry)
        pourbaix_entries.append(pb_entry)

    # 3. Load MP Ions
    print("\nQuerying MP for aqueous ions...")
    api_key = os.getenv("MP_API_KEY")
    if not api_key:
        print("Error: MP_API_KEY not set.")
        return 1

    with MPRester(api_key) as mpr:
        # get_pourbaix_entries returns entries already wrapped in PourbaixEntry
        # and their energies are already referenced to MP's internal scale.
        # We need to fetch for all elements in our composition + O + H
        query_elements = elements_of_interest + ['O', 'H']
        print(f"Fetching ions for: {query_elements}")
        mp_pb_entries = mpr.get_pourbaix_entries(query_elements)

    for pb_entry in mp_pb_entries:
        if pb_entry.phase_type == "Ion":
            # Set desired concentration for specific element
            # Ions are often multielement (e.g. Fe(OH)+). 
            # We usually set concentration based on the 'main' metal.
            # Here we just use default strategy or check if one of our interest elements is in it?
            # conc_dict provides per-element settings. Pymatgen handles this in PourbaixDiagram logic?
            # Actually, PourbaixDiagram constructor takes conc_dict.
            # But we can also set concentration on the entry itself.
            # Convention: if an ion has multiple metals, it's tricky.
            # If we pass conc_dict to PourbaixDiagram, we might not need to set it on entry manually?
            # Let's add them to the list and rely on PourbaixDiagram(conc_dict=...)
            
            pourbaix_entries.append(pb_entry)
            print(f"  {pb_entry.name:20} | PB_E={pb_entry.energy:8.3f}")


    if not pourbaix_entries:
        print("No valid entries found for Pourbaix Diagram.")
        return 1

    # 6. Construct Diagram
    print(f"Constructing Pourbaix Diagram with {len(pourbaix_entries)} entries...")
    print(f"Composition: {comp_dict}")
    print(f"Concentrations: {conc_dict}")
    
    try:
        pb = PourbaixDiagram(
            pourbaix_entries, 
            comp_dict=comp_dict, 
            conc_dict=conc_dict,
            filter_solids=True
        )
    except Exception as e:
        print(f"Error constructing PourbaixDiagram: {e}")
        return 1

    # 7. Plotting
    plotter = PourbaixPlotter(pb)

    # ... (Rest of plotting code unchanged) ...
    ax = plotter.get_pourbaix_plot(
        limits=[[-2, 16], [-4, 4]], # User requested -3 to 3
        label_domains=True
    )
    
    # Targeted removal of V=0 and pH=7 lines if they exist
    # We do NOT want to remove water stability lines (which are also dashed).
    lines_to_remove = []
    for line in ax.lines:
        # Check if line is dashed (optional filter, but user mentioned dashed)
        if line.get_linestyle() in ['--', 'dashed']:
            x_data = line.get_xdata()
            y_data = line.get_ydata()
            
            # Check for vertical line at pH=7
            # All x values close to 7, and variation in y
            if np.all(np.isclose(x_data, 7.0, atol=0.01)):
                 lines_to_remove.append(line)
                 print("Removed vertical line at pH=7")
                 continue

            # Check for horizontal line at V=0
            # All y values close to 0, and variation in x
            if np.all(np.isclose(y_data, 0.0, atol=0.01)):
                 lines_to_remove.append(line)
                 print("Removed horizontal line at V=0")
                 continue

    for line in lines_to_remove:
        line.remove()

    ax.set_title(f"Pourbaix Diagram ({args.target}) - {args.mlip_name}")
    
    # Save
    out_file = args.output / f"{args.target}_pourbaix_{args.mlip_name}.png"
    ax.figure.tight_layout()
    ax.figure.savefig(out_file, dpi=300)
    print(f"Saved plot to {out_file}")

    # Print stable entries
    print("\nStable Entries:")
    stable_data = []
    for e in pb.stable_entries:
        print(f"  {e.name}")
        stable_data.append({
            "name": e.name,
            "phase_type": e.phase_type,
            "energy": e.energy,
            "entry_id": e.entry_id
        })

    with open(args.output / "stable_entries.json", "w") as f:
        json.dump(stable_data, f, indent=2)

    return 0

if __name__ == "__main__":
    sys.exit(main())
