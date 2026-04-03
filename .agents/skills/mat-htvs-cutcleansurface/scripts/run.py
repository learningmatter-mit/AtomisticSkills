"""
Cut clean surfaces from crystals in the HTVS database.

Usage:
    python run.py --group <group_name> --bulk_pkl <pkl_path> --MI h k l --settings <module>

Requirements:
    - Conda environment: htvs-agent
    - Required packages: django, pgmols, jobs, catkit, ase, numpy, tqdm
"""
import os
import sys
import argparse
import pickle as pkl

from src.utils.htvs.script_runner import setup_django

import numpy as np
from tqdm import tqdm

def main() -> None:
    parser = argparse.ArgumentParser(description="Cut clean surfaces from crystals in the HTVS database.")
    parser.add_argument("--group", type=str, required=True, help="Name of the project group")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum number of bulk crystals to process")
    parser.add_argument("--dry_run", action="store_true", help="Simulate without writing to the database")
    parser.add_argument("--MI", nargs="+", required=True, type=int, help="Miller index (e.g. --MI 1 1 0)")
    parser.add_argument("--bulk_pkl", type=str, required=True, help="Pickle file of crystal IDs to process")
    parser.add_argument("--settings", type=str, required=True, help="Django settings module")
    parser.add_argument("--djangochem", type=str, default=None, help="Path to the djangochem project root")
    args = parser.parse_args()

    setup_django(args.settings, args.djangochem)

    from django.utils import timezone
    from django.contrib.contenttypes.models import ContentType
    from jobs.models import Job, JobConfig
    from pgmols.models import Group, Crystal, Surface, MillerIndex, Calc
    from pgmols.utils.surfaces import surface_from_bulk

    def log(msg: str) -> None:
        print(f"CUT_CLEAN_SURFACE: {msg}")

    crystal_ids = pkl.load(open(args.bulk_pkl, "rb"))

    MI_hkl = list(args.MI)
    mi_obj, _ = MillerIndex.objects.get_or_create(hkl=MI_hkl)
    group_obj = Group.objects.get(name=args.group)
    config_obj, _ = JobConfig.objects.get_or_create(name="clean_surface_cut")

    crystals = Crystal.objects.filter(id__in=crystal_ids, parentjob__group=group_obj)
    if crystals.count() > args.limit:
        limited_ids = list(crystals.values_list("id", flat=True))[: args.limit]
        crystals = Crystal.objects.filter(id__in=limited_ids)

    log(f"Processing {crystals.count()} crystals.")
    num_surfaces = 0
    num_broken = 0

    for bulk in tqdm(crystals, total=len(crystals)):
        new_surfaces = []
        details_B = (bulk.details or {}).get("B", [])

        for B in details_B:
            try:
                bulk_ase = bulk.as_ase_atoms()
                iterm = 0
                slab, surface_atoms = surface_from_bulk(bulk_ase, MI_hkl, iterm=iterm)
                s_atoms = np.where(surface_atoms)[0]
                while B not in slab.symbols[s_atoms]:
                    iterm += 1
                    slab, surface_atoms = surface_from_bulk(bulk_ase, MI_hkl, iterm=iterm)
                    s_atoms = np.where(surface_atoms)[0]
            except Exception:
                num_broken += 1
                continue

            surface = Surface(bulk=bulk, miller_index=mi_obj)
            as_crystal = Crystal.from_ase_atoms(slab)
            surface.xyz = as_crystal.xyz
            surface.lattice = as_crystal.lattice
            surface.stoichiometry = as_crystal.stoichiometry
            surface.spacegroup = bulk.spacegroup
            surface.method = bulk.method
            surface.surface_atoms = surface_atoms
            surface.adsorbate_atoms = [False] * len(surface.xyz)
            chemical_tag = surface.generate_hash()
            surface.chemical_tag = chemical_tag

            magmoms = slab.get_initial_magnetic_moments().tolist()
            if np.sum(np.abs(magmoms)) > 0:
                surface.magmoms = magmoms
            surface.details = {"B": [B]}

            already_exists = Surface.objects.filter(
                bulk=bulk,
                chemical_tag=chemical_tag,
                parentjob__group=group_obj,
                parentjob__config=config_obj,
            ).exists()
            if already_exists:
                continue

            dup_idx = np.where([s.chemical_tag == chemical_tag for s in new_surfaces])[0]
            if len(dup_idx) == 0:
                new_surfaces.append(surface)
            else:
                existing = new_surfaces[dup_idx[0]]
                existing.details["B"].append(B)

        for surf in new_surfaces:
            num_surfaces += 1
            if not args.dry_run:
                job = Job(
                    config=config_obj,
                    group=group_obj,
                    status="done",
                    parentct=ContentType.objects.get_for_model(bulk),
                    parentid=bulk.id,
                    completetime=timezone.now(),
                )
                job.save()
                surf.parentjob = job
                surf.save()
                props = {"magmoms": surf.magmoms} if hasattr(surf, "magmoms") else {}
                calc = Calc(method=surf.method, props=props)
                calc.parentjob = job
                calc.save()
                calc.geoms.add(surf)

    if not args.dry_run:
        log(f"Added {num_surfaces} surfaces to the database.")
        log(f"{num_broken} crystals could not be converted to surfaces.")
    else:
        log(f"[DRY_RUN] Would have added {num_surfaces} surfaces.")
        log(f"[DRY_RUN] {num_broken} crystals would have failed.")

if __name__ == "__main__":
    main()
