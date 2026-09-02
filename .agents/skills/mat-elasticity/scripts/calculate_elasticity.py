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
from typing import Any

import numpy as np

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
from ase.io import read

# Conversion factors
EV_PER_A3_TO_GPA = 160.2176634  # 1 eV/ų = 160.2176634 GPa

# Voigt index pairs, and constants for the Debye estimate.
VOIGT_PAIRS = ((0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1))
HBAR_SI = 1.054571817e-34
KB_SI = 1.380649e-23
AMU_SI = 1.66053906660e-27

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("Elasticity-Skill")


from src.utils.mlips.loader import load_wrapper
from pymatgen.core.elasticity import ComplianceTensor, ElasticTensor


def full_compliance_tensor(voigt_compliance: np.ndarray) -> ComplianceTensor:
    """Expand a 6x6 Voigt compliance matrix into the full S_ijkl using pymatgen's ComplianceTensor.

    The engineering-strain Voigt convention folds a factor of 2 into each shear index
    pair of the compliance, so a shear-shear entry carries 1/4 and a normal-shear
    entry 1/2: S_1122 = S_12, but S_1212 = S_66 / 4. pymatgen's ComplianceTensor.from_voigt
    implements this standard conversion directly.
    """
    return ComplianceTensor.from_voigt(voigt_compliance)


def _sphere_directions(phi: np.ndarray, theta: np.ndarray) -> np.ndarray:
    grid_phi, grid_theta = np.meshgrid(phi, theta, indexing="ij")
    return np.stack(
        [
            np.sin(grid_theta) * np.cos(grid_phi),
            np.sin(grid_theta) * np.sin(grid_phi),
            np.cos(grid_theta),
        ],
        axis=-1,
    ).reshape(-1, 3)


def youngs_modulus_along(full_compliance: np.ndarray, direction) -> float:
    """E(n) = 1 / (S_ijkl n_i n_j n_k n_l) for a unit direction n."""
    n = np.asarray(direction, dtype=float)
    n = n / np.linalg.norm(n)
    if hasattr(full_compliance, "einsum_sequence"):
        return float(1.0 / full_compliance.einsum_sequence([n] * 4))
    return float(1.0 / np.einsum("ijkl,i,j,k,l->", full_compliance, n, n, n, n))


def youngs_modulus_extrema(full_compliance: np.ndarray, n_coarse: int = 721) -> dict:
    """Global extrema of Young's modulus over all directions.

    The extremes of an anisotropic crystal need not lie on a crystal axis, so scanning
    only [100]/[010]/[001] is not enough -- for an orthorhombic intermetallic the
    stiffest direction can sit well off-axis and be over 10% stiffer than the stiffest
    axis. Coarse scan over the sphere followed by a shrinking local grid; deterministic
    and numpy-only, so it needs no optimiser dependency.
    """
    phi = np.linspace(0.0, 2.0 * np.pi, n_coarse)
    theta = np.linspace(0.0, np.pi, n_coarse // 2 + 1)
    nodes = _sphere_directions(phi, theta)
    inverse = np.einsum(
        "ijkl,ni,nj,nk,nl->n", full_compliance, nodes, nodes, nodes, nodes
    )

    result = {}
    # Largest inverse is the softest direction; smallest inverse the stiffest.
    for tag, seed_index, take_max in (
        ("min", int(inverse.argmax()), True),
        ("max", int(inverse.argmin()), False),
    ):
        seed = nodes[seed_index]
        angle_phi = np.arctan2(seed[1], seed[0])
        angle_theta = np.arccos(np.clip(seed[2], -1.0, 1.0))
        span = 4.0 * 2.0 * np.pi / n_coarse
        for _ in range(28):
            local = _sphere_directions(
                np.linspace(angle_phi - span, angle_phi + span, 41),
                np.linspace(angle_theta - span, angle_theta + span, 41),
            )
            values = np.einsum(
                "ijkl,ni,nj,nk,nl->n", full_compliance, local, local, local, local
            )
            best = local[int(values.argmax() if take_max else values.argmin())]
            angle_phi = np.arctan2(best[1], best[0])
            angle_theta = np.arccos(np.clip(best[2], -1.0, 1.0))
            span *= 0.55
        direction = best / np.linalg.norm(best)
        result[f"youngs_modulus_{tag}_GPa"] = youngs_modulus_along(
            full_compliance, direction
        )
        result[f"youngs_modulus_{tag}_direction"] = [
            float(x) for x in direction.round(6)
        ]
    return result


def anisotropy_and_bounds(voigt_stiffness: np.ndarray) -> dict:
    """Voigt and Reuss bounds, the VRH averages and the universal anisotropy index via pymatgen.

    A^U = 5 G_V/G_R + B_V/B_R - 6 (Ranganathan & Ostoja-Starzewski, PRL 101, 055504
    (2008)); zero only for an elastically isotropic crystal. It needs the Voigt and
    Reuss bounds kept separate, so it cannot be recovered from the VRH averages alone.
    """
    et = ElasticTensor.from_voigt(voigt_stiffness)
    return {
        "bulk_modulus_voigt_GPa": float(et.k_voigt),
        "bulk_modulus_reuss_GPa": float(et.k_reuss),
        "shear_modulus_voigt_GPa": float(et.g_voigt),
        "shear_modulus_reuss_GPa": float(et.g_reuss),
        "universal_anisotropy_index": float(et.universal_anisotropy),
    }


def debye_properties(bulk_gpa: float, shear_gpa: float, atoms) -> dict:
    """Anderson estimate: isotropic sound velocities, then the Debye temperature.

    Theta_D = (hbar / k_B) (6 pi^2 N/V)^(1/3) v_m, algebraically identical to the
    (h/k_B)(3n/4pi)^(1/3) form usually written with the mass density. The mean velocity
    is the Debye harmonic-cube mean over one longitudinal and two transverse branches,
    NOT the arithmetic mean of the two -- the arithmetic mean runs ~20% high.
    """
    volume_m3 = float(atoms.get_volume()) * 1e-30
    density = float(atoms.get_masses().sum()) * AMU_SI / volume_m3
    v_long = float(np.sqrt((bulk_gpa + 4.0 * shear_gpa / 3.0) * 1e9 / density))
    v_trans = float(np.sqrt(shear_gpa * 1e9 / density))
    v_mean = float((((2.0 / v_trans**3) + (1.0 / v_long**3)) / 3.0) ** (-1.0 / 3.0))
    number_density = len(atoms) / volume_m3
    theta = float(
        (HBAR_SI / KB_SI) * (6.0 * np.pi**2 * number_density) ** (1.0 / 3.0) * v_mean
    )
    return {
        "density_g_cm3": density / 1000.0,
        "longitudinal_velocity_m_s": v_long,
        "transverse_velocity_m_s": v_trans,
        "mean_velocity_m_s": v_mean,
        "debye_temperature_K": theta,
    }


def derived_elastic_properties(
    voigt_stiffness_gpa: np.ndarray, atoms, bulk_gpa: float, shear_gpa: float
) -> dict:
    """Standard post-processing of an elastic tensor: bounds, anisotropy, directional
    moduli and the acoustic/Debye estimates."""
    et = ElasticTensor.from_voigt(voigt_stiffness_gpa)
    full = et.compliance_tensor
    out = dict(anisotropy_and_bounds(voigt_stiffness_gpa))
    out.update(
        {
            "youngs_modulus_100_GPa": youngs_modulus_along(full, (1.0, 0.0, 0.0)),
            "youngs_modulus_010_GPa": youngs_modulus_along(full, (0.0, 1.0, 0.0)),
            "youngs_modulus_001_GPa": youngs_modulus_along(full, (0.0, 0.0, 1.0)),
        }
    )
    out.update(youngs_modulus_extrema(full))
    out.update(debye_properties(bulk_gpa, shear_gpa, atoms))
    eigenvalues = np.linalg.eigvalsh(np.asarray(voigt_stiffness_gpa, dtype=float))
    out["elastic_eigenvalues_GPa"] = [float(x) for x in eigenvalues]
    out["born_stable"] = bool(np.all(eigenvalues > 0.0))
    out["pugh_ratio_G_over_B"] = float(shear_gpa / bulk_gpa)
    return out


def resolve_force_threshold(
    fmax: float, deformed_fmax: float, relax_deformed: bool
) -> float:
    """Pick the force threshold to hand matcalc, which accepts only one.

    ``ElasticityCalc`` applies a single ``fmax`` to both the pre-relaxation and the
    per-deformation ion relaxation -- it builds the latter as
    ``RelaxCalc(calculator, fmax=self.fmax, ...)``, and ``relax_calc_kwargs`` cannot
    override it because that would be a duplicate keyword. The two stages want very
    different thresholds: a cell pre-relaxation is fine at 0.01-0.03 eV/A, but residual
    forces in a *deformed* cell contaminate the very stress the elastic tensor is
    fitted from.

    Left at a loose threshold, the relaxed-ion path silently degenerates to the
    clamped-ion answer it was supposed to replace: on an EMT Cu3Au cell with atoms on
    general positions, relaxing the deformed structures at fmax=0.1 reproduces the
    clamped-ion shear modulus exactly (54.42 GPa), against 46.64 GPa converged -- so
    the flag appeared to do nothing at all. Hence the tighter of the two whenever the
    relaxed-ion path is active.
    """
    return min(fmax, deformed_fmax) if relax_deformed else fmax


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

    effective_fmax = resolve_force_threshold(
        args.fmax, args.deformed_fmax, args.relax_deformed
    )

    logger.info(f"Normal strains: {args.norm_strains}")
    logger.info(f"Shear strains: {args.shear_strains}")
    logger.info(f"Relax structure: {args.relax_structure}")
    logger.info(f"Relax deformed structures: {args.relax_deformed}")
    logger.info(
        f"Force threshold: {effective_fmax} eV/A"
        + (
            f" (tightened from --fmax {args.fmax} for the relaxed-ion path)"
            if effective_fmax < args.fmax
            else ""
        )
    )

    elast_calc = ElasticityCalc(
        calculator=calc,
        norm_strains=args.norm_strains,
        shear_strains=args.shear_strains,
        fmax=effective_fmax,
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

    derived = derived_elastic_properties(
        voigt_tensor_gpa, atoms, bulk_modulus_gpa, shear_modulus_gpa
    )

    logger.info(
        "Universal anisotropy index A^U: %.4f", derived["universal_anisotropy_index"]
    )
    logger.info(
        "Young's modulus [100]/[010]/[001]: %.2f / %.2f / %.2f GPa",
        derived["youngs_modulus_100_GPa"],
        derived["youngs_modulus_010_GPa"],
        derived["youngs_modulus_001_GPa"],
    )
    logger.info(
        "Young's modulus over all directions: min %.2f GPa along %s, max %.2f GPa along %s",
        derived["youngs_modulus_min_GPa"],
        derived["youngs_modulus_min_direction"],
        derived["youngs_modulus_max_GPa"],
        derived["youngs_modulus_max_direction"],
    )
    logger.info(
        "Sound velocities vl/vt/vm: %.0f / %.0f / %.0f m/s; Debye temperature %.1f K",
        derived["longitudinal_velocity_m_s"],
        derived["transverse_velocity_m_s"],
        derived["mean_velocity_m_s"],
        derived["debye_temperature_K"],
    )
    logger.info("Born stable: %s", derived["born_stable"])
    logger.info("=" * 50)

    # Create summary
    summary = {
        "elastic_tensor_GPa": voigt_tensor_gpa.tolist(),
        "bulk_modulus_vrh_GPa": bulk_modulus_gpa,
        "shear_modulus_vrh_GPa": shear_modulus_gpa,
        "youngs_modulus_GPa": youngs_modulus_gpa,
        "poissons_ratio": poissons_ratio,
        **derived,
        "ion_relaxation": "relaxed-ion" if args.relax_deformed else "clamped-ion",
        "residuals_sum": residuals_sum,
        "norm_strains": list(args.norm_strains),
        "shear_strains": list(args.shear_strains),
        "fmax_eV_per_A": effective_fmax,
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
        "--norm_strains",
        nargs="+",
        type=float,
        default=[-0.01, -0.005, 0.005, 0.01],
        help="Normal strain magnitudes",
    )
    parser.add_argument(
        "--shear_strains",
        nargs="+",
        type=float,
        default=[-0.06, -0.03, 0.03, 0.06],
        help="Shear strain magnitudes",
    )
    parser.add_argument(
        "--fmax", type=float, default=0.1, help="Force convergence tolerance (eV/Å)"
    )
    parser.add_argument(
        "--relax_structure",
        action="store_true",
        default=True,
        help="Relax the structure before applying strains",
    )
    parser.add_argument(
        "--no_relax_structure",
        action="store_true",
        default=False,
        help="Skip structure relaxation",
    )
    parser.add_argument(
        "--relax_deformed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Re-minimise the ions inside each deformed cell, at fixed cell, giving "
        "the RELAXED-ION (equilibrium) elastic constants -- the second derivative of "
        "the energy minimised over the internal degrees of freedom the strain does not "
        "fix. This is what a real crystal exhibits and what the Materials Project and "
        "atomate2 elastic workflows compute. Use --no-relax_deformed for the "
        "CLAMPED-ION (frozen-ion) response, in which every atom is carried rigidly by "
        "the affine strain: cheaper, and matcalc's own default, but systematically "
        "stiffer whenever the structure has internal degrees of freedom. The gap is "
        "the non-affine softening and is not small -- for Pnma CaMgSi it reaches 7.5% "
        "on the shear modulus. Defaults to the physical answer rather than inheriting "
        "matcalc's screening default.",
    )
    parser.add_argument(
        "--deformed_fmax",
        type=float,
        default=1.0e-4,
        help="Force threshold (eV/A) for the per-deformation ion relaxation of the "
        "relaxed-ion path. Residual forces in a deformed cell contaminate the stress "
        "the elastic tensor is fitted from, so this has to be far tighter than a cell "
        "pre-relaxation needs; a loose value silently returns something close to the "
        "clamped-ion answer. Ignored with --no-relax_deformed. matcalc accepts only "
        "one threshold for both stages, so the effective value is min(--fmax, "
        "--deformed_fmax) whenever the relaxed-ion path is active.",
    )
    parser.add_argument(
        "--symmetry",
        action="store_true",
        default=False,
        help="Use symmetry to reduce number of deformations",
    )
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

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs

    save_skill_inputs(args, args.output_dir)
