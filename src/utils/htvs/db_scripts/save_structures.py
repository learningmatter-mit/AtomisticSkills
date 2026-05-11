import os
import json
import numpy as np
from ase import io
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from jobs.models import Job, JobConfig
from pgmols.models import Crystal, Group, Method, Framework, Surface, MillerIndex

# Load payload from environment
payload_str = os.environ.get("HTVS_PAYLOAD")
if not payload_str:
    print(json.dumps({"error": "No HTVS_PAYLOAD found in environment"}))
    exit(1)

try:
    payload = json.loads(payload_str)
except Exception as e:
    print(json.dumps({"error": f"Failed to parse HTVS_PAYLOAD: {str(e)}"}))
    exit(1)

structure_file = payload.get("structure_file")
config_name = payload.get("config_name")
group_name = payload.get("group_name")
method_name = payload.get("method_name")
framework_name = payload.get("framework_name")
structure_type = payload.get("structure_type", "crystal")
parent_bulk_id = payload.get("parent_bulk_id")
miller_index_arg = payload.get("miller_index")
details_arg = payload.get("details")

def get_miller_index(hkl):
    mi, _ = MillerIndex.objects.get_or_create(hkl=hkl)
    return mi

try:
    if not structure_file or not os.path.exists(structure_file):
        print(json.dumps({"error": f"File not found or not specified: {structure_file}"}))
        exit(1)

    samples = io.read(structure_file, ":")
    created_ids = []
    
    group_obj, _ = Group.objects.get_or_create(name=group_name)
    config_obj, _ = JobConfig.objects.get_or_create(name=config_name)
    
    default_method_name = method_name if method_name else "manual_import"
    method_obj, _ = Method.objects.get_or_create(name=default_method_name)
    
    # Process Parent object matching for job lineage
    parent_obj = None
    if structure_type == "surface":
        mi_obj = get_miller_index(miller_index_arg)
        try:
            parent_obj = Surface.objects.get(id=parent_bulk_id)
        except Surface.DoesNotExist:
            try:
                parent_obj = Crystal.objects.get(id=parent_bulk_id)
            except Crystal.DoesNotExist:
                print(json.dumps({"error": f"Parent ID {parent_bulk_id} not found"}))
                exit(1)

    for atoms in samples:
        if structure_type == "crystal":
            obj = Crystal.from_ase_atoms(atoms)
        else:
            obj = Surface.from_ase_atoms(atoms)
            
            if isinstance(parent_obj, Crystal):
                obj.bulk = parent_obj
            elif isinstance(parent_obj, Surface):
                obj.bulk = parent_obj.bulk
                
            if hasattr(parent_obj, "miller_index"):
                obj.miller_index = parent_obj.miller_index
            else:
                obj.miller_index = mi_obj

            if details_arg:
                obj.details = details_arg
                
            if obj.bulk is None:
                print(json.dumps({"error": f"Surface must have a bulk reference. Parent object {parent_obj} did not provide one."}))
                exit(1)
                
            # Comprehensive surface/adsorbate tagging logic
            # Explicit info
            if atoms.info.get("surf_atoms", None) is not None:
                surf_atoms = atoms.info.get("surf_atoms")
                obj.surface_atoms = np.array(surf_atoms, dtype=int).tolist()
                try:
                    obj.adsorbate_atoms = np.array(atoms.ads_atoms, dtype=int).tolist()
                except AttributeError:
                    obj.adsorbate_atoms = (atoms.get_tags() == 2).tolist()
            # method detection
            elif hasattr(atoms, "get_surface_atoms"):
                obj.surface_atoms = np.isin(
                    np.arange(len(atoms)),
                    np.array(atoms.get_surface_atoms(), dtype=int)
                ).tolist()
                try:
                    surf_indices = np.array(atoms.get_adsorbate_atoms(), dtype=int).tolist()
                except AttributeError:
                    surf_indices = []
                obj.adsorbate_atoms = np.isin(np.arange(len(atoms)), surf_indices).tolist()
            # fallback tags
            else:
                tags = atoms.get_tags()
                obj.surface_atoms = (tags == 1).tolist()
                obj.adsorbate_atoms = (tags == 2).tolist()
                
        obj.method = method_obj
        if hasattr(obj, 'generate_hash'):
            obj.chemical_tag = obj.generate_hash()
        
        obj.save() 

        # Create Generic Job
        job_parent = parent_obj if parent_obj else obj
        job = Job(
            config=config_obj,
            group=group_obj,
            method=method_obj,
            status="done",
            parentct=ContentType.objects.get_for_model(job_parent),
            parentid=job_parent.id,
            completetime=timezone.now(),
        )
        job.save()
        
        obj.parentjob = job
        
        # Link Framework
        if framework_name:
            framework, _ = Framework.objects.get_or_create(
                name=framework_name, 
                prototype=obj, 
                group=group_obj
            )
            obj.framework = framework
            
        obj.save()
        created_ids.append(obj.id)
            
    print(json.dumps(created_ids))

except Exception as e:
    import traceback
    # Note: we don't want to print the full traceback to stdout normally 
    # as db_handler.py expects only the JSON response. 
    # But for debugging, we can log it or print to stderr.
    # print(traceback.format_exc(), file=sys.stderr)
    print(json.dumps({"error": str(e)}))
