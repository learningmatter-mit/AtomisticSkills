import os
import sys
import argparse
import json

# Add repo root to find src.mcp_server
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(os.path.join(repo_root, "src/mcp_server"))
from htvs_server import setup_htvs_django as setup_django, get_htvs_config

def query_crystals(group_name, config_name=None, formula=None, limit=None, output_file=None, light_output_file=None):
    from pgmols.models import Crystal
    from django.contrib.auth.models import Group

    print(f"Querying Crystals for project group: {group_name}")
    
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

    # Filter Crystals that belong to this group via parentjob
    crystals = Crystal.objects.filter(parentjob__group=group).select_related('stoichiometry', 'spacegroup', 'parentjob')

    if config_name:
        crystals = crystals.filter(parentjob__config__name=config_name)

    if formula:
        crystals = crystals.filter(stoichiometry__formula=formula)

    if limit:
        crystals = crystals[:limit]

    results = []
    print(f"Found {crystals.count()} crystal records. Extracting data...")

    for crys in crystals:
        data = {
            "crystal_id": crys.id,
            "formula": crys.stoichiometry.formula if crys.stoichiometry else "Unknown",
            "spacegroup": crys.spacegroup.symbol if crys.spacegroup else "Unknown",
            "lattice": crys.lattice,
            "num_atoms": len(crys.xyz),
            "job_uuid": str(crys.parentjob.uuid) if crys.parentjob else None
        }
        results.append(data)

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Full results saved to {output_file}")
    
    if light_output_file:
        light_results = [r['crystal_id'] for r in results]
        with open(light_output_file, 'w') as f:
            json.dump(light_results, f, indent=2)
        print(f"Light results (IDs only) saved to {light_output_file}")
    
    if not output_file and not light_output_file:
        # Print a summary
        for r in results[:10]:
            print(f"Crystal {r['crystal_id']} | {r['formula']} | SG: {r['spacegroup']} | Atoms: {r['num_atoms']}")
        if len(results) > 10:
            print(f"... and {len(results) - 10} more.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Crystal structures from the database.")
    parser.add_argument("--group", default="perovskite", help="HTVS Project Group name")
    parser.add_argument("--config", help="Filter by JobConfig name (e.g. pbe_d3_paw_opt_vasp)")
    parser.add_argument("--formula", help="Filter by formula")
    parser.add_argument("--limit", type=int, help="Limit number of results")
    parser.add_argument("--output", help="Output file path for full information (.json)")
    parser.add_argument("--light-output", help="Output file path for object IDs only (.json)")
    
    parser.add_argument("--db", default="orgel", help="Database settings module (e.g. orgel, toy)")
    
    args = parser.parse_args()
    
    config = get_htvs_config()
    print(f"Using HTVS_DIR: {config['htvs_dir']}")
    
    setup_django(args.db)
    query_crystals(args.group, args.config, args.formula, args.limit, args.output, args.light_output)
