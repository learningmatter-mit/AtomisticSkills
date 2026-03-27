#!/usr/bin/env python
"""
Helper script to get atomic features from MACE and save to JSON.

This script uses the MACE MCP server to extract atomic features and saves them
in a format that check_phase.py can use.

Usage:
    python get_features.py <structure_file> <output_json>
"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, "/home/bdeng/projects/simulation_mcp")

from src.utils.mlips.mace.mace_wrapper import MACEWrapper


def get_features(structure_path, output_path):
    """Extract atomic features and save to JSON."""
    print(f"Loading MACE model...")
    wrapper = MACEWrapper(model_name="MACE-OMAT-0-small", device="cuda")
    wrapper.load()
    
    print(f"Extracting features from {structure_path}...")
    result = wrapper.predict_atomic_features(structure_path)
    
    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    
    # Save to JSON
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Saved features to {output_path}")
    print(f"  Atoms: {result['num_atoms']}")
    print(f"  Feature dimension: {result['feature_dim']}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    
    structure_file = sys.argv[1]
    output_file = sys.argv[2]
    
    get_features(structure_file, output_file)
