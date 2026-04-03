import os
import sys
import json
import argparse

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(repo_root)

from src.utils.htvs.db_handler import HTVSDbHandler, setup_query_parser, save_query_results

def main():
    parser = setup_query_parser("Query HTVS Jobs from the database.")
    parser.add_argument("--status", help="Filter by job status (e.g. done, error, claimed)")
    parser.add_argument("--config", help="Filter by JobConfig name (e.g. pbe_d3_paw_bomd_vasp)")
    parser.add_argument("--light-output", help="Output file path for job UUIDs only (.json)")
    
    args = parser.parse_args()
    
    # Initialize handler
    handler = HTVSDbHandler(settings_module=args.db)
    
    # Use centralized query method
    results_json = handler.query_jobs(
        group_name=args.group,
        status=args.status,
        config_name=args.config,
        limit=args.limit
    )
    
    results = json.loads(results_json)
    
    if "error" in results:
        print(f"Error: {results['error']}")
        sys.exit(1)
        
    print(f"Found {len(results)} job records.")
    
    # Handle outputs
    save_query_results(results, args.output)
    
    if args.light_output:
        light_results = [r['uuid'] for r in results]
        with open(args.light_output, 'w') as f:
            json.dump(light_results, f, indent=2)
        print(f"Light results (UUIDs only) saved to {args.light_output}")
    
    if not args.output and not args.light_output:
        # Print a summary
        for j in results[:10]:
            print(f"{j['uuid']} | {j['config']} | {j['status']} | Duration: {j['duration']}")
        if len(results) > 10:
            print(f"... and {len(results) - 10} more.")

if __name__ == "__main__":
    main()
