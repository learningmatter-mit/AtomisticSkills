import argparse
import json
import os
from optimade.client import OptimadeClient

def main():
    """
    Query OPTIMADE-compliant databases for crystal structures.
    
    Usage:
        python query_optimade.py results.json --filter 'elements HAS ALL "Na", "Cl"' --provider cod
        
    Requirements:
        - Conda environment: base-agent
        - Required packages: optimade[client]
    """
    parser = argparse.ArgumentParser(description="Query OPTIMADE-compliant databases.")
    parser.add_argument("output", help="Output JSON file path")
    parser.add_argument("--filter", required=True, help="OPTIMADE filter string (e.g. 'elements HAS ALL \"Na\", \"Cl\"')")
    parser.add_argument("--provider", default="cod", help="Comma-separated providers (e.g., cod, nomad, aflow)")
    parser.add_argument("--max_results", type=int, default=10, help="Max results per provider")
    args = parser.parse_args()
    
    providers = [p.strip() for p in args.provider.split(",")]
    
    # Initialize the OPTIMADE Client
    client = OptimadeClient(include_providers=providers, max_results_per_provider=args.max_results)
    
    print(f"Querying {providers} for filter: '{args.filter}'...")
    try:
        results = client.get(filter=args.filter, endpoint="structures")
    except Exception as e:
        print(f"Error executing OPTIMADE query: {e}")
        return
        
    all_structures = []
    
    # results is a nested dict mapping endpoint -> filter -> base_url -> payload
    endpoint_data = results.get("structures", {}).get(args.filter, {})
    
    for base_url, response in endpoint_data.items():
        data = response.get("data", [])
        for item in data:
            item["_optimade_provider_url"] = base_url
            all_structures.append(item)
            
    # Save the flattened search results
    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(args.output, "w") as f:
        json.dump(all_structures, f, indent=2)
        
    print(f"Saved {len(all_structures)} structures to {args.output}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)

if __name__ == "__main__":
    main()
