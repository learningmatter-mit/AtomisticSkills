#!/usr/bin/env python3
"""
Retrieve pre-computed phase diagrams from Materials Project.

This script retrieves phase diagrams computed by Materials Project for a given
chemical system. Phase diagrams are essential for understanding thermodynamic
stability and competing phases.

Usage:
    # Basic retrieval
    python get_phase_diagram.py --chemsys "Li-O" --output li_o_pd.json
    
    # With different thermo type (R2SCAN)
    python get_phase_diagram.py --chemsys "Li-Fe-P-O" --thermo_type "R2SCAN" --output lifepo4_pd.json
    
    # Generate plot
    python get_phase_diagram.py --chemsys "Li-O" --output li_o_pd.json --plot li_o_pd.png

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
from typing import Optional

from mp_api.client import MPRester
from pymatgen.analysis.phase_diagram import PhaseDiagram, PDPlotter


def get_phase_diagram(
    chemsys: str,
    thermo_type: str = "GGA_GGA+U",
    api_key: Optional[str] = None
) -> PhaseDiagram:
    """
    Retrieve pre-computed phase diagram from Materials Project.
    
    Args:
        chemsys: Chemical system (e.g., "Li-O", "Li-Fe-P-O")
        thermo_type: Thermodynamic calculation type
            Options: "GGA_GGA+U" (default), "R2SCAN", "GGA"
        api_key: MP API key (defaults to MP_API_KEY environment variable)
        
    Returns:
        PhaseDiagram: Pymatgen phase diagram object
    """
    # Get API key
    mp_key = api_key or os.environ.get('MP_API_KEY')
    if not mp_key:
        raise ValueError("Materials Project API key not found. Set MP_API_KEY environment variable.")
    
    print(f"Retrieving phase diagram for {chemsys}...")
    print(f"  Thermo type: {thermo_type}")
    
    with MPRester(mp_key) as mpr:
        try:
            pd = mpr.materials.thermo.get_phase_diagram_from_chemsys(
                chemsys=chemsys,
                thermo_type=thermo_type
            )
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve phase diagram: {str(e)}")
    
    if pd is None:
        raise ValueError(f"No phase diagram found for {chemsys} with thermo_type={thermo_type}")
    
    print(f"✓ Successfully retrieved phase diagram with {len(pd.all_entries)} entries")
    
    return pd


def save_phase_diagram(pd: PhaseDiagram, output_path: str) -> None:
    """
    Save phase diagram to JSON file.
    
    Args:
        pd: Phase diagram object
        output_path: Output file path (.json)
    """
    from monty.json import MontyEncoder
    output_path = Path(output_path)
    
    # Serialize phase diagram using MontyEncoder to handle complex objects
    pd_dict = pd.as_dict()
    
    with open(output_path, 'w') as f:
        json.dump(pd_dict, f, indent=2, cls=MontyEncoder)
    
    print(f"✓ Saved phase diagram to {output_path}")


def plot_phase_diagram(pd: PhaseDiagram, plot_path: str) -> None:
    """
    Generate and save phase diagram plot.
    
    Args:
        pd: Phase diagram object
        plot_path: Output plot file path (.png, .pdf, .svg)
    """

    plot_path = Path(plot_path)
    
    print(f"Generating phase diagram plot...")
    
    plotter = PDPlotter(pd, show_unstable=True)
    fig = plotter.get_plot()  # Returns a Plotly Figure
    
    # PDPlotter uses Plotly, not matplotlib
    fig.write_image(str(plot_path), width=1200, height=800)
    print(f"✓ Saved plot to {plot_path}")



def main():
    parser = argparse.ArgumentParser(
        description="Retrieve pre-computed phase diagrams from Materials Project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Li-O binary phase diagram
    python get_phase_diagram.py --chemsys "Li-O" --output li_o_pd.json
    
    # Li-Fe-P-O quaternary with R2SCAN functional
    python get_phase_diagram.py --chemsys "Li-Fe-P-O" --thermo_type "R2SCAN" --output lifepo4_pd.json
    
    # Generate plot
    python get_phase_diagram.py --chemsys "Li-O" --output li_o_pd.json --plot li_o_pd.png
        """
    )
    
    parser.add_argument(
        "--chemsys",
        type=str,
        required=True,
        help="Chemical system (e.g., 'Li-O', 'Li-Fe-P-O')"
    )
    parser.add_argument(
        "--thermo_type",
        type=str,
        default="GGA_GGA+U",
        choices=["GGA_GGA+U", "R2SCAN", "GGA"],
        help="Thermodynamic calculation type (default: GGA_GGA+U)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--plot",
        type=str,
        help="Optional: Generate and save phase diagram plot to this path"
    )
    parser.add_argument(
        "--api_key",
        type=str,
        help="Materials Project API key (defaults to MP_API_KEY env var)"
    )
    
    args = parser.parse_args()
    
    try:
        # Retrieve phase diagram
        pd = get_phase_diagram(
            chemsys=args.chemsys,
            thermo_type=args.thermo_type,
            api_key=args.api_key
        )
        
        # Save to JSON
        save_phase_diagram(pd, args.output)
        
        # Optionally plot
        if args.plot:
            plot_phase_diagram(pd, args.plot)
        
        print(f"\n✓ Phase diagram retrieval complete")
        
        # Print summary info
        print(f"\nPhase Diagram Summary:")
        print(f"  Chemical system: {args.chemsys}")
        print(f"  Number of entries: {len(pd.all_entries)}")
        print(f"  Stable entries: {len(pd.stable_entries)}")
        print(f"  Elements: {', '.join([str(el) for el in pd.elements])}")
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
