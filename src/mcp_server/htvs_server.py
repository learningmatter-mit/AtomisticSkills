import json
import os
import sys
import subprocess
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("htvs")

# Default mapping from VASP INCAR tags (uppercase) to HTVS 'details' keys (lowercase)
# This is based on common usage in HTVS templates (e.g., jobspec.py and INCAR templates)
VASP_TO_HTVS_MAPPING = {
    "ENCUT": "encut",
    "ISMEAR": "ismear",
    "SIGMA": "sigma",
    "ISPIN": "ispin",
    "LORBIT": "lorbit",
    "LREAL": "lreal",
    "NSW": "nsteps", # NSW in INCAR maps to nsteps in details
    "IBRION": "ibrion",
    "ISIF": "isif",
    "EDIFF": "ediff",
    "EDIFFG": "ediffg",
    "POTIM": "timestep",
    "TEBEG": "temperature",
    "ALGO": "algo",
    "PREC": "prec",
    "KPOINT_DENSITY": "kppa", # standard pymatgen/atomate naming -> htvs kppa
    "KPOINTS": "kpoints", # Explicit kpoints list
}

@mcp.tool()
def vasp_to_htvs_details(vasp_input: Dict[str, Any], additional_details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Converts standard VASP input parameters (INCAR tags) to the 'details' dictionary format
    expected by HTVS templates.

    Args:
        vasp_input: Dictionary of VASP INCAR tags (e.g., {'ENCUT': 500, 'ISPIN': 2})
        additional_details: Optional dictionary of extra HTVS-specific details 
                           (e.g., {'compute_platform': 'slurm', 'priority': 100})

    Returns:
        A dictionary ready to be passed as the 'details' argument to request_htvs_job.
    """
    details = {}
    
    # 1. Map standard VASP tags
    for vasp_tag, value in vasp_input.items():
        htvs_key = VASP_TO_HTVS_MAPPING.get(vasp_tag, vasp_tag.lower())
        details[htvs_key] = value

    # 2. Handle specific complex mappings if necessary
    # Example: If user passes 'user_kpoints_settings' for KPOINTS, we might need logic here.
    # For now, simplistic mapping is a good start.

    # 3. Merge additional details
    if additional_details:
        details.update(additional_details)

    return details


@mcp.tool()
def request_htvs_job(
    project_name: str,
    chem_config: str,
    details: Dict[str, Any],
    parent_pks: Optional[List[int]] = None,
    parent_config: Optional[str] = None,
    requester: Optional[str] = None,
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Requests a new HTVS job by calling 'python manage.py requestjobs'.

    Args:
        project_name: The name of the project.
        chem_config: The name of the chemical configuration (e.g., 'pbe_d3_paw_bomd_vasp').
        details: A dictionary of job details (will be converted to JSON string).
        parent_pks: List of parent job primary keys (optional).
        parent_config: Name of the parent configuration (optional).
        requester: Name of the user requesting the job (optional).
        settings_module: Django settings module to use.
        djangochem_dir: Path to the directory containing manage.py. 
                        If None, uses 'HTVS_DJANGOCHEM_DIR' env var or defaults to current working dir.

    Returns:
        The output of the command (stdout).
    """
    
    # Resolve manage.py location
    if djangochem_dir is None:
        djangochem_dir = os.environ.get("HTVS_DJANGOCHEM_DIR", os.getcwd())
    
    manage_py_path = os.path.join(djangochem_dir, "manage.py")
    if not os.path.exists(manage_py_path):
         return f"Error: manage.py not found at {manage_py_path}. Please provide correct djangochem_dir."

    # Construct command
    cmd = [
        sys.executable, manage_py_path, "requestjobs",
        project_name,
        chem_config,
        "--settings", settings_module,
        "--details", json.dumps(details)
    ]

    if requester:
        cmd.extend(["--requester", requester])

    if parent_pks:
        # Convert list of ints to space-separated strings
        cmd.extend(["--parentpks"] + [str(pk) for pk in parent_pks])
    
    if parent_config:
        cmd.extend(["--parent_config", parent_config])
        
    # Check for force in details or separate arg?
    # Usually requestjobs has --force.
    # Let's check logic: explicit --force flag in command line.
    if details.get("force", False):
         cmd.append("--force")

    try:
        # Run command
        # We assume the environment is already set up (conda activated)
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=djangochem_dir, # Run from djangochem dir to be safe
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        if result.returncode != 0:
            return f"Command Failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        
        return f"Success:\n{result.stdout}"

    except Exception as e:
        return f"Execution Error: {str(e)}"


@mcp.tool()
def build_htvs_job(
    project_name: str,
    inbox_path: str,
    config_name: Optional[str] = None,
    limit: Optional[int] = None,
    compute_platform: Optional[str] = None,
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Builds requested HTVS jobs (creates files in inbox) by calling 'python manage.py buildjobs'.

    Args:
        project_name: The name of the project.
        inbox_path: The directory where job folders should be created.
        config_name: Filter by specific configuration name (optional).
        limit: Max number of jobs to build (optional).
        compute_platform: Compute platform string (e.g., 'slurm', 'local') (optional).
        settings_module: Django settings module to use.
        djangochem_dir: Path to directory containing manage.py.

    Returns:
        The output of the command.
    """
    if djangochem_dir is None:
        djangochem_dir = os.environ.get("HTVS_DJANGOCHEM_DIR", os.getcwd())
    
    manage_py_path = os.path.join(djangochem_dir, "manage.py")
    if not os.path.exists(manage_py_path):
         return f"Error: manage.py not found at {manage_py_path}."

    cmd = [
        sys.executable, manage_py_path, "buildjobs",
        project_name,
        inbox_path,
        "--settings", settings_module,
    ]

    if config_name:
        cmd.extend(["--config", config_name])
    
    if limit is not None:
         cmd.extend(["--limit", str(limit)])

    if compute_platform:
        cmd.extend(["--compute_platform", compute_platform])

    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=djangochem_dir,
             env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        if result.returncode != 0:
            return f"Command Failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        
        return f"Success:\n{result.stdout}"

    except Exception as e:
        return f"Execution Error: {str(e)}"


@mcp.tool()
def parse_htvs_job(
    project_name: str,
    completed_path: str,
    config_name: Optional[str] = None,
    limit: Optional[int] = None,
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Parses completed HTVS jobs by calling 'python manage.py parsejobs'.

    Args:
        project_name: The name of the project.
        completed_path: The directory containing completed job folders.
        config_name: Filter by specific configuration name (optional).
        limit: Max number of jobs to parse (optional).
        settings_module: Django settings module to use.
        djangochem_dir: Path to directory containing manage.py.

    Returns:
        The output of the command.
    """
    if djangochem_dir is None:
        djangochem_dir = os.environ.get("HTVS_DJANGOCHEM_DIR", os.getcwd())
    
    manage_py_path = os.path.join(djangochem_dir, "manage.py")
    if not os.path.exists(manage_py_path):
         return f"Error: manage.py not found at {manage_py_path}."

    cmd = [
        sys.executable, manage_py_path, "parsejobs",
        project_name,
        completed_path,
        "--settings", settings_module,
    ]

    if config_name:
        cmd.extend(["--config", config_name])
    
    if limit is not None:
         cmd.extend(["--limit", str(limit)])

    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=djangochem_dir,
             env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        if result.returncode != 0:
            return f"Command Failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        
        return f"Success:\n{result.stdout}"

    except Exception as e:
        return f"Execution Error: {str(e)}"

import tempfile

if __name__ == "__main__":
    mcp.run()
    
    
def run_htvs_script(
    script_body: str, 
    settings_module: str = "djangochem.settings.orgel", 
    djangochem_dir: Optional[str] = None
) -> str:
    """
    Executes a python script within the HTVS django environment.
    
    Args:
        script_body: The python code to execute.
        settings_module: The settings module to use.
        djangochem_dir: The directory containing manage.py.
        
    Returns:
        The stdout of the execution or error message.
    """
    if djangochem_dir is None:
        djangochem_dir = os.environ.get("HTVS_DJANGOCHEM_DIR", os.getcwd())

    # Create a temporary python file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
        temp_file_path = temp_file.name
        
        # Write boilerplate code to setup django
        boilerplate = f"""
import sys
import os
import django
import json

sys.path.append("{djangochem_dir}")
sys.path.append(os.path.abspath(os.path.join("{djangochem_dir}", "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{settings_module}")
django.setup()

"""
        temp_file.write(boilerplate + script_body)
        
    try:
        # Run the temporary file using the same python interpreter (or standard python)
        # We assume 'python' in the environment is the correct one for HTVS if not specified otherwise
        result = subprocess.run(
            [sys.executable, temp_file_path],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        if result.returncode != 0:
             return f"Script Execution Failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        
        return result.stdout.strip()
        
    except Exception as e:
        return f"Execution Error: {str(e)}"
    finally:
        # Clean up
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@mcp.tool()
def list_htvs_configs(
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Lists all available JobConfigs in the HTVS database.
    
    Returns:
        JSON string containing list of configs with 'name' and 'parent_class_name'.
    """
    script = """
from jobs.models import JobConfig
configs = JobConfig.objects.all().values('name', 'parent_class_name')
print(json.dumps(list(configs), indent=2))
"""
    return run_htvs_script(script, settings_module, djangochem_dir)


@mcp.tool()
def get_htvs_job_status(
    job_uuids: Optional[List[str]] = None,
    project_name: Optional[str] = None,
    limit: int = 10,
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Get the status of HTVS jobs.
    
    Args:
        job_uuids: List of job UUIDs to check.
        project_name: Project name to filter by (if job_uuids not provided).
        limit: Max number of jobs to return when filtering by project.
        
    Returns:
        JSON string mapping UUIDs to status.
    """
    script = f"""
from jobs.models import Job
from django.db.models import Q
import json

results = {{}}
uuids = {json.dumps(job_uuids) if job_uuids else 'None'}
project_name = "{project_name}" if {1 if project_name else 0} else None
limit = {limit}

if uuids:
    jobs = Job.objects.filter(uuid__in=uuids)
    for job in jobs:
        results[str(job.uuid)] = job.status
elif project_name:
    jobs = Job.objects.filter(group__name=project_name).order_by('-createtime')[:limit]
    for job in jobs:
        results[str(job.uuid)] = job.status

print(json.dumps(results, indent=2))
"""
    return run_htvs_script(script, settings_module, djangochem_dir)


@mcp.tool()
def get_htvs_job_results(
    job_uuids: List[str],
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Get results for specific HTVS jobs.
    
    Args:
        job_uuids: List of job UUIDs to retrieve results for.
        
    Returns:
        JSON string containing job details and results.
    """
    script = f"""
from jobs.models import Job
import json
from django.core.serializers.json import DjangoJSONEncoder

uuids = {json.dumps(job_uuids)}
results = {{}}

jobs = Job.objects.filter(uuid__in=uuids)

for job in jobs:
    job_data = {{
        "uuid": str(job.uuid),
        "status": job.status,
        "config": job.config.name if job.config else None,
        "details": job.details,
    }}
    
    # Try to fetch associated results based on parent type or children
    # This is a simplified fetch - strictly getting Job details and maybe checking for simple properties
    # Deeper result parsing (like parsing the Geom props directly) might be needed depending on usage
    
    results[str(job.uuid)] = job_data

print(json.dumps(results, indent=2, cls=DjangoJSONEncoder))
"""
    return run_htvs_script(script, settings_module, djangochem_dir)


@mcp.tool()
def save_htvs_structures(
    structure_file: str,
    config_name: str,
    parent_bulk_id: int,
    miller_index: Optional[List[int]] = None,
    group_name: str = "default_group",
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Saves structures from a file to the HTVS database as Surfaces, creating jobs for them.
    
    Args:
        structure_file: Absolute path to the structure file (must be readable by ase.io).
        config_name: Name of the JobConfig to use.
        parent_bulk_id: ID of the parent Crystal or Surface in the DB.
        miller_index: List of 3 integers for Miller index (e.g. [1, 1, 1]). Defaults to [0, 0, 1].
        group_name: Name of the project/group.
        
    Returns:
        JSON string containing list of created Surface IDs.
    """
    if miller_index is None:
        miller_index = [0, 0, 1]
        
    script = f"""
import os
import json
import numpy as np
from ase import io
from tqdm import tqdm
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from jobs.models import Job, JobConfig
from pgmols.models import Calc, Crystal, Group, MillerIndex, Surface

structure_file = "{structure_file}"
config_name = "{config_name}"
parent_bulk_id = {parent_bulk_id}
miller_index_arg = {miller_index}
group_name = "{group_name}"

def get_miller_index(hkl):
    miller_indexes = MillerIndex.objects.filter(hkl=hkl)
    if miller_indexes.count() == 0:
        mi = MillerIndex(hkl=hkl)
        mi.save()
        return mi
    else:
        return miller_indexes.first()

def get_jobconfig(name):
    jc, created = JobConfig.objects.get_or_create(name=name)
    return jc

def get_group(name):
    g, created = Group.objects.get_or_create(name=name)
    return g

def create_job(parent, group_obj, config_obj):
    return Job(
        config=config_obj,
        group=group_obj,
        status="done",
        parentct=ContentType.objects.get_for_model(parent),
        parentid=parent.id,
        completetime=timezone.now(),
    )

def create_surface_object(structure, config_obj, parent_id, miller_idx_obj, group_obj):
    surf = Surface.from_ase_atoms(structure, reorder=True)
    
    # Try finding parent
    try:
        parent = Surface.objects.get(id=parent_id)
    except Surface.DoesNotExist:
        try:
            parent = Crystal.objects.get(id=parent_id)
        except Crystal.DoesNotExist:
            print(f"Error: Parent with id {{parent_id}} not found (checked Surface and Crystal)")
            return None

    if hasattr(parent, 'method'):
        surf.method = parent.method
        
    if hasattr(parent, "miller_index"):
        surf.miller_index = parent.miller_index
    else:
        surf.miller_index = miller_idx_obj
        
    surf.chemical_tag = surf.generate_hash()
    
    # Handle surface/adsorbate atoms tagging
    if structure.info.get("surf_atoms", None) is not None:
        surf_atoms = structure.info.get("surf_atoms")
        surf.surface_atoms = np.array(surf_atoms, dtype=int).tolist()
        try:
            surf.adsorbate_atoms = np.array(structure.ads_atoms, dtype=int).tolist()
        except AttributeError:
             # structure.get_tags() == 2 logic from user script seems specific to their construction
             # Defaulting to False/Empty if not found, or relying on tags if available
             tags = structure.get_tags()
             surf.adsorbate_atoms = (tags == 2).tolist()
    elif hasattr(structure, "get_surface_atoms"):
        surf.surface_atoms = np.isin(
            np.arange(len(structure)),
            np.array(structure.get_surface_atoms(), dtype=int),
        ).tolist()
        try:
            surf_indices = np.array(structure.get_adsorbate_atoms(), dtype=int).tolist()
        except AttributeError:
            surf_indices = []
        surf.adsorbate_atoms = np.isin(np.arange(len(structure)), surf_indices).tolist()
    else:
        # Fallback to tags
        tags = structure.get_tags()
        surf.surface_atoms = (tags == 1).tolist()
        surf.adsorbate_atoms = (tags == 2).tolist()

    # Create Job
    job = create_job(parent, group_obj, config_obj)
    job.save()
    
    surf.parentjob = job
    surf.save()
    return surf.id

# Main Execution
try:
    if not os.path.exists(structure_file):
        print(json.dumps({{"error": f"File not found: {{structure_file}}"}}))
        exit(1)

    samples = io.read(structure_file, ":")
    created_ids = []
    
    config_obj = get_jobconfig(config_name)
    group_obj = get_group(group_name)
    miller_idx_obj = get_miller_index(miller_index_arg)
    
    for sample in samples:
        sid = create_surface_object(sample, config_obj, parent_bulk_id, miller_idx_obj, group_obj)
        if sid is not None:
            created_ids.append(sid)
            
    print(json.dumps(created_ids))

except Exception as e:
    import traceback
    traceback.print_exc()
    print(json.dumps({{"error": str(e)}}))
"""
    return run_htvs_script(script, settings_module, djangochem_dir)

@mcp.tool()
def inspect_chem_config(config_name: str, htvs_repo_root: Optional[str] = None) -> str:
    """
    Inspects the job script (job.sh) for a given chemical configuration.
    Useful for determining cluster requirements (compute_platform, partitions, etc.).

    Args:
        config_name: The name of the configuration (e.g., 'pbe_d3_paw_bomd_vasp').
        htvs_repo_root: Path to the HTVS repository root. 
                        Defaults to '/home/hojechun/ssd_mnt/repos/htvs' if not provided.

    Returns:
        The content of the job.sh file, or an error message if not found.
    """
    if htvs_repo_root is None:
        htvs_repo_root = "/home/hojechun/ssd_mnt/repos/htvs"
    
    chemconfigs_root = os.path.join(htvs_repo_root, "chemconfigs")
    if not os.path.exists(chemconfigs_root):
        return f"Error: chemconfigs directory not found at {chemconfigs_root}"

    # Search for the config directory
    found_path = None
    for root, dirs, files in os.walk(chemconfigs_root):
        if config_name in dirs:
            found_path = os.path.join(root, config_name)
            break
    
    if not found_path:
        return f"Error: Configuration '{config_name}' not found in {chemconfigs_root}"
    
    job_sh_path = os.path.join(found_path, "job.sh")
    if not os.path.exists(job_sh_path):
        return f"Error: job.sh not found in {found_path}"
    
    try:
        with open(job_sh_path, "r") as f:
            content = f.read()
        return f"Found config at: {found_path}\n\n--- job.sh content ---\n{content}"
    except Exception as e:
        return f"Error reading job.sh: {str(e)}"


@mcp.tool()
def create_htvs_group(
    group_name: str,
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Creates a new Group (Project) in the HTVS database if it doesn't exist.
    
    Args:
        group_name: Name of the group to create.
        settings_module: Django settings module to use (default: 'djangochem.settings.orgel').
        djangochem_dir: Path to directory containing manage.py.
    
    Returns:
        JSON string indicating if the group was created or already existed.
    """
    script = f"""
import json
from django.contrib.auth.models import Group

group_name = "{group_name}"
group, created = Group.objects.get_or_create(name=group_name)

print(json.dumps({{"name": group.name, "created": created}}))
"""
    return run_htvs_script(script, settings_module, djangochem_dir)


@mcp.tool()
def query_htvs_structures(
    group_name: str,
    structure_type: str = "Crystal",
    limit: int = 10,
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Query structures in the HTVS database.
    
    Args:
        group_name: Name of the project/group (e.g., 'perovskite').
        structure_type: Type of structure: 'Crystal', 'Surface', 'Species', 'Geom'. Default 'Crystal'.
        limit: Max number of results.
        
    Returns:
        JSON string list of structure summaries.
    """
    script = f"""
import json
from pgmols.models import Crystal, Surface, Species, Geom, Group
from django.db.models import Q

group_name = "{group_name}"
structure_type = "{structure_type}"
limit = {limit}

try:
    group = Group.objects.get(name=group_name)
except Group.DoesNotExist:
    # Avoid nested f-string complexity by using concatenation
    print(json.dumps({{"error": "Group '" + group_name + "' not found"}}))
    exit(0)

results = []

if structure_type == "Crystal":
    qs = Crystal.objects.filter(Q(species__group=group) | Q(parentjob__group=group))[:limit]
    for obj in qs:
        # Stoichiometry might be null? usually not for Crystal
        formula = obj.stoichiometry.formula if obj.stoichiometry else "Unknown"
        sg = obj.spacegroup.symbol if obj.spacegroup else "Unknown"
        results.append({{
            "id": obj.id,
            "type": "Crystal",
            "formula": formula,
            "spacegroup": sg,
            "parentjob_id": obj.parentjob.id if (hasattr(obj, 'parentjob') and obj.parentjob) else None
        }})

elif structure_type == "Surface":
    qs = Surface.objects.filter(Q(species__group=group) | Q(parentjob__group=group))[:limit]
    for obj in qs:
        formula = obj.stoichiometry.formula if obj.stoichiometry else "Unknown"
        results.append({{
            "id": obj.id,
            "type": "Surface",
            "formula": formula,
            "miller_index": obj.miller_index.hkl if obj.miller_index else None
        }})

elif structure_type == "Species":
    qs = Species.objects.filter(group=group)[:limit]
    for obj in qs:
        formula = obj.stoichiometry.formula if obj.stoichiometry else "Unknown"
        results.append({{
            "id": obj.id,
            "type": "Species",
            "formula": formula,
            "smiles": obj.smiles,
            "inchikey": obj.inchikey
        }})

elif structure_type == "Geom":
    qs = Geom.objects.filter(Q(species__group=group) | Q(parentjob__group=group), parentjob__status='done')[:limit]
    for obj in qs:
        formula = obj.stoichiometry.formula if obj.stoichiometry else "Unknown"
        results.append({{
            "id": obj.id,
            "type": "Geom",
            "formula": formula,
        }})

print(json.dumps(results, indent=2))
"""
    return run_htvs_script(script, settings_module, djangochem_dir)

@mcp.tool()
def save_htvs_crystals(
    structure_file: str,
    group_name: str,
    config_name: str = "pbe_d3_paw_bomd_vasp",
    settings_module: str = "djangochem.settings.orgel",
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Saves a structure file (cif, xyz, etc.) to the HTVS database as 'Crystal' objects.
    Useful for importing bulk structures (like SQS alloys) to start a workflow.
    
    Args:
        structure_file: Absolute path to the structure file.
        group_name: Name of the group (Project) to assign the crystals to.
        config_name: Name of the JobConfig to associate with the import job (default: 'pbe_d3_paw_bomd_vasp').
        settings_module: Django settings module to use.
        djangochem_dir: Path to directory containing manage.py.
    
    Returns:
        JSON string of list of created Crystal IDs.
    """
    script = f"""
import os
import json
import sys
import numpy as np
from ase import io
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

# Models
from pgmols.models import Crystal, Method, Species, Geom
from django.contrib.auth.models import Group
from jobs.models import Job, JobConfig

structure_file = "{structure_file}"
group_name = "{group_name}"
config_name = "{config_name}"

def get_jobconfig(name):
    try:
        return JobConfig.objects.get(name=name)
    except JobConfig.DoesNotExist:
        # Fallback to first available if specific one not found, or error?
        # Better to error to be safe
        raise ValueError(f"JobConfig '{{name}}' not found")

def get_group(name):
    try:
        return Group.objects.get(name=name)
    except Group.DoesNotExist:
        raise ValueError(f"Group '{{name}}' not found")

def get_method():
    # Get or create a default method for manual uploads
    m, created = Method.objects.get_or_create(name="manual_upload")
    return m

def create_job(group_obj, config_obj):
    # Create a dummy job to act as parent
    j = Job(
        group=group_obj,
        config=config_obj,
        status='done',
        details={{'comments': f'Imported from {{structure_file}}', 'name': 'Import Job'}},
        createtime=timezone.now(),
        completetime=timezone.now()
    )
    j.save()
    return j

def create_crystal_object(atoms, group_obj, config_obj, method_obj):
    # unexpected argument 'spacegroup_number' in Crystal.from_ase_atoms? 
    # Checked pgmols/models.py: def from_ase_atoms(cls, atoms: Atoms, spacegroup_number: int | None = None) -> Crystal:
    # So we can pass None implicitly.
    
    crystal = Crystal.from_ase_atoms(atoms)
    crystal.method = method_obj
    
    # Needs a parent job
    job = create_job(group_obj, config_obj)
    crystal.parentjob = job
    
    # Save
    crystal.save()
    return crystal.id

# Main
try:
    if not os.path.exists(structure_file):
        print(json.dumps({{"error": f"File not found: {{structure_file}}"}}))
        exit(1)

    atoms_list = io.read(structure_file, ":")
    created_ids = []
    
    config_obj = get_jobconfig(config_name)
    group_obj = get_group(group_name)
    method_obj = get_method()
    
    for atoms in atoms_list:
        cid = create_crystal_object(atoms, group_obj, config_obj, method_obj)
        created_ids.append(cid)
        
    print(json.dumps(created_ids))

except Exception as e:
    import traceback
    traceback.print_exc()
    print(json.dumps({{"error": str(e)}}))
"""
    return run_htvs_script(script, settings_module, djangochem_dir)

if __name__ == "__main__":
    mcp.run()
