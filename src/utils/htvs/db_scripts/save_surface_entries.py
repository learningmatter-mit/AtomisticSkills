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
    
    results = {"success": [], "errors": []}
    
    group_obj = Group.objects.get(name=payload["group_name"])
    config_obj = JobConfig.objects.get(name=payload["config_name"])
    
    entries = payload.get("entries", [])
    
    for entry in entries:
        try:
            bulk_obj = Crystal.objects.get(id=entry["bulk_id"])
            mi_obj, _ = MillerIndex.objects.get_or_create(hkl=entry["miller_index"])
            
            surf = Surface(
                bulk=bulk_obj,
                miller_index=mi_obj,
                xyz=entry["xyz"],
                lattice=entry["lattice"],
                stoichiometry=entry["stoichiometry"],
                spacegroup=bulk_obj.spacegroup,
                method=bulk_obj.method,
                surface_atoms=entry["surface_atoms"],
                adsorbate_atoms=entry["adsorbate_atoms"],
                details=entry.get("details", {})
            )
            
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
