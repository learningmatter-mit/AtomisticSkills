import argparse
import sys
import os
import json
import matplotlib.pyplot as plt
from pathlib import Path
from pymatgen.core import Structure
from pymatgen.analysis.diffraction.xrd import XRDCalculator


from xrd_utils import get_sim_xrd_from_pattern

def calculate_xrd(structure_path, output_dir, wavelength="CuKa", symprec=0.1, eta=0.1, caglioti_params=(0.1, 0.01, 0.1), bin=0.01):
    """
    Calculate and plot XRD pattern for a given structure.
    """
    # Load structure
    structure = Structure.from_file(structure_path)
    
    # Initialize XRD calculator
    # wavelength can be a float or a string like "CuKa"
    xrd_calc = XRDCalculator(wavelength=wavelength, symprec=symprec)
    
    # Get diffraction pattern
    pattern = xrd_calc.get_pattern(structure)

    # caglioti model for simulated xrd
    sim_xrd, theta = get_sim_xrd_from_pattern(pattern, eta, caglioti_params, bin=bin) #simulates
        
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save pattern data to JSON
    results = {
        "x": list(theta),
        "y": list(sim_xrd),
        "hkls": [str(hkl[0]['hkl']) for hkl in pattern.hkls], # Simplify HKL info
        "d_spacings": list(pattern.d_hkls)
    }
    
    base_name = Path(structure_path).stem
    json_path = os.path.join(output_dir, f"{base_name}_xrd.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=4)
    
    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(theta, sim_xrd, color='blue', linewidth=1)
    plt.xlabel(r"$2\theta$ (degrees)")
    plt.ylabel("Intensity (a.u.)")
    plt.title(f"XRD Pattern for {structure.composition.reduced_formula} ({wavelength})")
    plt.grid(True, linestyle='--', alpha=0.7)

    plot_path = os.path.join(output_dir, f"{base_name}_PV_xrd.png")
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"XRD analysis completed for {structure.composition.reduced_formula}")
    print(f"Results saved to: {json_path}")
    print(f"Plot saved to: {plot_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate XRD spectrum using pymatgen.")
    parser.add_argument("structure", help="Path to input structure file (CIF, POSCAR, etc.)")
    parser.add_argument("--output_dir", default=".", help="Directory to save output files.")
    parser.add_argument("--wavelength", default="CuKa", help="Radiation wavelength or source name (default: CuKa).")
    parser.add_argument("--symprec", type=float, default=0.1, help="Symmetry precision for XRD calculation.")
    parser.add_argument("--eta", type=float, default=0.1, help="Fraction of Lorentzian component for simulated XRD.")
    parser.add_argument("--caglioti_params", type=tuple, default=(0.1, 0.01, 0.1), help="Caglioti parameters for simulated XRD.")
    parser.add_argument("--bin", type=float, default=0.05, help="Bin size for simulated XRD.")
    args = parser.parse_args()
    
    calculate_xrd(args.structure, args.output_dir, args.wavelength, args.symprec, args.eta, args.caglioti_params, args.bin)
