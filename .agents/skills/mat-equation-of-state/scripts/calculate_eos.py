"""
Calculate equation of state (EOS) using Machine Learning Interatomic Potentials.

This script computes the energy-volume relationship by applying volumetric strains,
fits the Birch-Murnaghan equation of state, and extracts bulk modulus and equilibrium volume.

Usage:
    python calculate_eos.py --structure Si.cif --model_type mace --output_dir eos_results

Requirements:
    - Conda environment: mace-agent, matgl-agent, or fairchem-agent
    - Required packages: ase, matcalc, pymatgen
"""

import argparse
import os
import sys
import json
import logging

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
from ase.io import read

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("EOS-Skill")


from src.utils.mlips.loader import load_wrapper


def energy_volume_curve(result):
    """Pull the energy-volume scan out of a MatCalc EOSCalc result.

    MatCalc nests it as result["eos"]["volumes"/"energies"]; older releases put
    it at the top level. Returns ([], []) when neither is present.
    """
    eos = result.get("eos")
    if isinstance(eos, dict) and "volumes" in eos and "energies" in eos:
        return list(eos["volumes"]), list(eos["energies"])
    if "volumes" in result and "energies" in result:
        return list(result["volumes"]), list(result["energies"])
    return [], []


def r2(observed, predicted):
    """Coefficient of determination, so the fallback path needs no sklearn."""
    import numpy as np

    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    ss_res = float(((observed - predicted) ** 2).sum())
    ss_tot = float(((observed - observed.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot if ss_tot else float("nan")


def run_eos(args, wrapper, atoms):
    """
    Run equation of state calculation.

    Args:
        args: Parsed command-line arguments
        wrapper: MLIP wrapper instance
        atoms: ASE Atoms object

    Returns:
        Dictionary with EOS results
    """
    from matcalc import EOSCalc

    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "mechanical" / "eos")
    os.makedirs(args.output_dir, exist_ok=True)

    calc = wrapper.create_calculator()

    logger.info(
        f"Starting EOS calculation with {args.n_points} points, ±{args.max_abs_strain*100}% strain"
    )

    eos_calc = EOSCalc(
        calculator=calc,
        n_points=args.n_points,
        max_abs_strain=args.max_abs_strain,
        relax_structure=args.relax_structure,
        fmax=args.fmax,
        max_steps=args.max_steps,
    )

    result = eos_calc.calc(atoms)

    logger.info(f"Available result keys: {list(result.keys())}")

    # MatCalc's EOSCalc exposes the Birch-Murnaghan fit only as `bulk_modulus_bm`
    # and `r2_score_bm` -- never the fitted v0/e0. The `volume` and `energy` keys
    # it does carry are inherited from its RelaxCalc step (`return result | {...}`),
    # so they describe the relaxed input cell, not the EOS minimum. Reading them
    # here reported the wrong quantity: for diamond Si at +/-8% strain they came
    # out 0.88 A^3 and 3 meV away from the fit minimum, enough to fail a
    # reproduction against a reference EOS. Refit the curve and read v0/e0 off
    # the fit itself.
    volumes, energies = energy_volume_curve(result)
    bulk_modulus = result.get("bulk_modulus_bm")
    r2_score = result.get("r2_score_bm")

    if volumes and energies:
        from pymatgen.analysis.eos import BirchMurnaghan

        bm = BirchMurnaghan(volumes=volumes, energies=energies)
        bm.fit()
        equilibrium_volume = float(bm.v0)
        equilibrium_energy = float(bm.e0)
        if bulk_modulus is None:
            bulk_modulus = float(bm.b0_GPa)
        if r2_score is None:
            r2_score = r2(energies, bm.func(volumes))
    else:
        # No E-V curve to refit (unexpected matcalc payload). Fall back to the
        # relaxation keys and say so, rather than silently reporting them as
        # the equilibrium values.
        logger.warning(
            "EOSCalc returned no energy-volume curve; falling back to the "
            "relaxed-cell volume/energy, which are NOT the Birch-Murnaghan minimum"
        )
        equilibrium_volume = result.get("volume")
        equilibrium_energy = result.get("energy")

    if bulk_modulus is not None:
        logger.info(f"Bulk modulus: {bulk_modulus:.2f} GPa")
    if equilibrium_volume is not None:
        logger.info(f"Equilibrium volume: {equilibrium_volume:.4f} ų")
    if equilibrium_energy is not None:
        logger.info(f"Equilibrium energy: {equilibrium_energy:.6f} eV")
    if r2_score is not None:
        logger.info(f"R² fit score: {r2_score:.6f}")

    # Save energy-volume data. matcalc nests the curve under result["eos"], so the
    # old top-level "volumes"/"energies" check never fired and this file was never
    # written -- leaving no way to audit the fit.
    if volumes and energies:
        data_file = os.path.join(args.output_dir, "energies_volumes.dat")
        with open(data_file, "w") as f:
            f.write("# Volume (ų)    Energy (eV)\n")
            for v, e in zip(volumes, energies):
                f.write(f"{v:12.6f}  {e:16.8f}\n")
        logger.info(f"Saved energy-volume data to {data_file}")

    # Create summary
    summary = {
        "bulk_modulus_GPa": bulk_modulus,
        "equilibrium_volume_A3": equilibrium_volume,
        "equilibrium_energy_eV": equilibrium_energy,
        "r2_score": r2_score,
        "energy_volume_curve": {"volumes_A3": volumes, "energies_eV": energies},
        "n_points": args.n_points,
        "max_abs_strain": args.max_abs_strain,
        "output_dir": args.output_dir,
        "model_type": args.model_type,
        "model_name": wrapper.model_name,
    }

    # Save results
    results_file = os.path.join(args.output_dir, "eos_results.json")
    with open(results_file, "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)

    logger.info(f"EOS calculation completed. Results saved to {args.output_dir}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate equation of state with MLIPs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--structure", required=True, help="Path to structure file (CIF, POSCAR, etc.)"
    )
    parser.add_argument(
        "--model_type",
        required=True,
        choices=["mace", "fairchem", "matgl"],
        help="MLIP type",
    )
    parser.add_argument(
        "--model_name", default=None, help="Specific model name (optional)"
    )
    parser.add_argument(
        "--n_points", type=int, default=11, help="Number of strain points"
    )
    parser.add_argument(
        "--max_abs_strain",
        type=float,
        default=0.1,
        help="Maximum absolute volumetric strain (0.1 = ±10%%)",
    )
    parser.add_argument(
        "--relax_structure",
        action="store_true",
        default=True,
        help="Relax atomic positions at each strain point",
    )
    parser.add_argument(
        "--fmax", type=float, default=0.1, help="Force convergence tolerance (eV/Å)"
    )
    parser.add_argument(
        "--max_steps", type=int, default=500, help="Maximum relaxation steps"
    )
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")

    args = parser.parse_args()

    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    atoms = read(args.structure)

    logger.info(f"Input structure: {args.structure}")
    logger.info(f"Formula: {atoms.get_chemical_formula()}")
    logger.info(f"Number of atoms: {len(atoms)}")

    run_eos(args, wrapper, atoms)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs

    save_skill_inputs(args, args.output_dir)
