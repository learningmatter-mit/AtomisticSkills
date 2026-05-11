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
    from src.utils.htvs.config_handler import HTVSConfigHandler
    import yaml
    
    config_handler = HTVSConfigHandler()
    config = config_handler.config
    
    # Load config file if provided
    if hasattr(args, 'config_file') and args.config_file:
        with open(args.config_file, 'r') as f:
            if args.config_file.endswith('.yaml') or args.config_file.endswith('.yml'):
                file_config = yaml.safe_load(f)
            else:
                file_config = json.load(f)
            
            # Map global settings
            globals_dict = file_config.get("global_settings", {})
            for k, v in globals_dict.items():
                if getattr(args, k, None) is None:  # Don't override explicit CLI args
                    setattr(args, k, v)
                    
            # Map step specific settings
            if args.chem_config:
                steps_dict = file_config.get("steps", file_config.get("vasp_steps", {}))
                if args.chem_config not in steps_dict:
                    raise ValueError(f"Strict config mode: chem_config '{args.chem_config}' must be explicitly defined in the provided config file")
                
                step_config = steps_dict.get(args.chem_config, {})
                for k, v in step_config.items():
                    if k == "custom_settings" and isinstance(v, dict):
                        setattr(args, k, json.dumps(v))
                    elif getattr(args, k, None) is None:
                        setattr(args, k, v)
    else:
        # Fallback to reading step-specific settings from global ~/.atomistic_skills.yaml
        vasp_steps = config.get("vasp_steps", {})
        if args.chem_config not in vasp_steps:
            raise ValueError(f"Strict config mode: chem_config '{args.chem_config}' must be explicitly defined in 'vasp_steps' inside ~/.atomistic_skills.yaml")
            
        step_config = vasp_steps[args.chem_config]
        for k, v in step_config.items():
            if k == "custom_settings" and isinstance(v, dict):
                setattr(args, k, json.dumps(v))
            elif getattr(args, k, None) is None:
                setattr(args, k, v)

    args.settings_module = args.settings_module or config.get("settings_module")
    args.group_name = args.group_name or config.get("group_name")
    args.compute_platform = args.compute_platform or config.get("compute_platform")
    args.requester = args.requester or config.get("requester")
    args.inbox_path = args.inbox_path or config.get("inbox_path")
    args.potcar_path = args.potcar_path or config.get("potcar_path")
    args.project_name = args.project_name or config.get("project_name")
    
    if not all([args.settings_module, args.group_name, args.compute_platform, args.requester, args.inbox_path]):
        raise ValueError(f"Missing required configuration. Please ensure ~/.atomistic_skills.yaml is configured or pass them as arguments.")

    if args.tracking_file:
        args.tracking_file = os.path.abspath(args.tracking_file)
    else:
        args.tracking_file = os.path.abspath("job_tracking.json")

    setup_django(args.settings_module)
    djangochem_dir = config.get("htvs_djangochem_dir")
    if djangochem_dir:
        os.chdir(djangochem_dir)

    from pgmols.models import Crystal, Surface, Group
    from jobs.models import Job, JobConfig
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    from ase.io import write

    def log(msg: str) -> None:
        print(f"SUBMIT_JOBS: {msg}", file=sys.stderr)

    # Autodetect parent_config if missing
    if not args.parent_config and args.parentpks:
        log("Attempting to auto-detect parent_config...")
        try:
            first_id = args.parentpks[0]
            if Surface.objects.filter(id=first_id).exists():
                surf = Surface.objects.get(id=first_id)
                if getattr(surf, 'parentjob', None):
                    args.parent_config = surf.parentjob.config.name
                    log(f"Auto-detected parent_config from Surface: {args.parent_config}")
            elif Crystal.objects.filter(id=first_id).exists():
                cryst = Crystal.objects.get(id=first_id)
                if getattr(cryst, 'parentjob', None):
                    args.parent_config = cryst.parentjob.config.name
                    log(f"Auto-detected parent_config from Crystal: {args.parent_config}")
        except Exception as e:
            log(f"Auto-detect parent_config failed: {e}")
            
    if not args.parent_config:
        args.parent_config = "agent_generated"

    # Get structures to process
    imported_objects = []
    if args.parentpks:
        for gid in args.parentpks:
            try:
                if args.parent_type == "Crystal":
                    if Crystal.objects.filter(id=gid).exists():
                        imported_objects.append((gid, "Crystal"))
                    else:
                        log(f"Warning: Crystal ID {gid} not found in database.")
                elif args.parent_type == "Surface":
                    if Surface.objects.filter(id=gid).exists():
                        imported_objects.append((gid, "Surface"))
                    else:
                        log(f"Warning: Surface ID {gid} not found in database.")
                else:
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
        chem_config = JobConfig.objects.get(name=args.chem_config)
        
        # We find the Geoms whose parentjob has the requested parent_config
        # and belong to the correct group.
        
        # Look for Crystals first
        crystals = Crystal.objects.filter(
            parentjob__group=group, 
            parentjob__config__name=args.parent_config,
            parentjob__status="done"
        )
        
        for obj in crystals:
            existing = Job.objects.filter(
                group=group,
                config=chem_config,
                parentct=ContentType.objects.get_for_model(obj),
                parentid=obj.id
            ).exclude(status='cancelled').exists()
            
            if not existing:
                imported_objects.append((obj.id, "Crystal"))
                if args.limit and len(imported_objects) >= args.limit:
                    break
                    
        # If limit not reached, look for Surfaces
        if not args.limit or len(imported_objects) < args.limit:
            surfaces = Surface.objects.filter(
                parentjob__group=group, 
                parentjob__config__name=args.parent_config,
                parentjob__status="done"
            )
            
            for obj in surfaces:
                existing = Job.objects.filter(
                    group=group,
                    config=chem_config,
                    parentct=ContentType.objects.get_for_model(obj),
                    parentid=obj.id
                ).exclude(status='cancelled').exists()
                
                if not existing:
                    imported_objects.append((obj.id, "Surface"))
                    if args.limit and len(imported_objects) >= args.limit:
                        break
    
    if not imported_objects:
        return {"status": "warning", "message": "No structures found to process!"}
    
    log(f"Found {len(imported_objects)} structures to submit.")
    
    # Initialize handlers
    job_handler = HTVSJobHandler(args.settings_module)
    vasp_handler = HTVSVaspHandler()
    
    submitted_ids = []
    
    # Clear old error or cancelled jobs for this config to allow resubmission
    if not getattr(args, 'preview_incar', False):
        try:
            from jobs.models import Job
            Job.objects.filter(
                group__name=args.group_name, 
                config__name=args.chem_config,
                status__in=['error', 'cancelled']
            ).delete()
        except Exception as e:
            log(f"Failed to clear old jobs: {e}")
        
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
            # Parse custom settings if provided
            custom_settings_dict = None
            if hasattr(args, 'custom_settings') and args.custom_settings:
                try:
                    custom_settings_dict = json.loads(args.custom_settings)
                except Exception as e:
                    log(f"Failed to parse custom_settings: {e}")
            
            # Generate VASP details using handler
            details_json = vasp_handler.generate_details(
                structure_file=temp_file,
                preset_type=args.preset_type,
                calculation_type=args.calculation_type,
                magnetism=True,
                custom_settings=custom_settings_dict
            )
            details = json.loads(details_json)
            
            # Autotranslate uppercase VASP INCAR tags to lowercase for HTVS templates
            htvs_mappings = {"NSW": "nsteps"}
            for key in list(details.keys()):
                val = details[key]
                
                # Convert list-based tags like LDAUU/ldauu to space-separated strings for HTVS
                if isinstance(val, list) and key.lower().startswith("ldau"):
                    val = " ".join(map(str, val))
                    details[key] = val
                
                if key.isupper():
                    # Apply specific HTVS template mappings if exist, otherwise lowercase
                    mapped_key = htvs_mappings.get(key, key.lower())
                    details[mapped_key] = val
                    if mapped_key != key:
                        del details[key]
            
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
                
            # Override the 66 core fallback from default_details.json for Perlmutter
            if "perlmutter" in args.compute_platform.lower() and "nprocs" not in (custom_settings_dict or {}):
                details["nprocs"] = 128
            
            # Inject unconverged_geoms so newly cut surfaces are not filtered out by requestjobs
            details["unconverged_geoms"] = True

            if hasattr(args, 'preview_incar') and args.preview_incar:
                print(f"--- PREVIEW INCAR DEFAULTS FOR {args.preset_type} ---")
                print(json.dumps(details, indent=2))
                # Cleanup temp file and return immediately for preview
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return {"status": "preview", "message": "Preview mode enabled. Exiting before submission."}

            # Request job using handler
            print("SUBMITTING DETAILS:", details)
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
    tracking_file = args.tracking_file or "job_tracking.json"
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
    parser.add_argument("--group_name", help="HTVS Group Name")
    parser.add_argument("--chem_config", required=True, help="HTVS Chemical Configuration")
    parser.add_argument("--parent_config", help="Parent Job Configuration Name")
    parser.add_argument("--parent_type", choices=["Crystal", "Surface"], help="Type of parent (Crystal or Surface)")
    parser.add_argument("--parentpks", type=int, nargs="+", help="Explicit parent IDs (Crystal/Surface)")
    parser.add_argument("--compute_platform", help="Compute Platform")
    parser.add_argument("--requester", help="User requesting the job")
    parser.add_argument("--settings_module", help="Django Settings Module")
    parser.add_argument("--potcar_path", help="Path to VASP POTCAR files")
    parser.add_argument("--inbox_path", help="Directory for generated job files")
    parser.add_argument("--project_name", help="Compute project name (required for Perlmutter)")
    parser.add_argument("--preset_type", default="omat", choices=["mp", "omat", "matpes-pbe", "matpes-r2scan"], 
                       help="Pymatgen VASP preset")
    parser.add_argument("--calculation_type", choices=["static", "relaxation"], 
                       help="VASP calculation type")
    parser.add_argument("--custom_settings", help="JSON string of custom VASP INCAR settings (e.g. '{\"NSW\": 200}')")
    parser.add_argument("--limit", type=int, help="Max number of jobs to submit")
    parser.add_argument("--tracking_file", help="Path to save the job tracking JSON log")
    parser.add_argument("--config_file", help="Path to JSON configuration file (overrides CLI arguments)")
    parser.add_argument("--preview_incar", action="store_true", help="Print fully resolved INCAR parameters and exit without submitting")
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
