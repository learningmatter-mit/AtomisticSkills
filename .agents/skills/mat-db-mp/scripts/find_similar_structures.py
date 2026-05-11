#!/usr/bin/env python3
"""
Find materials structurally similar to a query structure using Materials Project API.

This script uses MP's crystal structure similarity endpoint to find materials with similar
crystal structures based on CrystalNN fingerprinting.

## Similarity Search Mechanism

Materials Project employs a sophisticated multi-step process to quantify crystal structure similarity:

### 1. Near-Neighbor Detection (CrystalNN)
The CrystalNN algorithm (Crystal Nearest Neighbor) identifies the near neighbors of all atomic 
sites in both crystal structures being compared. This is a crucial first step that determines 
the local coordination environment around each atom.

**Reference**: Pan, H. et al. (2019). Benchmarking Coordination Number Prediction Algorithms on 
Inorganic Crystal Structures. Inorg. Chem. 2019, 60, 1590-1603. DOI: 10.1039/C9RA07755C

### 2. Site Fingerprint Generation
For each atomic site, a "site fingerprint" is computed using the CrystalNNFingerprint from 
matminer. This fingerprint is a high-dimensional vector (61 dimensions) that encodes detailed 
information about the local coordination environment:

- Coordination numbers and geometries
- Bond distances and angles  
- Order parameters (e.g., tetrahedral, octahedral)
- Bonding environment descriptors

The fingerprint uses the "ops" (order parameters) preset, which provides a comprehensive 
description of local structural motifs.

### 3. Structure Fingerprint Generation  
To characterize the entire structure (not just individual sites), statistics are computed 
across all site fingerprints in the structure:

- **Mean**: Average coordination environment across all sites
- **Maximum**: Most extreme coordination characteristics

This produces a composite "structure fingerprint" that summarizes the entire crystal's 
local bonding patterns. The Materials Project uses a structure fingerprint with multiple 
statistical moments computed from the site-level descriptors.

### 4. Similarity Scoring
Finally, structures are compared by computing the Euclidean distance between their structure 
fingerprints in this high-dimensional feature space:

    distance = ||fingerprint_A - fingerprint_B||

The dissimilarity score is then computed as:

    dissimilarity = 100 * (1 - exp(-distance))

Where:
- dissimilarity = 0%  → Identical structures
- dissimilarity = 100% → Maximally different structures

The MP API performs vector search in this fingerprint space to efficiently find the 
top-N most similar structures (lowest distances) to a query structure.

### Vector Search Implementation
When you query `find_similar`, Materials Project:

1. Computes the fingerprint of your query structure (or retrieves pre-computed for MP IDs)
2. Performs vector similarity search against all structures in the database
3. Returns the top matches ranked by increasing dissimilarity

This approach allows for efficient similarity searches across hundreds of thousands of 
materials in the MP database.

## Usage Examples

Find structures similar to a material ID:
    python find_similar_structures.py --material_id mp-19017 --top 10 --output similar_lifepo4.json
    
Find structures similar to a custom structure file:
    python find_similar_structures.py --structure LiFePO4.cif --top 20 --output similar.json
    
Filter results by chemical system:
    python find_similar_structures.py --material_id mp-149 --top 20 --chemsys "Si-O" --output similar_si_o.json
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from mp_api.client import MPRester
from monty.json import MontyEncoder
from pymatgen.core import Structure


def find_similar_structures(
    structure_or_mpid: str,
    top: int = 50,
    chemsys: Optional[str] = None,
    output_path: Optional[str] = None,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Find materials structurally similar to a query structure.
    
    Args:
        structure_or_mpid: Either a material ID (e.g., "mp-149") or path to structure file
        top: Number of most similar structures to return (default: 50)
        chemsys: Optional chemical system filter to apply after retrieval (e.g., "Si-O")
        output_path: Optional path to save results as JSON
        api_key: Optional MP API key (defaults to MP_API_KEY environment variable)
    
    Returns:
        List of similar structure entries with similarity scores
    """
    api_key = api_key or os.environ.get('MP_API_KEY')
    if not api_key:
        raise ValueError("MP_API_KEY environment variable not set")
    
    # Determine if input is a material ID or structure file
    is_mpid = structure_or_mpid.startswith('mp-')
    
    if not is_mpid:
        # Load structure from file
        structure = Structure.from_file(structure_or_mpid)
        print(f"Loaded structure from {structure_or_mpid}")
        print(f"  Formula: {structure.composition.reduced_formula}")
        print(f"  Space group: {structure.get_space_group_info()[1]}")
        query_input = structure
    else:
        query_input = structure_or_mpid
        print(f"Searching for structures similar to {structure_or_mpid}")
    
    print(f"  Requesting top {top} similar structures...")
    if chemsys:
        print(f"  Will filter results by chemical system: {chemsys}")
    
    # Query similarity endpoint
    with MPRester(api_key) as mpr:
        try:
            # Find similar structures using the new API
            results = mpr.materials.similarity.find_similar(
                structure_or_mpid=query_input,
                top=top
            )
            
        except Exception as e:
            print(f"Error querying similarity endpoint: {e}")
            raise
    
    print(f"✓ Found {len(results)} similar structures from API")
    
    # Apply chemical system filter if specified
    if chemsys:
        # Parse chemsys elements
        chemsys_elements = set(chemsys.split('-'))
        filtered_results = []
        for entry in results:
            # Get formula from entry (could be dict or object)
            if isinstance(entry, dict):
                formula = entry.get('formula', '')
            else:
                formula = getattr(entry, 'formula', '')
            
            # Parse elements from formula
            from pymatgen.core import Composition
            try:
                comp = Composition(formula)
                entry_elements = set(str(el) for el in comp.elements)
                # Check if entry elements match chemsys
                if entry_elements == chemsys_elements:
                    filtered_results.append(entry)
            except:
                continue
        
        print(f"✓ Filtered to {len(filtered_results)} structures matching chemical system {chemsys}")
        results = filtered_results
    
    # Print summary of top results
    if results:
        print(f"\nTop 5 most similar structures:")
        for i, entry in enumerate(results[:5], 1):
            # Handle both dict and object formats
            if isinstance(entry, dict):
                mat_id = entry.get('task_id', 'unknown')
                formula = entry.get('formula', 'unknown')
                dissim = entry.get('dissimilarity', 0)
                similarity = 1.0 - (dissim / 100.0)
            else:
                mat_id = getattr(entry, 'task_id', 'unknown')
                formula = getattr(entry, 'formula', 'unknown')
                dissim = getattr(entry, 'dissimilarity', 0)
                similarity = 1.0 - (dissim / 100.0)
            
            print(f"  {i}. {mat_id}: {formula} (similarity: {similarity:.3f})")
    
    # Save results if output path specified
    if output_path:
        save_data(results, output_path)
        print(f"✓ Saved similarity results to {output_path}")
    
    return results


def save_data(data: List[Any], output_path: str) -> None:
    """
    Save similarity results to JSON file.
    
    Args:
        data: List of similarity result entries
        output_path: Path to save JSON file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to serializable format
    results_list = []
    for item in data:
        if isinstance(item, dict):
            results_list.append(item)
        else:
            # Convert object to dict using model_dump if available, else as dict
            if hasattr(item, 'model_dump'):
                results_list.append(item.model_dump())
            elif hasattr(item, 'dict'):
                results_list.append(item.dict())
            else:
                results_list.append(dict(item))
    
    results_dict = {
        "num_results": len(results_list),
        "results": results_list
    }
    
    with open(output_path, 'w') as f:
        json.dump(results_dict, f, indent=2, cls=MontyEncoder)


def main():
    parser = argparse.ArgumentParser(
        description="Find structurally similar materials using Materials Project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Query input
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--material_id',
        type=str,
        help='Material ID to find similar structures for (e.g., mp-149)'
    )
    input_group.add_argument(
        '--structure',
        type=str,
        help='Path to structure file (CIF, POSCAR, etc.)'
    )
    
    # Query parameters
    parser.add_argument(
        '--top',
        type=int,
        default=50,
        help='Number of most similar structures to return (default: 50)'
    )
    parser.add_argument(
        '--chemsys',
        type=str,
        help='Optional chemical system filter to apply after retrieval (e.g., "Si-O")'
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
    
    # Determine input
    query_input = args.material_id if args.material_id else args.structure
    
    # Find similar structures
    results = find_similar_structures(
        structure_or_mpid=query_input,
        top=args.top,
        chemsys=args.chemsys,
        output_path=args.output,
        api_key=args.api_key
    )
    
    print(f"\n✓ Similarity search complete")
    print(f"  Query: {query_input}")
    print(f"  Results: {len(results)} structures")
    print(f"  Output: {args.output}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
