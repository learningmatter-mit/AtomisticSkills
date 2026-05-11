
"""
Example Workflow for HTVS Submission and Parsing using Python Handlers.

This script demonstrates the recommended way to use the HTVS tools programmatically:
1.  Initialize Handlers
2.  Save Structures to DB
3.  Prepare VASP Job Details using Pymatgen
4.  Submit Jobs via HTVSJobHandler
5.  Build Jobs
6.  Monitor & Parse Results
"""

import os
import sys
import json
import time

# Add repo root to path if running from examples/
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.utils.htvs import HTVSJobHandler, HTVSVaspHandler, HTVSDbHandler

# --- 1. Configuration ---
# These should be confirmed with the user or loaded from environment
SETTINGS_MODULE = os.environ.get("DJANGO_SETTINGS_MODULE", "djangochem.settings.toy")
GROUP_NAME = "agent_example_group"
CONFIG_NAME = "pbe_d3_paw_engrad_vasp" # "pbe_d3_paw_opt_vasp" for relaxation
COMPUTE_PLATFORM = "perlmutter"
REQUESTER = os.environ.get("USER", "agent")
INBOX_PATH = os.environ.get("HTVS_INBOX", "/tmp/htvs_inbox") # Should be cluster path
PROJECT_NAME = "m5068" # Required for Perlmutter

# Ensure inbox exists
os.makedirs(INBOX_PATH, exist_ok=True)

def run_workflow():
    print(f"--- Starting HTVS Workflow: {GROUP_NAME} ---")
    
    # Initialize Handlers
    db_handler = HTVSDbHandler(SETTINGS_MODULE)
    job_handler = HTVSJobHandler(SETTINGS_MODULE)
    vasp_handler = HTVSVaspHandler()
    
    # --- 2. Save Structure ---
    # Create a dummy structure for demonstration if none exists
    structure_file = "example.cif"
    if not os.path.exists(structure_file):
        from ase.build import bulk
        from ase.io import write
        atoms = bulk("Cu", "fcc", a=3.6)
        write(structure_file, atoms)
        print(f"Created dummy structure: {structure_file}")
        
    print("Saving structure to DB...")
    # Using 'auto' logic to detect Crystal vs Surface
    # result is a JSON string with list of IDs
    save_result = db_handler.save_structures(
        structure_path=structure_file,
        config_name="agent_generated",
        group_name=GROUP_NAME,
        structure_type="crystal" 
    )
    print(f"Save Result: {save_result}")
    
    # Parse IDs from result
    try:
        res_data = json.loads(save_result)
        # Handle 'structures' list format from save_structures
        if "structures" in res_data:
            structure_ids = res_data["structures"][0]["ids"]
            structure_id = structure_ids[0]
        else:
            # Fallback if manual save_crystals was used
            structure_ids = res_data
            structure_id = structure_ids[0]
            
        print(f"Structure ID: {structure_id}")
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Failed to parse structure ID: {e}")
        return

    # --- 3. Prepare VASP Details ---
    print("Generating VASP details...")
    # Use HTVSVaspHandler which wraps Pymatgen sets
    details_json = vasp_handler.generate_details(
        structure_file=structure_file,
        preset_type="omat", # or "mp", "matpes-pbe"
        calculation_type="static", # or "relaxation"
        magnetism=True
    )
    details = json.loads(details_json)
    
    # Add platform specific details
    details.update({
        "compute_platform": COMPUTE_PLATFORM,
        "requester": REQUESTER,
        "priority": 100,
        "project_name": PROJECT_NAME,
        # "pseudo_dir": "/path/to/potcars" # Uncomment and set if needed
    })
    
    # --- 4. Submit Job ---
    print("Requesting Job...")
    req_result = job_handler.request_job(
        group_name=GROUP_NAME,
        chem_config=CONFIG_NAME,
        details=details,
        requester=REQUESTER,
        parent_pks=[structure_id],
        parent_config="agent_generated"
    )
    print(f"Request Result: {req_result}")
    
    # --- 5. Build Job ---
    print("Building Job...")
    build_result = job_handler.build_jobs(
        group_name=GROUP_NAME,
        inbox_path=INBOX_PATH,
        config_name=CONFIG_NAME,
        compute_platform=COMPUTE_PLATFORM
    )
    print(f"Build Result: {build_result}")
    
    # --- 6. Parse Results (Once Complete) ---
    print("\n--- Parsing Phase (Simulated) ---")
    print("In a real scenario, you would wait for jobs to complete on the cluster.")
    print("Then you run:")
    
    print(f"""
    job_handler.parse_jobs(
        group_name="{GROUP_NAME}",
        completed_path="/path/to/completed_jobs",
        config_name="{CONFIG_NAME}"
    )
    """)
    
    print("\n--- Retrieving Results from DB ---")
    # This script demonstrates how to query the DB for results after parsing
    # We can embed this as a script to run in the django environment
    
    query_script = f'''
import json
from jobs.models import Job, JobConfig
from pgmols.models import SinglePoint, Group

group_name = "{GROUP_NAME}"
config_name = "{CONFIG_NAME}"

try:
    group = Group.objects.get(name=group_name)
    config = JobConfig.objects.get(name=config_name)
    
    # Filter completed jobs
    jobs = Job.objects.filter(group=group, config=config, status="done")
    
    results = []
    for job in jobs:
        # Get energy from SinglePoint child calculation
        calcs = job.childcalcs.instance_of(SinglePoint)
        if calcs.exists():
            calc = calcs.first()
            
            # Get output geometry if available
            geom = calc.geoms.first()
            coords = geom.xyz if geom else None
            
            results.append({{
                "job_id": job.id,
                "parent_id": job.parent.id,
                "energy": calc.energy,
                "coords": coords
            }})
            
    print(json.dumps(results, indent=2))

except Exception as e:
    print(json.dumps({{"error": str(e)}}))
'''
    # We can run this query script using run_htvs_script from utils
    # (Not running it now as jobs are not actually completed/parsed)
    print("Query Script Preview:")
    print(query_script)

    # Cleanup dummy file
    if os.path.exists(structure_file):
        os.remove(structure_file)

if __name__ == "__main__":
    run_workflow()
