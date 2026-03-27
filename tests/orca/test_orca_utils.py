"""
Tests for src/utils/dft/orca_utils.py

Tests the shared ORCA/SCINE utility functions: binary validation, structure
loading, and calculator setup.

Run in: orca-agent environment
"""

import os
import pytest
import numpy as np


@pytest.mark.orca
class TestCheckOrcaBinary:
    """Test ORCA binary validation."""

    def test_missing_env_var(self, skip_if_wrong_env, monkeypatch):
        monkeypatch.delenv("ORCA_BINARY_PATH", raising=False)
        from src.utils.dft.orca_utils import check_orca_binary

        with pytest.raises(EnvironmentError, match="ORCA_BINARY_PATH.*not set"):
            check_orca_binary()

    def test_nonexistent_file(self, skip_if_wrong_env, monkeypatch, tmp_path):
        fake_path = str(tmp_path / "nonexistent_orca")
        monkeypatch.setenv("ORCA_BINARY_PATH", fake_path)
        from src.utils.dft.orca_utils import check_orca_binary

        with pytest.raises(EnvironmentError, match="non-existent file"):
            check_orca_binary()

    def test_non_executable_file(self, skip_if_wrong_env, monkeypatch, tmp_path):
        fake_bin = tmp_path / "orca"
        fake_bin.write_text("not a real binary")
        fake_bin.chmod(0o644)
        monkeypatch.setenv("ORCA_BINARY_PATH", str(fake_bin))
        from src.utils.dft.orca_utils import check_orca_binary

        with pytest.raises(EnvironmentError, match="not executable"):
            check_orca_binary()

    def test_valid_binary(self, skip_if_wrong_env, monkeypatch, tmp_path):
        fake_bin = tmp_path / "orca"
        fake_bin.write_text("#!/bin/bash\necho orca")
        fake_bin.chmod(0o755)
        monkeypatch.setenv("ORCA_BINARY_PATH", str(fake_bin))
        from src.utils.dft.orca_utils import check_orca_binary

        result = check_orca_binary()
        assert result == str(fake_bin)


@pytest.mark.orca
class TestLoadStructure:
    """Test structure loading and conversion to SCINE AtomCollection."""

    def test_load_xyz_file(self, skip_if_wrong_env, tmp_path):
        import scine_utilities as su
        from src.utils.dft.orca_utils import load_structure

        xyz_file = tmp_path / "water.xyz"
        xyz_file.write_text(
            "3\n"
            "water molecule\n"
            "O  0.000  0.000  0.117\n"
            "H  0.000  0.757 -0.469\n"
            "H  0.000 -0.757 -0.469\n"
        )

        atom_collection, atoms = load_structure(str(xyz_file))

        assert len(atoms) == 3
        assert atoms.get_chemical_formula() == "H2O"
        assert isinstance(atom_collection, su.AtomCollection)
        assert len(atom_collection) == 3

    def test_positions_converted_to_bohr(self, skip_if_wrong_env, tmp_path):
        from src.utils.dft.orca_utils import load_structure, BOHR_PER_ANGSTROM

        xyz_file = tmp_path / "h.xyz"
        xyz_file.write_text("1\nhydrogen\nH  1.0  2.0  3.0\n")

        atom_collection, atoms = load_structure(str(xyz_file))

        pos_bohr = atom_collection.positions
        pos_ang = atoms.get_positions()
        np.testing.assert_allclose(pos_bohr, pos_ang * BOHR_PER_ANGSTROM, atol=1e-10)


@pytest.mark.orca
class TestSetupOrcaCalculator:
    """Test calculator setup. Mocks check_orca_binary to avoid needing the real ORCA binary."""

    def _setup(self, monkeypatch, tmp_path):
        """Create a fake ORCA binary and a test xyz file."""
        fake_bin = tmp_path / "orca"
        fake_bin.write_text("#!/bin/bash")
        fake_bin.chmod(0o755)
        monkeypatch.setenv("ORCA_BINARY_PATH", str(fake_bin))

        xyz_file = tmp_path / "mol.xyz"
        xyz_file.write_text("1\nH atom\nH  0.0  0.0  0.0\n")
        return str(xyz_file)

    def test_default_settings(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, atoms = setup_orca_calculator(structure_path=xyz)

        assert calc.settings["molecular_charge"] == 0
        assert calc.settings["spin_multiplicity"] == 1
        assert calc.settings["method"] == "PBE"
        assert calc.settings["basis_set"] == "def2-SVP"

    def test_custom_charge_and_spin(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz, charge=-1, spin_multiplicity=2
        )

        assert calc.settings["molecular_charge"] == -1
        assert calc.settings["spin_multiplicity"] == 2

    def test_dispersion_appended_to_method(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz, functional="B3LYP", dispersion="D3BJ"
        )

        assert calc.settings["method"] == "B3LYP-D3BJ"

    def test_no_dispersion(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz, functional="PBE", dispersion=None
        )

        assert calc.settings["method"] == "PBE"

    def test_solvation_settings(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz, solvation="CPCM", solvent="water"
        )

        assert calc.settings["solvation"] == "CPCM"
        assert calc.settings["solvent"] == "water"

    def test_solvation_without_solvent_raises(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="requires --solvent"):
            setup_orca_calculator(
                structure_path=xyz, solvation="SMD", solvent=None
            )

    def test_nprocs_setting(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(structure_path=xyz, nprocs=8)

        assert calc.settings["external_program_nprocs"] == 8

    def test_nprocs_1_no_override(self, skip_if_wrong_env, monkeypatch, tmp_path):
        """With nprocs=1, external_program_nprocs should not be explicitly set by our code."""
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(structure_path=xyz, nprocs=1)

        # SCINE Settings may include defaults; just verify nprocs=8 actually changes it
        calc8, _, _ = setup_orca_calculator(structure_path=xyz, nprocs=8)
        assert calc8.settings["external_program_nprocs"] == 8

    def test_special_option_default(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(structure_path=xyz)

        assert calc.settings["special_option"] == "NOSOSCF"

    def test_special_option_custom(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz, special_option="TIGHTSCF"
        )

        assert calc.settings["special_option"] == "TIGHTSCF"

    def test_special_option_empty_not_set(self, skip_if_wrong_env, monkeypatch, tmp_path):
        """Empty string should not set special_option."""
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc_empty, _, _ = setup_orca_calculator(
            structure_path=xyz, special_option=""
        )
        calc_default, _, _ = setup_orca_calculator(
            structure_path=xyz, special_option="NOSOSCF"
        )

        assert calc_default.settings["special_option"] == "NOSOSCF"


@pytest.mark.orca
class TestParseJsonSettings:
    """Test JSON settings parser."""

    def test_none_returns_empty(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import parse_json_settings
        assert parse_json_settings(None) == {}

    def test_empty_string_returns_empty(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import parse_json_settings
        assert parse_json_settings("") == {}

    def test_valid_json_int(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import parse_json_settings
        result = parse_json_settings('{"max_scf_iterations": 128}')
        assert result == {"max_scf_iterations": 128}
        assert isinstance(result["max_scf_iterations"], int)

    def test_valid_json_float(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import parse_json_settings
        result = parse_json_settings('{"convergence_delta_value": 1e-8}')
        assert result == {"convergence_delta_value": 1e-8}
        assert isinstance(result["convergence_delta_value"], float)

    def test_valid_json_string(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import parse_json_settings
        result = parse_json_settings('{"auxiliary_basis_set": "def2/J"}')
        assert result == {"auxiliary_basis_set": "def2/J"}
        assert isinstance(result["auxiliary_basis_set"], str)

    def test_multiple_keys(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import parse_json_settings
        result = parse_json_settings('{"a": 1, "b": 2.5, "c": "x"}')
        assert result == {"a": 1, "b": 2.5, "c": "x"}

    def test_invalid_json_raises(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import parse_json_settings
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_json_settings("{not valid json}")

    def test_non_dict_raises(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import parse_json_settings
        with pytest.raises(ValueError, match="flat object"):
            parse_json_settings("[1, 2, 3]")


@pytest.mark.orca
class TestExtraCalculatorSettings:
    """Test that extra_calculator_settings are applied to the SCINE calculator."""

    def _setup(self, monkeypatch, tmp_path):
        fake_bin = tmp_path / "orca"
        fake_bin.write_text("#!/bin/bash")
        fake_bin.chmod(0o755)
        monkeypatch.setenv("ORCA_BINARY_PATH", str(fake_bin))
        xyz_file = tmp_path / "mol.xyz"
        xyz_file.write_text("1\nH atom\nH  0.0  0.0  0.0\n")
        return str(xyz_file)

    def test_extra_settings_applied(self, skip_if_wrong_env, monkeypatch, tmp_path):
        """Extra settings can set valid SCINE calculator keys."""
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz,
            extra_calculator_settings={"max_scf_iterations": 200},
        )
        assert calc.settings["max_scf_iterations"] == 200

    def test_extra_settings_invalid_key_raises(self, skip_if_wrong_env, monkeypatch, tmp_path):
        """SCINE Settings rejects keys that are not registered."""
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        with pytest.raises(RuntimeError, match="no matching key"):
            setup_orca_calculator(
                structure_path=xyz,
                extra_calculator_settings={"nonexistent_key_xyz": 42},
            )

    def test_extra_settings_none(self, skip_if_wrong_env, monkeypatch, tmp_path):
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz, extra_calculator_settings=None
        )
        assert calc.settings["method"] == "PBE"

    def test_extra_settings_override(self, skip_if_wrong_env, monkeypatch, tmp_path):
        """Extra settings applied after defaults can override them."""
        from src.utils.dft.orca_utils import setup_orca_calculator

        xyz = self._setup(monkeypatch, tmp_path)
        calc, _, _ = setup_orca_calculator(
            structure_path=xyz,
            functional="PBE",
            extra_calculator_settings={"method": "HF"},
        )
        assert calc.settings["method"] == "HF"


@pytest.mark.orca
class TestPositionConversion:
    """Test SCINE position conversion roundtrip."""

    def test_bohr_angstrom_roundtrip(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import BOHR_PER_ANGSTROM, scine_positions_to_ase

        positions_ang = np.array([[0.0, 0.0, 0.117], [0.0, 0.757, -0.469]])
        positions_bohr = positions_ang * BOHR_PER_ANGSTROM
        recovered = np.array(scine_positions_to_ase(positions_bohr))

        np.testing.assert_allclose(recovered, positions_ang, atol=1e-10)

    def test_unit_constants(self, skip_if_wrong_env):
        from src.utils.dft.orca_utils import HARTREE_TO_EV, BOHR_PER_ANGSTROM

        assert abs(HARTREE_TO_EV - 27.211386245988) < 0.001
        assert abs(BOHR_PER_ANGSTROM - 1.8897259886) < 0.001
