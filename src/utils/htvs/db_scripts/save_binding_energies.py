"""
Template script to save BindingEnergy records to the HTVS database.
Payload contains a list of energy records to save/update.
"""
import os
import json
import logging
from django.utils import timezone

def run(payload):
    from docking.models import BindingEnergy, AffinityType
    from pgmols.models import Surface
    
    results = {"success": [], "errors": []}
    
    metric_name = payload.get("metric", "surface_binding_dE")
    metric_obj, _ = AffinityType.objects.get_or_create(name=metric_name)
    
    entries = payload.get("entries", [])
    
    for entry in entries:
        try:
            clean_surf = Surface.objects.get(id=entry["clean_id"])
            ads_surf = Surface.objects.get(id=entry["ads_id"])
            
            be, created = BindingEnergy.objects.get_or_create(
                metric=metric_obj,
                clean_surface=clean_surf,
                surface_w_adsorbate=ads_surf,
                defaults={
                    "value": entry["value"],
                    "units": entry.get("units", "Ha"),
                    "adsorbate": entry["adsorbate"]
                }
            )
            
            if not created:
                be.value = entry["value"]
                be.save()
                
            results["success"].append(be.id)
            
        except Exception as e:
            results["errors"].append({"entry": entry, "error": str(e)})
            
    return results

if __name__ == "__main__":
    payload_str = os.environ.get("HTVS_PAYLOAD", "{}")
    payload = json.loads(payload_str)
    
    try:
        from src.utils.htvs.script_runner import setup_django
        # setup_django is called by the runner already
        output = run(payload)
        print(json.dumps(output))
    except Exception as e:
        import traceback
        print(json.dumps({"error": str(e), "traceback": traceback.format_exc()}))
