"""
Query Crystal structures from the HTVS database.

Author: Hoje Chun
Contact: GitHub @hojechun
"""
import os
import sys
import json
import argparse
import traceback
from typing import Any, Dict, List

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.db_handler import HTVSDbHandler, setup_query_parser, save_query_results

def run_query_crystals(args: argparse.Namespace) -> Dict[str, Any]:
    # Initialize handler
    handler = HTVSDbHandler(settings_module=args.db)
    
    # Use centralized query method
    results_json = handler.query_structures(
        group_name=args.group,
        structure_type="crystal",
        config_name=args.config,
        formula=args.formula,
        limit=args.limit
    )
    
    results = json.loads(results_json)
    
    if "error" in results:
        raise Exception(results["error"])
        
    # Handle outputs
    if args.output:
        save_query_results(results, args.output)
    
    light_results = [r['id'] for r in results]
    if args.light_output:
        with open(args.light_output, 'w') as f:
            json.dump(light_results, f, indent=2)
    
    return {
        "status": "success",
        "num_found": len(results),
        "found_ids": light_results,
        "output_file": args.output,
        "light_output_file": args.light_output
    }

def main():
    parser = setup_query_parser("Query Crystal structures from the database.")
    parser.add_argument("--config", help="Filter by JobConfig name (e.g. pbe_d3_paw_opt_vasp)")
    parser.add_argument("--formula", help="Filter by formula")
    parser.add_argument("--light-output", help="Output file path for object IDs only (.json)")
    
    args = parser.parse_args()
    
    try:
        results = run_query_crystals(args)
        print(json.dumps(results, indent=2))
    except Exception as e:
        error_results = {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_results, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
