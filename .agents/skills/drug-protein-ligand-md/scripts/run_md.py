"""
Run a protein-ligand MD simulation with OpenMM.

Performs energy minimization, restrained NVT equilibration, restrained NPT
equilibration, and production NPT. Reads a serialized System XML and solvated
PDB from drug-complex-system-builder.

Usage:
    python run_md.py --system_xml system.xml --input_pdb complex.pdb --output_dir run/

Requirements:
    - Conda environment: drugmd-agent
    - Required packages: openmm
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import openmm
import openmm.app as app
import openmm.unit as unit


def step_with_progress(simulation, total_steps: int, chunk: int = 10000, label: str = "") -> None:
    """Run simulation steps with periodic progress to stdout."""
    done = 0
    while done < total_steps:
        n = min(chunk, total_steps - done)
        simulation.step(n)
        done += n
        state = simulation.context.getState(getEnergy=True)
        temp_k = (2 * state.getKineticEnergy() / (simulation.system.getNumParticles() * 3 * unit.MOLAR_GAS_CONSTANT_R)).value_in_unit(unit.kelvin)
        pe = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        pct = 100 * done / total_steps
        print(f"  {label} {done}/{total_steps} ({pct:.0f}%) T={temp_k:.1f} K  PE={pe:.0f} kJ/mol", flush=True)


def select_platform() -> openmm.Platform:
    """Select the fastest available platform (CUDA > OpenCL > CPU)."""
    for name in ["CUDA", "OpenCL", "CPU"]:
        try:
            platform = openmm.Platform.getPlatformByName(name)
            print(f"Using platform: {name}")
            return platform
        except Exception:
            continue
    raise RuntimeError("No OpenMM platform available")


def add_restraints(
    system: openmm.System,
    topology: app.Topology,
    positions,
    restraint_k: float,
) -> openmm.CustomExternalForce:
    """
    Add positional restraints on non-water, non-ion heavy atoms.

    Args:
        system: OpenMM System to add restraints to.
        topology: System topology.
        positions: Atom positions.
        restraint_k: Force constant in kJ/mol/nm^2.

    Returns:
        The CustomExternalForce object (for later removal or scaling).
    """
    force = openmm.CustomExternalForce(
        "k*periodicdistance(x, y, z, x0, y0, z0)^2"
    )
    force.addGlobalParameter("k", restraint_k)
    force.addPerParticleParameter("x0")
    force.addPerParticleParameter("y0")
    force.addPerParticleParameter("z0")

    solvent_residues = {"HOH", "WAT", "NA", "CL", "Na+", "Cl-", "K", "K+"}

    for atom in topology.atoms():
        if atom.residue.name in solvent_residues:
            continue
        if atom.element is not None and atom.element.mass > 2.0 * unit.amu:
            pos = positions[atom.index]
            x0 = pos[0].value_in_unit(unit.nanometer)
            y0 = pos[1].value_in_unit(unit.nanometer)
            z0 = pos[2].value_in_unit(unit.nanometer)
            force.addParticle(atom.index, [x0, y0, z0])

    system.addForce(force)
    return force


def run_md(
    system_xml_path: Path,
    input_pdb_path: Path,
    state_xml_path: Path | None = None,
    temperature: float = 300.0,
    pressure: float = 1.0,
    timestep: float = 4.0,
    minimize_steps: int = 5000,
    equil_nvt_steps: int = 25000,
    equil_npt_steps: int = 50000,
    production_steps: int = 2500000,
    restraint_k: float = 50.0,
    reporting_interval: int = 5000,
    checkpoint_interval: int = 25000,
    seed: int = 0,
    restart_from: Path | None = None,
    output_dir: Path = Path("run"),
) -> dict:
    """Run a complete protein-ligand MD workflow."""
    output_dir.mkdir(parents=True, exist_ok=True)
    wall_start = time.time()

    # Load system and topology
    print(f"Loading system from {system_xml_path}...")
    with open(system_xml_path, "r") as f:
        system = openmm.XmlSerializer.deserialize(f.read())

    print(f"Loading topology from {input_pdb_path}...")
    pdb = app.PDBFile(str(input_pdb_path))
    topology = pdb.topology
    positions = pdb.positions

    if state_xml_path is not None and state_xml_path.exists():
        print(f"Loading full-precision positions from {state_xml_path}...")
        with open(state_xml_path, "r") as f:
            state = openmm.XmlSerializer.deserialize(f.read())
        positions = state.getPositions()
        box = state.getPeriodicBoxVectors()
        if box is not None:
            system.setDefaultPeriodicBoxVectors(*box)
        print("Using state XML positions (full precision) instead of PDB.")

    platform = select_platform()
    dt = timestep * unit.femtosecond
    temp = temperature * unit.kelvin

    # Warn if timestep looks incompatible with hydrogen masses
    if timestep > 2.0:
        h_masses = []
        for atom in topology.atoms():
            if atom.element is not None and atom.element.symbol == "H":
                mass = system.getParticleMass(atom.index).value_in_unit(unit.amu)
                h_masses.append(mass)
        if h_masses:
            max_h = max(h_masses)
            if max_h < 1.1:
                print(
                    f"WARNING: timestep is {timestep} fs but hydrogen masses are ~{max_h:.3f} amu "
                    f"(no HMR detected). This will likely cause instability. "
                    f"Use --timestep 2.0 or rebuild the system with HMR.",
                    file=sys.stderr,
                )

    # Track box vectors across phases
    box = topology.getPeriodicBoxVectors()
    velocities = None

    # Add restraints for equilibration
    add_restraints(system, topology, positions, restraint_k)

    # -- Phase 1: Energy Minimization --
    if minimize_steps > 0:
        print(f"\n--- Energy Minimization (max {minimize_steps} steps) ---")
        integrator = openmm.LangevinMiddleIntegrator(temp, 1.0 / unit.picosecond, dt)
        if seed != 0:
            integrator.setRandomNumberSeed(seed)
        simulation = app.Simulation(topology, system, integrator, platform)
        simulation.context.setPositions(positions)
        box = topology.getPeriodicBoxVectors()
        if box is not None:
            simulation.context.setPeriodicBoxVectors(*box)
        simulation.minimizeEnergy(maxIterations=minimize_steps)

        state = simulation.context.getState(
            getPositions=True, getEnergy=True
        )
        positions = state.getPositions()
        box = state.getPeriodicBoxVectors()
        pe = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        print(f"Minimized PE: {pe:.1f} kJ/mol")

        min_pdb_path = output_dir / "minimized.pdb"
        with open(min_pdb_path, "w") as f:
            app.PDBFile.writeFile(topology, positions, f)
        print(f"Wrote: {min_pdb_path}")
        del simulation, integrator

    # -- Phase 2: NVT Equilibration (restrained) --
    if equil_nvt_steps > 0:
        print(f"\n--- NVT Equilibration ({equil_nvt_steps} steps, restrained) ---")
        integrator = openmm.LangevinMiddleIntegrator(temp, 1.0 / unit.picosecond, dt)
        if seed != 0:
            integrator.setRandomNumberSeed(seed + 1)
        simulation = app.Simulation(topology, system, integrator, platform)
        simulation.context.setPositions(positions)
        if box is not None:
            simulation.context.setPeriodicBoxVectors(*box)
        simulation.context.setVelocitiesToTemperature(temp)

        nvt_log_path = output_dir / "nvt_equilibration.log"
        simulation.reporters.append(
            app.StateDataReporter(
                str(nvt_log_path),
                reporting_interval,
                step=True,
                temperature=True,
                potentialEnergy=True,
                totalEnergy=True,
                speed=True,
            )
        )

        step_with_progress(simulation, equil_nvt_steps, chunk=5000, label="NVT")
        state = simulation.context.getState(getPositions=True)
        positions = state.getPositions()
        box = state.getPeriodicBoxVectors()
        print("NVT equilibration complete.")
        del simulation, integrator

    # -- Phase 3: NPT Equilibration (restrained, then released) --
    if equil_npt_steps > 0:
        print(f"\n--- NPT Equilibration ({equil_npt_steps} steps) ---")
        barostat = openmm.MonteCarloBarostat(
            pressure * unit.atmosphere, temp, 25
        )
        system.addForce(barostat)

        integrator = openmm.LangevinMiddleIntegrator(temp, 1.0 / unit.picosecond, dt)
        if seed != 0:
            integrator.setRandomNumberSeed(seed + 2)
        simulation = app.Simulation(topology, system, integrator, platform)
        simulation.context.setPositions(positions)
        if box is not None:
            simulation.context.setPeriodicBoxVectors(*box)
        simulation.context.setVelocitiesToTemperature(temp)

        npt_log_path = output_dir / "npt_equilibration.log"
        simulation.reporters.append(
            app.StateDataReporter(
                str(npt_log_path),
                reporting_interval,
                step=True,
                temperature=True,
                potentialEnergy=True,
                density=True,
                speed=True,
            )
        )

        # Run half with full restraints, half with reduced restraints
        half = equil_npt_steps // 2
        step_with_progress(simulation, half, chunk=5000, label="NPT-restrained")
        simulation.context.setParameter("k", restraint_k * 0.1)
        step_with_progress(simulation, equil_npt_steps - half, chunk=5000, label="NPT-releasing")

        state = simulation.context.getState(getPositions=True, getVelocities=True)
        positions = state.getPositions()
        velocities = state.getVelocities()
        box = state.getPeriodicBoxVectors()
        print("NPT equilibration complete.")
        del simulation, integrator

    # -- Phase 4: Production NPT --
    print(f"\n--- Production NPT ({production_steps} steps) ---")

    integrator = openmm.LangevinMiddleIntegrator(temp, 1.0 / unit.picosecond, dt)
    if seed != 0:
        integrator.setRandomNumberSeed(seed + 3)

    simulation = app.Simulation(topology, system, integrator, platform)
    simulation.context.setParameter("k", 0.0)

    if restart_from is not None:
        print(f"Restarting from {restart_from}...")
        with open(restart_from, "r") as f:
            simulation.context.setState(openmm.XmlSerializer.deserialize(f.read()))
    else:
        simulation.context.setPositions(positions)
        if box is not None:
            simulation.context.setPeriodicBoxVectors(*box)
        if equil_npt_steps > 0:
            simulation.context.setVelocities(velocities)
        else:
            simulation.context.setVelocitiesToTemperature(temp)

    # Reporters
    dcd_path = output_dir / "production.dcd"
    simulation.reporters.append(app.DCDReporter(str(dcd_path), reporting_interval))

    prod_log_path = output_dir / "production.log"
    simulation.reporters.append(
        app.StateDataReporter(
            str(prod_log_path),
            reporting_interval,
            step=True,
            time=True,
            temperature=True,
            potentialEnergy=True,
            totalEnergy=True,
            density=True,
            speed=True,
        )
    )

    chk_path = output_dir / "checkpoint.chk"
    simulation.reporters.append(
        app.CheckpointReporter(str(chk_path), checkpoint_interval)
    )

    step_with_progress(simulation, production_steps, chunk=25000, label="Production")

    final_state_path = output_dir / "final_state.xml"
    state = simulation.context.getState(
        getPositions=True, getVelocities=True, getForces=True
    )
    with open(final_state_path, "w") as f:
        f.write(openmm.XmlSerializer.serialize(state))
    print(f"Wrote final state: {final_state_path}")

    wall_time = time.time() - wall_start

    provenance = {
        "system_xml": str(system_xml_path),
        "input_pdb": str(input_pdb_path),
        "temperature_K": temperature,
        "pressure_atm": pressure,
        "timestep_fs": timestep,
        "minimize_steps": minimize_steps,
        "equil_nvt_steps": equil_nvt_steps,
        "equil_npt_steps": equil_npt_steps,
        "production_steps": production_steps,
        "restraint_k_kJ_mol_nm2": restraint_k,
        "reporting_interval": reporting_interval,
        "checkpoint_interval": checkpoint_interval,
        "seed": seed,
        "platform": platform.getName(),
        "wall_time_seconds": round(wall_time, 1),
        "production_dcd": str(dcd_path),
        "production_log": str(prod_log_path),
        "final_state": str(final_state_path),
    }

    prov_path = output_dir / "md_provenance.json"
    with open(prov_path, "w") as f:
        json.dump(provenance, f, indent=4)
    print(f"Wrote provenance: {prov_path}")
    print(f"Total wall time: {wall_time:.1f} s")

    return provenance


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run protein-ligand MD simulation with OpenMM."
    )
    parser.add_argument("--system_xml", required=True, help="Serialized OpenMM System XML.")
    parser.add_argument("--input_pdb", required=True, help="Solvated complex PDB (topology).")
    parser.add_argument("--state_xml", default=None, help="Initial state XML for full-precision positions and box vectors.")
    parser.add_argument("--temperature", type=float, default=300.0, help="Temperature in K (default: 300).")
    parser.add_argument("--pressure", type=float, default=1.0, help="Pressure in atm (default: 1.0).")
    parser.add_argument("--timestep", type=float, default=4.0, help="Timestep in fs (default: 4.0).")
    parser.add_argument("--minimize_steps", type=int, default=5000, help="Max minimization steps (default: 5000).")
    parser.add_argument("--equil_nvt_steps", type=int, default=25000, help="NVT equilibration steps (default: 25000).")
    parser.add_argument("--equil_npt_steps", type=int, default=50000, help="NPT equilibration steps (default: 50000).")
    parser.add_argument("--production_steps", type=int, default=2500000, help="Production NPT steps (default: 2500000).")
    parser.add_argument("--restraint_k", type=float, default=50.0, help="Restraint k in kJ/mol/nm^2 (default: 50.0).")
    parser.add_argument("--reporting_interval", type=int, default=5000, help="Trajectory save interval in steps (default: 5000).")
    parser.add_argument("--checkpoint_interval", type=int, default=25000, help="Checkpoint save interval in steps (default: 25000).")
    parser.add_argument("--seed", type=int, default=0, help="Random seed (default: 0 = random).")
    parser.add_argument("--restart_from", default=None, help="State XML to restart from.")
    parser.add_argument("--output_dir", required=True, help="Output directory.")
    args = parser.parse_args()

    system_xml_path = Path(args.system_xml)
    input_pdb_path = Path(args.input_pdb)

    if not system_xml_path.exists():
        print(f"ERROR: System XML not found: {system_xml_path}", file=sys.stderr)
        sys.exit(1)
    if not input_pdb_path.exists():
        print(f"ERROR: Input PDB not found: {input_pdb_path}", file=sys.stderr)
        sys.exit(1)

    restart = Path(args.restart_from) if args.restart_from else None
    state_xml = Path(args.state_xml) if args.state_xml else None

    run_md(
        system_xml_path=system_xml_path,
        input_pdb_path=input_pdb_path,
        state_xml_path=state_xml,
        temperature=args.temperature,
        pressure=args.pressure,
        timestep=args.timestep,
        minimize_steps=args.minimize_steps,
        equil_nvt_steps=args.equil_nvt_steps,
        equil_npt_steps=args.equil_npt_steps,
        production_steps=args.production_steps,
        restraint_k=args.restraint_k,
        reporting_interval=args.reporting_interval,
        checkpoint_interval=args.checkpoint_interval,
        seed=args.seed,
        restart_from=restart,
        output_dir=Path(args.output_dir),
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
