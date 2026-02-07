import os
import sys
import argparse
import json

# Add repo root to find src.mcp_server
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(os.path.join(repo_root, "src/mcp_server"))
from htvs_server import setup_htvs_django as setup_django, get_htvs_config

def query_surfaces(group_name, config_name=None, limit=None, output_file=None, light_output_file=None):
    from pgmols.models import Surface, Crystal
    from django.contrib.auth.models import Group

    print(f"Querying surfaces cut from bulk for project group: {group_name}")
    
    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        # Try case-insensitive search or singular/plural
        potential_groups = Group.objects.filter(name__icontains=group_name.rstrip('s'))
        if potential_groups.exists():
            group = potential_groups.first()
            print(f"Warning: Group '{group_name}' not found. Using '{group.name}' instead.")
        else:
            print(f"Error: Group matching '{group_name}' not found.")
            return

    # Filter surfaces that belong to this group via parentjob and have a bulk reference
    surfaces = Surface.objects.filter(parentjob__group=group, bulk__isnull=False).select_related('bulk', 'miller_index', 'stoichiometry')

    if config_name:
        surfaces = surfaces.filter(parentjob__config__name=config_name)

    if limit:
        surfaces = surfaces[:limit]

    results = []
    print(f"Found {surfaces.count()} surface records. Extracting data...")

    for surf in surfaces:
        data = {
            "surface_id": surf.id,
            "formula": surf.stoichiometry.formula if surf.stoichiometry else "Unknown",
            "miller_index": surf.miller_index.hkl if surf.miller_index else None,
            "bulk_id": surf.bulk.id if surf.bulk else None,
            "bulk_formula": surf.bulk.stoichiometry.formula if surf.bulk and surf.bulk.stoichiometry else "Unknown",
            "lattice": surf.lattice,
            "num_atoms": len(surf.xyz)
        }
        results.append(data)

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Full results saved to {output_file}")
    
    if light_output_file:
        light_results = [r['surface_id'] for r in results]
        with open(light_output_file, 'w') as f:
            json.dump(light_results, f, indent=2)
        print(f"Light results (IDs only) saved to {light_output_file}")
    
    if not output_file and not light_output_file:
        # Print a summary
        for r in results[:10]:
            print(f"Surface {r['surface_id']} | {r['formula']} | Miller: {r['miller_index']} | Bulk: {r['bulk_formula']}")
        if len(results) > 10:
            print(f"... and {len(results) - 10} more.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query surfaces cut from bulk structures.")
    parser.add_argument("--group", default="perovskites", help="HTVS Project Group name")
    parser.add_argument("--config", help="Filter by JobConfig name (e.g. clean_surface_cut)")
    parser.add_argument("--limit", type=int, help="Limit number of results")
    parser.add_argument("--output", help="Output file path for full information (.json)")
    parser.add_argument("--light-output", help="Output file path for object IDs only (.json)")
    
    parser.add_argument("--db", default="orgel", help="Database settings module (e.g. orgel, toy)")
    
    args = parser.parse_args()
    
    config = get_htvs_config()
    print(f"Using HTVS_DIR: {config['htvs_dir']}")
    
    setup_django(args.db)
    query_surfaces(args.group, args.config, args.limit, args.output, args.light_output)
