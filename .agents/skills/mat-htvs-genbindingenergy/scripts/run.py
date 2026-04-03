"""
Calculate and store surface binding energies in the HTVS database.

Usage:
    python run.py --group <group_name> --config_name <config>
                  --ref_group <ref_group> --ref_config <ref_config>
                  --method <method_name> --metric <metric_name>
                  --settings <module>

Requirements:
    - Conda environment: htvs-agent
    - Required packages: django, pgmols, docking, pymatgen, numpy, tqdm
"""
import os
import sys
import argparse

from src.utils.htvs.script_runner import setup_django

import numpy as np
from tqdm import tqdm

def get_adsorbate_formula(surface_obj) -> str:
    """Extract the adsorbate formula from a surface object.

    Args:
        surface_obj: HTVS Surface ORM object with adsorbate_atoms and xyz fields.

    Returns:
        Sorted string of adsorbate element symbols (e.g. 'HO', 'HOO', 'O').
    """
    from pymatgen.core.periodic_table import Element

    atomic_numbers = [row[0] for row in surface_obj.xyz]
    symbols = [Element.from_Z(z).symbol for z in atomic_numbers]
    ads_symbols = [symbols[i] for i in np.where(surface_obj.adsorbate_atoms)[0]]
    ads_symbols.sort()
    return "".join(ads_symbols)

def get_energy(geom_obj, method_obj) -> float:
    """Retrieve the total DFT energy from a crystal/surface record.

    Args:
        geom_obj: HTVS Crystal or Surface ORM object.
        method_obj: HTVS Method ORM object to filter calcs by.

    Returns:
        Total energy in Ha.
    """
    calc = geom_obj.calcs.get(props__totalenergy__isnull=False, method=method_obj)
    return calc.props["totalenergy"]

def get_optimized_clean(surface_obj, config_obj):
    """Walk up the job chain to the clean surface, then fetch its optimized child slab.

    Args:
        surface_obj: Adsorbate-bearing surface ORM object.
        config_obj: JobConfig ORM object for the relaxation config.

    Returns:
        Queryset of optimized clean slab geoms, or None if not found.
    """
    parent = surface_obj
    while parent.parentjob.config.name != "clean_surface_cut":
        parent = parent.parentjob.parent

    done_job = parent.childjobs.filter(config=config_obj, status="done").first()
    if done_job is None:
        return None
    return done_job.childgeoms.all()

def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate surface binding energies in the HTVS database.")
    parser.add_argument("--group", type=str, required=True, help="Name of the project group")
    parser.add_argument("--config_name", type=str, required=True, help="JobConfig name for adsorbate surface calculations")
    parser.add_argument("--ref_group", type=str, default="surface_binding_energy_references",
                        help="Group name containing gas-phase reference crystals (default: surface_binding_energy_references)")
    parser.add_argument("--ref_config", type=str, default="pbe_u_paw_spinpol_opt_vasp",
                        help="Config name of gas-phase reference calculations (default: pbe_u_paw_spinpol_opt_vasp)")
    parser.add_argument("--method", type=str, default="dft_d3_paw_gga_pbe",
                        help="Method name used for surface energy calculations (default: dft_d3_paw_gga_pbe)")
    parser.add_argument("--metric", type=str, default="surface_binding_dE",
                        help="AffinityType name for the stored binding energy (default: surface_binding_dE)")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum number of surfaces to process")
    parser.add_argument("--dry_run", action="store_true", help="Simulate without writing to the database")
    parser.add_argument("--settings", type=str, required=True, help="Django settings module")
    parser.add_argument("--djangochem", type=str, default=None, help="Path to the djangochem project root")
    args = parser.parse_args()

    setup_django(args.settings, args.djangochem)

    from jobs.models import JobConfig
    from pgmols.models import Group, Crystal, Surface, Method
    from docking.models import AffinityType, BindingEnergy

    def log(msg: str) -> None:
        print(f"GEN_BINDING_ENERGY: {msg}")

    group_obj = Group.objects.get(name=args.group)
    config_obj = JobConfig.objects.get(name=args.config_name)
    method_obj = Method.objects.get(name=args.method)
    metric_obj = AffinityType.objects.get(name=args.metric)

    # Load gas-phase references dynamically
    ref_group_obj = Group.objects.get(name=args.ref_group)
    ref_config_obj = JobConfig.objects.get(name=args.ref_config)
    ref_crystals = Crystal.objects.filter(
        parentjob__group=ref_group_obj,
        parentjob__config=ref_config_obj,
    )
    h2o_ref = get_energy(ref_crystals.get(stoichiometry__formula="H2O"), method_obj)
    h2_ref = get_energy(ref_crystals.get(stoichiometry__formula="H2"), method_obj)
    log(f"Gas references: H2O={h2o_ref:.6f} Ha, H2={h2_ref:.6f} Ha")

    surfaces = Surface.objects.filter(
        parentjob__group=group_obj,
        parentjob__config=config_obj,
    ).filter(adsorbate_atoms__contains=[True])

    if args.limit:
        surfaces = surfaces[: args.limit]

    log(f"Processing {len(surfaces)} adsorbate surfaces.")
    num_created = 0

    for surface in tqdm(surfaces, total=len(surfaces)):
        # Skip if binding energy already exists
        if BindingEnergy.objects.filter(metric=metric_obj, surface_w_adsorbate=surface).exists():
            continue

        clean_geoms = get_optimized_clean(surface, config_obj)
        if not clean_geoms:
            continue

        clean_surface = clean_geoms.first().crystal.surface
        adsorbate = get_adsorbate_formula(surface)

        # Stoichiometric coefficients for OER intermediates
        coeff_map = {
            "O":   {"n_h2o": 1, "n_h": -2},
            "HO":  {"n_h2o": 1, "n_h": -1},
            "HOO": {"n_h2o": 2, "n_h": -3},
        }
        if adsorbate not in coeff_map:
            log(f"Skipping unsupported adsorbate: {adsorbate!r}")
            continue

        n_h2o = coeff_map[adsorbate]["n_h2o"]
        n_h = coeff_map[adsorbate]["n_h"]

        energy_w_ads = get_energy(surface, method_obj)
        energy_clean = get_energy(clean_surface, method_obj)
        dE = energy_w_ads - energy_clean - n_h2o * h2o_ref - n_h * h2_ref / 2

        be = BindingEnergy(
            metric=metric_obj,
            value=dE,
            units="Ha",
            adsorbate=adsorbate,
            clean_surface=clean_surface,
            surface_w_adsorbate=surface,
        )
        num_created += 1
        if not args.dry_run:
            be.save()

    if not args.dry_run:
        log(f"Saved {num_created} binding energies to the database.")
    else:
        log(f"[DRY_RUN] Would have saved {num_created} binding energies.")

if __name__ == "__main__":
    main()
