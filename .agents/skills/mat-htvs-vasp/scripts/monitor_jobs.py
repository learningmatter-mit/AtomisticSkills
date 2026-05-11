"""
Monitor HTVS job completion.

Author: Hoje Chun
Contact: GitHub @hojechun
"""
import os
import sys
import json
import argparse
import traceback
from pathlib import Path
from typing import Any, Dict

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.script_runner import setup_django

def run_monitor_jobs(args: argparse.Namespace) -> Dict[str, Any]:
    if not os.path.exists(args.tracking_file):
        raise FileNotFoundError(f"Tracking file not found: {args.tracking_file}")
        
    with open(args.tracking_file, 'r') as f:
        tracking_data = json.load(f)
        
    group_name = tracking_data.get("group_name")
    chem_config = tracking_data.get("chem_config")
    # For backward compatibility and robustness
    job_dirs = tracking_data.get("job_dirs") or tracking_data.get("submitted_ids")
    
    if not job_dirs:
        return {"status": "warning", "message": "No jobs found in tracking file."}
        
    completed = []
    pending = []
    
    # Simple check for directory presence. In reality, we might check for specific files.
    for job_id in job_dirs:
        # Check if directory exists for the job
        # Note: job directory usually follows some naming convention
        # For simplicity, we assume we check against completed_path provided by user
        path = os.path.join(args.completed_path, str(job_id))
        if os.path.exists(path):
            completed.append(job_id)
        else:
            pending.append(job_id)
            
    parse_result = None
    if args.parse and completed:
        if not args.settings_module:
            raise ValueError("--settings_module is required for parsing.")
            
        setup_django(args.settings_module)
        from django.core.management import call_command
        
        # Use stdout redirection if needed, but here we just call it
        call_command(
            'parsejobs',
            group_name,
            args.completed_path,
            settings=args.settings_module,
            config=chem_config
        )
        parse_result = "Parse complete."

    return {
        "status": "success",
        "total": len(job_dirs),
        "completed_count": len(completed),
        "pending_count": len(pending),
        "completed": completed,
        "pending": pending,
        "parse_result": parse_result
    }

def main():
    parser = argparse.ArgumentParser(description="Monitor HTVS job completion.")
    parser.add_argument("--tracking_file", required=True, help="Path to job_tracking.json")
    parser.add_argument("--completed_path", required=True, help="Path to the completed jobs directory")
    parser.add_argument("--settings_module", help="Django Settings Module (if parsing requested)")
    parser.add_argument("--parse", action="store_true", help="Automatically run parsejobs for completed jobs")
    
    args = parser.parse_args()
    
    try:
        results = run_monitor_jobs(args)
        print(json.dumps(results, indent=2))
    except Exception as e:
        error_results = {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_results, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
