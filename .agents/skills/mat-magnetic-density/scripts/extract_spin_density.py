"""
Extract spin density from VASP CHGCAR file.

This script reads the CHGCAR file from a spin-polarized VASP calculation
and extracts the spin density (difference between up and down spin densities).

Usage:
    python extract_spin_density.py <vasp_output_dir> --output spin_density.json

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional
import sys


def extract_spin_density(vasp_dir: Path) -> Dict[str, Any]:
    """
    Extract spin density from VASP CHGCAR file.
    
    Args:
        vasp_dir: Path to directory containing VASP output files
        
    Returns:
        Dictionary containing:
        - 'integrated_magnetization': Total magnetization from spin density
        - 'grid_shape': Shape of the charge density grid
        - 'has_spin_density': Whether spin density data is available
    """
    try:
        from pymatgen.io.vasp import Chgcar
    except ImportError:
        print("Error: pymatgen is required. Please install it in base-agent environment.", 
              file=sys.stderr)
        sys.exit(1)
    
    chgcar_path = vasp_dir / "CHGCAR"
    
    if not chgcar_path.exists():
        print(f"Error: CHGCAR file not found in {vasp_dir}", file=sys.stderr)
        print("Make sure the VASP calculation completed and CHGCAR is available.",
              file=sys.stderr)
        sys.exit(1)
    
    # Read CHGCAR
    chgcar = Chgcar.from_file(str(chgcar_path))
    
    result = {
        'has_spin_density': False,
        'integrated_magnetization': None,
        'grid_shape': None,
        'structure_formula': str(chgcar.structure.composition.reduced_formula)
    }
    
    # Check if spin density is available
    if hasattr(chgcar, 'spin_up_data') and chgcar.spin_up_data is not None:
        result['has_spin_density'] = True
        
        # Get grid shape
        result['grid_shape'] = list(chgcar.data['total'].shape)
        
        # Calculate integrated magnetization from spin density
        # Spin density = spin_up - spin_down
        spin_density = chgcar.spin_up_data - chgcar.spin_down_data
        
        # Integrate over the grid
        volume = chgcar.structure.volume
        grid_volume = volume / spin_density.size
        integrated_mag = float(spin_density.sum() * grid_volume)
        
        result['integrated_magnetization'] = integrated_mag
    else:
        result['grid_shape'] = list(chgcar.data['total'].shape)
        print("Warning: No spin density data found in CHGCAR.", file=sys.stderr)
        print("This may be a non-spin-polarized calculation.", file=sys.stderr)
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Extract spin density from VASP CHGCAR file"
    )
    parser.add_argument(
        "vasp_dir",
        type=str,
        help="Path to directory containing VASP output files (CHGCAR)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to save spin density analysis as JSON (optional)"
    )
    
    args = parser.parse_args()
    
    vasp_path = Path(args.vasp_dir)
    if not vasp_path.exists():
        print(f"Error: Directory '{args.vasp_dir}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Extract spin density
    result = extract_spin_density(vasp_path)
    
    # Print summary
    print("=" * 60)
    print("SPIN DENSITY ANALYSIS")
    print("=" * 60)
    print(f"\nFormula: {result['structure_formula']}")
    print(f"Has spin density: {result['has_spin_density']}")
    
    if result['grid_shape']:
        print(f"Grid shape: {result['grid_shape']}")
    
    if result['integrated_magnetization'] is not None:
        print(f"Integrated magnetization: {result['integrated_magnetization']:.3f} μB")
    
    print("=" * 60)
    
    # Save to JSON if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nAnalysis saved to: {output_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
