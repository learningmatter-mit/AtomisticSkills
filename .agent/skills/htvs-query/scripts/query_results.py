import os
import sys
import json
import csv
import argparse
import uuid
from datetime import datetime

# Add current script directory and server directory to path for config import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Add repo root to find src.mcp_server
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(os.path.join(repo_root, "src/mcp_server"))
from htvs_server import setup_htvs_django as setup_django, get_htvs_config

def query_results(group_name, config_name=None, formula=None, limit=None, output_file=None, light_output_file=None):
    from pgmols.models import Calc, SinglePoint, Jacobian, Hessian, Geom, Crystal
    from django.contrib.auth.models import Group

    print(f"Querying results for project group: {group_name}")
    
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

    # Base query for Calcs associated with jobs in this group
    # We use Calc (the base model) to ensure we get all simulation results
    calcs = Calc.objects.filter(parentjob__group=group).select_related('species__stoichiometry', 'parentjob')

    if config_name:
        calcs = calcs.filter(parentjob__config__name=config_name)

    if formula:
        calcs = calcs.filter(species__stoichiometry__formula=formula)

    if limit:
        calcs = calcs[:limit]

    results = []
    print(f"Found {calcs.count()} calculation records. Extracting data...")

    for calc in calcs:
        # The Calc model is the base for SinglePoint, Jacobian, Hessian, etc.
        data = {
            "uuid": str(calc.parentjob.uuid) if calc.parentjob else None,
            "calc_id": calc.id,
            "formula": calc.species.stoichiometry.formula if calc.species and calc.species.stoichiometry else "Unknown",
            "energy": calc.totalenergy,
            "completetime": calc.parentjob.completetime.isoformat() if calc.parentjob and calc.parentjob.completetime else None,
            "props": calc.props or {}
        }

        # Try to get more detailed data from subclasses if they exist
        # Django multi-table inheritance creates a 1to1 link back to the base model
        if hasattr(calc, 'jacobian'):
            data["forces"] = calc.jacobian.forces
            data["is_optimum"] = calc.jacobian.isoptimum
        elif hasattr(calc, 'singlepoint'):
            if data["energy"] is None:
                data["energy"] = calc.singlepoint.energy
            data["dipole"] = calc.singlepoint.dipole
        elif hasattr(calc, 'hessian'):
            data["vibfreqs"] = calc.hessian.vibfreqs
            data["freeenergy"] = calc.hessian.freeenergy

        # Fallback for energy from props if totalenergy and subclasses didn't provide it
        if data["energy"] is None and "totalenergy" in data["props"]:
            data["energy"] = data["props"]["totalenergy"]

        # Get structure info if available
        geom = calc.geoms.first()
        if geom:
            data["structure"] = {
                "coords": geom.get_coords(),
            }
            if hasattr(geom, 'crystal'):
                data["structure"]["lattice"] = geom.crystal.lattice

        results.append(data)

    if output_file:
        ext = os.path.splitext(output_file)[1].lower()
        if ext == '.json':
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Full results saved to {output_file}")
        elif ext == '.csv':
            if not results:
                print("No results to save.")
                return
            keys = results[0].keys()
            with open(output_file, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(results)
            print(f"Full results saved to {output_file}")
        else:
            print(f"Unsupported file format: {ext}. Use .json or .csv")
    
    if light_output_file:
        # Save calc_id as the light version
        light_results = [r['calc_id'] for r in results]
        with open(light_output_file, 'w') as f:
            json.dump(light_results, f, indent=2)
        print(f"Light results (IDs only) saved to {light_output_file}")

    if not output_file and not light_output_file:
        # Print a summary if no output file
        for r in results[:10]:
            print(f"{r['uuid']} | {r['formula']} | Energy: {r['energy']}")
        if len(results) > 10:
            print(f"... and {len(results) - 10} more.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query and save HTVS results.")
    parser.add_argument("--group", required=True, help="HTVS Project Group name")
    parser.add_argument("--config", help="Filter by JobConfig name (e.g. pbe_d3_paw_opt_vasp)")
    parser.add_argument("--formula", help="Filter by formula (e.g. LiFePO4)")
    parser.add_argument("--limit", type=int, help="Limit number of results")
    parser.add_argument("--output", help="Output file path for full information (.json or .csv)")
    parser.add_argument("--light-output", help="Output file path for calculation IDs only (.json)")
    parser.add_argument("--db", default="orgel", help="Database settings module (e.g. orgel, toy)")
    
    args = parser.parse_args()
    
    config = get_htvs_config()
    print(f"Using HTVS_DIR: {config['htvs_dir']}")
    
    setup_django(args.db)
    query_results(args.group, args.config, args.formula, args.limit, args.output, args.light_output)
