import os
import sys
import json
import argparse

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
    
    # Add simulation_mcp to path for handler imports
    sim_mcp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    if sim_mcp_dir not in sys.path:
        sys.path.insert(0, sim_mcp_dir)
    
    from src.utils.htvs import HTVSJobHandler, HTVSVaspHandler
    
    # Setup Django and get structures to submit
    htvs_repo = os.environ.get("HTVS_DIR")
    if not htvs_repo:
        djangochem_dir = os.environ.get("HTVS_DJANGOCHEM_DIR")
        if djangochem_dir:
            htvs_repo = os.path.dirname(djangochem_dir)
    
    if htvs_repo and htvs_repo not in sys.path:
        sys.path.append(htvs_repo)
    
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", args.settings_module)
    
    try:
        import django
        django.setup()
    except ModuleNotFoundError as e:
        print(f"Error setting up Django: {e}")
        sys.exit(1)
    
    # Get structures to process
    if args.parentpks:
        from pgmols.models import Crystal, Surface
        imported_objects = []
        for gid in args.parentpks:
            try:
                if Crystal.objects.filter(id=gid).exists():
                    imported_objects.append((gid, "Crystal"))
                elif Surface.objects.filter(id=gid).exists():
                    imported_objects.append((gid, "Surface"))
                else:
                    print(f"Warning: Geom ID {gid} not found in database.")
            except Exception as e:
                print(f"Error checking Geom ID {gid}: {e}")
    else:
        # Find structures that need jobs
        from pgmols.models import Crystal, Surface, Group
        from jobs.models import Job, JobConfig
        from django.contrib.contenttypes.models import ContentType
        
        group = Group.objects.get(name=args.group_name)
        parent_config = JobConfig.objects.get(name=args.parent_config)
        chem_config = JobConfig.objects.get(name=args.chem_config)
        
        parent_jobs = Job.objects.filter(group=group, config=parent_config, status="done")
        
        imported_objects = []
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
        print("No structures found to process!")
        return
    
    print(f"Found {len(imported_objects)} structures to submit.")
    
    # Initialize handlers
    job_handler = HTVSJobHandler(args.settings_module)
    vasp_handler = HTVSVaspHandler()
    
    # Process each structure
    from pgmols.models import Crystal, Surface
    from django.utils import timezone
    
    for obj_id, obj_type in imported_objects:
        if obj_type == "Crystal":
            obj = Crystal.objects.get(id=obj_id)
        else:
            obj = Surface.objects.get(id=obj_id)
        
        # Save structure temporarily to generate VASP details
        temp_file = f"/tmp/struct_{obj_id}.cif"
        atoms = obj.as_ase_atoms()
        from ase.io import write
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
                print(f"Warning: No --project_name for Perlmutter. Using default 'm5068'.")
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
            
            print(f"Submitted {obj_type} {obj_id}: {result.strip()}")
            
        finally:
            # Cleanup temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    # Build jobs
    print(f"\nBuilding jobs in: {args.inbox_path}")
    result = job_handler.build_jobs(
        group_name=args.group_name,
        inbox_path=args.inbox_path,
        config_name=args.chem_config,
        compute_platform=args.compute_platform
    )
    print(result)
    
    # Save job tracking info
    tracking_file = "job_tracking.json"
    tracking_data = {
        "settings_module": os.environ.get('DJANGO_SETTINGS_MODULE'),
        "group_name": args.group_name,
        "chem_config": args.chem_config,
        "inbox_path": args.inbox_path,
        "timestamp": timezone.now().isoformat(),
        "num_jobs": len(imported_objects)
    }
    with open(tracking_file, 'w') as f:
        json.dump(tracking_data, f, indent=2)
    print(f"\nSaved tracking info to {tracking_file}")
    print("Submission complete.")

if __name__ == "__main__":
    main()
