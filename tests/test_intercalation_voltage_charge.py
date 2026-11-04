"""Synthetic regressions for charge normalization in intercalation voltages."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.base

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/mat-intercalation-voltage/scripts/calculate_voltage.py"
SPEC = importlib.util.spec_from_file_location("intercalation_voltage_charge", SCRIPT)
VOLTAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VOLTAGE)


def test_monovalent_keeps_existing_positional_api(tmp_path):
    """The original seven positional arguments retain their order and result."""
    output = tmp_path / "voltage.json"
    result = VOLTAGE.calculate_voltage(-20.0, -10.0, -2.0, 2, 2, "Li", str(output))
    assert result["voltage_V"] == pytest.approx(4.0)
    assert result["electrons_per_ion"] == 1.0
    assert result["n_electrons"] == 2.0
    assert json.loads(output.read_text()) == result


def test_divalent_voltage_is_half_monovalent():
    """Identical reaction energies are normalized by the transferred charge."""
    monovalent = VOLTAGE.calculate_voltage(-20.0, -10.0, -2.0, 2, 2)
    divalent = VOLTAGE.calculate_voltage(
        -20.0, -10.0, -2.0, 2, 2, metal_symbol="Mg", electrons_per_ion=2.0
    )
    assert divalent["voltage_V"] == pytest.approx(2.0)
    assert divalent["voltage_V"] == pytest.approx(monovalent["voltage_V"] / 2)
    assert divalent["electrons_per_ion"] == 2.0
    assert divalent["n_electrons"] == 4.0


def test_charge_is_explicit_and_not_inferred_from_symbol():
    """A metal label is documentation, not an assumed oxidation state."""
    result = VOLTAGE.calculate_voltage(-20.0, -10.0, -2.0, 2, 2, metal_symbol="Mg")
    assert result["voltage_V"] == pytest.approx(4.0)
    result = VOLTAGE.calculate_voltage(
        -20.0, -10.0, -2.0, 2, 2, electrons_per_ion=2.5
    )
    assert result["voltage_V"] == pytest.approx(1.6)


@pytest.mark.parametrize("charge", [0.0, -1.0, float("nan"), float("inf"), -float("inf")])
def test_invalid_charge_fails_before_writing(charge, tmp_path):
    """A nonpositive or nonfinite electron transfer is not a voltage input."""
    output = tmp_path / "voltage.json"
    with pytest.raises(ValueError, match="electrons_per_ion must be positive and finite"):
        VOLTAGE.calculate_voltage(
            -20.0, -10.0, -2.0, 2, 2,
            output_file=str(output), electrons_per_ion=charge,
        )
    assert not output.exists()


def run_cli(tmp_path, charge=None):
    """Run the actual script, including its input-config writer."""
    output = tmp_path / "voltage.json"
    command = [
        sys.executable, str(SCRIPT),
        "--e_full", "-20", "--e_empty", "-10", "--e_metal", "-2",
        "--n_metal", "2", "--n_ions", "2", "--metal", "Mg",
        "--output", str(output),
    ]
    if charge is not None:
        command.append(f"--electrons_per_ion={charge}")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), env.get("PYTHONPATH")]))
    process = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    return process, output


@pytest.mark.parametrize("charge,expected", [(None, 4.0), (1.0, 4.0), (2.0, 2.0)])
def test_cli_charge_and_saved_inputs(charge, expected, tmp_path):
    """The public CLI forwards explicit/default charge and persists it."""
    import yaml

    process, output = run_cli(tmp_path, charge)
    assert process.returncode == 0, process.stderr
    result = json.loads(output.read_text())
    assert result["voltage_V"] == pytest.approx(expected)
    assert result["electrons_per_ion"] == (charge if charge is not None else 1.0)
    config = yaml.safe_load((tmp_path / "input_configs.yaml").read_text())
    assert config["electrons_per_ion"] == result["electrons_per_ion"]


@pytest.mark.parametrize("charge", ["0", "-1", "nan", "inf", "-inf"])
def test_cli_rejects_invalid_charge(charge, tmp_path):
    """Invalid charge exits unsuccessfully without a result or input config."""
    process, output = run_cli(tmp_path, charge)
    assert process.returncode != 0
    assert "electrons_per_ion must be positive and finite" in process.stderr
    assert not output.exists()
    assert not (tmp_path / "input_configs.yaml").exists()
