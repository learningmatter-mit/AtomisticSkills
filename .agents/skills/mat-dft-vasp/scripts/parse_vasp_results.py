"""
Parse VASP outputs (vasprun.xml, OUTCAR).

Usage:
    python parse_vasp_results.py output_dir --save_to_file results.json

Requirements:
    - Conda environment: base-agent
    - Required packages: ase, pymatgen
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.dft.vasp_parser import VASPParser

def main():
    parser = argparse.ArgumentParser(description="Parse VASP outputs (vasprun.xml, OUTCAR).")
    parser.add_argument("output_dir", help="Directory with VASP outputs.")
    parser.add_argument("--save_to_file", default=None, help="Optional JSON save path.")
    
    args = parser.parse_args()
    
    output_dir = args.output_dir
    save_to_file = args.save_to_file
    
    parser_obj = VASPParser(output_dir)
    
    # Check if this is a single calculation directory
    has_vasprun = (parser_obj.output_dir / "vasprun.xml").exists()
    
    if has_vasprun:
        # Parse single VASP calculation
        result = parser_obj.parse_vasprun()
        outcar_result = parser_obj.parse_outcar()
        result.update(outcar_result)
        
        # Serialize for JSON
        results = parser_obj._prepare_for_json(result)
        
        if save_to_file:
            with open(save_to_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Successfully parsed VASP output and saved to {save_to_file}")
        else:
            print(json.dumps(results, indent=2))
            
    else:
        # Otherwise, parse all subdirectories
        try:
            all_results = parser_obj.parse_all()
        except Exception as e:
            print(f"Error parsing directory {output_dir}: {str(e)}")
            sys.exit(1)
            
        if not all_results:
            print(f"No valid VASP results found in {output_dir}")
            sys.exit(1)
            
        # Return serialized list
        results = {"results": parser_obj._prepare_for_json(all_results)}
        
        if save_to_file:
            with open(save_to_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Successfully parsed {len(all_results)} VASP directories and saved to {save_to_file}")
        else:
            print(json.dumps(results, indent=2))

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

if __name__ == "__main__":
    main()
