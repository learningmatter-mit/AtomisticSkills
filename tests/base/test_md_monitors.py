"""
Tests for MD monitoring functionality.

These tests verify that MD monitors (Explosion, Volume, Equilibration) correctly
detect and stop simulations when their criteria are met.
"""
import pytest
from ase.build import bulk
from ase.calculators.emt import EMT
from ase import units
from ase.md.verlet import VelocityVerlet
from ase.md.nptberendsen import Inhomogeneous_NPTBerendsen
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary, ZeroRotation

from src.utils.mlips.md_utils import ExplosionMonitor, VolumeMonitor, EquilibrationMonitor, MDStopIteration


def test_explosion_monitor():
    """
    Test ExplosionMonitor with EMT and VelocityVerlet.
    Using a huge timestep to force instability.
    """
    atoms = bulk("Al", "fcc", a=4.05) * (2, 2, 2)
    atoms.calc = EMT()
    
    # Initialize velocities
    MaxwellBoltzmannDistribution(atoms, temperature_K=1000.0)
    Stationary(atoms)
    ZeroRotation(atoms)
    
    # Very large timestep (100 fs) to cause explosion
    dyn = VelocityVerlet(atoms, timestep=100.0 * units.fs)
    
    # Initialize and attach monitor
    monitor = ExplosionMonitor(atoms=atoms)
    dyn.attach(monitor, interval=1, dyn=dyn)
    
    # Run simulation - should stop early due to explosion
    error_message = None
    try:
        dyn.run(steps=20)
    except (MDStopIteration, StopIteration) as e:
        error_message = str(e)
    
    # Verify it stopped early
    assert dyn.nsteps < 20, f"Explosion monitor failed to stop simulation early (ran {dyn.nsteps}/20 steps)"
    
    # Verify the error message indicates explosion was detected
    assert error_message and "Explosion detected" in error_message, \
        f"Expected 'Explosion detected' in error message, got: {error_message}"


def test_volume_monitor():
    """
    Test VolumeMonitor with EMT and VelocityVerlet.
    Manually expand the cell during MD to trigger the monitor.
    """
    atoms = bulk("Al", "fcc", a=4.05) * (2, 2, 2)
    atoms.calc = EMT()
    
    # Initialize velocities
    MaxwellBoltzmannDistribution(atoms, temperature_K=300.0)
    Stationary(atoms)
    ZeroRotation(atoms)
    
    # Simple NVE dynamics
    dyn = VelocityVerlet(atoms, timestep=2.0 * units.fs)
    
    # Callback to manually expand cell to trigger volume monitor
    expansion_rate = 1.002  # 0.2% per call
    def expand_cell():
        cell = atoms.get_cell()
        atoms.set_cell(cell * expansion_rate, scale_atoms=True)
    
    # Attach expansion callback every 2 steps
    dyn.attach(expand_cell, interval=2)
    
    # Monitor with 5% upper limit - should trigger around step 50 (5% / 0.2% per 2 steps)
    monitor = VolumeMonitor(atoms=atoms, upper_limit_ratio=1.05, lower_limit_ratio=0.0)
    dyn.attach(monitor, interval=2, dyn=dyn)
    
    # Run simulation
    error_message = None
    try:
        dyn.run(steps=200)
    except (MDStopIteration, StopIteration) as e:
        error_message = str(e)
    
    # Verify it stopped early (should stop around step 50)
    assert dyn.nsteps < 200, f"Volume monitor failed to stop simulation early (ran {dyn.nsteps}/200 steps)"
    
    # Verify the error message indicates volume expansion was detected
    assert error_message and "Volume expansion detected" in error_message, \
        f"Expected 'Volume expansion detected' in error message, got: {error_message}"


def test_equilibration_monitor():
    """
    Test EquilibrationMonitor with EMT and Langevin.
    Should detect equilibration and stop simulation.
    """
    atoms = bulk("Al", "fcc", a=4.05) * (2, 2, 2)
    atoms.calc = EMT()
    
    temperature = 300.0
    
    # Initialize velocities
    MaxwellBoltzmannDistribution(atoms, temperature_K=temperature)
    Stationary(atoms)
    ZeroRotation(atoms)
    
    # Use Langevin thermostat
    dyn = Langevin(
        atoms,
        timestep=2.0 * units.fs,
        temperature_K=temperature,
        friction=0.01
    )
    
    # Very loose criteria to ensure quick triggering in test
    monitor = EquilibrationMonitor(
        atoms=atoms,
        window_ps=0.01,      # 10 fs window
        stability_ps=0.02,   # 20 fs stability check
        temp_std_threshold=1000.0  # High threshold
    )
    dyn.attach(monitor, interval=1, dyn=dyn)
    
    # Run simulation
    error_message = None
    try:
        dyn.run(steps=200)
    except (MDStopIteration, StopIteration) as e:
        error_message = str(e)
    
    # Verify it stopped early (should equilibrate within ~15-20 steps)
    assert dyn.nsteps < 200, f"Equilibration monitor failed to stop simulation early (ran {dyn.nsteps}/200 steps)"
    
    # Verify the error message indicates equilibration was detected
    assert error_message and "Equilibration reached" in error_message, \
        f"Expected 'Equilibration reached' in error message, got: {error_message}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
