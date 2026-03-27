"""
Tests for the ORCA singlepoint skill script.

Tests calculator setup and result handling for single-point calculations.
Mocks only the ORCA binary (not SCINE/ASE).

Run in: orca-agent environment
"""

import json
import os
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


@pytest.mark.orca
class TestSinglepointSetup:
    """Test single-point calculator configuration via orca_utils."""

    def _setup(self, monkeypatch, tmp_path):
        fake_bin = tmp_path / "orca"
        fake_bin.write_text("#!/bin/bash")
        fake_bin.chmod(0o755)
        monkeypatch.setenv("ORCA_BINARY_PATH", str(fake_bin))

        xyz_file = tmp_path / "water.xyz"
        xyz_file.write_text(
            "3\nwater\nO 0.0 0.0 0.117\nH 0.0 0.757 -0.469\nH 0.0 -0.757 -0.469\n"
        )
        return str(xyz_file)

    def test_energy_only_properties(self, skip_if_wrong_env, monkeypatch, tmp_path):
        import scine_utilities as su
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, atoms = setup_orca_calculator(structure_path=xyz)

        props = [su.Property.Energy]
        calc.set_required_properties(props)

        assert atoms.get_chemical_formula() == "H2O"
        assert len(atoms) == 3

    def test_all_properties_requested(self, skip_if_wrong_env, monkeypatch, tmp_path):
        import scine_utilities as su
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(structure_path=xyz)

        props = [su.Property.Energy, su.Property.Gradients, su.Property.Hessian]
        calc.set_required_properties(props)

    def test_hybrid_functional_with_dispersion(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz,
            functional="B3LYP",
            basis_set="def2-TZVP",
            dispersion="D3BJ",
        )

        assert calc.settings["method"] == "B3LYP-D3BJ"
        assert calc.settings["basis_set"] == "def2-TZVP"

    def test_solvated_calculation(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz,
            functional="PBE0",
            solvation="SMD",
            solvent="water",
        )

        assert calc.settings["solvation"] == "SMD"
        assert calc.settings["solvent"] == "water"

    def test_arbitrary_settings(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz,
            functional="PBE0",
            solvation="SMD",
            solvent="water",
            extra_calculator_settings={'max_scf_iterations': 200, 'solvent': 'ethanol', 'enforce_scf_criterion': True},
        )

        assert calc.settings["method"] == "PBE0"
        assert calc.settings["solvation"] == "SMD"
        assert calc.settings["solvent"] == "ethanol"
        assert calc.settings["max_scf_iterations"] == 200
        assert calc.settings["enforce_scf_criterion"] is True


@pytest.mark.orca
class TestSinglepointUnitConversions:
    """Test that energy/force unit conversions are correct."""

    def test_energy_conversion(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import HARTREE_TO_EV

        energy_hartree = -76.0
        energy_ev = energy_hartree * HARTREE_TO_EV
        assert energy_ev < 0
        assert energy_ev == pytest.approx(-76.0 * 27.211386245988, rel=1e-4)

    def test_force_conversion(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import HARTREE_TO_EV, BOHR_PER_ANGSTROM

        gradient_au = np.array([[0.01, -0.02, 0.005]])
        forces_ev_ang = -1.0 * gradient_au * HARTREE_TO_EV * BOHR_PER_ANGSTROM

        assert forces_ev_ang.shape == (1, 3)
        assert forces_ev_ang[0, 0] < 0  # Negative gradient -> positive force direction flipped

    def test_hessian_conversion(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import HARTREE_TO_EV, BOHR_PER_ANGSTROM

        hessian_au = np.eye(3) * 0.5
        hessian_ev_ang2 = hessian_au * HARTREE_TO_EV * BOHR_PER_ANGSTROM**2

        assert hessian_ev_ang2.shape == (3, 3)
        assert hessian_ev_ang2[0, 0] > 0
