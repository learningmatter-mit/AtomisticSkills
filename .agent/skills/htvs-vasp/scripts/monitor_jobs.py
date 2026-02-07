import os
import sys
import json
import argparse
import glob
from pathlib import Path

def setup_django(settings_module, djangochem_dir):
    """Sets up Django environment for HTVS and returns if successful."""
    try:
        sys.path.append(djangochem_dir)
        sys.path.append(os.path.abspath(os.path.join(djangochem_dir, "..")))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
        import django
        django.setup()
        return True
    except Exception as e:
        print(f"Error setting up Django: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Monitor HTVS job completion.")
    parser.add_argument("--tracking_file", required=True, help="Path to job_tracking.json")
    parser.add_argument("--completed_path", required=True, help="Path to the completed jobs directory")
    parser.add_argument("--settings_module", help="Django Settings Module (if parsing requested)")
    parser.add_argument("--parse", action="store_true", help="Automatically run parsejobs for completed jobs")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.tracking_file):
        print(f"Tracking file not found: {args.tracking_file}")
        return
        
    with open(args.tracking_file, 'r') as f:
        tracking_data = json.load(f)
        
    group_name = tracking_data.get("group_name")
    chem_config = tracking_data.get("chem_config")
    job_dirs = tracking_data.get("job_dirs", [])
    
    if not job_dirs:
        print("No jobs found in tracking file.")
        return
        
    print(f"Monitoring {len(job_dirs)} jobs in {args.completed_path}")
    
    completed = []
    pending = []
    
    for job_name in job_dirs:
        path = os.path.join(args.completed_path, job_name)
        if os.path.exists(path):
            completed.append(job_name)
        else:
            pending.append(job_name)
            
    print(f"\nStatus Summary:")
    print(f"  Total:     {len(job_dirs)}")
    print(f"  Completed: {len(completed)}")
    print(f"  Pending:   {len(pending)}")
    
    if completed:
        print("\nCompleted Jobs:")
        for job in completed[:10]:
            print(f"  [x] {job}")
        if len(completed) > 10:
            print(f"  ... and {len(completed) - 10} more.")
            
    if pending:
        print("\nPending Jobs:")
        for job in pending[:10]:
            print(f"  [ ] {job}")
        if len(pending) > 10:
            print(f"  ... and {len(pending) - 10} more.")
            
    if args.parse and completed:
        if not args.settings_module:
            print("\nError: --settings_module is required for parsing.")
            return
            
        htvs_repo = os.environ.get("HTVS_DIR")
        if not htvs_repo:
            print("\nError: HTVS_DIR environment variable not set.")
            return
            
        djangochem_dir = os.path.join(htvs_repo, "djangochem")
        if setup_django(args.settings_module, djangochem_dir):
            from django.core.management import call_command
            print(f"\nRunning parsejobs for {len(completed)} jobs...")
            call_command(
                'parsejobs',
                group_name,
                args.completed_path,
                settings=args.settings_module,
                config=chem_config
            )
            print("Parsing complete.")

if __name__ == "__main__":
    main()
