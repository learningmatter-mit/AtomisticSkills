"""
Calculate the average intercalation voltage from relaxed structure energies.

This script takes the energies of the fully intercalated state, de-intercalated state,
and bulk metal to compute the average voltage.

Usage:
    python calculate_voltage.py --e_full -123.45 --e_empty -98.76 --e_metal -1.23 --n_metal 16 --n_ions 4

Requirements:
    - Conda environment: base-agent
    - Required packages: argparse, json, pathlib
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any


def calculate_voltage(
    e_full: float,
    e_empty: float,
    e_metal: float,
    n_metal: int,
    n_ions: int,
    metal_symbol: str = None,
    output_file: str = None
) -> Dict[str, Any]:
    """
    Calculate the average intercalation voltage.
    
    The voltage is calculated using:
    V = -(E_full - E_empty - n * μ_metal) / n
    
    where μ_metal = E_metal / n_metal_atoms
    
    Args:
        e_full: Total energy of fully intercalated structure (eV)
        e_empty: Total energy of de-intercalated structure (eV)
        e_metal: Total energy of bulk metal structure (eV)
        n_metal: Number of metal atoms in the bulk metal structure
        n_ions: Number of intercalated ions (n_full - n_empty)
        metal_symbol: Optional symbol of intercalating ion for documentation
        output_file: Optional path to save results as JSON
        
    Returns:
        Dictionary with voltage and energy data
    """
    # Calculate chemical potential of metal
    mu_metal = e_metal / n_metal
    
    # Calculate voltage
    # V = -(E_full - E_empty - n*μ_metal) / n
    voltage = -(e_full - e_empty - n_ions * mu_metal) / n_ions
    
    results = {
        "voltage_V": voltage,
        "n_ions": n_ions,
        "E_full_eV": e_full,
        "E_empty_eV": e_empty,
        "E_metal_total_eV": e_metal,
        "n_metal_atoms": n_metal,
        "mu_metal_eV": mu_metal,
        "energy_difference_eV": e_full - e_empty,
        "metal_contribution_eV": n_ions * mu_metal
    }
    
    if metal_symbol:
        results["metal_symbol"] = metal_symbol
    
    # Print results
    print("\n" + "="*60)
    print("INTERCALATION VOLTAGE CALCULATION")
    print("="*60)
    print(f"Average Voltage: {voltage:.4f} V")
    print(f"\nEnergies:")
    print(f"  E(full):        {e_full:.6f} eV")
    print(f"  E(empty):       {e_empty:.6f} eV")
    print(f"  E(metal):       {e_metal:.6f} eV ({n_metal} atoms)")
    print(f"  μ(metal):       {mu_metal:.6f} eV/atom")
    print(f"\nIntercalation:")
    print(f"  Number of ions: {n_ions}")
    print(f"  ΔE:             {e_full - e_empty:.6f} eV")
    print(f"  n×μ(metal):     {n_ions * mu_metal:.6f} eV")
    print("="*60 + "\n")
    
    # Save results if output file specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {output_path}\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Calculate average intercalation voltage from energies"
    )
    parser.add_argument("--e_full", type=float, required=True,
                       help="Total energy of fully intercalated structure (eV)")
    parser.add_argument("--e_empty", type=float, required=True,
                       help="Total energy of de-intercalated structure (eV)")
    parser.add_argument("--e_metal", type=float, required=True,
                       help="Total energy of bulk metal structure (eV)")
    parser.add_argument("--n_metal", type=int, required=True,
                       help="Number of metal atoms in the bulk metal structure")
    parser.add_argument("--n_ions", type=int, required=True,
                       help="Number of intercalated ions (difference between full and empty)")
    parser.add_argument("--metal", type=str, default=None,
                       help="Symbol of intercalating ion (for documentation)")
    parser.add_argument("--output", type=str, default=None,
                       help="Path to save results as JSON")
    
    args = parser.parse_args()
    
    calculate_voltage(
        e_full=args.e_full,
        e_empty=args.e_empty,
        e_metal=args.e_metal,
        n_metal=args.n_metal,
        n_ions=args.n_ions,
        metal_symbol=args.metal,
        output_file=args.output
    )


if __name__ == "__main__":
    main()
