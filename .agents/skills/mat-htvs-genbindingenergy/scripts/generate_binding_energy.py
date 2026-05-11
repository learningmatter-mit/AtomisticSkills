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
    calc = geom_obj.calcs.get(props__totalenergy__isnull=False, method=method_obj)
    return calc.props["totalenergy"]

def get_optimized_clean(surface_obj, config_obj):
    parent = surface_obj
    while parent.parentjob.config.name != "clean_surface_cut":
        parent = parent.parentjob.parent

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
    method_obj = Method.objects.get(name=args.method)
    metric_obj, _ = AffinityType.objects.get_or_create(name=args.metric)

    ref_group_obj = Group.objects.get(name=args.ref_group)
    ref_config_obj = JobConfig.objects.get(name=args.ref_config)
    ref_crystals = Crystal.objects.filter(
        parentjob__group=ref_group_obj,
        parentjob__config=ref_config_obj,
    )
    
    try:
        h2o_ref = get_energy(ref_crystals.get(stoichiometry__formula="H2O"), method_obj)
        h2_ref = get_energy(ref_crystals.get(stoichiometry__formula="H2"), method_obj)
        log(f"Gas references: H2O={h2o_ref:.6f} Ha, H2={h2_ref:.6f} Ha")
    except Exception as e:
        log(f"Error fetching gas references: {e}")
        raise

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
            
        clean_geoms = get_optimized_clean(surface, config_obj)
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
        except Exception:
            continue
            
        dE = energy_w_ads - energy_clean - n_h2o * h2o_ref - n_h * h2_ref / 2
        
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
    parser.add_argument("--ref_group", type=str, default="surface_binding_energy_references")
    parser.add_argument("--ref_config", type=str, default="pbe_u_paw_spinpol_opt_vasp")
    parser.add_argument("--method", type=str, default="dft_d3_paw_gga_pbe")
    parser.add_argument("--metric", type=str, default="surface_binding_dE")
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
