#!/usr/bin/env python3
"""
Retrieve pre-computed phonon data from Materials Project.

Use for validation and benchmarking of MLIP phonon calculations against DFT reference data.

Usage:
    # Retrieve phonon data for Silicon
    python get_mp_phonon.py --material_id mp-149 --phonon_method dfpt --output si_phonon_mp.json
    
    # Retrieve with plots
    python get_mp_phonon.py --material_id mp-149 --phonon_method dfpt --output si_phonon_mp.json --plot

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
from pymatgen.phonon.plotter import PhononBSPlotter, PhononDosPlotter


def get_mp_phonon(
    material_id: str,
    phonon_method: str = "dfpt",
    include_force_constants: bool = False,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve phonon data from Materials Project.
    
    Args:
        material_id: Materials Project ID (e.g., "mp-149")
        phonon_method: Phonon calculation method ("dfpt", "phonopy", "pheasy")
        include_force_constants: Whether to retrieve force constants
        api_key: MP API key (defaults to MP_API_KEY environment variable)
        
    Returns:
        Dict containing phonon band structure, DOS, and metadata
    """
    # Get API key
    mp_key = api_key or os.environ.get('MP_API_KEY')
    if not mp_key:
        raise ValueError("Materials Project API key not found. Set MP_API_KEY environment variable.")
    
    print(f"Retrieving phonon data for {material_id}...")
    print(f"  Phonon method: {phonon_method}")
    
    with MPRester(mp_key) as mpr:
        try:
            # Get phonon band structure using materials.phonon
            phonon_bs = mpr.materials.phonon.get_bandstructure_from_material_id(
                material_id=material_id,
                phonon_method=phonon_method
            )
            
            # Get phonon DOS
            phonon_dos = mpr.materials.phonon.get_dos_from_material_id(
                material_id=material_id,
                phonon_method=phonon_method
            )
            
            # Optionally get force constants
            force_constants = None
            if include_force_constants:
                try:
                    force_constants = mpr.materials.phonon.get_data_by_id(
                        document_id=material_id,
                        fields=["ph_force_constants"]
                    )
                except:
                    print("  Warning: Force constants not available")
            
            # Get summary info for metadata
            summary = mpr.materials.summary.search(material_ids=[material_id])[0]
            
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve phonon data: {str(e)}")
    
    if phonon_bs is None:
        raise ValueError(f"No phonon band structure found for {material_id} (method: {phonon_method})")
    
    # Extract key properties
    result = {
        "material_id": material_id,
        "formula": summary.formula_pretty,
        "phonon_method": phonon_method,
        "phonon_bandstructure": phonon_bs,  # MontyEncoder handles pymatgen objects
        "phonon_dos": phonon_dos,  # MontyEncoder handles pymatgen objects
        "force_constants": force_constants,
        "source": "Materials Project",
    }
    
    print(f"✓ Successfully retrieved phonon data")
    print(f"  Material: {result['formula']}")
    print(f"  Phonon method: {phonon_method}")
    
    return result, phonon_bs, phonon_dos


def save_phonon_data(data: Dict, output_path: str) -> None:
    """
    Save phonon data to JSON file.
    
    Args:
        data: Phonon data dictionary
        output_path: Output file path (.json)
    """
    from monty.json import MontyEncoder
    output_path = Path(output_path)
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, cls=MontyEncoder)
    
    print(f"✓ Saved phonon data to {output_path}")


def plot_phonon_bandstructure(phonon_bs, output_dir: Path, formula: str) -> None:
    """
    Generate phonon band structure plot.
    
    Args:
        phonon_bs: PhononBandStructure object
        output_dir: Output directory for plot
        formula: Material formula for title
    """
    import matplotlib.pyplot as plt
    
    print(f"Generating phonon band structure plot...")
    
    plotter = PhononBSPlotter(phonon_bs)
    plotter.get_plot(ylim=(0, None))
    
    plot_path = output_dir / "phonon_bandstructure.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close('all')
    print(f"✓ Saved phonon band structure plot to {plot_path}")


def plot_phonon_dos(phonon_dos, output_dir: Path, formula: str) -> None:
    """
    Generate phonon DOS plot.
    
    Args:
        phonon_dos: PhononDos object
        output_dir: Output directory for plot
        formula: Material formula for title
    """
    import matplotlib.pyplot as plt
    
    if phonon_dos is None:
        print("Warning: Phonon DOS data not available, skipping DOS plot")
        return
    
    print(f"Generating phonon DOS plot...")
    
    plotter = PhononDosPlotter()
    plotter.add_dos("Total DOS", phonon_dos)
    plotter.get_plot()
    
    plot_path = output_dir / "phonon_dos.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close('all')
    print(f"✓ Saved phonon DOS plot to {plot_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve pre-computed phonon data from Materials Project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Retrieve DFPT phonon data for Silicon
    python get_mp_phonon.py --material_id mp-149 --phonon_method dfpt --output si_phonon_mp.json
    
    # With plots
    python get_mp_phonon.py --material_id mp-149 --phonon_method dfpt --output si_phonon_mp.json --plot
    
    # Include force constants
    python get_mp_phonon.py --material_id mp-149 --phonon_method dfpt --output si_phonon_mp.json --force_constants
        """
    )
    
    parser.add_argument(
        "--material_id",
        type=str,
        required=True,
        help="Materials Project ID (e.g., 'mp-149')"
    )
    parser.add_argument(
        "--phonon_method",
        type=str,
        default="dfpt",
        choices=["dfpt", "phonopy", "pheasy"],
        help="Phonon calculation method (default: dfpt)"
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
        help="Generate phonon band structure and DOS plots"
    )
    parser.add_argument(
        "--force_constants",
        action="store_true",
        help="Include force constants in output"
    )
    parser.add_argument(
        "--api_key",
        type=str,
        help="Materials Project API key (defaults to MP_API_KEY env var)"
    )
    
    args = parser.parse_args()
    
    try:
        # Retrieve phonon data
        data, phonon_bs, phonon_dos = get_mp_phonon(
            material_id=args.material_id,
            phonon_method=args.phonon_method,
            include_force_constants=args.force_constants,
            api_key=args.api_key
        )
        
        # Save to JSON
        save_phonon_data(data, args.output)
        
        # Optionally plot
        if args.plot:
            output_dir = Path(args.output).parent
            plot_phonon_bandstructure(phonon_bs, output_dir, data["formula"])
            plot_phonon_dos(phonon_dos, output_dir, data["formula"])
        
        print(f"\n✓ Phonon data retrieval complete")
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
