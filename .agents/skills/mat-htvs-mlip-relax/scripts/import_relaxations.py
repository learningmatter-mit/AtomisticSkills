"""
Ingest MLIP relaxation results back into HTVS database as Calc models.

Usage:
    python import_relaxations.py --input_dir <dir> --model_name <name> --settings <module>

Requirements:
    - Conda environment: htvs-agent
"""
import os
import sys
import json
import argparse
from typing import Dict, Any

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.script_runner import setup_django

def run_import(args: argparse.Namespace) -> Dict[str, Any]:
    setup_django(args.settings, args.djangochem)
    from pgmols.models import Surface, Calc, Method, Group
    from jobs.models import Job, JobConfig
    from django.contrib.contenttypes.models import ContentType
    
    results_path = os.path.join(args.input_dir, "results.json")
    with open(results_path, "r") as f:
        results = json.load(f)
        
    method_obj, _ = Method.objects.get_or_create(name=args.model_name)
    group_obj = Group.objects.get(name=args.group)
    config_obj, _ = JobConfig.objects.get_or_create(name=args.config_name)
    count = 0
    
    for item in results:
        parent_surf = Surface.objects.get(id=item["id"])
        
        # Duplicate check: prevent importing the same relaxation multiple times
        existing_jobs = Job.objects.filter(
            config=config_obj,
            parentid=parent_surf.id,
            parentct=ContentType.objects.get_for_model(parent_surf)
        )
        if existing_jobs.exists():
            continue
            
        # Create a new Surface for the relaxed coordinates
        new_surf = Surface(
            bulk=parent_surf.bulk,
            framework=parent_surf.framework,
            miller_index=parent_surf.miller_index,
            xyz=item["xyz"],
            lattice=parent_surf.lattice,
            stoichiometry=parent_surf.stoichiometry,
            spacegroup=parent_surf.spacegroup,
            method=method_obj,
            surface_atoms=parent_surf.surface_atoms,
            adsorbate_atoms=parent_surf.adsorbate_atoms,
            details=parent_surf.details
        )
        new_surf.chemical_tag = new_surf.generate_hash()
        new_surf.save()
        
        # Create a new Job
        job = Job.objects.create(
            config=config_obj,
            group=group_obj,
            status="done",
            parentct=ContentType.objects.get_for_model(parent_surf),
            parentid=parent_surf.id,
            method=method_obj
        )
        new_surf.parentjob = job
        new_surf.save()
        
        # Attach Calc
        calc = Calc.objects.create(
            totalenergy=item["energy"],
            method=method_obj,
            parentjob=job,
            props={"label": "mlip_relaxation", "is_converged": True}
        )
        calc.geoms.add(new_surf)
        count += 1
        
    return {"status": "success", "count": count}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", type=str, required=True)
    parser.add_argument("--model_name", type=str, required=True, help="Name of the MLIP model used")
    parser.add_argument("--config_name", type=str, default="mlip_relaxed_surf", help="Config name for the new relaxed jobs")
    parser.add_argument("--group", type=str, required=True, help="Project group name")
    parser.add_argument("--settings", type=str, required=True)
    parser.add_argument("--djangochem", type=str, default=None)
    
    args = parser.parse_args()
    
    try:
        res = run_import(args)
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
