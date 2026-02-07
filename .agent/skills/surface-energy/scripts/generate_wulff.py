"""
Script to generate a Wulff shape from calculated surface energies.

Usage:
    python generate_wulff.py --energies_json surface_energies.json --bulk bulk.cif --output wulff_shape.png

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, matplotlib
"""

import argparse
import json
import matplotlib.pyplot as plt
from pymatgen.core import Structure
from pymatgen.analysis.wulff import WulffShape

def main():
    parser = argparse.ArgumentParser(description="Generate Wulff shape from surface energies.")
    parser.add_argument("--energies_json", required=True, help="Path to surface_energies.json")
    parser.add_argument("--bulk", required=True, help="Path to reference bulk structure")
    parser.add_argument("--output", default="wulff_shape.png", help="Output path for Wulff shape plot")
    
    args = parser.parse_args()

    # Load data
    with open(args.energies_json) as f:
        data = json.load(f)
    
    bulk = Structure.from_file(args.bulk)
    lattice = bulk.lattice

    # Prepare miller indices and energies
    miller_indices = []
    energies = []
    
    for entry in data["unique_min_slabs"]:
        miller_indices.append(entry["miller_index"])
        energies.append(entry["gamma_j_m2"])

    print(f"Generating Wulff shape with {len(miller_indices)} planes...")
    for hkl, e in zip(miller_indices, energies):
        print(f"  {hkl}: {e:.4f} J/m^2")

    # Construct Wulff shape
    wulff = WulffShape(lattice, miller_indices, energies)
    
    # Plot and save
    # Note: WulffShape.get_plot() uses matplotlib/plotly depending on arguments
    # For a static image, we can use the matplotlib backend
    fig = wulff.get_plot()
    plt.savefig(args.output, dpi=300, bbox_inches="tight")
    print(f"✓ Wulff shape saved to {args.output}")
    
    # Save some properties
    info = {
        "surface_area": wulff.surface_area,
        "volume": wulff.volume,
        "area_fraction_dict": {str(k): v for k, v in wulff.area_fraction_dict.items()},
        "weighted_surface_energy": wulff.weighted_surface_energy
    }
    with open(args.output.replace(".png", ".json"), "w") as f:
        json.dump(info, f, indent=2)

if __name__ == "__main__":
    main()
