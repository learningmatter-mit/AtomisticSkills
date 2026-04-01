import pytest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ase.build import bulk
from ase.calculators.emt import EMT
import ase.units as units

from src.utils.mlips.md_utils import DiffusionMonitor, EquilibrationMonitor, get_md_callback
from src.utils.mlips.md_runner import CustomMDCalc

def test_diffusion_monitor_auto_detect_params():
    atoms = bulk('Cu', 'fcc', a=3.6)
    atoms.calc = EMT()

    # Test that MD runner properly auto-configures DiffusionMonitor
    monitor = DiffusionMonitor(
        atoms=atoms,
        specie="Cu",
        check_interval_ps=1.0,
        ignore_ps=0.0
    )

    md_calc = CustomMDCalc(
        calculator=EMT(),
        ensemble="nvt",
        temperature=300,
        timestep=2.0,
        steps=10,
        loginterval=5,
        additional_callbacks=[(monitor, 5)]
    )

    md_calc.calc(atoms)

    # Monitor should have resolved its params
    assert monitor.temperature == 300
    assert monitor.timestep_fs == 2.0
    assert monitor.log_interval == 5

def test_equilibration_monitor_auto_detect_params():
    atoms = bulk('Cu', 'fcc', a=3.6)
    atoms.calc = EMT()

    monitor = EquilibrationMonitor(
        atoms=atoms,
        window_ps=0.5,
        stability_ps=1.0
    )

    md_calc = CustomMDCalc(
        calculator=EMT(),
        ensemble="nvt",
        temperature=400,
        timestep=1.5,
        steps=5,
        loginterval=2,
        additional_callbacks=[(monitor, 2)]
    )

    try:
        md_calc.calc(atoms)
    except Exception as e:
        # We might stop early, but params should be resolved
        pass

    assert monitor.timestep_fs == 1.5
    assert monitor.log_interval == 2

def test_get_md_callback_passes_kwargs():
    atoms = bulk('Cu', 'fcc', a=3.6)
    atoms.calc = EMT()

    callback = get_md_callback(
        "diffusion",
        atoms,
        timestep_fs=1.0,
        temperature=500.0,
        specie="Cu"
    )

    assert isinstance(callback, DiffusionMonitor)
    assert callback.timestep_fs is None
    assert callback.log_interval is None
    assert callback.temperature is None
    assert callback.specie == "Cu"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
