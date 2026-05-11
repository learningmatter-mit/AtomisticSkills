"""
Add adsorbates to clean surfaces in the HTVS database.

Usage:
    python run.py --group <group_name> --config_name <config> --species <O|OH|OOH>
                  --bulk_pkl <pkl_path> --settings <module>

Requirements:
    - Conda environment: htvs-agent
    - Required packages: django, pgmols, jobs, catkit, ase, numpy, tqdm

Author: Hoje Chun
Contact: GitHub @hojechun
"""
import os
import sys
import argparse
import pickle as pkl
import json
import traceback
from typing import Any, Dict, List

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.script_runner import setup_django
from src.utils.htvs import get_adsorbate
import numpy as np
from tqdm import tqdm

def get_clean_surface_parent(surface_obj) -> object:
    """Walk up the Job-parent chain to find the root clean_surface_cut surface."""
    parent = surface_obj
    while parent.parentjob.config.name != "clean_surface_cut":
        parent = parent.parentjob.parent
    return parent

def run_add_adsorbate(args: argparse.Namespace) -> Dict[str, Any]:
    setup_django(args.settings, args.djangochem)

    from django.utils import timezone
    from django.contrib.contenttypes.models import ContentType
    from jobs.models import Job, JobConfig
    from pgmols.models import Group, Surface, Calc
    from pgmols.utils.surfaces import add_adsorbate

    def log(msg: str) -> None:
        print(f"ADD_ADSORBATE: {msg}", file=sys.stderr)

    adsorbate = get_adsorbate(args.species)
    bulk_ids = pkl.load(open(args.bulk_pkl, "rb"))

    group_obj = Group.objects.get(name=args.group)
    config_obj = JobConfig.objects.get(name=args.config_name)
    adsorbate_config_obj, _ = JobConfig.objects.get_or_create(name="add_adsorbate")

    surfaces = Surface.objects.filter(
        parentjob__group=group_obj,
        parentjob__config=config_obj,
        bulk__id__in=bulk_ids,
    )
    log(f"Processing {surfaces.count()} clean surfaces.")

    num_created = 0
    num_broken = 0
    created_surface_ids = []

    for surface in tqdm(surfaces, total=len(surfaces), disable=None):
        try:
            clean_cut = get_clean_surface_parent(surface)
        except Exception:
            num_broken += 1
            continue

        details_B = (clean_cut.details or {}).get("B", [])
        if not details_B:
            if args.active_site:
                details_B = [args.active_site]
            else:
                log(f"Surface {surface.id} has no active site metadata. Skipping.")
                continue
            
        for B in details_B:
            try:
                slab = surface.as_ase_gratoms()
                B_indices = np.intersect1d(
                    np.where(surface.surface_atoms)[0],
                    np.where(slab.symbols == B)[0],
                )
                if len(B_indices) == 0:
                    continue

                from ase.data import covalent_radii, atomic_numbers
                slab.wrap()
                
                top_B_idx = B_indices[np.argmax(slab.positions[B_indices, 2])]
                site_pos = slab.positions[top_B_idx]
                r_B = covalent_radii[atomic_numbers[B]]
                
                bind_symbol = adsorbate.symbols[0]
                r_bind = covalent_radii[atomic_numbers[bind_symbol]]
                d_target = 0.85 * (r_B + r_bind)
                shift = site_pos + np.array([0, 0, d_target])
                
                ads_copy = adsorbate.copy()
                ads_copy.translate(shift)
                slab_w_ads = slab + ads_copy
                
                n_slab = len(slab)
                n_ads = len(adsorbate)
                ads_atoms = [False] * n_slab + [True] * n_ads
                surf_atoms = list(surface.surface_atoms) + [True] * n_ads
                
            except Exception as e:
                log(f"Error processing surface {surface.id}: {str(e)}")
                num_broken += 1
                continue

            from src.utils.htvs.db_handler import HTVSDbHandler
            handler = HTVSDbHandler(args.settings, djangochem_dir=args.djangochem)

            num_created += 1
            if not args.dry_run:
                raw_magmoms = slab_w_ads.get_initial_magnetic_moments()
                magmoms_payload = None
                if raw_magmoms is not None:
                    m_list = raw_magmoms.tolist()
                    magmoms_payload = [float(x) for x in m_list]
                    if sum(abs(x) for x in magmoms_payload) == 0:
                        magmoms_payload = None
                
                # We need to getxyz and lattice for payload
                from pgmols.models import Surface as SurfaceModel
                as_surf = SurfaceModel.from_ase_atoms(slab_w_ads)

                payload = {
                    "bulk_id": clean_cut.bulk.id,
                    "parent_id": surface.id,
                    "miller_index": list(clean_cut.miller_index.hkl) if hasattr(clean_cut.miller_index, "hkl") else clean_cut.miller_index,
                    "xyz": as_surf.xyz,
                    "lattice": as_surf.lattice,
                    "stoichiometry": slab_w_ads.get_chemical_formula(),
                    "surface_atoms": [bool(x) for x in surf_atoms],
                    "adsorbate_atoms": [bool(x) for x in ads_atoms],
                    "active_site": [B],
                    "group_name": args.group,
                    "magmoms": magmoms_payload
                }
                
                res_str = handler.save_adsorbate_surface(payload)
                res_data = json.loads(res_str)
                
                if "error" in res_data:
                    log(f"Error saving adsorbate surface: {res_data['error']}")
                    num_broken += 1
                elif res_data.get("status") == "created":
                    created_surface_ids.append(res_data["id"])
                elif res_data.get("status") == "exists":
                    num_created -= 1 # Already exists

    if not args.dry_run and args.output_log:
        with open(args.output_log, "w") as f:
            json.dump(created_surface_ids, f, indent=2)

    return {
        "status": "success",
        "num_created": num_created,
        "num_broken": num_broken,
        "created_ids": created_surface_ids,
        "dry_run": args.dry_run
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Add adsorbates to clean surfaces in the HTVS database.")
    parser.add_argument("--group", type=str, required=True, help="Name of the project group")
    parser.add_argument("--config_name", type=str, required=True, help="Config name of the clean surfaces")
    parser.add_argument("--species", type=str, required=True, help="Adsorbate species: O, OH, or OOH")
    parser.add_argument("--bulk_pkl", type=str, required=True, help="Pickle file of bulk IDs to filter surfaces")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum number of surfaces to process")
    parser.add_argument("--dry_run", action="store_true", help="Simulate without writing to the database")
    parser.add_argument("--output_log", type=str, default=None, help="JSON file path to save created surface IDs")
    parser.add_argument("--settings", type=str, required=True, help="Django settings module")
    parser.add_argument("--djangochem", type=str, default=None, help="Path to the djangochem project root")
    parser.add_argument("--active_site", type=str, default=None, help="Fallback active site species if missing in DB")
    args = parser.parse_args()

    try:
        results = run_add_adsorbate(args)
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
