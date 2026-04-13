import os
import json
import sys
from db_common import get_project_group
from jobs.models import Job
from pgmols.models import Crystal, Surface

# Load payload
payload_str = os.environ.get("HTVS_PAYLOAD")
if not payload_str:
    print(json.dumps({"error": "No HTVS_PAYLOAD found"}))
    exit(1)

try:
    payload = json.loads(payload_str)
except Exception as e:
    print(json.dumps({"error": f"Parse error: {str(e)}"}))
    exit(1)

query_type = payload.get("query_type")
group_name = payload.get("group_name")
config_name = payload.get("config_name")
formula = payload.get("formula")
limit = payload.get("limit")
status = payload.get("status")
structure_id = payload.get("structure_id")
structure_type = payload.get("structure_type", "crystal")

def handle_query_results():
    group = get_project_group(group_name)
    if not group:
        return {"error": f"Group '{group_name}' not found"}

    jobs = Job.objects.filter(group=group, status="done").select_related('config')
    if config_name:
        jobs = jobs.filter(config__name=config_name)
    if limit:
        jobs = jobs[:limit]

    results = []
    for job in jobs:
        parent = job.parent
        if not parent:
            continue
        if formula and hasattr(parent, 'stoichiometry') and parent.stoichiometry:
            if parent.stoichiometry.formula != formula:
                continue
        
        results.append({
            "job_id": job.id,
            "uuid": str(job.uuid),
            "config": job.config.name if job.config else "Unknown",
            "formula": parent.stoichiometry.formula if hasattr(parent, 'stoichiometry') and parent.stoichiometry else "Unknown",
            "structure_id": parent.id,
            "structure_type": "surface" if isinstance(parent, Surface) else "crystal",
            "energy": job.energy,
            "forces": job.forces,
            "stress": job.stress,
            "completetime": job.completetime.isoformat() if job.completetime else None
        })
    return results

def handle_query_structures():
    group = get_project_group(group_name)
    if not group:
        return {"error": f"Group '{group_name}' not found"}

    model = Crystal if structure_type.lower() == "crystal" else Surface
    query = model.objects.filter(parentjob__group=group).select_related('stoichiometry', 'parentjob')
    
    if config_name:
        query = query.filter(parentjob__config__name=config_name)
    if formula:
        query = query.filter(stoichiometry__formula=formula)
    if limit:
        query = query[:limit]

    results = []
    for obj in query:
        data = {
            "id": obj.id,
            "formula": obj.stoichiometry.formula if obj.stoichiometry else "Unknown",
            "num_atoms": len(obj.xyz),
            "job_uuid": str(obj.parentjob.uuid) if obj.parentjob else None
        }
        if hasattr(obj, "spacegroup") and obj.spacegroup:
            data["spacegroup"] = obj.spacegroup.symbol
        if hasattr(obj, "miller_index") and obj.miller_index:
            data["miller_index"] = obj.miller_index.hkl
        results.append(data)
    return results

def handle_query_jobs():
    group = get_project_group(group_name)
    if not group:
        return {"error": f"Group '{group_name}' not found"}

    jobs = Job.objects.filter(group=group).select_related('config')
    if status:
        jobs = jobs.filter(status=status)
    if config_name:
        jobs = jobs.filter(config__name=config_name)
    if limit:
        jobs = jobs[:limit]

    results = []
    for job in jobs:
        results.append({
            "job_id": job.id,
            "uuid": str(job.uuid),
            "config": job.config.name if job.config else "Unknown",
            "status": job.status,
            "priority": job.priority,
            "createtime": job.createtime.isoformat() if job.createtime else None,
            "duration": job.duration
        })
    return results

def handle_get_structure():
    model = Crystal if structure_type.lower() == "crystal" else Surface
    try:
        obj = model.objects.get(id=structure_id)
        atoms = obj.to_ase_atoms()
        data = {
            "id": obj.id,
            "numbers": atoms.get_atomic_numbers().tolist(),
            "positions": atoms.get_positions().tolist(),
            "cell": atoms.get_cell().tolist(),
            "pbc": atoms.get_pbc().tolist(),
            "info": {}
        }
        if structure_type.lower() == "surface":
            data["info"]["surface_atoms"] = obj.surface_atoms
            data["info"]["adsorbate_atoms"] = obj.adsorbate_atoms
            if obj.miller_index:
                data["info"]["miller_index"] = obj.miller_index.hkl
        return data
    except Exception as e:
        return {"error": str(e)}

# Dispatch
try:
    if query_type == "results":
        res = handle_query_results()
    elif query_type == "structures":
        res = handle_query_structures()
    elif query_type == "jobs":
        res = handle_query_jobs()
    elif query_type == "get_structure":
        res = handle_get_structure()
    else:
        res = {"error": f"Unknown query_type: {query_type}"}
    
    print(json.dumps(res))
except Exception as e:
    print(json.dumps({"error": str(e)}))
