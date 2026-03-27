#!/usr/bin/env python3
"""
Query elastic properties from Materials Project.

This script retrieves elastic tensor data, bulk modulus, shear modulus, and other
elastic properties calculated from DFT.

Usage:
    # Get elasticity for specific material
    python get_elasticity.py --material_id mp-149 --output si_elasticity.json
    
    # Query all elastic data for a chemical system
    python get_elasticity.py --chemsys "Si" --output si_all_elasticity.json
    
    # Filter by bulk modulus range
    python get_elasticity.py --chemsys "Fe-O" --bulk_modulus_min 100 --bulk_modulus_max 300 --output feo_elastic.json
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from mp_api.client import MPRester
from monty.json import MontyEncoder


def get_elasticity(
    material_ids: Optional[List[str]] = None,
    bulk_modulus_min: Optional[float] = None,
    bulk_modulus_max: Optional[float] = None,
    shear_modulus_min: Optional[float] = None,
    shear_modulus_max: Optional[float] = None,
    output_path: Optional[str] = None,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query elastic properties from Materials Project.
    
    Args:
        material_ids: List of material IDs to query
        chemsys: Chemical system filter (e.g., "Si", "Fe-O")
        bulk_modulus_min: Minimum bulk modulus (GPa)
        bulk_modulus_max: Maximum bulk modulus (GPa)
        shear_modulus_min: Minimum shear modulus (GPa)
        shear_modulus_max: Maximum shear modulus (GPa)
        output_path: Optional path to save results as JSON
        api_key: Optional MP API key (defaults to MP_API_KEY environment variable)
    
    Returns:
        List of elasticity documents
    """
    api_key = api_key or os.environ.get('MP_API_KEY')
    if not api_key:
        raise ValueError("MP_API_KEY environment variable not set")
    
    print("Querying elasticity data from Materials Project...")
    if material_ids:
        print(f"  Material IDs: {material_ids}")
    if bulk_modulus_min or bulk_modulus_max:
        print(f"  Bulk modulus range: {bulk_modulus_min or 'any'} - {bulk_modulus_max or 'any'} GPa")
    if shear_modulus_min or shear_modulus_max:
        print(f"  Shear modulus range: {shear_modulus_min or 'any'} - {shear_modulus_max or 'any'} GPa")
    
    # Query elasticity endpoint (use materials.elasticity)
    with MPRester(api_key) as mpr:
        try:
            # Build query parameters as tuples
            kwargs = {}
            if material_ids:
                kwargs['material_ids'] = material_ids
            if bulk_modulus_min is not None and bulk_modulus_max is not None:
                kwargs['k_vrh'] = (bulk_modulus_min, bulk_modulus_max)
            elif bulk_modulus_min is not None:
                kwargs['k_vrh'] = (bulk_modulus_min, 1e6)  # Large max
            elif bulk_modulus_max is not None:
                kwargs['k_vrh'] = (0, bulk_modulus_max)
                
            if shear_modulus_min is not None and shear_modulus_max is not None:
                kwargs['g_vrh'] = (shear_modulus_min, shear_modulus_max)
            elif shear_modulus_min is not None:
                kwargs['g_vrh'] = (shear_modulus_min, 1e6)
            elif shear_modulus_max is not None:
                kwargs['g_vrh'] = (0, shear_modulus_max)
            
            docs = mpr.materials.elasticity.search(**kwargs)
        except Exception as e:
            print(f"Error querying elasticity endpoint: {e}")
            raise
    
    print(f"✓ Retrieved {len(docs)} elasticity documents")
    
    # Print summary
    if docs:
        print(f"\nSample results:")
        for i, doc in enumerate(docs[:5], 1):
            bulk_dict = doc.bulk_modulus if hasattr(doc, 'bulk_modulus') else None
            shear_dict = doc.shear_modulus if hasattr(doc, 'shear_modulus') else None
            # Extract VRH values from nested dicts
            bulk_vrh = bulk_dict.vrh if bulk_dict and hasattr(bulk_dict, 'vrh') else 'N/A'
            shear_vrh = shear_dict.vrh if shear_dict and hasattr(shear_dict, 'vrh') else 'N/A'
            print(f"  {i}. {doc.material_id}: {doc.formula_pretty}")
            print(f"      Bulk modulus (VRH): {bulk_vrh} GPa")
            print(f"      Shear modulus (VRH): {shear_vrh} GPa")
    
    # Save results if output path specified
    if output_path:
        save_data(docs, output_path)
        print(f"✓ Saved elasticity data to {output_path}")
    
    return docs


def save_data(data: List[Any], output_path: str) -> None:
    """
    Save elasticity results to JSON file.
    
    Args:
        data: List of elasticity documents
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
        description="Query elastic properties from Materials Project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Query filters
    parser.add_argument(
        '--material_id',
        type=str,
        help='Chemical system filter (e.g., "Si", "Fe-O")'
    )
    parser.add_argument(
        '--bulk_modulus_min',
        type=float,
        help='Minimum bulk modulus (GPa)'
    )
    parser.add_argument(
        '--bulk_modulus_max',
        type=float,
        help='Maximum bulk modulus (GPa)'
    )
    parser.add_argument(
        '--shear_modulus_min',
        type=float,
        help='Minimum shear modulus (GPa)'
    )
    parser.add_argument(
        '--shear_modulus_max',
        type=float,
        help='Maximum shear modulus (GPa)'
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
    
    # Query elasticity data
    results = get_elasticity(
        material_ids=args.material_id,
        bulk_modulus_min=args.bulk_modulus_min,
        bulk_modulus_max=args.bulk_modulus_max,
        shear_modulus_min=args.shear_modulus_min,
        shear_modulus_max=args.shear_modulus_max,
        output_path=args.output,
        api_key=args.api_key
    )
    
    print(f"\n✓ Elasticity query complete")
    print(f"  Results: {len(results)} documents")
    print(f"  Output: {args.output}")


if __name__ == "__main__":
    main()
