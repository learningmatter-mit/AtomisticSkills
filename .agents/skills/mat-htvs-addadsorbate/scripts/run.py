"""
Add adsorbates to clean surfaces in the HTVS database.

Usage:
    python run.py --group <group_name> --config_name <config> --species <O|OH|OOH>
                  --bulk_pkl <pkl_path> --settings <module>

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

def get_adsorbate(species: str):
    """Build the Gratoms adsorbate object for the requested species.

    Args:
        species: Adsorbate species string ("O", "OH", or "OOH").

    Returns:
        catkit.Gratoms: Adsorbate structure.

    Raises:
        ValueError: If species is not supported.
    """
    from catkit import Gratoms

    if species == "O":
        return Gratoms("O", positions=[(0, 0, 0)])
    elif species == "OH":
        return Gratoms("OH", positions=[(0, 0, 0), (0, 1, 0.1)])
    elif species == "OOH":
        ads = Gratoms("OOH", positions=[(0, 0, 0), (0, 0, 1.4), (0, 0.9, 1.5)])
        ads.set_initial_magnetic_moments([0.7, 0.7, 0])
        return ads
    else:
        raise ValueError(f"Unsupported adsorbate species: {species!r}. Use 'O', 'OH', or 'OOH'.")

def get_clean_surface_parent(surface_obj) -> object:
    """Walk up the Job-parent chain to find the root clean_surface_cut surface.

    Args:
        surface_obj: HTVS Surface ORM object.

    Returns:
        Surface ORM object whose parentjob has config name 'clean_surface_cut'.
    """
    parent = surface_obj
    while parent.parentjob.config.name != "clean_surface_cut":
        parent = parent.parentjob.parent
    return parent

def main() -> None:
    parser = argparse.ArgumentParser(description="Add adsorbates to clean surfaces in the HTVS database.")
    parser.add_argument("--group", type=str, required=True, help="Name of the project group")
    parser.add_argument("--config_name", type=str, required=True, help="Config name of the clean surfaces")
    parser.add_argument("--species", type=str, required=True, help="Adsorbate species: O, OH, or OOH")
    parser.add_argument("--bulk_pkl", type=str, required=True, help="Pickle file of bulk IDs to filter surfaces")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum number of surfaces to process")
    parser.add_argument("--dry_run", action="store_true", help="Simulate without writing to the database")
    parser.add_argument("--settings", type=str, required=True, help="Django settings module")
    parser.add_argument("--djangochem", type=str, default=None, help="Path to the djangochem project root")
    args = parser.parse_args()

    setup_django(args.settings, args.djangochem)

    from django.utils import timezone
    from django.contrib.contenttypes.models import ContentType
    from jobs.models import Job, JobConfig
    from pgmols.models import Group, Surface, Calc
    from pgmols.utils.surfaces import add_adsorbate

    def log(msg: str) -> None:
        print(f"ADD_ADSORBATE: {msg}")

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

    for surface in tqdm(surfaces, total=len(surfaces)):
        try:
            clean_cut = get_clean_surface_parent(surface)
        except Exception:
            num_broken += 1
            continue

        details_B = (clean_cut.details or {}).get("B", [])
        for B in details_B:
            try:
                slab = surface.as_ase_gratoms()
                B_indices = np.intersect1d(
                    np.where(surface.surface_atoms)[0],
                    np.where(slab.symbols == B)[0],
                )
                if len(B_indices) == 0:
                    continue

                # Find B-top adsorption site
                found = False
                for idx in range(100):
                    slab_w_ads, surf_atoms, ads_atoms = add_adsorbate(slab, adsorbate, index=idx)
                    base = len(slab_w_ads.numbers) - len(adsorbate.numbers)
                    neighbors = slab_w_ads.get_neighbor_symbols(base)
                    if len(neighbors) == 1 and neighbors[0] == B:
                        found = True
                        break
                if not found:
                    num_broken += 1
                    continue

                # Shift adsorbate slightly inward
                pos = slab_w_ads.get_positions()
                pos[-len(adsorbate):] += [0, 0, -0.2]
                slab_w_ads.set_positions(pos)

            except Exception:
                num_broken += 1
                continue

            # Build Surface ORM object
            surf_w_ads = Surface(bulk=clean_cut.bulk, miller_index=clean_cut.miller_index)
            as_surf = Surface.from_ase_atoms(slab_w_ads)
            surf_w_ads.xyz = as_surf.xyz
            surf_w_ads.lattice = as_surf.lattice
            surf_w_ads.stoichiometry = as_surf.stoichiometry
            surf_w_ads.spacegroup = clean_cut.bulk.spacegroup
            surf_w_ads.method = clean_cut.bulk.method
            surf_w_ads.surface_atoms = surf_atoms
            surf_w_ads.adsorbate_atoms = ads_atoms
            chemical_tag = surf_w_ads.generate_hash()
            surf_w_ads.chemical_tag = chemical_tag

            magmoms = slab_w_ads.get_initial_magnetic_moments().tolist()
            if np.sum(np.abs(magmoms)) > 0:
                surf_w_ads.magmoms = magmoms
            surf_w_ads.details = {"B": [B]}

            exists = Surface.objects.filter(
                bulk=surf_w_ads.bulk,
                chemical_tag=chemical_tag,
                parentjob__group=group_obj,
                details__B__contains=B,
            ).exists()
            if exists:
                continue

            num_created += 1
            if not args.dry_run:
                job = Job(
                    config=adsorbate_config_obj,
                    group=group_obj,
                    status="done",
                    parentct=ContentType.objects.get_for_model(surface),
                    parentid=surface.id,
                    completetime=timezone.now(),
                )
                job.save()
                surf_w_ads.parentjob = job
                surf_w_ads.save()
                props = {"magmoms": surf_w_ads.magmoms} if hasattr(surf_w_ads, "magmoms") else {}
                calc = Calc(method=surf_w_ads.method, props=props)
                calc.parentjob = job
                calc.save()
                calc.geoms.add(surf_w_ads)

    if not args.dry_run:
        log(f"Added {num_created} adsorbate surfaces to the database.")
        log(f"Failed to add adsorbates to {num_broken} surfaces.")
    else:
        log(f"[DRY_RUN] Would have added {num_created} adsorbate surfaces.")
        log(f"[DRY_RUN] {num_broken} surfaces would have failed.")

if __name__ == "__main__":
    main()
