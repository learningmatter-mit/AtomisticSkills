#!/usr/bin/env python3
"""
Retrieve pre-computed electronic structure data (band structure and DOS) from Materials Project.

This script provides an alternative to running DFT calculations - retrieve existing MP data
for validation, comparison, or quick screening.

Usage:
    # Retrieve band structure for Silicon
    python get_mp_electronic_structure.py --material_id mp-149 --output si_electronic.json
    
    # Retrieve with plots
    python get_mp_electronic_structure.py --material_id mp-149 --output si_electronic.json --plot

Requirements:
    - Conda environment: base-agent
    - MP_API_KEY environment variable must be set
    - Required packages: mp-api, pymatgen, matplotlib
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from mp_api.client import MPRester
from pymatgen.electronic_structure.plotter import BSPlotter, DosPlotter


def get_mp_electronic_structure(
    material_id: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve electronic structure data from Materials Project.
    
    Args:
        material_id: Materials Project ID (e.g., "mp-149")
        api_key: MP API key (defaults to MP_API_KEY environment variable)
        
    Returns:
        Dict containing band structure, DOS, and metadata
    """
    # Get API key
    mp_key = api_key or os.environ.get('MP_API_KEY')
    if not mp_key:
        raise ValueError("Materials Project API key not found. Set MP_API_KEY environment variable.")
    
    print(f"Retrieving electronic structure data for {material_id}...")
    
    with MPRester(mp_key) as mpr:
        try:
            # Get band structure using BandStructureRester
            bs = mpr.materials.electronic_structure_bandstructure.get_bandstructure_from_material_id(
                material_id=material_id,
                line_mode=True
            )
            
            # Get DOS using DosRester
            dos = mpr.materials.electronic_structure_dos.get_dos_from_material_id(
                material_id=material_id
            )
            
            # Get summary info for metadata
            summary = mpr.materials.summary.search(material_ids=[material_id])[0]
            
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve electronic structure: {str(e)}")
    
    if bs is None:
        raise ValueError(f"No band structure found for {material_id}")
    
    # Extract key properties
    result = {
        "material_id": material_id,
        "formula": summary.formula_pretty,
        "band_gap": bs.get_band_gap()["energy"] if not bs.is_metal() else 0.0,
        "is_metal": bs.is_metal(),
        "is_gap_direct": bs.get_band_gap()["direct"] if not bs.is_metal() else None,
        "band_structure": bs.as_dict(),
        "dos": dos.as_dict() if dos else None,
        "efermi": bs.efermi,
    }
    
    print(f"✓ Successfully retrieved electronic structure")
    if result["is_metal"]:
        print(f"  Material: {result['formula']} (metallic)")
    else:
        gap_type = "direct" if result["is_gap_direct"] else "indirect"
        print(f"  Material: {result['formula']}")
        print(f"  Band gap: {result['band_gap']:.3f} eV ({gap_type})")
    
    return result, bs, dos


def save_electronic_structure(data: Dict, output_path: str) -> None:
    """
    Save electronic structure data to JSON file.
    
    Args:
        data: Electronic structure dictionary
        output_path: Output file path (.json)
    """
    from monty.json import MontyEncoder
    output_path = Path(output_path)
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, cls=MontyEncoder)
    
    print(f"✓ Saved electronic structure data to {output_path}")


def plot_band_structure(bs, output_dir: Path, formula: str) -> None:
    """
    Generate band structure plot.
    
    Args:
        bs: BandStructure object or dict
        output_dir: Output directory for plot
        formula: Material formula for title
    """
    import matplotlib.pyplot as plt
    
    # BS is already a pymatgen object from the API
    print(f"Generating band structure plot...")
    
    plotter = BSPlotter(bs)
    plotter.get_plot(ylim=(-10, 10))
    
    plot_path = output_dir / "band_structure.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close('all')
    print(f"✓ Saved band structure plot to {plot_path}")


def plot_dos(dos, output_dir: Path, formula: str) -> None:
    """
    Generate DOS plot.
    
    Args:
        dos: CompleteDos object or dict
        output_dir: Output directory for plot
        formula: Material formula for title
    """
    import matplotlib.pyplot as plt
    
    if dos is None:
        print("Warning: DOS data not available, skipping DOS plot")
        return
    
    # Convert dict to CompleteDos if needed
    if isinstance(dos, dict):
        dos = CompleteDos.from_dict(dos)
    
    print(f"Generating DOS plot...")
    
    plotter = DosPlotter()
    plotter.add_dos("Total DOS", dos)
    plotter.get_plot(xlim=(-10, 10))
    
    plot_path = output_dir / "dos.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close('all')
    print(f"✓ Saved DOS plot to {plot_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve pre-computed electronic structure data from Materials Project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Retrieve for Silicon
    python get_mp_electronic_structure.py --material_id mp-149 --output si_electronic.json
    
    # With plots
    python get_mp_electronic_structure.py --material_id mp-149 --output si_electronic.json --plot
        """
    )
    
    parser.add_argument(
        "--material_id",
        type=str,
        required=True,
        help="Materials Project ID (e.g., 'mp-149')"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate band structure and DOS plots"
    )
    parser.add_argument(
        "--api_key",
        type=str,
        help="Materials Project API key (defaults to MP_API_KEY env var)"
    )
    
    args = parser.parse_args()
    
    try:
        # Retrieve electronic structure
        data, bs, dos = get_mp_electronic_structure(
            material_id=args.material_id,
            api_key=args.api_key
        )
        
        # Save to JSON
        save_electronic_structure(data, args.output)
        
        # Optionally plot
        if args.plot:
            output_dir = Path(args.output).parent
            plot_band_structure(bs, output_dir, data["formula"])
            plot_dos(dos, output_dir, data["formula"])
        
        print(f"\n✓ Electronic structure retrieval complete")
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
