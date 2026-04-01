"""
Run a DFT single-point energy calculation using ORCA via SCINE wrapper.

Computes the electronic energy and optionally gradients (forces) and/or the
Hessian for a given molecular structure. Uses curated defaults suitable for
standard DFT calculations.

Usage:
    python run_singlepoint.py --structure molecule.xyz
    python run_singlepoint.py --structure molecule.xyz --functional B3LYP --basis_set def2-TZVP --compute_gradients
    python run_singlepoint.py --structure molecule.xyz --solvation SMD --solvent water

Requirements:
    - Conda environment: orca-agent
    - Required packages: scine_utilities, ase, numpy
    - Environment variable: ORCA_BINARY_PATH
"""

import argparse
import json
import logging
import os
import sys
from typing import Optional

import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import ase.io
import scine_utilities as su

from src.utils.dft.orca_utils import (
    BOHR_PER_ANGSTROM,
    HARTREE_TO_EV,
    parse_json_settings,
    setup_orca_calculator,
)
from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ORCA-Singlepoint")


def run_singlepoint(
    structure_path: str,
    charge: int = 0,
    spin_multiplicity: int = 1,
    functional: str = "PBE",
    basis_set: str = "def2-SVP",
    dispersion: Optional[str] = None,
    solvation: Optional[str] = None,
    solvent: Optional[str] = None,
    special_option: str = "NOSOSCF",
    nprocs: int = 1,
    compute_gradients: bool = False,
    compute_hessian: bool = False,
    extra_calculator_settings: Optional[dict] = None,
    output_dir: str = ".",
) -> dict:
    """
    Execute a DFT single-point calculation and return results.

    Args:
        structure_path: Path to input structure file
        charge: Molecular charge
        spin_multiplicity: Spin multiplicity (2S+1)
        functional: DFT functional
        basis_set: Basis set
        dispersion: Dispersion correction or None
        solvation: Solvation model (CPCM/SMD) or None
        solvent: Solvent name or None
        special_option: ORCA special option (default: NOSOSCF)
        nprocs: Number of CPU cores
        compute_gradients: Whether to compute gradients/forces
        compute_hessian: Whether to compute the Hessian matrix
        extra_calculator_settings: Additional SCINE calculator settings (dict)
        output_dir: Output directory

    Returns:
        Dictionary with calculation results
    """
    os.makedirs(output_dir, exist_ok=True)

    calculator, atom_collection, atoms = setup_orca_calculator(
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
    )

    props = [su.Property.Energy]
    if compute_gradients:
        props.append(su.Property.Gradients)
    if compute_hessian:
        props.append(su.Property.Hessian)

    logger.info(f"Requesting properties: {[p.name for p in props]}")
    calculator.set_required_properties(props)

    logger.info("Running ORCA single-point calculation...")
    results = calculator.calculate()
    logger.info("Calculation completed.")

    energy_hartree = results.energy
    energy_ev = energy_hartree * HARTREE_TO_EV
    logger.info(f"Energy: {energy_hartree:.10f} Hartree = {energy_ev:.6f} eV")

    output = {
        "structure": os.path.basename(structure_path),
        "formula": atoms.get_chemical_formula(),
        "n_atoms": len(atoms),
        "charge": charge,
        "spin_multiplicity": spin_multiplicity,
        "functional": functional,
        "basis_set": basis_set,
        "dispersion": dispersion,
        "solvation": solvation,
        "solvent": solvent,
        "energy_hartree": energy_hartree,
        "energy_eV": energy_ev,
    }

    if compute_gradients:
        gradients = results.gradients
        forces_ev_ang = -1.0 * gradients * HARTREE_TO_EV * BOHR_PER_ANGSTROM
        max_force = float(np.max(np.abs(forces_ev_ang)))
        rms_force = float(np.sqrt(np.mean(forces_ev_ang**2)))
        logger.info(f"Max force: {max_force:.6f} eV/A, RMS force: {rms_force:.6f} eV/A")
        output["forces_eV_per_Ang"] = forces_ev_ang.tolist()
        output["max_force_eV_per_Ang"] = max_force
        output["rms_force_eV_per_Ang"] = rms_force

    if compute_hessian:
        hessian = results.hessian
        hessian_ev_ang2 = hessian * HARTREE_TO_EV * BOHR_PER_ANGSTROM**2
        output["hessian_eV_per_Ang2"] = hessian_ev_ang2.tolist()
        logger.info(f"Hessian computed: {hessian_ev_ang2.shape[0]}x{hessian_ev_ang2.shape[1]} matrix")

    ase.io.write(os.path.join(output_dir, "input_structure.xyz"), atoms)

    return output


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run DFT single-point calculation with ORCA via SCINE",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--structure", required=True, help="Path to input structure (.xyz, .cif, etc.)")
    parser.add_argument("--charge", type=int, default=0, help="Molecular charge")
    parser.add_argument("--spin_multiplicity", type=int, default=1, help="Spin multiplicity (2S+1)")
    parser.add_argument("--functional", default="PBE", help="DFT functional (e.g. PBE, B3LYP, wB97X-V)")
    parser.add_argument("--basis_set", default="def2-SVP", help="Basis set (e.g. def2-SVP, def2-TZVP)")
    parser.add_argument("--dispersion", default=None, help="Dispersion correction (e.g. D3BJ, D4)")
    parser.add_argument("--solvation", default=None, choices=["CPCM", "SMD"], help="Implicit solvation model")
    parser.add_argument("--solvent", default=None, help="Solvent name (e.g. water, ethanol); required if --solvation is set")
    parser.add_argument("--special_option", default="NOSOSCF", help="ORCA special option (default: NOSOSCF). Set to empty string to disable.")
    parser.add_argument("--nprocs", type=int, default=1, help="Number of CPU cores for ORCA")
    parser.add_argument("--compute_gradients", action="store_true", help="Compute gradients (forces)")
    parser.add_argument("--compute_hessian", action="store_true", help="Compute Hessian matrix")
    parser.add_argument("--calculator_settings", default=None,
                        help='Extra SCINE calculator settings as JSON string, e.g. \'{"max_scf_iterations": 420}\'')
    parser.add_argument("--output_dir", default=None, help="Output directory")

    args = parser.parse_args()

    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "orca_singlepoint")
    os.makedirs(args.output_dir, exist_ok=True)

    extra_calc = parse_json_settings(args.calculator_settings)

    result = run_singlepoint(
        structure_path=args.structure,
        charge=args.charge,
        spin_multiplicity=args.spin_multiplicity,
        functional=args.functional,
        basis_set=args.basis_set,
        dispersion=args.dispersion,
        solvation=args.solvation,
        solvent=args.solvent,
        special_option=args.special_option,
        nprocs=args.nprocs,
        compute_gradients=args.compute_gradients,
        compute_hessian=args.compute_hessian,
        extra_calculator_settings=extra_calc,
        output_dir=args.output_dir,
    )

    results_file = os.path.join(args.output_dir, "singlepoint_results.json")
    with open(results_file, "w") as f:
        json.dump(recursive_tolist(result), f, indent=4)
    logger.info(f"Results saved to {results_file}")


if __name__ == "__main__":
    main()
