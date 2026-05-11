#!/usr/bin/env python
import os
import sys
import argparse
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to python path to access src package
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.script_runner import setup_django

def main():
    parser = argparse.ArgumentParser(description="Migrate gas-phase reference energies between HTVS databases.")
    parser.add_argument("--settings", required=True, help="Django settings module for the target project (e.g. djangochem.settings.toy)")
    parser.add_argument("--orgel_settings", default="djangochem.settings.orgel", help="Orgel database settings")
    parser.add_argument("--research_dir", required=True, help="Path to current research directory for provenance logging")
    parser.add_argument("--method", default="dft_d3_paw_gga_pbe", help="Method name to look up/create")
    parser.add_argument("--config", default="ref_import", help="JobConfig name for shell jobs")
    parser.add_argument("--group_name", default="htvs-fe-binary", help="Target Group name")
    parser.add_argument("--level", default="PBE", help="Theoretical level to extract from JSON")
    parser.add_argument("--djangochem", type=str, default=None)
    args = parser.parse_args()

    # --- Step 1: Load Centralized References ---
    resource_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "reference_molecules.json")
    if os.path.exists(resource_path):
        with open(resource_path, 'r') as f:
            resource_data = json.load(f)
            level_data = resource_data.get(args.level, {})
            references = {f: d["totalenergy_ha"] for f, d in level_data.items()}
            logger.info(f"MIGRATION: Loaded {len(references)} references from centralized resource ({args.level}).")
    else:
        logger.warning(f"MIGRATION: Centralized resource not found at {resource_path}. Using internal defaults.")
        # internal fallbacks
        references = {
            "H2": -1.1666,
            "H2O": -76.43
        }
    
    # --- Step 2: Inject into Target Project ---
    logger.info(f"MIGRATION: Injecting references into '{args.settings}'")
    setup_django(args.settings, args.djangochem)

    from pgmols.models import Group, Geom, Stoichiometry, Method, Calc
    from jobs.models import Job, JobConfig

    # 1. Ensure Group exists
    group_obj, created = Group.objects.get_or_create(name=args.group_name)
    if created:
        logger.info(f"MIGRATION: Created Group '{args.group_name}'")

    # 2. Ensure JobConfig exists
    config_obj, created = JobConfig.objects.get_or_create(name=args.config)
    if created:
        logger.info(f"MIGRATION: Created JobConfig '{args.config}'")

    # 3. Ensure Method exists (multi-record safe)
    method_obj = Method.objects.filter(name=args.method).first()
    if not method_obj:
        method_obj = Method.objects.create(name=args.method, description="Imported via Skill Initialization Utility")
    
    # 4. Reference Metadata (Mass/Coordinates)
    # xyz format: [AtomicNumber, X, Y, Z]
    meta = {
        "H2": {
            "mass": 2.016, 
            "charge": 0,
            "xyz": [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.74]]
        },
        "H2O": {
            "mass": 18.015, 
            "charge": 0,
            "xyz": [[8.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.76, 0.59], [1.0, 0.0, -0.76, 0.59]]
        },
        "CO2": {
            "mass": 44.01,
            "charge": 0,
            "xyz": [[6.0, 0.0, 0.0, 0.0], [8.0, 0.0, 0.0, 1.16], [8.0, 0.0, 0.0, -1.16]]
        },
        "N2": {
            "mass": 28.01,
            "charge": 0,
            "xyz": [[7.0, 0.0, 0.0, 0.0], [7.0, 0.0, 0.0, 1.10]]
        }
    }

    migrated_ids = {}
    for formula, energy in references.items():
        if formula not in meta:
            logger.warning(f"MIGRATION: Missing metadata (XYZ/Mass) for {formula}. Skipping.")
            continue

        # Create/Get Stoichiometry
        stoich_obj, _ = Stoichiometry.objects.get_or_create(
            formula=formula, 
            defaults={"mass": meta[formula]["mass"], "charge": meta[formula]["charge"]}
        )
        
        # Check if already exists in this group/config
        existing_geom = Geom.objects.filter(
            stoichiometry=stoich_obj,
            parentjob__config=config_obj,
            parentjob__group=group_obj
        ).first()

        if existing_geom:
            logger.info(f"MIGRATION: Reference for {formula} already exists. Skipping.")
            migrated_ids[formula] = existing_geom.id
            continue

        # Create a dummy "shell" job to hold the reference
        job_obj = Job.objects.create(
            group=group_obj,
            config=config_obj,
            status="done",
            details={"source": "centralized_resource", "energy_ha": energy, "formula": formula}
        )

        # Create Geom (Molecular reference, not Crystal)
        geom_obj = Geom.objects.create(
            stoichiometry=stoich_obj,
            method=method_obj,
            xyz=meta[formula]["xyz"],
            parentjob=job_obj,
            converged=True,
            details={"imported_from": "centralized_json", "original_energy_ha": energy}
        )

        # Create Calc with the fixed energy
        props = {
            "totalenergy": energy, 
            "is_converged": True,
            "method": resource_data.get("metadata", {}).get("method", args.method),
            "units": resource_data.get("metadata", {}).get("units", "Hartree")
        }
        calc_obj = Calc.objects.create(
            method=method_obj,
            props=props,
            parentjob=job_obj
        )
        calc_obj.geoms.add(geom_obj)

        logger.info(f"MIGRATION: Success for {formula} (Geom ID: {geom_obj.id})")
        migrated_ids[formula] = geom_obj.id

    # --- Step 3: Provenance Logging ---
    provenance_path = os.path.join(args.research_dir, "provenance_references.json")
    provenance_data = {
        "timestamp": datetime.now().isoformat(),
        "source_db": args.orgel_settings,
        "target_db": args.settings,
        "group": args.group_name,
        "references": [
            {"formula": f, "geom_id": gid, "energy_ha": references[f]} 
            for f, gid in migrated_ids.items()
        ],
        "notes": "Reference molecules stored as Geom (isolated molecules) to avoid periodic artifacts."
    }
    
    with open(provenance_path, 'w') as f:
        json.dump(provenance_data, f, indent=4)
    logger.info(f"MIGRATION: Provenance log saved to {provenance_path}")

if __name__ == "__main__":
    main()
