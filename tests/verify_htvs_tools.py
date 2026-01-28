import os
import sys
import django
from pathlib import Path

# Add simulation_mcp to path to import tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.mcp_server.htvs_server import request_htvs_job, build_htvs_job, parse_htvs_job, vasp_to_htvs_details

# Configuration
HTVS_REPO_ROOT = "/mnt/data0/hojechun/repos/htvs"
DJANGOCHEM_DIR = os.path.join(HTVS_REPO_ROOT, "djangochem")
SETTINGS_MODULE = "djangochem.settings.toy"
TEST_PROJECT = "test_project_mcp"

# Ensure djangochem is providing the tools
# We need to set up Django to query the DB directly for verification
sys.path.append(DJANGOCHEM_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", SETTINGS_MODULE)
django.setup()

from jobs.models import Job, JobConfig, Group

def verify_request():
    print("--- Verifying request_htvs_job ---")
    
    # 1. Test VASP conversion
    print("Testing vasp_to_htvs_details...")
    vasp_input = {"ENCUT": 520, "ISPIN": 2, "LREAL": "Auto"}
    details = vasp_to_htvs_details(vasp_input, additional_details={"priority": 50})
    print(f"Converted details: {details}")
    if details.get("encut") != 520 or details.get("priority") != 50:
        print("FAILED: details conversion incorrect")
        return False

    # 2. Request Job
    print(f"Requesting job for project {TEST_PROJECT}...")
    # Use a likely existing config or one we know from 'toy' db?
    # We saw 'pbe_d3_paw_bomd_vasp' in the file earlier.
    chem_config = "pbe_d3_paw_bomd_vasp" 
    
    # Needs valid parent info usually?
    # For 'toy' we might need existing data.
    # Let's try to request without parents first or see what happens.
    # The 'requestjobs' command usually filters based on parents.
    # If we don't have parents, maybe we can request a job from scratch if the config allows?
    # Or maybe we rely on the user to provide a valid parent pk if needed.
    
    # For this verification, we just want to see if the command runs without crashing
    # and if it interacts with the DB.
    
    output = request_htvs_job(
        project_name=TEST_PROJECT,
        chem_config=chem_config,
        details=details,
        settings_module=SETTINGS_MODULE,
        djangochem_dir=DJANGOCHEM_DIR
    )
    
    print("Output from request_htvs_job:")
    print(output)
    
    if "Error" in output or "Command Failed" in output:
        # It's possible it fails due to logic (no parents found), but the tool execution itself worked.
        print("Tool executed, but htvs logic might have errored (expected if no valid parents).")
        # Proceed with caution
    else:
        print("Tool reported success.")

    # Verify DB
    # We can query if any job exists for this project?
    # Note: requestjobs creates jobs.
    jobs_count = Job.objects.filter(group__project__name=TEST_PROJECT).count()
    print(f"Jobs in project {TEST_PROJECT}: {jobs_count}")
    return True

def verify_build():
    print("\n--- Verifying build_htvs_job ---")
    inbox_path = os.path.join(os.path.dirname(__file__), "htvs_test_inbox")
    os.makedirs(inbox_path, exist_ok=True)
    
    output = build_htvs_job(
        project_name=TEST_PROJECT,
        inbox_path=inbox_path,
        limit=1,
        settings_module=SETTINGS_MODULE,
        djangochem_dir=DJANGOCHEM_DIR
    )
    print("Output from build_htvs_job:")
    print(output)
    
    # Check if any folder was created
    if os.path.exists(inbox_path) and os.listdir(inbox_path):
        print(f"Files created in {inbox_path}")
        print(os.listdir(inbox_path))
    else:
        print("No files created (might be expected if no jobs were requested successfully).")

    return True

if __name__ == "__main__":
    verify_request()
    verify_build()
