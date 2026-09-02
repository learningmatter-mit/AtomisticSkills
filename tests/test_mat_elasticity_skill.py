"""Tests for the mat-elasticity skill's elastic post-processing and force thresholds.

The regression test at the bottom is the important one: it pins the bug that made
``--relax_deformed`` a silent no-op, so a revert cannot pass unnoticed.
"""

import importlib.util
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SKILL_SCRIPT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../.agents/skills/mat-elasticity/scripts/calculate_elasticity.py",
    )
)


def _load_skill_module():
    spec = importlib.util.spec_from_file_location("calculate_elasticity", SKILL_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


elasticity = _load_skill_module()


from pymatgen.core.elasticity import ComplianceTensor, ElasticTensor


def isotropic_voigt_stiffness(youngs: float, poisson: float) -> np.ndarray:
    """Voigt 6x6 stiffness of an isotropic solid with the given E and nu.

    An isotropic reference is what makes the directional machinery testable without
    golden numbers: every direction must give back exactly ``youngs``, and the
    anisotropy index must be exactly zero.
    """
    lam = youngs * poisson / ((1.0 + poisson) * (1.0 - 2.0 * poisson))
    mu = youngs / (2.0 * (1.0 + poisson))
    c = np.zeros((6, 6))
    c[:3, :3] = lam
    for i in range(3):
        c[i, i] = lam + 2.0 * mu
        c[i + 3, i + 3] = mu
    return c


# --------------------------------------------------------------------------------------
# Voigt -> full compliance expansion via pymatgen ComplianceTensor
# --------------------------------------------------------------------------------------


@pytest.mark.base
def test_shear_compliance_carries_the_quarter_factor():
    """S_1212 = S_66/4 and S_1122 = S_12, per the engineering-strain convention."""
    compliance = np.linalg.inv(isotropic_voigt_stiffness(100.0, 0.3))
    full = ComplianceTensor.from_voigt(compliance)

    assert full[0, 0, 1, 1] == pytest.approx(compliance[0, 1])  # normal-normal: 1
    assert full[1, 2, 1, 2] == pytest.approx(compliance[3, 3] / 4.0)  # shear-shear: 1/4
    assert full[0, 2, 0, 2] == pytest.approx(compliance[4, 4] / 4.0)
    assert full[0, 1, 0, 1] == pytest.approx(compliance[5, 5] / 4.0)


@pytest.mark.base
def test_full_compliance_has_the_expected_index_symmetries():
    compliance = np.linalg.inv(isotropic_voigt_stiffness(100.0, 0.3))
    full = ComplianceTensor.from_voigt(compliance)
    assert np.allclose(full, np.transpose(full, (1, 0, 2, 3)))  # i<->j
    assert np.allclose(full, np.transpose(full, (0, 1, 3, 2)))  # k<->l
    assert np.allclose(full, np.transpose(full, (2, 3, 0, 1)))  # pair exchange


# --------------------------------------------------------------------------------------
# Directional moduli. An isotropic solid is the analytic check with teeth: the axial
# moduli come out right even with a mis-expanded shear compliance, so only the
# off-axis directions catch that error.
# --------------------------------------------------------------------------------------


@pytest.mark.base
def test_isotropic_youngs_modulus_is_direction_independent():
    youngs = 137.0
    full = ComplianceTensor.from_voigt(
        np.linalg.inv(isotropic_voigt_stiffness(youngs, 0.27))
    )
    rng = np.random.default_rng(20260902)
    for direction in rng.normal(size=(40, 3)):
        assert elasticity.youngs_modulus_along(full, direction) == pytest.approx(
            youngs, rel=1e-9
        )


@pytest.mark.base
def test_isotropic_extrema_collapse_to_the_isotropic_modulus():
    youngs = 137.0
    full = ComplianceTensor.from_voigt(
        np.linalg.inv(isotropic_voigt_stiffness(youngs, 0.27))
    )
    extrema = elasticity.youngs_modulus_extrema(full)
    assert extrema["youngs_modulus_min_GPa"] == pytest.approx(youngs, rel=1e-6)
    assert extrema["youngs_modulus_max_GPa"] == pytest.approx(youngs, rel=1e-6)


@pytest.mark.base
def test_mis_expanded_shear_compliance_is_detectably_wrong():
    """Guard that the two tests above have teeth.

    Expanding with 1/2 on the shear-shear entries instead of 1/4 -- i.e. reusing the
    stiffness convention, which carries no factors -- leaves every *axial* modulus
    exactly right while breaking the off-axis ones. So a test suite that only checked
    [100]/[010]/[001] would not notice.
    """
    stiffness = isotropic_voigt_stiffness(137.0, 0.27)
    compliance = np.linalg.inv(stiffness)
    correct = ComplianceTensor.from_voigt(compliance)

    voigt_pairs = ((0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1))
    wrong = np.zeros((3, 3, 3, 3))
    for row, (i, j) in enumerate(voigt_pairs):
        for col, (k, m) in enumerate(voigt_pairs):
            factor = (1.0 if row >= 3 else 1.0) * (1.0 if col >= 3 else 1.0)
            for a, b in {(i, j), (j, i)}:
                for c, d in {(k, m), (m, k)}:
                    wrong[a, b, c, d] = compliance[row, col] * factor

    for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        assert elasticity.youngs_modulus_along(wrong, axis) == pytest.approx(
            elasticity.youngs_modulus_along(correct, axis), rel=1e-9
        )

    off_axis = (1.0, 1.0, 0.0)
    assert elasticity.youngs_modulus_along(wrong, off_axis) != pytest.approx(
        elasticity.youngs_modulus_along(correct, off_axis), rel=1e-3
    )


@pytest.mark.base
def test_extrema_find_an_off_axis_maximum():
    """A tensor whose stiffest direction is not a crystal axis must not be missed.

    Orthorhombic CaMgSi relaxed-ion tensor (MACE-OMAT-0-small): the stiffest direction
    lies ~40 degrees off a in the a-c plane, and is 13% stiffer than the stiffest axis.
    """
    stiffness = np.array(
        [
            [102.13, 24.33, 36.14, 0.0, 0.0, 0.0],
            [24.33, 100.72, 23.42, 0.0, 0.0, 0.0],
            [36.14, 23.42, 88.03, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 36.86, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 46.74, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 42.42],
        ]
    )
    compliance = np.linalg.inv(stiffness)
    full = ComplianceTensor.from_voigt(compliance)
    axial = [
        elasticity.youngs_modulus_along(full, ax)
        for ax in ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    ]
    extrema = elasticity.youngs_modulus_extrema(full)

    assert extrema["youngs_modulus_max_GPa"] > max(axial) * 1.05
    direction = np.abs(extrema["youngs_modulus_max_direction"])
    assert direction.max() < 0.95, "maximum should not sit on a crystal axis"
    # the softest direction of this particular tensor *is* [001]
    assert extrema["youngs_modulus_min_GPa"] == pytest.approx(min(axial), rel=1e-6)


# --------------------------------------------------------------------------------------
# Anisotropy index and derived properties
# --------------------------------------------------------------------------------------


@pytest.mark.base
def test_universal_anisotropy_index_vanishes_for_an_isotropic_solid():
    from ase.build import bulk

    atoms = bulk("Cu", "fcc", a=3.6)
    stiffness = isotropic_voigt_stiffness(100.0, 0.3)
    derived = elasticity.derived_elastic_properties(
        stiffness, atoms, 100.0 / (3 * 0.4), 100.0 / (2 * 1.3)
    )
    assert derived["universal_anisotropy_index"] == pytest.approx(0.0, abs=1e-10)
    assert derived["bulk_modulus_voigt_GPa"] == pytest.approx(
        derived["bulk_modulus_reuss_GPa"]
    )
    assert derived["shear_modulus_voigt_GPa"] == pytest.approx(
        derived["shear_modulus_reuss_GPa"]
    )


@pytest.mark.base
def test_universal_anisotropy_index_is_positive_for_an_anisotropic_solid():
    from ase.build import bulk

    atoms = bulk("Cu", "fcc", a=3.6)
    stiffness = isotropic_voigt_stiffness(100.0, 0.3)
    stiffness[3, 3] *= 2.0  # break cubic/isotropic shear degeneracy
    derived = elasticity.derived_elastic_properties(stiffness, atoms, 100.0, 40.0)
    assert derived["universal_anisotropy_index"] > 0


@pytest.mark.base
def test_derived_bounds_match_pymatgen_elastic_tensor():
    from ase.build import bulk

    atoms = bulk("Cu", "fcc", a=3.6)
    stiffness = np.array(
        [
            [102.13, 24.33, 36.14, 0.0, 0.0, 0.0],
            [24.33, 100.72, 23.42, 0.0, 0.0, 0.0],
            [36.14, 23.42, 88.03, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 36.86, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 46.74, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 42.42],
        ]
    )
    derived = elasticity.derived_elastic_properties(stiffness, atoms, 50.0, 35.0)
    et = ElasticTensor.from_voigt(stiffness)
    assert derived["bulk_modulus_voigt_GPa"] == pytest.approx(et.k_voigt)
    assert derived["bulk_modulus_reuss_GPa"] == pytest.approx(et.k_reuss)
    assert derived["shear_modulus_voigt_GPa"] == pytest.approx(et.g_voigt)
    assert derived["shear_modulus_reuss_GPa"] == pytest.approx(et.g_reuss)
    assert derived["universal_anisotropy_index"] == pytest.approx(
        et.universal_anisotropy
    )


# --------------------------------------------------------------------------------------
# Debye estimate
# --------------------------------------------------------------------------------------


@pytest.mark.base
def test_debye_temperature_matches_the_mass_density_form():
    """The two forms in the literature are algebraically identical; check ours is both.

    Theta_D = (hbar/k_B)(6 pi^2 N/V)^(1/3) v_m == (h/k_B)(3 N/4 pi V)^(1/3) v_m
    """
    from ase.build import bulk

    atoms = bulk("Cu", "fcc", a=3.6)
    result = elasticity.debye_properties(140.0, 48.0, atoms)

    volume_m3 = atoms.get_volume() * 1e-30
    number_density = len(atoms) / volume_m3
    planck = 2.0 * math.pi * elasticity.HBAR_SI
    alternative = (
        (planck / elasticity.KB_SI)
        * (3.0 * number_density / (4.0 * math.pi)) ** (1.0 / 3.0)
        * result["mean_velocity_m_s"]
    )
    assert result["debye_temperature_K"] == pytest.approx(alternative, rel=1e-12)


@pytest.mark.base
def test_debye_mean_velocity_is_the_harmonic_cube_mean():
    from ase.build import bulk

    atoms = bulk("Cu", "fcc", a=3.6)
    result = elasticity.debye_properties(140.0, 48.0, atoms)
    v_long = result["longitudinal_velocity_m_s"]
    v_trans = result["transverse_velocity_m_s"]

    expected = (((2.0 / v_trans**3) + (1.0 / v_long**3)) / 3.0) ** (-1.0 / 3.0)
    assert result["mean_velocity_m_s"] == pytest.approx(expected, rel=1e-12)
    # and it is emphatically not the arithmetic mean, which runs ~20% high
    assert result["mean_velocity_m_s"] < 0.9 * 0.5 * (v_long + v_trans)


@pytest.mark.base
def test_sound_velocities_follow_the_closed_forms():
    from ase.build import bulk

    atoms = bulk("Cu", "fcc", a=3.6)
    bulk_gpa, shear_gpa = 140.0, 48.0
    result = elasticity.debye_properties(bulk_gpa, shear_gpa, atoms)
    density = result["density_g_cm3"] * 1000.0

    assert result["longitudinal_velocity_m_s"] == pytest.approx(
        math.sqrt((bulk_gpa + 4.0 * shear_gpa / 3.0) * 1e9 / density), rel=1e-12
    )
    assert result["transverse_velocity_m_s"] == pytest.approx(
        math.sqrt(shear_gpa * 1e9 / density), rel=1e-12
    )


# --------------------------------------------------------------------------------------
# Force-threshold resolution, and the bug it exists to fix
# --------------------------------------------------------------------------------------


@pytest.mark.base
def test_relaxed_ion_path_takes_the_tighter_threshold():
    assert elasticity.resolve_force_threshold(0.1, 1e-4, True) == 1e-4
    assert elasticity.resolve_force_threshold(1e-5, 1e-4, True) == 1e-5


@pytest.mark.base
def test_clamped_ion_path_leaves_the_pre_relaxation_threshold_alone():
    """With no per-deformation relaxation, --deformed_fmax is irrelevant."""
    assert elasticity.resolve_force_threshold(0.03, 1e-4, False) == 0.03


@pytest.mark.mace
def test_loose_threshold_makes_relax_deformed_a_silent_no_op():
    """Regression test for the bug this skill's --deformed_fmax exists to fix.

    ``ElasticityCalc`` applies one ``fmax`` to both the pre-relaxation and the
    per-deformation ion relaxation. Before the fix the skill handed it ``--fmax``,
    whose default was 0.1 eV/A -- far too loose to converge the ions inside a deformed
    cell. The consequence was not a small bias: the relaxed-ion result came back
    *identical* to the clamped-ion one, so ``--relax_deformed`` appeared to do nothing.

    EMT on a Cu3Au cell with atoms on general positions reproduces this with no model
    weights: there is a real 16% non-affine softening to find, the loose threshold
    finds none of it, and the shipped default finds it.
    """
    from ase import Atoms
    from ase.calculators.emt import EMT
    from ase.filters import FrechetCellFilter
    from ase.optimize import BFGS
    from matcalc import ElasticityCalc

    atoms = Atoms(
        "Cu3Au",
        scaled_positions=[
            [0.01, 0.02, 0.00],
            [0.50, 0.48, 0.02],
            [0.26, 0.75, 0.50],
            [0.74, 0.25, 0.52],
        ],
        cell=[3.9, 4.1, 4.6],
        pbc=True,
    )
    # Pre-relax once, here, so that the fmax handed to ElasticityCalc below governs
    # only the per-deformation ion relaxation -- the single variable under test.
    atoms.calc = EMT()
    BFGS(FrechetCellFilter(atoms), logfile=None).run(fmax=0.005, steps=600)

    def shear_modulus(relax_deformed: bool, fmax: float) -> float:
        calc = ElasticityCalc(
            calculator=EMT(),
            norm_strains=[-0.01, -0.005, 0.005, 0.01],
            shear_strains=[-0.01, -0.005, 0.005, 0.01],
            fmax=fmax,
            relax_structure=False,
            relax_deformed_structures=relax_deformed,
            use_equilibrium=True,
        )
        return float(
            calc.calc(atoms)["shear_modulus_vrh"] * elasticity.EV_PER_A3_TO_GPA
        )

    clamped = shear_modulus(False, 0.1)
    loose = shear_modulus(True, 0.1)  # what the pre-fix code passed through
    tight = shear_modulus(True, 1e-4)  # what --deformed_fmax now delivers

    # There is a real non-affine softening in this structure to be found.
    assert (
        clamped > tight * 1.05
    ), f"expected >5% non-affine softening, got clamped={clamped:.3f} tight={tight:.3f}"

    # The bug: at the old default threshold the relaxed-ion path recovers none of it.
    assert loose == pytest.approx(clamped, rel=1e-3), (
        "expected the loose threshold to reproduce the clamped-ion answer "
        f"(clamped={clamped:.3f}, loose={loose:.3f})"
    )

    # The fix: the shipped default resolves to a threshold that actually works.
    resolved = elasticity.resolve_force_threshold(0.1, 1e-4, True)
    recovered = shear_modulus(True, resolved)
    assert recovered == pytest.approx(tight, rel=1e-3)
    assert abs(recovered - clamped) > 0.05 * clamped, (
        "resolve_force_threshold must not hand back a threshold that degenerates "
        "to the clamped-ion answer"
    )
