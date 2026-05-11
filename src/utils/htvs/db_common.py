from typing import List, Dict, Any, Optional

def get_project_group(group_name: str):
    """
    Retrieve the Group object robustly with case-insensitive and plural matching.
    Must be called within a Django script context.
    """
    from pgmols.models import Group  # Note: in HTVS context, it's usually pgmols.models.Group

    try:
        group = Group.objects.get(name=group_name)
        return group
    except Group.DoesNotExist:
        # Try finding by name (case-insensitive) or stem
        potential_groups = Group.objects.filter(name__icontains=group_name.rstrip('s'))
        if potential_groups.exists():
            group = potential_groups.first()
            return group
        else:
            return None

def setup_query_parser(description: str):
    """
    Setup a standard argparse argument parser for HTVS query scripts.
    """
    import argparse
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--group", required=True, help="HTVS Project Group name")
    parser.add_argument("--db", default="orgel", help="Database settings module (e.g. orgel, toy)")
    parser.add_argument("--limit", type=int, help="Limit number of results")
    parser.add_argument("--output", help="Output file path (.json or .csv)")
    return parser

def save_query_results(results: List[Dict[str, Any]], output_file: Optional[str] = None) -> None:
    """
    Take a list of result dictionaries and standardly save them to JSON or CSV.
    """
    import os, json, csv
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
