"""
Export unrelaxed surfaces from the HTVS database to a directory for MLIP relaxation.

Usage:
    python export_surfaces.py --group <group_name> --config_name <config> 
                              --output_dir <dir> --settings <module>

Requirements:
    - Conda environment: htvs-agent
"""
import os
import sys
import argparse
import json
from typing import Dict, Any

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.script_runner import setup_django

def run_export(args: argparse.Namespace) -> Dict[str, Any]:
    setup_django(args.settings, args.djangochem)
    from pgmols.models import Group, Surface
    from jobs.models import JobConfig
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    group_obj = Group.objects.get(name=args.group)
    config_obj = JobConfig.objects.get(name=args.config_name)
    
    surfaces = Surface.objects.filter(
        parentjob__group=group_obj,
        parentjob__config=config_obj
    )
    
    if args.bulk_ids_json:
        with open(args.bulk_ids_json, 'r') as f:
            bids = json.load(f)
        surfaces = surfaces.filter(bulk__id__in=bids)
    
    if args.surface_ids_json:
        with open(args.surface_ids_json, 'r') as f:
            sids = json.load(f)
        surfaces = surfaces.filter(id__in=sids)
        
    exported = []
    
    for surf in surfaces:
        atoms = surf.as_ase_atoms()
        
        fixed_indices = []
        if hasattr(surf, "surface_atoms") and surf.surface_atoms:
            fixed_indices = [i for i, is_surf in enumerate(surf.surface_atoms) if not is_surf]
            
        cif_path = os.path.join(args.output_dir, f"surface_{surf.id}.cif")
        atoms.write(cif_path)
        
        exported.append({
            "id": surf.id,
            "cif_path": cif_path,
            "fixed_indices": fixed_indices
        })
        
    with open(os.path.join(args.output_dir, "metadata.json"), "w") as f:
        json.dump(exported, f, indent=2)
        
    return {"status": "success", "count": len(exported), "output_dir": args.output_dir}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", type=str, required=True)
    parser.add_argument("--config_name", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--bulk_ids_json", type=str, default=None)
    parser.add_argument("--surface_ids_json", type=str, default=None)
    parser.add_argument("--settings", type=str, required=True)
    parser.add_argument("--djangochem", type=str, default=None)
    
    args = parser.parse_args()
    
    try:
        res = run_export(args)
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
