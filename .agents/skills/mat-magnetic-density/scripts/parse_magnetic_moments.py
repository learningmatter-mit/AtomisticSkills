"""
Parse magnetic moments from atomate2 VASP calculation results.

This script extracts site-resolved magnetic moments, total magnetization,
and analyzes the magnetic ordering pattern from DFT calculation results.

Usage:
    python parse_magnetic_moments.py results.json --output analysis.json

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Any
import sys


def parse_magnetic_moments(results_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and analyze magnetic moments from atomate2 results.
    
    Args:
        results_data: Dictionary containing atomate2 calculation results
        
    Returns:
        Dictionary containing magnetic analysis with keys:
        - 'total_magnetization': Total magnetic moment (μB)
        - 'site_moments': List of magnetic moments per site
        - 'magnetic_ordering': Classification of ordering type
        - 'structure': Structure information
    """
    analysis = {
        'total_magnetization': None,
        'site_moments': [],
        'species': [],
        'magnetic_ordering': 'unknown',
        'structure_formula': None
    }
    
    # Extract data from results
    if 'data' in results_data:
        data = results_data['data']
        
        # Handle both list and single structure cases
        if isinstance(data, list) and len(data) > 0:
            calc_data = data[0]
        else:
            calc_data = data
            
        # Extract structure information
        if 'structure' in calc_data:
            structure_data = calc_data['structure']
            if 'sites' in structure_data:
                for site in structure_data['sites']:
                    if 'species' in site:
                        species_list = site['species']
                        if species_list:
                            element = species_list[0].get('element', 'Unknown')
                            analysis['species'].append(element)
            
            # Try to get formula
            if 'composition' in structure_data:
                analysis['structure_formula'] = structure_data.get('formula', 'Unknown')
        
        # Extract magnetic moments - check various possible locations
        if 'magmom' in calc_data:
            site_moments = calc_data['magmom']
            if isinstance(site_moments, (list, tuple)):
                analysis['site_moments'] = [float(m) for m in site_moments]
        elif 'output' in calc_data and 'magnetic_moments' in calc_data['output']:
            site_moments = calc_data['output']['magnetic_moments']
            if isinstance(site_moments, (list, tuple)):
                analysis['site_moments'] = [float(m) for m in site_moments]
        
        # Calculate total magnetization if site moments exist
        if analysis['site_moments']:
            analysis['total_magnetization'] = sum(analysis['site_moments'])
            
            # Classify magnetic ordering
            analysis['magnetic_ordering'] = classify_magnetic_ordering(
                analysis['site_moments']
            )
    
    return analysis


def classify_magnetic_ordering(moments: List[float], threshold: float = 0.1) -> str:
    """
    Classify the type of magnetic ordering based on site moments.
    
    Args:
        moments: List of magnetic moments per site
        threshold: Threshold below which moments are considered zero (μB)
        
    Returns:
        String describing the magnetic ordering type
    """
    if not moments:
        return 'unknown'
    
    # Count positive, negative, and near-zero moments
    positive = sum(1 for m in moments if m > threshold)
    negative = sum(1 for m in moments if m < -threshold)
    zero = sum(1 for m in moments if abs(m) <= threshold)
    
    total_mag = abs(sum(moments))
    
    if zero == len(moments):
        return 'non-magnetic'
    elif negative == 0 and positive > 0:
        return 'ferromagnetic'
    elif positive > 0 and negative > 0:
        if total_mag < threshold:
            return 'antiferromagnetic'
        else:
            return 'ferrimagnetic'
    else:
        return 'unknown'


def format_output(analysis: Dict[str, Any]) -> str:
    """
    Format the analysis results as a human-readable string.
    
    Args:
        analysis: Analysis results dictionary
        
    Returns:
        Formatted string representation
    """
    lines = []
    lines.append("=" * 60)
    lines.append("MAGNETIC MOMENT ANALYSIS")
    lines.append("=" * 60)
    
    if analysis['structure_formula']:
        lines.append(f"\nFormula: {analysis['structure_formula']}")
    
    if analysis['total_magnetization'] is not None:
        lines.append(f"\nTotal Magnetization: {analysis['total_magnetization']:.3f} μB")
    
    lines.append(f"Magnetic Ordering: {analysis['magnetic_ordering']}")
    
    if analysis['site_moments']:
        lines.append(f"\nNumber of sites: {len(analysis['site_moments'])}")
        lines.append("\nSite-resolved magnetic moments (μB):")
        lines.append("-" * 40)
        lines.append(f"{'Site':<8} {'Element':<10} {'Moment (μB)':<15}")
        lines.append("-" * 40)
        
        for i, (moment, species) in enumerate(zip(
            analysis['site_moments'], 
            analysis['species'] if analysis['species'] else ['?'] * len(analysis['site_moments'])
        ), 1):
            lines.append(f"{i:<8} {species:<10} {moment:>10.3f}")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Parse magnetic moments from atomate2 VASP calculation results"
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to JSON file containing atomate2 results"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to save analysis results as JSON (optional)"
    )
    
    args = parser.parse_args()
    
    # Load input data
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)
    
    with open(input_path, 'r') as f:
        results_data = json.load(f)
    
    # Parse magnetic moments
    analysis = parse_magnetic_moments(results_data)
    
    # Print formatted output
    print(format_output(analysis))
    
    # Save to JSON if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"\nAnalysis saved to: {output_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
