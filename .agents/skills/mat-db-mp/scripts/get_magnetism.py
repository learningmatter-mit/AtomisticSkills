#!/usr/bin/env python3
"""
Query magnetic properties from Materials Project.

This script retrieves magnetic ordering, magnetic moments, and other magnetic properties
calculated from DFT.

Usage:
    # Get magnetism for specific material
    python get_magnetism.py --material_id mp-19770 --output fe_magnetism.json
    
    # Query ferromagnetic materials in a chemical system
    python get_magnetism.py --chemsys "Fe-O" --ordering FM --output feo_ferromagnetic.json
    
    # Filter by total magnetization range
    python get_magnetism.py --chemsys "Fe" --total_magnetization_min 2.0 --output fe_magnetic.json
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from mp_api.client import MPRester
from monty.json import MontyEncoder
from pymatgen.analysis.magnetism import Ordering


def get_magnetism(
    material_ids: Optional[List[str]] = None,
    ordering: Optional[str] = None,
    total_magnetization_min: Optional[float] = None,
    total_magnetization_max: Optional[float] = None,
    output_path: Optional[str] = None,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query magnetic properties from Materials Project.
    
    Args:
        material_ids: List of material IDs to query
        chemsys: Chemical system filter (e.g., "Fe", "Fe-O")
        ordering: Magnetic ordering type ("FM" for ferromagnetic, "AFM" for antiferromagnetic, "FiM" for ferrimagnetic, "NM" for non-magnetic)
        total_magnetization_min: Minimum total magnetization (μB)
        total_magnetization_max: Maximum total magnetization (μB)
        output_path: Optional path to save results as JSON
        api_key: Optional MP API key (defaults to MP_API_KEY environment variable)
    
    Returns:
        List of magnetism documents
    """
    api_key = api_key or os.environ.get('MP_API_KEY')
    if not api_key:
        raise ValueError("MP_API_KEY environment variable not set")
    
    print("Querying magnetism data from Materials Project...")
    if material_ids:
        print(f"  Material IDs: {material_ids}")
    if ordering:
        print(f"  Magnetic ordering: {ordering}")
    if total_magnetization_min or total_magnetization_max:
        print(f"  Total magnetization range: {total_magnetization_min or 'any'} - {total_magnetization_max or 'any'} μB")
    
    # Convert ordering string to enum if provided
    ordering_enum = None
    if ordering:
        ordering_enum = Ordering(ordering)
    
    # Query magnetism endpoint (use materials.magnetism)
    with MPRester(api_key) as mpr:
        try:
            # Build query parameters as tuples
            kwargs = {}
            if material_ids:
                kwargs['material_ids'] = material_ids
            if ordering_enum:
                kwargs['ordering'] = ordering_enum
            if total_magnetization_min is not None and total_magnetization_max is not None:
                kwargs['total_magnetization'] = (total_magnetization_min, total_magnetization_max)
            elif total_magnetization_min is not None:
                kwargs['total_magnetization'] = (total_magnetization_min, 1e6)
            elif total_magnetization_max is not None:
                kwargs['total_magnetization'] = (0, total_magnetization_max)
            
            docs = mpr.materials.magnetism.search(**kwargs)
        except Exception as e:
            print(f"Error querying magnetism endpoint: {e}")
            raise
    
    print(f"✓ Retrieved {len(docs)} magnetism documents")
    
    # Print summary
    if docs:
        print(f"\nSample results:")
        for i, doc in enumerate(docs[:5], 1):
            ordering = doc.ordering if hasattr(doc, 'ordering') else 'N/A'
            total_mag = doc.total_magnetization if hasattr(doc, 'total_magnetization') else 'N/A'
            print(f"  {i}. {doc.material_id}: {doc.formula_pretty}")
            print(f"      Ordering: {ordering}")
            print(f"      Total magnetization: {total_mag} μB")
    
    # Save results if output path specified
    if output_path:
        save_data(docs, output_path)
        print(f"✓ Saved magnetism data to {output_path}")
    
    return docs


def save_data(data: List[Any], output_path: str) -> None:
    """
    Save magnetism results to JSON file.
    
    Args:
        data: List of magnetism documents
        output_path: Path to save JSON file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to serializable format
    results_dict = {
        "num_results": len(data),
        "results": [doc.model_dump() for doc in data]
    }
    
    with open(output_path, 'w') as f:
        json.dump(results_dict, f, indent=2, cls=MontyEncoder)


def main():
    parser = argparse.ArgumentParser(
        description="Query magnetic properties from Materials Project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Query filters
    parser.add_argument(
        '--material_id',
        type=str,
        help='Chemical system filter (e.g., "Fe", "Fe-O")'
    )
    parser.add_argument(
        '--ordering',
        type=str,
        choices=['FM', 'AFM', 'FiM', 'NM'],
        help='Magnetic ordering type (FM=ferromagnetic, AFM=antiferromagnetic, FiM=ferrimagnetic, NM=non-magnetic)'
    )
    parser.add_argument(
        '--total_magnetization_min',
        type=float,
        help='Minimum total magnetization (μB)'
    )
    parser.add_argument(
        '--total_magnetization_max',
        type=float,
        help='Maximum total magnetization (μB)'
    )
    
    # Output
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output JSON file path'
    )
    parser.add_argument(
        '--api_key',
        type=str,
        help='Materials Project API key (defaults to MP_API_KEY env var)'
    )
    
    args = parser.parse_args()
    
    # Query magnetism data
    results = get_magnetism(
        material_ids=args.material_id,
        ordering=args.ordering,
        total_magnetization_min=args.total_magnetization_min,
        total_magnetization_max=args.total_magnetization_max,
        output_path=args.output,
        api_key=args.api_key
    )
    
    print(f"\n✓ Magnetism query complete")
    print(f"  Results: {len(results)} documents")
    print(f"  Output: {args.output}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
