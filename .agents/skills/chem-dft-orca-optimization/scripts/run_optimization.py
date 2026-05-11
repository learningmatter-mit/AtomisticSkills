"""
Run DFT geometry optimization (minimization or TS search) using ORCA via
SCINE/ReaDuct wrapper.

Supports two optimization modes:
  - Minimization (default): finds the nearest local minimum
  - TS optimization: single-ended transition state search

Usage:
    python run_optimization.py --structure molecule.xyz --opt_type min
    python run_optimization.py --structure ts_guess.xyz --opt_type ts --functional B3LYP --basis_set def2-TZVP

Requirements:
    - Conda environment: orca-agent
    - Required packages: scine_utilities, scine_readuct, ase, numpy
    - Environment variable: ORCA_BINARY_PATH
"""

import argparse
import json
import logging
import os
import sys
from contextlib import contextmanager
from typing import Optional

import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import ase.io
import scine_readuct as readuct
import scine_utilities as su

from src.utils.dft.orca_utils import (
    BOHR_PER_ANGSTROM,
    HARTREE_TO_EV,
    parse_json_settings,
    scine_positions_to_ase,
    setup_orca_calculator,
)
from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ORCA-Optimization")


@contextmanager
def cwd(path):
    oldpwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldpwd)


def run_optimization(
    structure_path: str,
    opt_type: str = "min",
    charge: int = 0,
    spin_multiplicity: int = 1,
    functional: str = "PBE",
    basis_set: str = "def2-SVP",
    dispersion: Optional[str] = None,
    solvation: Optional[str] = None,
    solvent: Optional[str] = None,
    special_option: str = "NOSOSCF",
    nprocs: int = 1,
    convergence_max_iterations: int = 200,
    extra_calculator_settings: Optional[dict] = None,
    extra_optimizer_settings: Optional[dict] = None,
    calculate_final_hessian: bool = False,
    output_dir: str = ".",
) -> dict:
    """
    Execute a DFT geometry optimization and return results.

    Args:
        structure_path: Path to input structure file
        opt_type: Optimization type, "min" for minimization or "ts" for TS search
        charge: Molecular charge
        spin_multiplicity: Spin multiplicity (2S+1)
        functional: DFT functional
        basis_set: Basis set
        dispersion: Dispersion correction or None
        solvation: Solvation model (CPCM/SMD) or None
        solvent: Solvent name or None
        special_option: ORCA special option (default: NOSOSCF)
        nprocs: Number of CPU cores
        convergence_max_iterations: Maximum optimization steps
        extra_calculator_settings: Additional SCINE calculator settings (dict)
        extra_optimizer_settings: Additional ReaDuct optimizer kwargs (dict)
        calculate_final_hessian: Whether to compute the Hessian at the optimized geometry
        output_dir: Output directory

    Returns:
        Dictionary with optimization results
    """
    os.makedirs(output_dir, exist_ok=True)

    calculator, atom_collection, atoms_initial = setup_orca_calculator(
        structure_path=structure_path,
        charge=charge,
        spin_multiplicity=spin_multiplicity,
        functional=functional,
        basis_set=basis_set,
        dispersion=dispersion,
        solvation=solvation,
        solvent=solvent,
        special_option=special_option,
        nprocs=nprocs,
        extra_calculator_settings=extra_calculator_settings,
        output_dir=output_dir
    )

    ase.io.write(os.path.join(output_dir, "initial_structure.xyz"), atoms_initial)

    systems = {"input": calculator}
    task_kwargs = {
        "convergence_max_iterations": convergence_max_iterations,
    }
    if extra_optimizer_settings:
        task_kwargs.update(extra_optimizer_settings)
        logger.info(f"Extra optimizer settings: {extra_optimizer_settings}")

    with cwd(output_dir):
        if opt_type == "min":
            logger.info(f"Running geometry minimization (max {convergence_max_iterations} steps)...")
            output_key = "opt"
            systems, success = readuct.run_opt_task(
                systems, ["input"], output=[output_key], **task_kwargs
            )
            if calculate_final_hessian:
                systems, success = readuct.run_hessian_task(
                    systems, [output_key]
                )
        elif opt_type == "ts":
            logger.info(f"Running TS optimization (max {convergence_max_iterations} steps)...")
            output_key = "tsopt"
            systems, success = readuct.run_tsopt_task(
                systems, ["input"], output=[output_key], **task_kwargs
            )
            if calculate_final_hessian:
                systems, success = readuct.run_hessian_task(
                    systems, [output_key],
                )
        else:
            raise ValueError(f"Unknown opt_type: {opt_type}. Must be 'min' or 'ts'.")

        if success:
            logger.info("Optimization converged successfully.")
        else:
            logger.warning("Optimization did NOT converge within the maximum number of steps.")

    opt_calculator = systems[output_key]
    final_structure = opt_calculator.structure
    final_positions_ang = scine_positions_to_ase(final_structure.positions)

    atoms_final = atoms_initial.copy()
    atoms_final.set_positions(final_positions_ang)
    ase.io.write(os.path.join(output_dir, "optimized_structure.xyz"), atoms_final)
    logger.info(f"Optimized structure written to {output_dir}/optimized_structure.xyz")

    final_results = opt_calculator.get_results()
    if (final_results.energy is None or final_results.gradients is None
            or (calculate_final_hessian and final_results.hessian is None)):
        if calculate_final_hessian:
            opt_calculator.set_required_properties([su.Property.Energy, su.Property.Gradients, su.Property.Hessian])
        else:
            opt_calculator.set_required_properties([su.Property.Energy, su.Property.Gradients])
        final_results = opt_calculator.calculate()

    final_energy_hartree = final_results.energy
    final_energy_ev = final_energy_hartree * HARTREE_TO_EV
    final_gradients = final_results.gradients
    final_forces = -1.0 * final_gradients * HARTREE_TO_EV * BOHR_PER_ANGSTROM
    max_force = float(np.max(np.abs(final_forces)))
    rms_force = float(np.sqrt(np.mean(final_forces**2)))

    logger.info(f"Final energy: {final_energy_hartree:.10f} Hartree = {final_energy_ev:.6f} eV")
    logger.info(f"Final max force: {max_force:.6f} eV/A, RMS force: {rms_force:.6f} eV/A")

    output = {
        "structure": os.path.basename(structure_path),
        "formula": atoms_initial.get_chemical_formula(),
        "n_atoms": len(atoms_initial),
        "opt_type": opt_type,
        "converged": bool(success),
        "charge": charge,
        "spin_multiplicity": spin_multiplicity,
        "functional": functional,
        "basis_set": basis_set,
        "dispersion": dispersion,
        "solvation": solvation,
        "solvent": solvent,
        "max_iterations": convergence_max_iterations,
        "final_energy_hartree": final_energy_hartree,
        "final_energy_eV": final_energy_ev,
        "final_max_force_eV_per_Ang": max_force,
        "final_rms_force_eV_per_Ang": rms_force,
        "initial_structure_file": "initial_structure.xyz",
        "optimized_structure_file": "optimized_structure.xyz",
    }

    if calculate_final_hessian:
        hessian = final_results.hessian
        hessian_ev_ang2 = hessian * HARTREE_TO_EV * BOHR_PER_ANGSTROM**2
        output["hessian_eV_per_Ang2"] = hessian_ev_ang2.tolist()

        n_atoms = len(atoms_initial)
        normal_modes_container = su.normal_modes.calculate(hessian, final_structure)
        wave_numbers = normal_modes_container.get_wave_numbers()

        n_imaginary = sum(int(n < -1e-6) for n in wave_numbers)
        output["n_imaginary_modes"] = n_imaginary
        output["hessian_wave_numbers_cm-1"] = wave_numbers

        logger.info(f"Hessian computed: {3 * n_atoms}x{3 * n_atoms} matrix")
        logger.info(f"Number of imaginary modes: {n_imaginary}")
        if opt_type == "ts" and n_imaginary != 1:
            logger.warning(
                f"TS optimization expects exactly 1 imaginary mode, found {n_imaginary}"
            )
        elif opt_type == "min" and n_imaginary != 0:
            logger.warning(
                f"Optimization expects no imaginary modes, found {n_imaginary}"
            )

    return output


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run DFT geometry optimization with ORCA via SCINE/ReaDuct",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--structure", required=True, help="Path to input structure (.xyz, .cif, etc.)")
    parser.add_argument("--opt_type", default="min", choices=["min", "ts"],
                        help="Optimization type: 'min' for minimization, 'ts' for transition state")
    parser.add_argument("--charge", type=int, default=0, help="Molecular charge")
    parser.add_argument("--spin_multiplicity", type=int, default=1, help="Spin multiplicity (2S+1)")
    parser.add_argument("--functional", default="PBE", help="DFT functional (e.g. PBE, B3LYP, wB97X-V)")
    parser.add_argument("--basis_set", default="def2-SVP", help="Basis set (e.g. def2-SVP, def2-TZVP)")
    parser.add_argument("--dispersion", default=None, help="Dispersion correction (e.g. D3BJ, D4)")
    parser.add_argument("--solvation", default=None, choices=["CPCM", "SMD"], help="Implicit solvation model")
    parser.add_argument("--solvent", default=None, help="Solvent name (e.g. water, ethanol); required if --solvation is set")
    parser.add_argument("--special_option", default="NOSOSCF", help="ORCA special option (default: NOSOSCF). Set to empty string to disable.")
    parser.add_argument("--nprocs", type=int, default=1, help="Number of CPU cores for ORCA")
    parser.add_argument("--convergence_max_iterations", type=int, default=200, help="Maximum optimization steps")
    parser.add_argument("--calculator_settings", default=None,
                        help='Extra SCINE calculator settings as JSON string, e.g. \'{"scf_max_iterations": 128}\'')
    parser.add_argument("--optimizer_settings", default=None,
                        help='Extra ReaDuct optimizer kwargs as JSON string, e.g. \'{"convergence_delta_value": 1e-6}\'')
    parser.add_argument("--calculate_final_hessian", action="store_true",
                        help="Compute Hessian at optimized geometry (useful for TS verification)")
    parser.add_argument("--output_dir", default=None, help="Output directory")

    args = parser.parse_args()

    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "orca_optimization")
    os.makedirs(args.output_dir, exist_ok=True)

    extra_calc = parse_json_settings(args.calculator_settings)
    extra_opt = parse_json_settings(args.optimizer_settings)

    result = run_optimization(
        structure_path=args.structure,
        opt_type=args.opt_type,
        charge=args.charge,
        spin_multiplicity=args.spin_multiplicity,
        functional=args.functional,
        basis_set=args.basis_set,
        dispersion=args.dispersion,
        solvation=args.solvation,
        solvent=args.solvent,
        special_option=args.special_option,
        nprocs=args.nprocs,
        convergence_max_iterations=args.convergence_max_iterations,
        extra_calculator_settings=extra_calc,
        extra_optimizer_settings=extra_opt,
        calculate_final_hessian=args.calculate_final_hessian,
        output_dir=args.output_dir,
    )

    results_file = os.path.join(args.output_dir, "optimization_results.json")
    with open(results_file, "w") as f:
        json.dump(recursive_tolist(result), f, indent=4)
    logger.info(f"Results saved to {results_file}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
