"""
Cut clean surfaces from crystals in the HTVS database.

Usage:
    python run.py --group <group_name> --bulk_pkl <pkl_path> --exact_mi 1,0,0 --settings <module>

Requirements:
    - Conda environment: htvs-agent
    - Required packages: django, pgmols, jobs, catkit, ase, numpy, tqdm
"""
import os
import sys
import argparse
import pickle as pkl
import json
import traceback
import tempfile
import subprocess
import shutil
from typing import Any, Dict, List

# Add repo root to find src
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from src.utils.htvs.script_runner import setup_django
import numpy as np
from tqdm import tqdm
from ase.io import write
from src.utils.htvs.db_handler import HTVSDbHandler

def run_cut_clean_surface(args: argparse.Namespace) -> Dict[str, Any]:
    setup_django(args.settings, args.djangochem)
    handler = HTVSDbHandler(args.settings, djangochem_dir=args.djangochem)

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
        try:
            bulk_pmg = AseAtomsAdaptor.get_structure(bulk.as_ase_atoms())
            helper = SurfaceHelper(bulk_pmg)
        except Exception as e:
            log(f"Error processing Crystal {bulk.id}: {str(e)}")
            num_broken += 1
            continue
            
        for MI_hkl in valid_indices:
            try:
                helper.set_slab_generator(
                    miller_index=MI_hkl,
                    min_slab_size=args.slab_thickness,
                    min_vacuum_size=args.vacuum,
                    center_slab=True,
                    primitive=False
                )
                
                scale_a = args.scale[0] if args.scale else None
                scale_b = args.scale[1] if args.scale else None
                
                pmg_slabs = helper.get_supercell_slab(
                    scale_a=scale_a,
                    scale_b=scale_b,
                    min_length=args.supercell_min_length,
                    rotation=args.rotation
                )
            except Exception:
                continue
                
            if args.max_terminations and len(pmg_slabs) > args.max_terminations:
                log(f"Evaluating {len(pmg_slabs)} terminations with FAIRChem...")
                with tempfile.TemporaryDirectory() as temp_dir:
                    bulk_ase = AseAtomsAdaptor.get_atoms(bulk_pmg)
                    write(os.path.join(temp_dir, "bulk.cif"), bulk_ase)
                    for i, slab in enumerate(pmg_slabs):
                        slab_ase = AseAtomsAdaptor.get_atoms(slab)
                        write(os.path.join(temp_dir, f"slab_{i}.cif"), slab_ase)
                    
                    eval_script = os.path.join(os.path.dirname(__file__), "eval_fairchem.py")
                    python_exec = "/mnt/data0/hojechun/miniforge3/envs/fairchem-agent/bin/python"
                    try:
                        subprocess.run(
                            [python_exec, eval_script, temp_dir, "--top_n", str(args.max_terminations)],
                            check=True, capture_output=True, text=True
                        )
                        ranking_path = os.path.join(temp_dir, "ranking.json")
                        with open(ranking_path, "r") as f:
                            ranking = json.load(f)
                            
                        selected_indices = [int(r["filename"].replace("slab_", "").replace(".cif", "")) for r in ranking]
                        pmg_slabs = [pmg_slabs[i] for i in selected_indices]
                        log(f"Selected {len(pmg_slabs)} best terminations.")
                    except Exception as e:
                        log(f"Error evaluating surface energies for crystal {bulk.id}: {e}")
                        if isinstance(e, subprocess.CalledProcessError):
                            log(f"Subprocess stderr: {e.stderr}")
                
            for slab in pmg_slabs:
                slab_ase = AseAtomsAdaptor.get_atoms(slab)
                
                # Identify layers and fix all except the top-most layer
                z_values = slab_ase.positions[:, 2]
                unique_zs = np.unique(np.round(z_values, 1))
                highest_z_layer = np.max(unique_zs)
                
                # Only the top-most layer relaxes (surf_atoms = 1)
                surface_atoms = [abs(z - highest_z_layer) < 0.5 for z in z_values]
                slab_ase.info["surf_atoms"] = [1 if x else 0 for x in surface_atoms]
                
                # Filter by species if requested
                s_atoms_idx = np.where(surface_atoms)[0]
                exposed_species = [slab_ase.symbols[idx] for idx in s_atoms_idx]
                if args.target_species and args.target_species not in exposed_species:
                    continue

                if not args.dry_run:
                    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tf:
                        write(tf.name, slab_ase)
                        temp_path = tf.name
                    
                    try:
                        details = {"B": [args.target_species]} if args.target_species else None
                        save_out = handler.save_surfaces(
                            temp_path,
                            config_name="clean_surface_cut",
                            parent_bulk_id=bulk.id,
                            group_name=args.group,
                            miller_index=list(MI_hkl),
                            details=details
                        )
                        created_ids_res = json.loads(save_out)
                        if isinstance(created_ids_res, list):
                            created_surface_ids.extend(created_ids_res)
                            num_surfaces += len(created_ids_res)
                        else:
                            log(f"Error saving surface for Crystal {bulk.id}: {save_out}")
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

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
    parser.add_argument("--slab_thickness", type=float, default=10.0, help="Minimum slab thickness in Angstroms")
    parser.add_argument("--vacuum", type=float, default=15.0, help="Vacuum thickness in Angstroms")
    parser.add_argument("--supercell_min_length", type=float, default=10.0, help="Minimum distance between periodic images in Angstroms")
    parser.add_argument("--scale", type=int, nargs=2, default=None, help="Supercell scaling")
    parser.add_argument("--rotation", type=float, default=0.0, help="Rotation angle")
    parser.add_argument("--max_terminations", type=int, default=None, help="Keep only top N terminations evaluated by surface energy (Requires fairchem-agent)")
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
