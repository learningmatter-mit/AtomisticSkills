"""
Tests for the ORCA optimization skill script.

Tests calculator setup and position conversion for optimization workflows.
Mocks only the ORCA binary (not SCINE/ASE).

Run in: orca-agent environment
"""

import pytest
import numpy as np


@pytest.mark.orca
class TestOptimizationCalculatorSetup:
    """Test that the optimization correctly sets up the calculator."""

    def _setup(self, monkeypatch, tmp_path):
        fake_bin = tmp_path / "orca"
        fake_bin.write_text("#!/bin/bash")
        fake_bin.chmod(0o755)
        monkeypatch.setenv("ORCA_BINARY_PATH", str(fake_bin))

        xyz_file = tmp_path / "mol.xyz"
        xyz_file.write_text(
            "3\nwater\nO 0.0 0.0 0.117\nH 0.0 0.757 -0.469\nH 0.0 -0.757 -0.469\n"
        )
        return str(xyz_file)

    def test_minimization_settings(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, atoms = setup_orca_calculator(
            structure_path=xyz,
            functional="PBE",
            basis_set="def2-SVP",
        )

        assert calc.settings["method"] == "PBE"
        assert calc.settings["basis_set"] == "def2-SVP"
        assert len(atoms) == 3

    def test_ts_settings_with_dispersion(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz,
            charge=1,
            spin_multiplicity=3,
            functional="B3LYP",
            basis_set="def2-TZVP",
            dispersion="D3BJ",
            nprocs=8,
        )

        assert calc.settings["molecular_charge"] == 1
        assert calc.settings["spin_multiplicity"] == 3
        assert calc.settings["method"] == "B3LYP-D3BJ"
        assert calc.settings["external_program_nprocs"] == 8

    def test_solvated_optimization(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz,
            solvation="CPCM",
            solvent="ethanol",
        )

        assert calc.settings["solvation"] == "CPCM"
        assert calc.settings["solvent"] == "ethanol"


@pytest.mark.orca
class TestPositionConversion:
    """Test SCINE position conversion back to ASE coordinates."""

    def test_scine_to_ase_roundtrip(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import BOHR_PER_ANGSTROM, scine_positions_to_ase

        positions_ang = np.array([[0.0, 0.0, 0.117], [0.0, 0.757, -0.469]])
        positions_bohr = positions_ang * BOHR_PER_ANGSTROM
        recovered = np.array(scine_positions_to_ase(positions_bohr))

        np.testing.assert_allclose(recovered, positions_ang, atol=1e-10)

    def test_load_and_convert_structure(self, skip_if_wrong_env, tmp_path, monkeypatch):
        """Test that loading a structure and converting back gives original positions."""
        from src.utils.dft.orca_utils import load_structure, scine_positions_to_ase

        fake_bin = tmp_path / "orca"
        fake_bin.write_text("#!/bin/bash")
        fake_bin.chmod(0o755)
        monkeypatch.setenv("ORCA_BINARY_PATH", str(fake_bin))

        xyz_file = tmp_path / "mol.xyz"
        xyz_file.write_text(
            "2\nH2\nH  0.0  0.0  0.0\nH  0.0  0.0  0.74\n"
        )

        atom_collection, atoms = load_structure(str(xyz_file))

        recovered = np.array(scine_positions_to_ase(atom_collection.positions))
        np.testing.assert_allclose(recovered, atoms.get_positions(), atol=1e-8)
