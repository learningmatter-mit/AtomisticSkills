"""
Submit HTVS jobs using HTVSJobHandler and HTVSVaspHandler.

Author: Hoje Chun
Contact: GitHub @hojechun
"""
import os
import sys
import json
import argparse
import traceback
from typing import Any, Dict, List

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.script_runner import setup_django
from src.utils.htvs import HTVSJobHandler, HTVSVaspHandler

def run_submit_jobs(args: argparse.Namespace) -> Dict[str, Any]:
    setup_django(args.settings_module)

    from pgmols.models import Crystal, Surface, Group
    from jobs.models import Job, JobConfig
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    from ase.io import write

    def log(msg: str) -> None:
        print(f"SUBMIT_JOBS: {msg}", file=sys.stderr)

    # Get structures to process
    imported_objects = []
    if args.parentpks:
        for gid in args.parentpks:
            try:
                if Crystal.objects.filter(id=gid).exists():
                    imported_objects.append((gid, "Crystal"))
                elif Surface.objects.filter(id=gid).exists():
                    imported_objects.append((gid, "Surface"))
                else:
                    log(f"Warning: Geom ID {gid} not found in database.")
            except Exception as e:
                log(f"Error checking Geom ID {gid}: {e}")
    else:
        group = Group.objects.get(name=args.group_name)
        parent_config = JobConfig.objects.get(name=args.parent_config)
        chem_config = JobConfig.objects.get(name=args.chem_config)
        
        parent_jobs = Job.objects.filter(group=group, config=parent_config, status="done")
        
        for p_job in parent_jobs:
            obj = p_job.parent
            if not obj:
                continue
            
            existing = Job.objects.filter(
                group=group,
                config=chem_config,
                parentct=ContentType.objects.get_for_model(obj),
                parentid=obj.id
            ).exists()
            
            if not existing:
                imported_objects.append((obj.id, obj.__class__.__name__))
                if args.limit and len(imported_objects) >= args.limit:
                    break
    
    if not imported_objects:
        return {"status": "warning", "message": "No structures found to process!"}
    
    log(f"Found {len(imported_objects)} structures to submit.")
    
    # Initialize handlers
    job_handler = HTVSJobHandler(args.settings_module)
    vasp_handler = HTVSVaspHandler()
    
    submitted_ids = []
    
    # Process each structure
    for obj_id, obj_type in imported_objects:
        if obj_type == "Crystal":
            obj = Crystal.objects.get(id=obj_id)
        else:
            obj = Surface.objects.get(id=obj_id)
        
        # Save structure temporarily to generate VASP details
        temp_file = f"/tmp/struct_{obj_id}.cif"
        atoms = obj.as_ase_atoms()
        write(temp_file, atoms)
        
        try:
            # Generate VASP details using handler
            details_json = vasp_handler.generate_details(
                structure_file=temp_file,
                preset_type=args.preset_type,
                calculation_type=args.calculation_type,
                magnetism=True
            )
            details = json.loads(details_json)
            
            # Add mandatory platform-specific settings
            details.update({
                "compute_platform": args.compute_platform,
                "requester": args.requester,
                "priority": 100
            })
            
            if args.potcar_path:
                details["pseudo_dir"] = args.potcar_path
                details["potcar_path"] = args.potcar_path
            
            if args.project_name:
                details["project_name"] = args.project_name
            elif "perlmutter" in args.compute_platform.lower():
                details["project_name"] = "m5068"
            
            # Request job using handler
            result = job_handler.request_job(
                group_name=args.group_name,
                chem_config=args.chem_config,
                details=details,
                requester=args.requester,
                parent_pks=[obj_id],
                parent_config=args.parent_config
            )
            
            if "Success" in result:
                submitted_ids.append(obj_id)
                log(f"Submitted {obj_type} {obj_id}")
            else:
                log(f"Failed to submit {obj_type} {obj_id}: {result}")
            
        finally:
            # Cleanup temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    # Build jobs
    log(f"Building jobs in: {args.inbox_path}")
    build_result = job_handler.build_jobs(
        group_name=args.group_name,
        inbox_path=args.inbox_path,
        config_name=args.chem_config,
        compute_platform=args.compute_platform
    )
    
    # Save job tracking info
    tracking_file = "job_tracking.json"
    tracking_data = {
        "settings_module": args.settings_module,
        "group_name": args.group_name,
        "chem_config": args.chem_config,
        "inbox_path": args.inbox_path,
        "timestamp": timezone.now().isoformat(),
        "num_jobs": len(submitted_ids),
        "submitted_ids": submitted_ids
    }
    with open(tracking_file, 'w') as f:
        json.dump(tracking_data, f, indent=2)
    
    return {
        "status": "success",
        "num_submitted": len(submitted_ids),
        "submitted_ids": submitted_ids,
        "build_output": build_result,
        "tracking_file": tracking_file
    }

def main():
    parser = argparse.ArgumentParser(description="Submit HTVS jobs using HTVSJobHandler and HTVSVaspHandler.")
    parser.add_argument("--group_name", required=True, help="HTVS Group Name")
    parser.add_argument("--chem_config", required=True, help="HTVS Chemical Configuration")
    parser.add_argument("--parent_config", default="agent_generated", help="Parent Job Configuration Name")
    parser.add_argument("--parentpks", type=int, nargs="+", help="Explicit parent IDs (Crystal/Surface)")
    parser.add_argument("--compute_platform", required=True, help="Compute Platform")
    parser.add_argument("--requester", required=True, help="User requesting the job")
    parser.add_argument("--settings_module", required=True, help="Django Settings Module")
    parser.add_argument("--potcar_path", help="Path to VASP POTCAR files")
    parser.add_argument("--inbox_path", required=True, help="Directory for generated job files")
    parser.add_argument("--project_name", help="Compute project name (required for Perlmutter)")
    parser.add_argument("--preset_type", default="omat", choices=["mp", "omat", "matpes-pbe", "matpes-r2scan"], 
                       help="Pymatgen VASP preset")
    parser.add_argument("--calculation_type", default="static", choices=["static", "relaxation"], 
                       help="VASP calculation type")
    parser.add_argument("--limit", type=int, help="Max number of jobs to submit")
    
    args = parser.parse_args()
    
    try:
        results = run_submit_jobs(args)
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
