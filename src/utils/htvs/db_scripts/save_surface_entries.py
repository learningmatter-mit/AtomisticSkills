"""
Template script to save multiple Surface records generated in-memory.
"""
import os
import json
import numpy as np
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

def run(payload):
    from pgmols.models import Group, Surface, MillerIndex, Crystal, Calc, Method
    from jobs.models import Job, JobConfig
    from ase import Atoms
    
    results = {"success": [], "errors": []}
    
    group_obj = Group.objects.get(name=payload["group_name"])
    config_obj = JobConfig.objects.get(name=payload["config_name"])
    method_name = payload.get("method_name")
    default_method_name = method_name if method_name else "manual_import"
    method_obj, _ = Method.objects.get_or_create(name=default_method_name)
    
    entries = payload.get("entries", [])
    
    for entry in entries:
        try:
            bulk_obj = Crystal.objects.get(id=entry["bulk_id"])
            mi_obj, _ = MillerIndex.objects.get_or_create(hkl=entry["miller_index"])
            
            atoms = Atoms(symbols=entry["symbols"], positions=entry["xyz"], cell=entry["lattice"], pbc=True)
            
            surf = Surface.from_ase_atoms(atoms)
            surf.bulk = bulk_obj
            surf.miller_index = mi_obj
            surf.surface_atoms = entry["surface_atoms"]
            surf.adsorbate_atoms = entry["adsorbate_atoms"]
            surf.details = entry.get("details", {})
            surf.method = method_obj
            
            chemical_tag = surf.generate_hash()
            surf.chemical_tag = chemical_tag
            
            if entry.get("magmoms"):
                surf.magmoms = entry["magmoms"]
            
            # Duplicate check
            exists = Surface.objects.filter(chemical_tag=chemical_tag).first()
            if exists:
                results["success"].append(exists.id)
                continue
                
            # Create Job
            job = Job(
                config=config_obj,
                group=group_obj,
                method=method_obj,
                status="done",
                parentct=ContentType.objects.get_for_model(bulk_obj),
                parentid=bulk_obj.id,
                completetime=timezone.now(),
            )
            job.save()
            
            surf.parentjob = job
            surf.save()
            
            # Create Calc
            props = {"magmoms": surf.magmoms} if hasattr(surf, "magmoms") else {}
            calc = Calc(method=surf.method, props=props)
            calc.parentjob = job
            calc.save()
            calc.geoms.add(surf)
            
            results["success"].append(surf.id)
            
        except Exception as e:
            results["errors"].append({"index": entries.index(entry), "error": str(e)})
            
    return results

if __name__ == "__main__":
    payload_str = os.environ.get("HTVS_PAYLOAD", "{}")
    payload = json.loads(payload_str)
    
    try:
        output = run(payload)
        print(json.dumps(output))
    except Exception as e:
        import traceback
        print(json.dumps({"error": str(e), "traceback": traceback.format_exc()}))
