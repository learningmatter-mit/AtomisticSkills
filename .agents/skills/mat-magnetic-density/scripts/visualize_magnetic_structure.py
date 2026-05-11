"""
Visualize magnetic structure with moment vectors.

This script creates a visualization of a structure with magnetic moment
vectors overlaid on each atom, color-coded by moment magnitude.

Usage:
    python visualize_magnetic_structure.py structure.cif moments.json --output image.png

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, matplotlib, numpy
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List
import sys


def visualize_magnetic_structure(
    structure_path: Path,
    moments_data: Dict[str, Any],
    output_path: Path
) -> None:
    """
    Create a visualization of the magnetic structure.
    
    Args:
        structure_path: Path to structure file (CIF, POSCAR, etc.)
        moments_data: Dictionary containing magnetic moment analysis
        output_path: Path to save the output image
    """
    try:
        from pymatgen.core import Structure
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        print(f"Error: Required package not found: {e}", file=sys.stderr)
        print("Please ensure pymatgen and matplotlib are installed in base-agent.",
              file=sys.stderr)
        sys.exit(1)
    
    # Load structure
    structure = Structure.from_file(str(structure_path))
    
    # Get site moments
    site_moments = moments_data.get('site_moments', [])
    
    if not site_moments:
        print("Error: No site moments found in the analysis data", file=sys.stderr)
        sys.exit(1)
    
    if len(site_moments) != len(structure):
        print(f"Warning: Number of moments ({len(site_moments)}) does not match "
              f"number of sites ({len(structure)})", file=sys.stderr)
    
    # Create figure
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Get fractional coordinates
    coords = structure.frac_coords
    
    # Plot atoms
    colors = []
    sizes = []
    
    for i, (site, moment) in enumerate(zip(structure, site_moments)):
        # Color by moment magnitude
        colors.append(moment)
        # Size by absolute moment
        sizes.append(abs(moment) * 100 + 50)
    
    # Scatter plot of atoms
    scatter = ax.scatter(
        coords[:, 0], coords[:, 1], coords[:, 2],
        c=colors,
        s=sizes,
        cmap='RdBu',
        alpha=0.7,
        edgecolors='black',
        linewidths=1
    )
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax, pad=0.1, shrink=0.8)
    cbar.set_label('Magnetic Moment (μB)', rotation=270, labelpad=20)
    
    # Add moment vectors
    max_moment = max(abs(m) for m in site_moments)
    scale = 0.15  # Scale factor for arrow length
    
    for i, (coord, moment) in enumerate(zip(coords, site_moments)):
        if abs(moment) > 0.01:  # Only show non-zero moments
            # Arrow pointing up for positive, down for negative
            direction = 1 if moment > 0 else -1
            length = (abs(moment) / max_moment) * scale
            
            ax.quiver(
                coord[0], coord[1], coord[2],
                0, 0, direction * length,
                color='red' if moment > 0 else 'blue',
                arrow_length_ratio=0.3,
                linewidth=2,
                alpha=0.8
            )
    
    # Set labels and title
    ax.set_xlabel('a (fractional)')
    ax.set_ylabel('b (fractional)')
    ax.set_zlabel('c (fractional)')
    
    formula = moments_data.get('structure_formula', 'Unknown')
    ordering = moments_data.get('magnetic_ordering', 'unknown')
    total_mag = moments_data.get('total_magnetization', 0)
    
    ax.set_title(
        f"{formula} - {ordering.capitalize()}\n"
        f"Total magnetization: {total_mag:.2f} μB",
        fontsize=14,
        fontweight='bold'
    )
    
    # Set aspect ratio
    ax.set_box_aspect([1, 1, 1])
    
    # Save figure
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Magnetic structure visualization saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Visualize magnetic structure with moment vectors"
    )
    parser.add_argument(
        "structure_file",
        type=str,
        help="Path to structure file (CIF, POSCAR, etc.)"
    )
    parser.add_argument(
        "moments_file",
        type=str,
        help="Path to JSON file containing magnetic moment analysis"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="magnetic_structure.png",
        help="Path to save output image (default: magnetic_structure.png)"
    )
    
    args = parser.parse_args()
    
    # Check input files
    structure_path = Path(args.structure_file)
    moments_path = Path(args.moments_file)
    
    if not structure_path.exists():
        print(f"Error: Structure file '{args.structure_file}' not found", 
              file=sys.stderr)
        sys.exit(1)
    
    if not moments_path.exists():
        print(f"Error: Moments file '{args.moments_file}' not found", 
              file=sys.stderr)
        sys.exit(1)
    
    # Load moments data
    with open(moments_path, 'r') as f:
        moments_data = json.load(f)
    
    # Create visualization
    output_path = Path(args.output)
    visualize_magnetic_structure(structure_path, moments_data, output_path)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
