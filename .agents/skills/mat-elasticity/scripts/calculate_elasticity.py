"""
Calculate elastic tensor and mechanical properties using Machine Learning Interatomic Potentials.

This script computes the full elastic tensor (C_ij) by applying systematic normal and shear
strains, computing stress responses, and fitting elastic constants via least-squares regression.
It uses MatCalc's ElasticityCalc, which builds on pymatgen's DeformedStructureSet and ElasticTensor.

Usage:
    python calculate_elasticity.py --structure Cu.cif --model_type mace --output_dir elasticity_results

Requirements:
    - Conda environment: mace-agent, matgl-agent, or fairchem-agent
    - Required packages: ase, matcalc, pymatgen
"""

import argparse
import os
import sys
import json
import logging
from typing import Optional, Any

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
from ase.io import read
import numpy as np

# Conversion factors
EV_PER_A3_TO_GPA = 160.2176634  # 1 eV/ų = 160.2176634 GPa

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("Elasticity-Skill")


from src.utils.mlips.loader import load_wrapper

def run_elasticity(args: argparse.Namespace, wrapper: Any, atoms) -> dict:
    """
    Run elastic tensor calculation using MatCalc's ElasticityCalc.

    Args:
        args: Parsed command-line arguments
        wrapper: MLIP wrapper instance
        atoms: ASE Atoms object

    Returns:
        Dictionary with elastic properties in GPa
    """
    from matcalc import ElasticityCalc

    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "mechanical" / "elasticity")
    os.makedirs(args.output_dir, exist_ok=True)

    calc = wrapper.create_calculator()

    logger.info(f"Normal strains: {args.norm_strains}")
    logger.info(f"Shear strains: {args.shear_strains}")
    logger.info(f"Relax structure: {args.relax_structure}")
    logger.info(f"Relax deformed structures: {args.relax_deformed}")

    elast_calc = ElasticityCalc(
        calculator=calc,
        norm_strains=args.norm_strains,
        shear_strains=args.shear_strains,
        fmax=args.fmax,
        symmetry=args.symmetry,
        relax_structure=args.relax_structure,
        relax_deformed_structures=args.relax_deformed,
        use_equilibrium=True,
    )

    result = elast_calc.calc(atoms)

    # Extract the elastic tensor in Voigt notation (6x6)
    elastic_tensor = result["elastic_tensor"]  # pymatgen ElasticTensor object (3x3x3x3)
    voigt_tensor = elastic_tensor.voigt  # 6x6 numpy array in eV/ų

    # Convert to GPa
    voigt_tensor_gpa = voigt_tensor * EV_PER_A3_TO_GPA
    bulk_modulus_gpa = result["bulk_modulus_vrh"] * EV_PER_A3_TO_GPA
    shear_modulus_gpa = result["shear_modulus_vrh"] * EV_PER_A3_TO_GPA

    # Compute Young's modulus and Poisson's ratio from VRH moduli in GPa
    # E = 9BG / (3B + G),  ν = (3B - 2G) / (6B + 2G)
    denom_e = 3 * bulk_modulus_gpa + shear_modulus_gpa
    denom_nu = 6 * bulk_modulus_gpa + 2 * shear_modulus_gpa
    if denom_e != 0 and denom_nu != 0:
        youngs_modulus_gpa = 9 * bulk_modulus_gpa * shear_modulus_gpa / denom_e
        poissons_ratio = (3 * bulk_modulus_gpa - 2 * shear_modulus_gpa) / denom_nu
    else:
        youngs_modulus_gpa = None
        poissons_ratio = None

    residuals_sum = result["residuals_sum"]

    logger.info("=" * 50)
    logger.info("Elastic Properties (GPa)")
    logger.info("=" * 50)
    logger.info(f"Bulk modulus (VRH):  {bulk_modulus_gpa:.2f} GPa")
    logger.info(f"Shear modulus (VRH): {shear_modulus_gpa:.2f} GPa")
    logger.info(f"Young's modulus:     {youngs_modulus_gpa:.2f} GPa")
    if poissons_ratio is not None:
        logger.info(f"Poisson's ratio:     {poissons_ratio:.4f}")
    logger.info(f"Residuals sum:       {residuals_sum:.2e}")
    logger.info("=" * 50)

    # Print Voigt tensor
    logger.info("Elastic tensor C_ij (GPa):")
    for i in range(6):
        row_str = "  ".join(f"{voigt_tensor_gpa[i, j]:8.2f}" for j in range(6))
        logger.info(f"  [{row_str}]")

    # Create summary
    summary = {
        "elastic_tensor_GPa": voigt_tensor_gpa.tolist(),
        "bulk_modulus_vrh_GPa": bulk_modulus_gpa,
        "shear_modulus_vrh_GPa": shear_modulus_gpa,
        "youngs_modulus_GPa": youngs_modulus_gpa,
        "poissons_ratio": poissons_ratio,
        "residuals_sum": residuals_sum,
        "norm_strains": list(args.norm_strains),
        "shear_strains": list(args.shear_strains),
        "model_type": args.model_type,
        "model_name": wrapper.model_name,
        "output_dir": args.output_dir,
    }

    # Save results
    results_file = os.path.join(args.output_dir, "elasticity_results.json")
    with open(results_file, "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)

    logger.info(f"Results saved to {results_file}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate elastic tensor and mechanical properties with MLIPs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--structure", required=True, help="Path to structure file (CIF, POSCAR, etc.)")
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem", "matgl"],
                        help="MLIP type")
    parser.add_argument("--model_name", default=None, help="Specific model name (optional)")
    parser.add_argument("--norm_strains", nargs="+", type=float, default=[-0.01, -0.005, 0.005, 0.01],
                        help="Normal strain magnitudes")
    parser.add_argument("--shear_strains", nargs="+", type=float, default=[-0.06, -0.03, 0.03, 0.06],
                        help="Shear strain magnitudes")
    parser.add_argument("--fmax", type=float, default=0.1,
                        help="Force convergence tolerance (eV/Å)")
    parser.add_argument("--relax_structure", action="store_true", default=True,
                        help="Relax the structure before applying strains")
    parser.add_argument("--no_relax_structure", action="store_true", default=False,
                        help="Skip structure relaxation")
    parser.add_argument("--relax_deformed", action="store_true", default=False,
                        help="Relax atomic positions in deformed structures")
    parser.add_argument("--symmetry", action="store_true", default=False,
                        help="Use symmetry to reduce number of deformations")
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")

    args = parser.parse_args()

    if args.no_relax_structure:
        args.relax_structure = False

    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    atoms = read(args.structure)

    logger.info(f"Input structure: {args.structure}")
    logger.info(f"Formula: {atoms.get_chemical_formula()}")
    logger.info(f"Number of atoms: {len(atoms)}")

    run_elasticity(args, wrapper, atoms)
