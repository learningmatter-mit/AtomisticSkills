---
name: mat-solid-free-energy
description: Calculate absolute solid Helmholtz free energy, and optional Gibbs free energy, with Frenkel-Ladd switching using portable MLIP wrappers on a pre-equilibrated periodic structure.
category: [materials]
---

# Solid Free Energy

This skill calculates the absolute free energy of a crystalline solid using **Frenkel-Ladd switching**, which is a specific form of **Thermodynamic Integration (TI)**. 

Thermodynamic integration computes the free energy difference between two states by integrating the derivative of the Hamiltonian along a continuous coupling path. In this skill, the path interpolates between a physical MLIP Hamiltonian (the target state) and a harmonic Einstein-crystal reference (where the exact absolute free energy is analytically known).

## Goal

Compute the Helmholtz free energy $F$ of a pre-equilibrated periodic solid at a target temperature, and optionally the Gibbs free energy $G = F + PV$ if pressure is supplied.

## Prerequisites

- A pre-equilibrated periodic solid structure in an ASE-readable format such as CIF or POSCAR.
- The transferable MLIP wrapper stack must be available in the target repo via `src.utils.mlips.loader.load_wrapper(...)`.
- ASE and pymatgen must be installed in the relevant conda environment.

> [!IMPORTANT]
> This skill only performs the Frenkel-Ladd free-energy workflow. It does not relax the structure, build a supercell, equilibrate the volume, perform alchemical switching, or apply center-of-mass corrections.

## Choosing a Foundation Potential

Frenkel-Ladd switching is an MD-based free-energy method, so both energy and force stability matter.

> [!IMPORTANT]
> - Prefer materials models intended for PES or MD use, such as `MACE-OMAT-0-small`, `MACE-MH-1`, `CHGNet-MatPES-*`, or `TensorNet-MatPES-*`.
> - Use smaller or faster models for long switching trajectories when practical.
> - Avoid changing model family between preparation and Frenkel-Ladd unless you intentionally want a different free-energy reference.

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for model selection guidance.

## Preparing Inputs

This skill assumes the input structure is already appropriate for the target thermodynamic state point. For production workflows, the most useful upstream skills are:

- [mat-db-mp](../mat-db-mp/SKILL.md): Retrieve a starting bulk crystal structure from Materials Project.
- [mat-equation-of-state](../mat-equation-of-state/SKILL.md): Estimate an equilibrium cell volume and generate a better-relaxed starting point before finite-temperature sampling.
- [mat-lammps-md](../mat-lammps-md/SKILL.md): Equilibrate a larger periodic cell at the target temperature or pressure using the same MLIP family.
- [mat-md-monitors](../mat-md-monitors/SKILL.md): Check MD stability, thermostat behavior, volume drift, and equilibration while preparing the input trajectory.
- [mat-phonon](../mat-phonon/SKILL.md): Screen for imaginary modes or other vibrational-instability warnings before running an expensive free-energy workflow.

## Calculation Workflow

Run the standalone Frenkel-Ladd script:

```bash
# Env: mace-agent
python .agents/skills/mat-solid-free-energy/scripts/run_frenkel_ladd.py \
    --structure path/to/pre_equilibrated_structure.cif \
    --name my_solid \
    --calculator mace \
    --model-name MACE-OMAT-0-small \
    --temperature 300 \
    --pressure-gpa 0.0 \
    --output-dir research/my_folder/frenkel_ladd
```

### Key Parameters

- `--structure`: Pre-equilibrated periodic solid at the target state point.
- `--calculator`: MLIP backend: `mace`, `fairchem`, or `matgl`.
- `--model-name`: Model name or checkpoint path.
- `--task-name`: Optional task head for multitask models.
- `--temperature`: Temperature in K.
- `--pressure-gpa`: Optional pressure in GPa. If provided, the script also reports Gibbs free energy.
- `--msd-equilibration-steps`: NVT equilibration before MSD collection.
- `--msd-production-steps`: NVT production used to estimate per-atom spring constants.
- `--equilibration-steps`: Harmonic-reference equilibration between forward and backward switching.
- `--switching-steps`: Number of MD steps in each switching direction.
- `--switching-type`: `linear` or `polynomial`. Default is the smoother `polynomial` schedule.
- `--record-interval`: Record every N MD steps.

### Default Production Settings

The script defaults are:

- `timestep_fs = 1.0`
- `thermostat_damping_fs = 100.0`
- `msd_equilibration_steps = 1000`
- `msd_production_steps = 10000`
- `equilibration_steps = 5000`
- `switching_steps = 25000`
- `switching_type = polynomial`
- `record_interval = 1`
- `symmetrize_spring_constants = True`

## Output Files

- `frenkel_ladd_results.json`: Summary including Helmholtz free energy, optional Gibbs free energy, dissipated energy, calculator metadata, and settings.
- `frenkel_ladd_traces.npz`: Raw recorded arrays:
  - `lambda_steps`
  - `forward_energy_contributions`
  - `backward_energy_contributions`
  - `spring_constants`
  - `mean_squared_displacement`
- `input_structure.cif`: Copy of the starting structure.
- `final_structure.cif`: Final structure after backward switching.

## Example

See `examples/Si_MACE/` for a minimal silicon example using MACE with reduced step counts for demonstration.

```bash
# Env: mace-agent
python .agents/skills/mat-solid-free-energy/scripts/run_frenkel_ladd.py \
    --structure .agents/skills/mat-solid-free-energy/examples/Si_MACE/Si.cif \
    --name Si_demo \
    --calculator mace \
    --model-name MACE-OMAT-0-small \
    --temperature 300 \
    --msd-equilibration-steps 50 \
    --msd-production-steps 200 \
    --equilibration-steps 100 \
    --switching-steps 500 \
    --record-interval 5 \
    --output-dir research/frenkel_ladd/Si_demo
```

> [!NOTE]
> The example is a smoke-test style demonstration. For production free-energy work, start from a genuinely pre-equilibrated structure and use the heavier default settings or stricter settings appropriate for your system.

## Constraints

- **Environment**:
  - `mace-agent` for MACE models
  - `fairchem-agent` for FairChem/UMA models
  - `matgl-agent` for MatGL/CHGNet models
- **Periodic solids only**: This method is intended for bulk crystalline solids, not molecules or non-periodic clusters.
- **Pre-equilibrated input required**: The script assumes the supplied structure already represents the desired thermodynamic state point.
- **Quality control**: Inspect `abs(dissipated_energy) / num_atoms`. Values much larger than about `0.05 eV/atom` suggest poor switching reversibility and should be treated with caution.
- **Cost**: Frenkel-Ladd calculations are expensive because they require long MD trajectories in both switching directions.

---

**Author:** Juno Nam
**Contact:** [GitHub @recisic](https://github.com/recisic)
