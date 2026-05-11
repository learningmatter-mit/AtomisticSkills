"""
Retrieve elemental energies from the library for a given list of elements and a checkpoint.

Usage:
    python get_elemental_energies.py --elements H Li Fe --checkpoint mace-mp-medium
"""

import argparse
import json
import os
import sys

def get_elemental_energies(elements, checkpoint, resources_dir="../resources"):
    """
    Retrieve energies for a list of elements from the library.
    """
    library_path = os.path.join(resources_dir, f"{checkpoint}_energies.json")
    
    if not os.path.exists(library_path):
        print(f"Error: Library file not found for checkpoint '{checkpoint}' at {library_path}")
        return None
        
    with open(library_path, 'r') as f:
        library = json.load(f)
        
    results = {}
    missing = []
    
    for element in elements:
        if element in library:
            results[element] = library[element]
        else:
            missing.append(element)
            
    if missing:
        print(f"Warning: Energies not found for elements: {', '.join(missing)}")
        
    return results

def main():
    parser = argparse.ArgumentParser(description="Get elemental energies from the library.")
    parser.add_argument("--elements", nargs="+", required=True, help="List of elements")
    parser.add_argument("--checkpoint", required=True, help="MLIP checkpoint name")
    parser.add_argument("--resources_dir", default="../resources", help="Directory containing library files")
    args = parser.parse_args()

    results = get_elemental_energies(args.elements, args.checkpoint, args.resources_dir)
    
    if results:
        print(json.dumps(results, indent=2))

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.resources_dir)

if __name__ == "__main__":
    main()
