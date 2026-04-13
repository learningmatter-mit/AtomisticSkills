"""
Template script to save a Surface with Adsorbate to the HTVS database.
"""
import os
import json
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

def run(payload):
    from pgmols.models import Group, Surface, Calc, Method, Crystal
    from jobs.models import Job, JobConfig
    
    group_obj = Group.objects.get(name=payload["group_name"])
    adsorbate_config_obj, _ = JobConfig.objects.get_or_create(name="add_adsorbate")
    
    # We assume bulk and parent surface are already in DB
    bulk_obj = Crystal.objects.get(id=payload["bulk_id"])
    parent_surface = Surface.objects.get(id=payload["parent_id"])
    
    # Create Surface
    surf_w_ads = Surface(
        bulk=bulk_obj,
        miller_index=payload["miller_index"],
        xyz=payload["xyz"],
        lattice=payload["lattice"],
        stoichiometry=payload["stoichiometry"],
        spacegroup=bulk_obj.spacegroup,
        method=bulk_obj.method,
        surface_atoms=payload["surface_atoms"],
        adsorbate_atoms=payload["adsorbate_atoms"],
        details={"B": payload["active_site"]}
    )
    
    chemical_tag = surf_w_ads.generate_hash()
    surf_w_ads.chemical_tag = chemical_tag
    
    if payload.get("magmoms"):
        surf_w_ads.magmoms = payload["magmoms"]
        
    # Check duplicate
    exists = Surface.objects.filter(
        bulk=bulk_obj,
        chemical_tag=chemical_tag,
        parentjob__group=group_obj,
        details__B__contains=payload["active_site"][0] if isinstance(payload["active_site"], list) else payload["active_site"]
    ).first()
    
    if exists:
        return {"status": "exists", "id": exists.id}
        
    # Create Job
    job = Job(
        config=adsorbate_config_obj,
        group=group_obj,
        status="done",
        parentct=ContentType.objects.get_for_model(parent_surface),
        parentid=parent_surface.id,
        completetime=timezone.now(),
    )
    job.save()
    
    surf_w_ads.parentjob = job
    surf_w_ads.save()
    
    # Create Calc
    props = {"magmoms": surf_w_ads.magmoms} if hasattr(surf_w_ads, "magmoms") else {}
    calc = Calc(method=surf_w_ads.method, props=props)
    calc.parentjob = job
    calc.save()
    calc.geoms.add(surf_w_ads)
    
    return {"status": "created", "id": surf_w_ads.id}

if __name__ == "__main__":
    payload_str = os.environ.get("HTVS_PAYLOAD", "{}")
    payload = json.loads(payload_str)
    
    try:
        output = run(payload)
        print(json.dumps(output))
    except Exception as e:
        import traceback
        print(json.dumps({"error": str(e), "traceback": traceback.format_exc()}))
