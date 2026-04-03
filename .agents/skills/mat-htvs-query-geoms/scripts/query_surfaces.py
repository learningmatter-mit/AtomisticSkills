import os
import sys
import json
import argparse

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(repo_root)

from src.utils.htvs.db_handler import HTVSDbHandler, setup_query_parser, save_query_results

def main():
    parser = setup_query_parser("Query Surface structures from the database.")
    parser.add_argument("--config", help="Filter by JobConfig name (e.g. clean_surface_cut)")
    parser.add_argument("--formula", help="Filter by formula")
    parser.add_argument("--light-output", help="Output file path for object IDs only (.json)")
    
    args = parser.parse_args()
    
    # Initialize handler
    handler = HTVSDbHandler(settings_module=args.db)
    
    # Use centralized query method
    results_json = handler.query_structures(
        group_name=args.group,
        structure_type="surface",
        config_name=args.config,
        formula=args.formula,
        limit=args.limit
    )
    
    results = json.loads(results_json)
    
    if "error" in results:
        print(f"Error: {results['error']}")
        sys.exit(1)
        
    print(f"Found {len(results)} surface records.")
    
    # Handle outputs
    save_query_results(results, args.output)
    
    if args.light_output:
        light_results = [r['id'] for r in results]
        with open(args.light_output, 'w') as f:
            json.dump(light_results, f, indent=2)
        print(f"Light results (IDs only) saved to {args.light_output}")
    
    if not args.output and not args.light_output:
        # Print a summary
        for r in results[:10]:
            print(f"Surface {r['id']} | {r['formula']} | Miller: {r.get('miller_index')} | Atoms: {r['num_atoms']}")
        if len(results) > 10:
            print(f"... and {len(results) - 10} more.")

if __name__ == "__main__":
    main()
