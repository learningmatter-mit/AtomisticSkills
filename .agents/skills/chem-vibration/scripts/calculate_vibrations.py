"""
Calculate vibrational frequencies and normal modes for molecules and clusters.

Uses ASE's Vibrations class within the harmonic approximation to compute
vibrational frequencies, zero-point energy, and mode trajectories for
finite (non-periodic) systems powered by MLIPs.

For periodic systems, use the mat-phonon skill instead.

Usage:
    python calculate_vibrations.py --molecule H2O --model_type mace --output_dir results
    python calculate_vibrations.py --structure mol.xyz --model_type mace --no_relax --output_dir results

Requirements:
    - Conda environment: mace-agent, matgl-agent, or fairchem-agent
    - Required packages: ase, numpy
"""

import argparse
import os
import sys
import json
import logging
import shutil
from typing import Optional, Any

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
from ase.io import read
from ase.build import molecule as ase_molecule
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("Vibration-Skill")

# Threshold below which a frequency is translational/rotational (cm^-1)
TRANSLATION_ROTATION_THRESHOLD = 50.0


from src.utils.mlips.loader import load_wrapper

def check_linearity(atoms, tol: float = 5.0) -> bool:
    """
    Check if a molecule is linear.

    A molecule is linear if all atoms lie along a single line. This is determined
    by checking if the smallest principal moment of inertia is near zero.

    Args:
        atoms: ASE Atoms object
        tol: Tolerance for moment of inertia ratio (default: 5.0 degrees)

    Returns:
        True if the molecule is linear
    """
    if len(atoms) <= 2:
        return True
    positions = atoms.get_positions()
    centered = positions - positions.mean(axis=0)
    # Use SVD to check collinearity
    _, s, _ = np.linalg.svd(centered)
    # If the second singular value is negligible compared to the first, it's linear
    if s[0] > 1e-10:
        return s[1] / s[0] < 0.01
    return True


def run_vibrations(args: argparse.Namespace, wrapper: Any, atoms) -> dict:
    """
    Run vibrational analysis using ASE's Vibrations class.

    Args:
        args: Parsed command-line arguments
        wrapper: MLIP wrapper instance
        atoms: ASE Atoms object (should be at equilibrium)

    Returns:
        Dictionary with vibrational analysis results
    """
    from ase.vibrations import Vibrations
    from ase.optimize import LBFGS

    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "vibrational" / "vibrations")
    os.makedirs(args.output_dir, exist_ok=True)

    calc = wrapper.create_calculator()
    atoms.calc = calc

    # Ensure non-periodic boundary conditions for molecules
    atoms.pbc = False

    # Optionally relax the structure
    if args.relax:
        logger.info(f"Relaxing structure with fmax={args.fmax} eV/Å ...")
        opt = LBFGS(atoms, logfile=os.path.join(args.output_dir, "relax.log"))
        opt.run(fmax=args.fmax)
        logger.info(f"Relaxation converged in {opt.nsteps} steps. Energy: {atoms.get_potential_energy():.6f} eV")

    # Check linearity
    is_linear = check_linearity(atoms)
    n_atoms = len(atoms)
    n_expected_modes = 3 * n_atoms - 5 if is_linear else 3 * n_atoms - 6
    logger.info(f"Molecule: {atoms.get_chemical_formula()}, {n_atoms} atoms, linear={is_linear}")
    logger.info(f"Expected vibrational modes: {n_expected_modes}")

    # Run vibration analysis
    vib_name = os.path.join(args.output_dir, "vib")
    vib = Vibrations(atoms, indices=None, delta=args.delta, name=vib_name, nfree=args.nfree)
    vib.clean()  # Remove any cached data
    vib.run()

    # Get results
    energies_ev = vib.get_energies()  # complex array in eV
    frequencies_cm1 = vib.get_frequencies()  # complex array in cm^-1

    # Classify modes
    real_modes = []
    imaginary_modes = []
    translational_rotational = []

    for i, (e_ev, f_cm1) in enumerate(zip(energies_ev, frequencies_cm1)):
        freq_real = float(np.real(f_cm1))
        freq_imag = float(np.imag(f_cm1))
        energy_mev = float(np.real(e_ev)) * 1000.0

        if abs(freq_imag) > TRANSLATION_ROTATION_THRESHOLD:
            imaginary_modes.append({
                "index": i,
                "frequency_cm1": -abs(freq_imag),
                "energy_meV": energy_mev,
                "type": "imaginary"
            })
        elif abs(freq_real) < TRANSLATION_ROTATION_THRESHOLD:
            translational_rotational.append({
                "index": i,
                "frequency_cm1": freq_real,
                "energy_meV": energy_mev,
                "type": "translation/rotation"
            })
        else:
            real_modes.append({
                "index": i,
                "frequency_cm1": freq_real,
                "energy_meV": energy_mev,
                "type": "vibration"
            })

    # Get ZPE
    zpe_ev = float(vib.get_zero_point_energy())

    # Print summary
    logger.info("=" * 60)
    logger.info("Vibration Analysis Summary")
    logger.info("=" * 60)
    vib.summary()
    logger.info(f"Zero-point energy: {zpe_ev:.4f} eV ({zpe_ev * 1000:.2f} meV)")
    logger.info(f"Real vibrational modes: {len(real_modes)}")
    logger.info(f"Translation/rotation modes: {len(translational_rotational)}")
    logger.info(f"Imaginary modes: {len(imaginary_modes)}")
    logger.info("=" * 60)

    if len(real_modes) != n_expected_modes:
        logger.warning(
            f"Found {len(real_modes)} real modes, expected {n_expected_modes}. "
            f"This may indicate the structure is not fully relaxed."
        )

    # Write mode trajectories
    for i in range(len(energies_ev)):
        vib.write_mode(i)

    # Build all-frequencies list for JSON
    all_frequencies_cm1 = []
    all_frequencies_mev = []
    for e_ev, f_cm1 in zip(energies_ev, frequencies_cm1):
        freq_imag = float(np.imag(f_cm1))
        freq_real = float(np.real(f_cm1))
        if abs(freq_imag) > 0.1:
            all_frequencies_cm1.append(f"{abs(freq_imag):.1f}i")
            all_frequencies_mev.append(f"{abs(float(np.imag(e_ev))) * 1000:.1f}i")
        else:
            all_frequencies_cm1.append(round(freq_real, 1))
            all_frequencies_mev.append(round(float(np.real(e_ev)) * 1000, 1))

    # Create summary
    summary = {
        "formula": atoms.get_chemical_formula(),
        "n_atoms": n_atoms,
        "is_linear": is_linear,
        "n_expected_vibrational_modes": n_expected_modes,
        "frequencies_cm1": all_frequencies_cm1,
        "frequencies_meV": all_frequencies_mev,
        "real_modes": real_modes,
        "imaginary_modes": imaginary_modes,
        "translational_rotational_modes": translational_rotational,
        "zero_point_energy_eV": zpe_ev,
        "zero_point_energy_meV": zpe_ev * 1000,
        "delta_angstrom": args.delta,
        "nfree": args.nfree,
        "model_type": args.model_type,
        "model_name": wrapper.model_name,
        "output_dir": args.output_dir,
    }

    # Save results
    results_file = os.path.join(args.output_dir, "vibration_results.json")
    with open(results_file, "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)

    logger.info(f"Results saved to {results_file}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate vibrational frequencies and normal modes with MLIPs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--molecule", help="ASE built-in molecule name (e.g., H2O, CO2, CH4, NH3)")
    group.add_argument("--structure", help="Path to structure file (.xyz, .cif, POSCAR, etc.)")

    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem", "matgl"],
                        help="MLIP type")
    parser.add_argument("--model_name", default=None, help="Specific model name (optional)")
    parser.add_argument("--delta", type=float, default=0.01,
                        help="Finite-difference displacement in Angstrom")
    parser.add_argument("--nfree", type=int, default=2, choices=[2, 4],
                        help="Number of displacements per degree of freedom (2 or 4)")
    parser.add_argument("--relax", action="store_true", default=True,
                        help="Relax structure before vibration analysis")
    parser.add_argument("--no_relax", action="store_true", default=False,
                        help="Skip structure relaxation")
    parser.add_argument("--fmax", type=float, default=0.001,
                        help="Force convergence for relaxation (eV/Angstrom)")
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")

    args = parser.parse_args()

    if args.no_relax:
        args.relax = False

    # Load structure
    if args.molecule:
        atoms = ase_molecule(args.molecule)
        logger.info(f"Built molecule: {args.molecule}")
    else:
        atoms = read(args.structure)
        logger.info(f"Loaded structure: {args.structure}")

    logger.info(f"Formula: {atoms.get_chemical_formula()}")
    logger.info(f"Number of atoms: {len(atoms)}")

    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    run_vibrations(args, wrapper, atoms)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
