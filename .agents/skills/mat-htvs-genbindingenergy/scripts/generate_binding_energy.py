"""
Calculate and store surface binding energies in the HTVS database.

Usage:
    python run.py --group <group_name> --config_name <config>
                  --ref_group <ref_group> --ref_config <ref_config>
                  --method <method_name> --metric <metric_name>
                  --settings <module> --output_data <binding_energies.json>

Requirements:
    - Conda environment: htvs-agent

Author: Hoje Chun
Contact: GitHub @hojechun
"""
import os
import sys
import argparse
import json
import traceback
import numpy as np
from tqdm import tqdm
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

# Add project root to python path to access src package
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.script_runner import setup_django

def get_adsorbate_formula(surface_obj) -> str:
    from pymatgen.core.periodic_table import Element
    atomic_numbers = [row[0] for row in surface_obj.xyz]
    symbols = [Element.from_Z(z).symbol for z in atomic_numbers]
    ads_symbols = [symbols[i] for i in np.where(surface_obj.adsorbate_atoms)[0]]
    ads_symbols.sort()
    formula = "".join(ads_symbols)
    
    mapping = {"HO": "OH", "HOO": "OOH"}
    return mapping.get(formula, formula)

def get_energy(geom_obj, method_obj) -> float:
    # Check if geom_obj is Surface or Crystal
    if hasattr(geom_obj, 'calcs'):
        calc = geom_obj.calcs.filter(totalenergy__isnull=False, method=method_obj).first()
        if calc:
            return calc.totalenergy
    return None

def get_optimized_clean(surface_obj, config_obj):
    # Find the original 'clean_surface_cut' ancestor
    parent = surface_obj
    # If it's a Surface, go to its parent Job, then its parent (which should be the original surface or job)
    while True:
        if hasattr(parent, "parentjob") and parent.parentjob and parent.parentjob.config.name == "clean_surface_cut":
            break
        if hasattr(parent, "parentjob") and parent.parentjob and parent.parentjob.parent:
             parent = parent.parentjob.parent
        else:
             return None
             
    done_job = parent.childjobs.filter(config=config_obj, status="done").first()
    if done_job is None:
        return None
    return done_job.childgeoms.all()

def run_generate_binding_energy(args: argparse.Namespace) -> Dict[str, Any]:
    setup_django(args.settings, args.djangochem)

    from jobs.models import JobConfig
    from pgmols.models import Group, Crystal, Surface, Method
    from docking.models import AffinityType, BindingEnergy

    def log(msg: str) -> None:
        print(f"GEN_BINDING_ENERGY: {msg}", file=sys.stderr)

    group_obj = Group.objects.get(name=args.group)
    config_obj = JobConfig.objects.get(name=args.config_name)
    clean_config_obj = JobConfig.objects.get(name=args.clean_config or args.config_name)
    method_obj = Method.objects.get(name=args.method)
    metric_obj, _ = AffinityType.objects.get_or_create(name=args.metric)

    ref_group_obj = Group.objects.get(name=args.ref_group)
    ref_config_obj = JobConfig.objects.get(name=args.ref_config)
    ref_crystals = Crystal.objects.filter(
        parentjob__group=ref_group_obj,
        parentjob__config=ref_config_obj,
    )
    
    # --- Step 1.1: Fetch Gas References (with JSON Fallback) ---
    h2o_ref, h2_ref = None, None
    from_db = False
    
    # Try Database First
    try:
        h2o_obj = ref_crystals.get(stoichiometry__formula="H2O")
        h2_obj = ref_crystals.get(stoichiometry__formula="H2")
        h2o_ref = get_energy(h2o_obj, method_obj)
        h2_ref = get_energy(h2_obj, method_obj)
        if h2o_ref is not None and h2_ref is not None:
            from_db = True
            log(f"Gas references loaded from database '{args.settings}'")
    except Exception as e:
        log(f"Database references not found, attempting centralized JSON fallback... ({e})")

    # JSON Fallback
    if h2o_ref is None or h2_ref is None:
        resource_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "reference_molecules.json")
        if os.path.exists(resource_path):
            with open(resource_path, 'r') as f:
                # Strip // comments before parsing JSON
                import re
                raw_content = f.read()
                clean_content = re.sub(r'//.*', '', raw_content)
                resource_data = json.loads(clean_content)
                
                level_data = resource_data.get(args.level, {})
                h2o_ref = level_data.get("H2O", {}).get("totalenergy_ha")
                h2_ref = level_data.get("H2", {}).get("totalenergy_ha")
                if h2o_ref and h2_ref:
                    log(f"Gas references loaded from centralized resource ({args.level}): {resource_path}")
                else:
                    log(f"Centralized resource missing H2 or H2O keys for level {args.level}.")
        else:
            log(f"Centralized resource NOT found at {resource_path}")

    if h2o_ref is None or h2_ref is None:
        log("CRITICAL: Could not find H2/H2O references in database or JSON resource.")
        raise ValueError(f"Missing gas-phase references (H2, H2O) for level {args.level}. Run migrate_references.py first.")

    # Convert to eV depending on source and method
    ha_to_ev = 27.211386245988
    
    # If from JSON, it is explicitly in Hartree (totalenergy_ha). 
    # If from DB, it's in Hartree for DFT, and eV for MLIP.
    if not from_db or "dft" in method_obj.name.lower() or "vasp" in method_obj.name.lower():
        h2o_ref_ev = h2o_ref * ha_to_ev
        h2_ref_ev = h2_ref * ha_to_ev
        log(f"Final References: H2O={h2o_ref:.6f} Ha ({h2o_ref_ev:.4f} eV), H2={h2_ref:.6f} Ha ({h2_ref_ev:.4f} eV)")
    else:
        h2o_ref_ev = h2o_ref
        h2_ref_ev = h2_ref
        log(f"Final References: H2O={h2o_ref_ev:.4f} eV, H2={h2_ref_ev:.4f} eV")

    surfaces = Surface.objects.filter(
        parentjob__group=group_obj,
        parentjob__config=config_obj,
    ).filter(adsorbate_atoms__contains=[True])

    if args.limit:
        surfaces = surfaces[: args.limit]

    log(f"Processing {len(surfaces)} adsorbate surfaces.")
    num_created = 0
    created_ids = []

    coeff_map = {
        "O":   {"n_h2o": 1, "n_h": -2},
        "OH":  {"n_h2o": 1, "n_h": -1},
        "OOH": {"n_h2o": 2, "n_h": -3},
    }

    json_payload = defaultdict(lambda: {"label": "", "active_site": "", "energies": {}})

    from src.utils.htvs.db_handler import HTVSDbHandler
    handler = HTVSDbHandler(args.settings, djangochem_dir=args.djangochem)
    entries_to_save = []

    for surface in tqdm(surfaces, total=len(surfaces), disable=None):
        adsorbate = get_adsorbate_formula(surface)
        if adsorbate not in coeff_map:
            continue
            
        clean_geoms = get_optimized_clean(surface, clean_config_obj)
        if not clean_geoms:
            continue
            
        clean_surface = clean_geoms.first().crystal.surface
        clean_id = clean_surface.id
        
        try:
            active_site = surface.parentjob.parent.details.get("B", [""])[0]
        except Exception:
            active_site = "Unknown"
            
        try:
            parent_bulk_formula = clean_surface.parentjob.parent.crystal.stoichiometry.formula
            h_index = clean_surface.parentjob.parent.details.get("miller_index", [0, 0, 0])
            base_label = f"{parent_bulk_formula}({''.join(map(str, h_index))})"
        except Exception:
            base_label = f"Surface_{clean_id}"

        json_payload[clean_id]["label"] = f"{base_label} - Act:{active_site}"
        json_payload[clean_id]["active_site"] = active_site

        existing_be = BindingEnergy.objects.filter(metric=metric_obj, surface_w_adsorbate=surface).first()
        
        if existing_be:
            json_payload[clean_id]["energies"][adsorbate] = existing_be.value
            created_ids.append(existing_be.id)
            continue
            
        n_h2o = coeff_map[adsorbate]["n_h2o"]
        n_h = coeff_map[adsorbate]["n_h"]

        try:
            energy_w_ads = get_energy(surface, method_obj)
            energy_clean = get_energy(clean_surface, method_obj)
            
            if energy_w_ads is None or energy_clean is None:
                continue

            # HTVS VASP parsers save totalenergy in Hartree, while MLIPs save in eV.
            if "dft" in method_obj.name.lower() or "vasp" in method_obj.name.lower():
                energy_w_ads *= ha_to_ev
                energy_clean *= ha_to_ev
        except Exception:
            continue
            
        dE = energy_w_ads - energy_clean - n_h2o * h2o_ref_ev - n_h * h2_ref_ev / 2
        
        entries_to_save.append({
            "clean_id": clean_id,
            "ads_id": surface.id,
            "value": dE,
            "adsorbate": adsorbate
        })
        json_payload[clean_id]["energies"][adsorbate] = dE

    if not args.dry_run and entries_to_save:
        save_out = handler.save_binding_energies(entries_to_save, metric=args.metric)
        save_results = json.loads(save_out)
        
        if "error" in save_results:
             log(f"Error in batch save: {save_results['error']}")
        else:
             created_ids.extend(save_results.get("success", []))
             num_created = len(save_results.get("success", []))
             if save_results.get("errors"):
                 log(f"Failed to save {len(save_results['errors'])} records.")

    out_file = Path(args.output_data)
    out_file.parent.mkdir(parents=True, exist_ok=True)
        
    with open(out_file, "w") as f:
        json.dump(json_payload, f, indent=2)

    return {
        "status": "success",
        "num_created": num_created,
        "created_ids": created_ids,
        "output_payload": str(out_file),
        "dry_run": args.dry_run
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate surface binding energies in the HTVS database.")
    parser.add_argument("--group", type=str, required=True, help="Name of the project group")
    parser.add_argument("--config_name", type=str, required=True, help="JobConfig name for adsorbate surface calculations")
    parser.add_argument("--clean_config", type=str, default=None, help="JobConfig name for clean surface calculations (defaults to config_name)")
    parser.add_argument("--ref_group", type=str, default="surface_binding_energy_references")
    parser.add_argument("--ref_config", type=str, default="pbe_u_paw_spinpol_opt_vasp")
    parser.add_argument("--method", type=str, default="dft_d3_paw_gga_pbe")
    parser.add_argument("--metric", type=str, default="surface_binding_dE")
    parser.add_argument("--level", type=str, default="PBE")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--dry_run", action="store_true", help="Simulate without writing to the database")
    parser.add_argument("--output_data", type=str, default="binding_energies.json", help="Output JSON capturing standard schema")
    parser.add_argument("--settings", type=str, required=True, help="Django settings module")
    parser.add_argument("--djangochem", type=str, default=None)
    args = parser.parse_args()

    try:
        results = run_generate_binding_energy(args)
        print(json.dumps(results, indent=2))
    except Exception as e:
        error_results = {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_results, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
