#!/usr/bin/env python3
"""
Prepare training data for MatterGen fine-tuning.

Converts structures and properties from various formats into MatterGen's
required CSV format with CIF strings and property columns.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd
from pymatgen.core import Structure
from pymatgen.io.cif import CifWriter


def load_structures_from_directory(structures_dir: Path) -> List[Dict[str, Any]]:
    """Load structures from a directory of CIF or POSCAR files."""
    structures = []
    
    for file_path in structures_dir.glob("*"):
        if file_path.suffix.lower() in [".cif", ".vasp", ""]:
            try:
                struct = Structure.from_file(str(file_path))
                structures.append({
                    "structure": struct,
                    "source_file": file_path.name
                })
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}", file=sys.stderr)
    
    return structures


def load_structures_from_json(json_path: Path) -> List[Dict[str, Any]]:
    """
    Load structures from JSON file.
    
    Expected format:
    [
        {
            "structure": <pymatgen dict>,
            "properties": {"property_name": value, ...}
        },
        ...
    ]
    """
    with open(json_path) as f:
        data = json.load(f)
    
    structures = []
    for item in data:
        try:
            struct = Structure.from_dict(item["structure"])
            structures.append({
                "structure": struct,
                "properties": item.get("properties", {}),
                "source": item.get("source", "unknown")
            })
        except Exception as e:
            print(f"Warning: Failed to parse structure: {e}", file=sys.stderr)
    
    return structures


def structure_to_cif_string(structure: Structure) -> str:
    """Convert pymatgen Structure to CIF string."""
    writer = CifWriter(structure)
    return str(writer)


def prepare_training_data(
    structures: List[Dict[str, Any]],
    property_name: str,
    output_path: Path
) -> None:
    """
    Prepare training data CSV for MatterGen.
    
    Args:
        structures: List of structure dicts with 'structure' and 'properties'
        property_name: Name of the property to extract
        output_path: Output CSV file path
    """
    rows = []
    
    for i, item in enumerate(structures):
        struct = item["structure"]
        properties = item.get("properties", {})
        
        # Check if property exists
        if property_name not in properties:
            print(f"Warning: Structure {i} missing property '{property_name}', skipping", 
                  file=sys.stderr)
            continue
        
        # Convert structure to CIF string
        cif_string = structure_to_cif_string(struct)
        
        # Create row with required material_id
        material_id = item.get("source", f"custom_{i:04d}")
        row = {
            "cif": cif_string,
            "material_id": material_id,
            property_name: properties[property_name]
        }
        
        # Add any additional metadata
        if "source_file" in item:
            row["source_file"] = item["source_file"]
        
        rows.append(row)
    
    # Create DataFrame and save
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    
    print(f"✓ Prepared {len(rows)} training samples")
    print(f"✓ Saved to: {output_path}")
    print(f"✓ Property: {property_name}")
    print(f"✓ Columns: {list(df.columns)}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare training data for MatterGen fine-tuning"
    )
    parser.add_argument(
        "--structures-json",
        type=Path,
        help="Path to JSON file with structures and properties"
    )
    parser.add_argument(
        "--structures-dir",
        type=Path,
        help="Directory containing structure files (CIF/POSCAR)"
    )
    parser.add_argument(
        "--properties-json",
        type=Path,
        help="JSON file mapping structure files to properties (for --structures-dir)"
    )
    parser.add_argument(
        "--property-name",
        required=True,
        help="Name of the property to use for conditioning"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output CSV file path"
    )
    
    args = parser.parse_args()
    
    # Load structures
    if args.structures_json:
        structures = load_structures_from_json(args.structures_json)
    elif args.structures_dir:
        if not args.properties_json:
            print("Error: --properties-json required when using --structures-dir", 
                  file=sys.stderr)
            sys.exit(1)
        
        # Load structures from directory
        structures = load_structures_from_directory(args.structures_dir)
        
        # Load properties
        with open(args.properties_json) as f:
            properties_map = json.load(f)
        
        # Match properties to structures
        for item in structures:
            source_file = item["source_file"]
            if source_file in properties_map:
                item["properties"] = properties_map[source_file]
    else:
        print("Error: Either --structures-json or --structures-dir must be provided", 
              file=sys.stderr)
        sys.exit(1)
    
    if not structures:
        print("Error: No structures loaded", file=sys.stderr)
        sys.exit(1)
    
    # Prepare training data
    prepare_training_data(structures, args.property_name, args.output)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
