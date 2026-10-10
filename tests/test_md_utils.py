import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ase.build import bulk
from ase.calculators.emt import EMT

from src.utils.mlips.base import MLIPModel
from src.utils.mlips.md_utils import (
    DiffusionMonitor,
    EquilibrationMonitor,
    MDStopIteration,
    get_md_callback,
)
from src.utils.mlips.md_runner import CustomMDCalc


class _EMTModel(MLIPModel):
    """Minimal MLIPModel backed by ASE's EMT calculator for CPU tests."""

    def __init__(self):
        super().__init__(model_name="EMT")
        self.is_loaded = True

    def load(self, model_path=None):
        pass

    def create_calculator(self):
        return EMT()

    def predict_atomic_features(self, structure_data):
        return {}

    def save_checkpoint(self, checkpoint_path):
        pass

    def load_checkpoint(self, checkpoint_path):
        pass


def test_custom_md_calc_draws_velocities_without_momenta():
    """An input without stored momenta must start from Maxwell-Boltzmann velocities.

    ``Atoms.get_velocities()`` returns zeros (not None) when no momenta are set,
    which previously started a perfect crystal at rest so that it never heated.
    """
    atoms = bulk("Cu", "fcc", a=3.6, cubic=True).repeat(2)

    md_calc = CustomMDCalc(
        calculator=EMT(),
        ensemble="nvt",
        temperature=300,
        timestep=2.0,
        steps=5,
        relax_structure=False,
    )
    result = md_calc.calc(atoms)

    # 3/2 kB T at 300 K is ~0.039 eV/atom; a crystal left at rest stays near 0.
    assert result["kinetic_energy"] / len(atoms) > 0.01


def test_explosion_monitor_reads_dynamics_atoms():
    """ExplosionMonitor must read the temperature of the atoms being integrated."""
    atoms = bulk("Cu", "fcc", a=3.6, cubic=True).repeat(2)
    monitor = get_md_callback("explosion", atoms, temp_threshold=1.0)

    md_calc = CustomMDCalc(
        calculator=EMT(),
        ensemble="nvt",
        temperature=300,
        timestep=2.0,
        steps=20,
        additional_callbacks=[(monitor, 1)],
    )
    with pytest.raises(MDStopIteration, match="Explosion detected"):
        md_calc.calc(atoms)


def test_run_md_reports_monitor_stop(tmp_path):
    """run_md heats a structure read without momenta and reports a monitor stop."""
    model = _EMTModel()
    atoms = bulk("Cu", "fcc", a=3.6, cubic=True).repeat(2)

    result = model.run_md(
        atoms,
        temperature=300.0,
        steps=50,
        timestep=2.0,
        log_interval=1,
        output_dir=str(tmp_path),
        monitor=True,
        monitor_type="explosion",
        monitor_params={"temp_threshold": 1.0},
    )

    assert result["status"] == "stopped"
    assert "Explosion detected" in result["stop_reason"]


def test_diffusion_monitor_auto_detect_params():
    atoms = bulk("Cu", "fcc", a=3.6)
    atoms.calc = EMT()

    # Test that MD runner properly auto-configures DiffusionMonitor
    monitor = DiffusionMonitor(
        atoms=atoms, specie="Cu", check_interval_ps=1.0, ignore_ps=0.0
    )

    md_calc = CustomMDCalc(
        calculator=EMT(),
        ensemble="nvt",
        temperature=300,
        timestep=2.0,
        steps=10,
        loginterval=5,
        additional_callbacks=[(monitor, 5)],
    )

    md_calc.calc(atoms)

    # Monitor should have resolved its params
    assert monitor.temperature == 300
    assert monitor.timestep_fs == 2.0
    assert monitor.log_interval == 5


def test_equilibration_monitor_auto_detect_params():
    atoms = bulk("Cu", "fcc", a=3.6)
    atoms.calc = EMT()

    monitor = EquilibrationMonitor(atoms=atoms, window_ps=0.5, stability_ps=1.0)

    md_calc = CustomMDCalc(
        calculator=EMT(),
        ensemble="nvt",
        temperature=400,
        timestep=1.5,
        steps=5,
        loginterval=2,
        additional_callbacks=[(monitor, 2)],
    )

    try:
        md_calc.calc(atoms)
    except Exception:
        # We might stop early, but params should be resolved
        pass

    assert monitor.timestep_fs == 1.5
    assert monitor.log_interval == 2


def test_get_md_callback_passes_kwargs():
    atoms = bulk("Cu", "fcc", a=3.6)
    atoms.calc = EMT()

    callback = get_md_callback(
        "diffusion", atoms, timestep_fs=1.0, temperature=500.0, specie="Cu"
    )

    assert isinstance(callback, DiffusionMonitor)
    assert callback.timestep_fs is None
    assert callback.log_interval is None
    assert callback.temperature is None
    assert callback.specie == "Cu"


def test_run_md_returns_last_md_frame(tmp_path):
    """run_md must return (and write) the last MD frame, not the input structure."""
    import numpy as np
    from ase.io import read

    model = _EMTModel()
    atoms = bulk("Cu", "fcc", a=3.6, cubic=True).repeat(2)

    result = model.run_md(
        atoms,
        temperature=300.0,
        steps=20,
        timestep=2.0,
        log_interval=5,
        output_dir=str(tmp_path),
    )

    final = read(result["cif_path"])
    last_frame = read(result["trajectory_path"], index=-1)

    def frac_gap(a, b):
        """Largest minimum-image fractional-coordinate difference (CIF wraps atoms)."""
        d = a.get_scaled_positions(wrap=False) - b.get_scaled_positions(wrap=False)
        return np.abs(d - np.round(d)).max()

    # The input is a perfect lattice; after 20 steps at 300 K atoms have moved.
    assert frac_gap(final, atoms) > 1e-4
    assert frac_gap(final, last_frame) < 1e-5


if __name__ == "__main__":
    pytest.main(["-v", __file__])
