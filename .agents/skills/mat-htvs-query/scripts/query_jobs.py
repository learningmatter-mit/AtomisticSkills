import os
import sys
import argparse
import json

# Add repo root to find src.mcp_server
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.append(os.path.join(repo_root, "src/mcp_server"))
from htvs_server import setup_htvs_django as setup_django, get_htvs_config

def query_jobs(group_name, status=None, config_name=None, limit=None, output_file=None, light_output_file=None):
    from jobs.models import Job
    from django.contrib.auth.models import Group

    print(f"Querying Jobs for project group: {group_name}")
    
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

    # Filter Jobs that belong to this group
    jobs = Job.objects.filter(group=group).select_related('config')

    if status:
        jobs = jobs.filter(status=status)

    if config_name:
        jobs = jobs.filter(config__name=config_name)

    if limit:
        jobs = jobs[:limit]

    results = []
    print(f"Found {jobs.count()} job records. Extracting data...")

    for job in jobs:
        data = {
            "job_id": job.id,
            "uuid": str(job.uuid),
            "config": job.config.name if job.config else "Unknown",
            "status": job.status,
            "createtime": job.createtime.isoformat() if job.createtime else None,
            "completetime": job.completetime.isoformat() if job.completetime else None,
            "duration": job.duration,
            "priority": job.priority,
            "details": job.details
        }
        results.append(data)

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Full results saved to {output_file}")
    
    if light_output_file:
        # Save job UUIDs as strings
        light_results = [r['uuid'] for r in results]
        with open(light_output_file, 'w') as f:
            json.dump(light_results, f, indent=2)
        print(f"Light results (UUIDs only) saved to {light_output_file}")
    
    if not output_file and not light_output_file:
        # Print a summary
        for j in results[:10]:
            print(f"{j['uuid']} | {j['config']} | {j['status']} | Duration: {j['duration']}")
        if len(results) > 10:
            print(f"... and {len(results) - 10} more.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query HTVS Jobs from the database.")
    parser.add_argument("--group", default="perovskite", help="HTVS Project Group name")
    parser.add_argument("--status", help="Filter by job status (e.g. done, error, claimed)")
    parser.add_argument("--config", help="Filter by JobConfig name (e.g. pbe_d3_paw_bomd_vasp)")
    parser.add_argument("--limit", type=int, help="Limit number of results")
    parser.add_argument("--output", help="Output file path for full information (.json)")
    parser.add_argument("--light-output", help="Output file path for job UUIDs only (.json)")
    
    parser.add_argument("--db", default="orgel", help="Database settings module (e.g. orgel, toy)")
    
    args = parser.parse_args()
    
    config = get_htvs_config()
    print(f"Using HTVS_DIR: {config['htvs_dir']}")
    
    setup_django(args.db)
    query_jobs(args.group, args.status, args.config, args.limit, args.output, args.light_output)
