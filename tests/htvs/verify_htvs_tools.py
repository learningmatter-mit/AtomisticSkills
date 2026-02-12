import os
import sys
import django
from pathlib import Path

# Add simulation_mcp to path to import tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.mcp_server.htvs_server import (
    request_htvs_job, 
    build_htvs_job, 
    parse_htvs_job, 
    vasp_to_htvs_details,
    save_htvs_crystals,
    save_htvs_surfaces
)

# Configuration
HTVS_REPO_ROOT = os.environ.get("HTVS_DIR", "/home/hojechun/ssd_mnt/repos/htvs")
DJANGOCHEM_DIR = os.environ.get("HTVS_DJANGOCHEM_DIR", os.path.join(HTVS_REPO_ROOT, "djangochem"))
SETTINGS_MODULE = "djangochem.settings.toy"
TEST_GROUP = "test_group_mcp"

# Ensure djangochem is providing the tools
sys.path.append(DJANGOCHEM_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", SETTINGS_MODULE)
django.setup()

from jobs.models import Job, JobConfig
from pgmols.models import Group, Crystal, Surface

# Ensure Group and Config exist
try:
    group, _ = Group.objects.get_or_create(name=TEST_GROUP)
    print(f"Ensured group '{TEST_GROUP}' exists.")
    
    config, _ = JobConfig.objects.get_or_create(
        name="manual_import",
        defaults={"parent_class_name": "GenericConfig"} 
    )
    print(f"Ensured config 'manual_import' exists.")
except Exception as e:
    print(f"Warning during setup: {e}")

# Create dummy CIF file
TEST_CIF = os.path.join(os.path.dirname(__file__), "test_structure.cif")
with open(TEST_CIF, "w") as f:
    f.write("""data_test
_cell_length_a 4.0
_cell_length_b 4.0
_cell_length_c 4.0
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
loop_
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Si 0.0 0.0 0.0
""")

def cleanup():
    if os.path.exists(TEST_CIF):
        os.remove(TEST_CIF)
    inbox = os.path.join(os.path.dirname(__file__), "htvs_test_inbox")
    import shutil
    if os.path.exists(inbox):
        shutil.rmtree(inbox)


def verify_request():
    print("--- Verifying request_htvs_job ---")
    
    # 1. Test VASP conversion
    print("Testing vasp_to_htvs_details...")
    
    # 1a. Explicit input
    vasp_input = {"ENCUT": 520, "ISPIN": 2, "LREAL": "Auto"}
    # Add force to pass job request without parent config
    details = vasp_to_htvs_details(vasp_input, additional_details={"priority": 50, "force": True})
    print(f"Converted details (explicit): {details}")
    if details.get("encut") != 520 or details.get("priority") != 50:
        print("FAILED: details conversion incorrect")
        return False
        
    # 1b. Structure-based input (Implicitly tests gen logic from handler)
    structure_file = os.path.join(os.path.dirname(__file__), "test_structure.cif")
    if os.path.exists(structure_file):
        print("Testing vasp_to_htvs_details with structure...")
        details_struct = vasp_to_htvs_details(
            structure_file=structure_file,
            preset_type="mp",
            calculation_type="static"
        )
        print(f"Converted details (structure): {details_struct}")
        # Check for MPStaticSet defaults (e.g. ALGO=Fast, LREAL=Auto)
        if details_struct.get("algo") != "Fast" or details_struct.get("lreal") != "Auto":
             print("FAILED: structure-based details incorrect")
             return False
    else:
        print("Warning: test_structure.cif not found, skipping structure test.")

    # 1c. Merge explicit + structure
    if os.path.exists(structure_file):
        print("Testing vasp_to_htvs_details merge...")
        details_merge = vasp_to_htvs_details(
            vasp_input={"ALGO": "VeryFast"}, # Override defaults
            structure_file=structure_file,
            preset_type="mp"
        )
        if details_merge.get("algo") != "VeryFast":
             print("FAILED: merge override incorrect")
             return False


    # 2. Request Job
    print(f"Requesting job for group {TEST_GROUP}...")
    chem_config = "pbe_d3_paw_bomd_vasp" 
    
    output = request_htvs_job(
        group_name=TEST_GROUP,
        chem_config=chem_config,
        details=details,
        settings_module=SETTINGS_MODULE,
        djangochem_dir=DJANGOCHEM_DIR
    )
    
    print("Output from request_htvs_job:")
    print(output)
    
    # Verify DB
    jobs_count = Job.objects.filter(group__name=TEST_GROUP).count()
    print(f"Jobs in group {TEST_GROUP}: {jobs_count}")
    return True

def verify_save():
    print("\n--- Verifying save tools ---")
    # Path to a test structure (re-use one from project if possible)
    structure_file = os.path.join(os.path.dirname(__file__), "test_structure.cif")
    
    if not os.path.exists(structure_file):
        print(f"Skipping save verification: {structure_file} not found")
        return True

    print("Checking save_htvs_crystals...")
    crystals_json = save_htvs_crystals(
        structure_file=structure_file,
        config_name="manual_import",
        group_name=TEST_GROUP,
        settings_module=SETTINGS_MODULE,
        method_name="verify_method",
        framework_name="verify_framework"
    )
    print(f"Created Crystal IDs: {crystals_json}")

    import json
    crystal_ids = json.loads(crystals_json)
    if crystal_ids and isinstance(crystal_ids, list):
        parent_id = crystal_ids[0]
        print(f"Checking save_htvs_surfaces for parent {parent_id}...")
        surfaces_json = save_htvs_surfaces(
            structure_file=structure_file,
            config_name="manual_import",
            parent_bulk_id=parent_id,
            group_name=TEST_GROUP,
            settings_module=SETTINGS_MODULE,
            miller_index=[0, 0, 1]
        )
        print(f"Created Surface IDs: {surfaces_json}")

    return True

def verify_build():
    print("\n--- Verifying build_htvs_job ---")
    inbox_path = os.path.join(os.path.dirname(__file__), "htvs_test_inbox")
    os.makedirs(inbox_path, exist_ok=True)
    
    output = build_htvs_job(
        group_name=TEST_GROUP,
        inbox_path=inbox_path,
        limit=1,
        settings_module=SETTINGS_MODULE,
        djangochem_dir=DJANGOCHEM_DIR
    )
    print("Output from build_htvs_job:")
    print(output)
    
    if os.path.exists(inbox_path) and os.listdir(inbox_path):
        print(f"Files created in {inbox_path}")
        print(os.listdir(inbox_path))
    else:
        print("No files created (expected if jobs were requested for a different partition/system).")

    return True

if __name__ == "__main__":
    try:
        verify_request()
        verify_save()
        verify_build()
    finally:
        cleanup()
