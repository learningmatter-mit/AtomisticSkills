
import argparse
import json
import os
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from pymatgen.analysis.pourbaix_diagram import PourbaixDiagram, PourbaixPlotter
from mp_api.client import MPRester

def main():
    parser = argparse.ArgumentParser(description='Pure Materials Project Pourbaix Diagram Script')
    parser.add_argument('--comp_dict', type=str, required=True, help='Composition dictionary, e.g. "Li=1,Fe=1"')
    parser.add_argument('--conc_dict', type=str, help='Concentration dictionary, e.g. "Li=1e-6,Fe=1e-6"')
    parser.add_argument('--output', type=Path, required=True, help='Output directory')
    parser.add_argument('--ion_concentration', type=float, default=1e-6, help='Default ion concentration in M')
    parser.add_argument('--title', type=str, default="Materials Project Pourbaix", help='Plot title')
    
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    # Parse comp_dict
    comp_dict = {}
    for item in args.comp_dict.split(','):
        el, amt = item.split('=')
        comp_dict[el.strip()] = float(amt)
        
    elements_of_interest = list(comp_dict.keys())
    
    # Parse conc_dict
    conc_dict = {}
    if args.conc_dict:
        for item in args.conc_dict.split(','):
             el, val = item.split('=')
             conc_dict[el.strip()] = float(val)
    else:
        # Default: Apply global ion_concentration to all elements of interest
        for el in elements_of_interest:
            conc_dict[el] = args.ion_concentration

    print(f"Target System: {elements_of_interest}")
    print(f"Composition: {comp_dict}")
    print(f"Concentrations: {conc_dict}")

    # Query MP
    api_key = os.getenv("MP_API_KEY")
    if not api_key:
        print("Error: MP_API_KEY not set.")
        return 1

    print("Querying Materials Project for Pourbaix entries...")
    with MPRester(api_key) as mpr:
        # We need to fetch for all elements in our composition + O + H
        query_elements = elements_of_interest + ['O', 'H']
        # remove duplicates if any
        query_elements = list(set(query_elements))
        
        print(f"Fetching entries for: {query_elements}")
        entries = mpr.get_pourbaix_entries(query_elements)

    if not entries:
        print("No entries found.")
        return 1
        
    print(f"Retrieved {len(entries)} entries.")

    # Construct Diagram
    print("Constructing Pourbaix Diagram...")
    try:
        pb = PourbaixDiagram(
            entries, 
            comp_dict=comp_dict, 
            conc_dict=conc_dict, 
            filter_solids=True
        )
    except Exception as e:
        print(f"Error constructing PourbaixDiagram: {e}")
        return 1

    # Plotting
    plotter = PourbaixPlotter(pb)
    
    # Use standard limits
    ax = plotter.get_pourbaix_plot(
        limits=[[-2, 16], [-4, 4]],
        label_domains=True
    )
    
    # Targeted removal of V=0 and pH=7 lines if they exist
    lines_to_remove = []
    for line in ax.lines:
        if line.get_linestyle() in ['--', 'dashed']:
            x_data = line.get_xdata()
            y_data = line.get_ydata()
            
            # Check for vertical line at pH=7
            if np.all(np.isclose(x_data, 7.0, atol=0.01)):
                 lines_to_remove.append(line)
                 continue

            # Check for horizontal line at V=0
            if np.all(np.isclose(y_data, 0.0, atol=0.01)):
                 lines_to_remove.append(line)
                 continue

    for line in lines_to_remove:
        line.remove()

    ax.set_title(args.title)
    
    # Save
    out_name = "_".join(elements_of_interest) + "_pourbaix_MP.png"
    out_file = args.output / out_name
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

    with open(args.output / "stable_entries_mp.json", "w") as f:
        json.dump(stable_data, f, indent=2)

    return 0

if __name__ == "__main__":
    sys.exit(main())
