"""
Tests for the advanced ORCA calculation skill scripts.

Tests input validation and ORCA output parsing. These functions are pure
Python (regex-based) and don't require SCINE, but are marked orca for
consistency with the skill's environment.

Run in: orca-agent environment
"""

import json
import os
import pytest
from importlib import util as importlib_util


SAMPLE_ORCA_OUTPUT = """\
                         --------------------------
                         ORCA - An Ab Initio, DFT and Semiempirical electronic structure package
                         --------------------------

SCF CONVERGED AFTER   12 CYCLES
  Total Energy       :         -76.34297815 Eh
  Nuclear Repulsion  :           9.08734440 Eh

ORBITAL ENERGIES
------------------
  NO   OCC          E(Eh)            E(eV)
   0   2.0000     -18.8340        -512.5607
   1   2.0000      -0.9223         -25.0972
   2   2.0000      -0.4784         -13.0182
   3   2.0000      -0.3413          -9.2873
   4   2.0000      -0.2621          -7.1322
   5   0.0000       0.0437           1.1890
   6   0.0000       0.1196           3.2544

FINAL SINGLE POINT ENERGY       -76.342978150000

Dispersion correction           -0.003412000000

TOTAL RUN TIME: 0 days 0 hours 2 min 34 sec
"""

SAMPLE_FREQ_OUTPUT = """\
VIBRATIONAL FREQUENCIES
-----------------------

Scaling factor for frequencies =  1.000000

   0:         0.00 cm**-1
   1:         0.00 cm**-1
   2:         0.00 cm**-1
   3:         0.00 cm**-1
   4:         0.00 cm**-1
   5:         0.00 cm**-1
   6:      1623.45 cm**-1
   7:      3701.12 cm**-1
   8:      3803.89 cm**-1
"""

SAMPLE_THERMO_OUTPUT = """\
Zero point energy                ...      0.02120832 Eh
Total enthalpy                   ...     -76.31940283 Eh
Final Gibbs free energy          ...     -76.34127815 Eh
Total entropy correction         ...     -0.02187532 Eh
Temperature                      ...    298.15 K
"""

SAMPLE_BAD_SCF = """\
SCF NOT CONVERGED
FINAL SINGLE POINT ENERGY        0.000000000000
"""


def _load_module(script_name):
    """Load a skill script as a module by file path."""
    script_path = os.path.join(
        os.path.dirname(__file__),
        f"../../.agent/skills/chem-dft-orca-advanced-calculation/scripts/{script_name}",
    )
    script_path = os.path.abspath(script_path)
    spec = importlib_util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    mod = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.orca
class TestInputValidation:
    """Test ORCA input file validation."""

    @pytest.fixture(autouse=True)
    def _load_runner(self, skip_if_wrong_env):
        self.runner = _load_module("run_orca_input.py")

    def test_valid_input_no_warnings(self, tmp_path):
        inp_file = tmp_path / "good.inp"
        inp_file.write_text(
            "! B3LYP def2-TZVP\n"
            "%pal nprocs 4 end\n"
            "%maxcore 4000\n"
            "* xyz 0 1\n"
            "H 0.0 0.0 0.0\n"
            "*\n"
        )
        warnings = self.runner.validate_input_file(str(inp_file))
        assert len(warnings) == 0

    def test_missing_pal_block(self, tmp_path):
        inp_file = tmp_path / "nopal.inp"
        inp_file.write_text("! B3LYP def2-TZVP\n%maxcore 4000\n* xyz 0 1\nH 0 0 0\n*\n")
        warnings = self.runner.validate_input_file(str(inp_file))

        assert any("%pal" in w for w in warnings)

    def test_missing_maxcore(self, tmp_path):
        inp_file = tmp_path / "nomem.inp"
        inp_file.write_text("! B3LYP def2-TZVP\n%pal nprocs 4 end\n* xyz 0 1\nH 0 0 0\n*\n")
        warnings = self.runner.validate_input_file(str(inp_file))

        assert any("maxcore" in w.lower() for w in warnings)

    def test_empty_file(self, tmp_path):
        inp_file = tmp_path / "empty.inp"
        inp_file.write_text("")
        warnings = self.runner.validate_input_file(str(inp_file))

        assert any("empty" in w.lower() for w in warnings)

    def test_missing_keyword_line(self, tmp_path):
        inp_file = tmp_path / "nokw.inp"
        inp_file.write_text("%pal nprocs 4 end\n%maxcore 4000\n* xyz 0 1\nH 0 0 0\n*\n")
        warnings = self.runner.validate_input_file(str(inp_file))

        assert any("!" in w or "keyword" in w.lower() for w in warnings)

    def test_missing_coordinate_block(self, tmp_path):
        inp_file = tmp_path / "nocoords.inp"
        inp_file.write_text("! B3LYP def2-TZVP\n%pal nprocs 4 end\n%maxcore 4000\n")
        warnings = self.runner.validate_input_file(str(inp_file))

        assert any("coordinate" in w.lower() for w in warnings)


@pytest.mark.orca
class TestRunnerEnergyParser:
    """Test the energy parser in run_orca_input.py."""

    @pytest.fixture(autouse=True)
    def _load_runner(self, skip_if_wrong_env):
        self.runner = _load_module("run_orca_input.py")

    def test_parse_final_energy(self, tmp_path):
        out_file = tmp_path / "test.out"
        out_file.write_text(SAMPLE_ORCA_OUTPUT)

        result = self.runner.parse_final_energy(str(out_file))

        assert result["energy_hartree"] == pytest.approx(-76.342978150000)
        assert result["energy_eV"] == pytest.approx(-76.342978150000 * 27.211386245988, rel=1e-6)
        assert result["scf_converged"] is True
        assert result["scf_cycles"] == 12
        assert "2 min 34 sec" in result["total_run_time"]

    def test_parse_scf_not_converged(self, tmp_path):
        out_file = tmp_path / "bad.out"
        out_file.write_text(SAMPLE_BAD_SCF)

        result = self.runner.parse_final_energy(str(out_file))

        assert result["scf_converged"] is False

    def test_parse_empty_output(self, tmp_path):
        out_file = tmp_path / "empty.out"
        out_file.write_text("")

        result = self.runner.parse_final_energy(str(out_file))

        assert result["energy_hartree"] is None
        assert result["scf_converged"] is None


@pytest.mark.orca
class TestOutputParser:
    """Test ORCA output file parsing (parse_orca_output.py)."""

    @pytest.fixture(autouse=True)
    def _load_parser(self, skip_if_wrong_env):
        self.parser = _load_module("parse_orca_output.py")

    def test_parse_energy(self):
        result = self.parser.parse_energy(SAMPLE_ORCA_OUTPUT)

        assert result["final_energy_hartree"] == pytest.approx(-76.342978150000)
        assert result["final_energy_eV"] == pytest.approx(-76.342978150000 * 27.211386245988, rel=1e-6)
        assert result["nuclear_repulsion_hartree"] == pytest.approx(9.08734440)
        assert result["dispersion_correction_hartree"] == pytest.approx(-0.003412)

    def test_parse_orbital_energies(self):
        result = self.parser.parse_orbital_energies(SAMPLE_ORCA_OUTPUT)

        assert len(result["orbitals"]) == 7
        assert result["homo_eV"] == pytest.approx(-7.1322)
        assert result["lumo_eV"] == pytest.approx(1.1890)
        assert result["homo_lumo_gap_eV"] == pytest.approx(1.1890 - (-7.1322))

    def test_homo_lumo_gap_positive(self):
        result = self.parser.parse_orbital_energies(SAMPLE_ORCA_OUTPUT)
        assert result["homo_lumo_gap_eV"] > 0

    def test_parse_frequencies(self):
        result = self.parser.parse_frequencies(SAMPLE_FREQ_OUTPUT)

        assert len(result["frequencies_cm1"]) == 9
        assert result["n_imaginary"] == 0
        assert result["n_real"] == 9
        assert result["frequencies_cm1"][-1] == pytest.approx(3803.89)

    def test_parse_frequencies_zero_modes(self):
        result = self.parser.parse_frequencies(SAMPLE_FREQ_OUTPUT)
        zero_modes = [f for f in result["frequencies_cm1"] if f == 0.0]
        assert len(zero_modes) == 6  # 3 translational + 3 rotational for nonlinear

    def test_parse_thermochemistry(self):
        result = self.parser.parse_thermochemistry(SAMPLE_THERMO_OUTPUT)

        assert result["zero_point_energy_hartree"] == pytest.approx(0.02120832)
        assert result["enthalpy_hartree"] == pytest.approx(-76.31940283)
        assert result["gibbs_energy_hartree"] == pytest.approx(-76.34127815)
        assert result["entropy_correction_hartree"] == pytest.approx(-0.02187532)
        assert result["temperature_K"] == pytest.approx(298.15)

    def test_parse_thermochemistry_ev_conversion(self):
        result = self.parser.parse_thermochemistry(SAMPLE_THERMO_OUTPUT)

        assert result["zero_point_energy_eV"] == pytest.approx(
            0.02120832 * 27.211386245988, rel=1e-6
        )

    def test_parse_all(self, tmp_path):
        combined = SAMPLE_ORCA_OUTPUT + "\n" + SAMPLE_FREQ_OUTPUT + "\n" + SAMPLE_THERMO_OUTPUT
        out_file = tmp_path / "full.out"
        out_file.write_text(combined)

        result = self.parser.parse_output(str(out_file), ["all"])

        assert "energy" in result
        assert "orbitals" in result
        assert "frequencies" in result
        assert "thermochemistry" in result
        assert result["energy"]["final_energy_hartree"] is not None

    def test_parse_empty_output(self):
        result = self.parser.parse_energy("")
        assert result == {}

    def test_parse_selective_properties(self, tmp_path):
        out_file = tmp_path / "test.out"
        out_file.write_text(SAMPLE_ORCA_OUTPUT)

        result = self.parser.parse_output(str(out_file), ["energy", "orbitals"])

        assert "energy" in result
        assert "orbitals" in result
        assert "frequencies" not in result
        assert "thermochemistry" not in result
