"""
Cut clean surfaces from crystals in the HTVS database.

Usage:
    python run.py --group <group_name> --bulk_pkl <pkl_path> --MI h k l --settings <module>

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
import numpy as np
from tqdm import tqdm

def run_cut_clean_surface(args: argparse.Namespace) -> Dict[str, Any]:
    setup_django(args.settings, args.djangochem)

    import math
    from django.utils import timezone
    from django.contrib.contenttypes.models import ContentType
    from jobs.models import Job, JobConfig
    from pgmols.models import Group, Crystal, Surface, MillerIndex, Calc
    
    from pymatgen.core.surface import SlabGenerator
    from pymatgen.io.ase import AseAtomsAdaptor
    from src.utils.htvs.surface_utils import SurfaceHelper, get_top_termination_stoichiometry

    def log(msg: str) -> None:
        print(f"CUT_CLEAN_SURFACE: {msg}", file=sys.stderr)

    crystal_ids = pkl.load(open(args.bulk_pkl, "rb"))

    group_obj = Group.objects.get(name=args.group)
    config_obj, _ = JobConfig.objects.get_or_create(name="clean_surface_cut")

    crystals = Crystal.objects.filter(id__in=crystal_ids, parentjob__group=group_obj)
    if crystals.count() > args.limit:
        limited_ids = list(crystals.values_list("id", flat=True))[: args.limit]
        crystals = Crystal.objects.filter(id__in=limited_ids)

    log(f"Processing {crystals.count()} crystals.")
    num_surfaces = 0
    num_broken = 0
    created_surface_ids = []
    
    valid_indices = []
    if args.exact_mi:
        for mi_str in args.exact_mi:
            try:
                parts = tuple(int(x.strip()) for x in mi_str.replace(" ", "").split(','))
                if len(parts) == 3:
                    valid_indices.append(parts)
            except ValueError:
                continue
    else:
        h_max, k_max, l_max = args.MI[0], args.MI[1], args.MI[2] if len(args.MI) > 2 else args.MI[1]
        for h in range(h_max + 1):
            for k in range(k_max + 1):
                for l in range(l_max + 1):
                    if h == 0 and k == 0 and l == 0: continue
                    if math.gcd(h, math.gcd(k, l)) == 1:
                        valid_indices.append((h, k, l))

    for bulk in tqdm(crystals, total=len(crystals), disable=None):
        new_surfaces = []
        try:
            bulk_pmg = AseAtomsAdaptor.get_structure(bulk.as_ase_atoms())
            helper = SurfaceHelper(bulk_pmg)
        except Exception as e:
            log(f"Error processing Crystal {bulk.id}: {str(e)}")
            num_broken += 1
            continue
            
        for MI_hkl in valid_indices:
            mi_obj, _ = MillerIndex.objects.get_or_create(hkl=list(MI_hkl))
            
            try:
                helper.set_slab_generator(
                    miller_index=MI_hkl,
                    min_slab_size=args.layers,
                    min_vacuum_size=args.vacuum,
                    center_slab=True,
                    primitive=False
                )
                
                scale_a = args.scale[0] if args.scale else None
                scale_b = args.scale[1] if args.scale else None
                
                pmg_slabs = helper.get_supercell_slab(
                    scale_a=scale_a,
                    scale_b=scale_b,
                    min_length=5.0,
                    rotation=args.rotation
                )
            except Exception:
                continue
                
            for slab in pmg_slabs:
                slab_ase = AseAtomsAdaptor.get_atoms(slab)
                termination_formula = get_top_termination_stoichiometry(slab)
                
                z_values = slab_ase.positions[:, 2]
                highest_z = np.max(z_values)
                surface_atoms = [highest_z - z_values[atom] < 1.0 for atom in range(len(slab_ase))]
                
                s_atoms_idx = np.where(surface_atoms)[0]
                exposed_species = [slab_ase.symbols[idx] for idx in s_atoms_idx]
                
                if args.target_species and args.target_species not in exposed_species:
                    continue

                surface = Surface(bulk=bulk, miller_index=mi_obj)
                as_crystal = Crystal.from_ase_atoms(slab_ase)
                surface.xyz = as_crystal.xyz
                surface.lattice = as_crystal.lattice
                surface.stoichiometry = as_crystal.stoichiometry
                surface.spacegroup = bulk.spacegroup
                surface.method = bulk.method
                surface.surface_atoms = surface_atoms
                surface.adsorbate_atoms = [False] * len(surface.xyz)
                chemical_tag = surface.generate_hash()
                surface.chemical_tag = chemical_tag
                surface.details = {
                    "B": exposed_species,
                    "termination": termination_formula,
                    "scale": args.scale if args.scale else "auto_5A",
                    "rotation": args.rotation
                }

                magmoms = slab_ase.get_initial_magnetic_moments()
                if magmoms is not None and np.sum(np.abs(magmoms)) > 0:
                    surface.magmoms = magmoms.tolist()
                
                already_exists = Surface.objects.filter(chemical_tag=chemical_tag).exists()
                if already_exists:
                    continue

                dup_idx = np.where([s.chemical_tag == chemical_tag for s in new_surfaces])[0]
                if len(dup_idx) == 0:
                    new_surfaces.append(surface)

        from src.utils.htvs.db_handler import HTVSDbHandler
        handler = HTVSDbHandler(args.settings, djangochem_dir=args.djangochem)
        
        db_entries = []
        for surf in new_surfaces:
             entry = {
                 "bulk_id": bulk.id,
                 "miller_index": list(surf.miller_index.hkl),
                 "xyz": surf.xyz,
                 "lattice": surf.lattice,
                 "stoichiometry": surf.stoichiometry,
                 "surface_atoms": surf.surface_atoms,
                 "adsorbate_atoms": surf.adsorbate_atoms,
                 "details": surf.details,
                 "magmoms": surf.magmoms if hasattr(surf, "magmoms") else None
             }
             db_entries.append(entry)
             
        if not args.dry_run and db_entries:
             save_out = handler.save_surface_entries(
                 db_entries, 
                 config_name="clean_surface_cut",
                 group_name=args.group
             )
             save_results = json.loads(save_out)
             
             if "error" in save_results:
                 log(f"Error in batch save for Crystal {bulk.id}: {save_results['error']}")
             else:
                 created_ids = save_results.get("success", [])
                 created_surface_ids.extend(created_ids)
                 num_surfaces += len(created_ids)
                 if save_results.get("errors"):
                     log(f"Failed to save {len(save_results['errors'])} surfaces for Crystal {bulk.id}.")

    if not args.dry_run and args.output_log:
        with open(args.output_log, "w") as f:
            json.dump(created_surface_ids, f, indent=2)

    return {
        "status": "success",
        "num_surfaces": num_surfaces,
        "num_broken": num_broken,
        "created_ids": created_surface_ids,
        "dry_run": args.dry_run
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Cut clean surfaces from crystals in the HTVS database.")
    parser.add_argument("--group", type=str, required=True, help="Name of the project group")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum number of bulk crystals to process")
    parser.add_argument("--dry_run", action="store_true", help="Simulate without writing to the database")
    parser.add_argument("--MI", nargs="+", type=int, help="Maximum Miller indices to sweep")
    parser.add_argument("--exact_mi", nargs="+", type=str, help="Exact Miller indices to cut")
    parser.add_argument("--bulk_pkl", type=str, required=True, help="Pickle file of crystal IDs to process")
    parser.add_argument("--output_log", type=str, default=None, help="JSON file path to save created surface IDs")
    parser.add_argument("--settings", type=str, required=True, help="Django settings module")
    parser.add_argument("--djangochem", type=str, default=None, help="Path to the djangochem project root")
    parser.add_argument("--target_species", type=str, default=None, help="Exposed species filter")
    parser.add_argument("--layers", type=int, default=4, help="Number of layers")
    parser.add_argument("--vacuum", type=float, default=10.0, help="Vacuum thickness")
    parser.add_argument("--scale", type=int, nargs=2, default=None, help="Supercell scaling")
    parser.add_argument("--rotation", type=float, default=0.0, help="Rotation angle")
    args = parser.parse_args()

    if not args.MI and not args.exact_mi:
        parser.error("At least one of --MI or --exact_mi must be provided.")

    try:
        results = run_cut_clean_surface(args)
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
