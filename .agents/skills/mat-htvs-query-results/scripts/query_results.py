import os
import sys
import json
import argparse

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(repo_root)

from src.utils.htvs.db_handler import HTVSDbHandler, setup_query_parser, save_query_results

def main():
    parser = setup_query_parser("Query HTVS Results from the database.")
    parser.add_argument("--config", help="Filter by JobConfig name (e.g. pbe_d3_paw_opt_vasp)")
    parser.add_argument("--formula", help="Filter by formula (e.g. LiFePO4)")
    parser.add_argument("--light-output", help="Output file path for calculation IDs only (.json)")
    
    args = parser.parse_args()
    
    # Initialize handler
    handler = HTVSDbHandler(settings_module=args.db)
    
    # Use centralized query method
    results_json = handler.query_results(
        group_name=args.group,
        config_name=args.config,
        formula=args.formula,
        limit=args.limit
    )
    
    results = json.loads(results_json)
    
    if "error" in results:
        print(f"Error: {results['error']}")
        sys.exit(1)
        
    print(f"Found {len(results)} calculation records.")
    
    # Handle outputs
    save_query_results(results, args.output)
    
    if args.light_output:
        light_results = [r['job_id'] for r in results]
        with open(args.light_output, 'w') as f:
            json.dump(light_results, f, indent=2)
        print(f"Light results (IDs only) saved to {args.light_output}")
    
    if not args.output and not args.light_output:
        # Print a summary
        for r in results[:10]:
            print(f"{r['uuid']} | {r['formula']} | Energy: {r['energy']}")
        if len(results) > 10:
            print(f"... and {len(results) - 10} more.")

if __name__ == "__main__":
    main()
