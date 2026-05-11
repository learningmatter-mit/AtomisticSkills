---
name: drug-protein-ligand-md
description: Run a protein-ligand MD simulation in OpenMM with energy minimization, restrained equilibration, and production NPT, producing trajectory and checkpoint files for downstream analysis.
category: [drug-discovery]
---

# drug-protein-ligand-md

## Goal
To run a complete protein-ligand molecular dynamics simulation using OpenMM, starting from a system bundle produced by [drug-complex-system-builder](../drug-complex-system-builder/SKILL.md). The workflow includes:

1. Energy minimization
2. NVT equilibration with positional restraints on heavy atoms
3. NPT equilibration with restraints gradually released
4. NPT production run

The output is a DCD trajectory + final state checkpoint suitable for [drug-trajectory-analysis](../drug-trajectory-analysis/SKILL.md).

## Instructions

### 1. Prepare inputs

Required from [drug-complex-system-builder](../drug-complex-system-builder/SKILL.md):
- `system.xml`: serialized OpenMM System
- `complex_solvated.pdb`: solvated complex PDB (used as topology reference)

### 2. Run the simulation

```bash
# Env: drugmd-agent
python .agents/skills/drug-protein-ligand-md/scripts/run_md.py \
  --system_xml md/system/system.xml \
  --input_pdb md/system/complex_solvated.pdb \
  --temperature 300 \
  --pressure 1.0 \
  --timestep 4.0 \
  --minimize_steps 5000 \
  --equil_nvt_steps 25000 \
  --equil_npt_steps 50000 \
  --production_steps 2500000 \
  --restraint_k 50.0 \
  --reporting_interval 5000 \
  --checkpoint_interval 25000 \
  --output_dir md/run/
```

Key parameters:
- `--temperature`: simulation temperature in Kelvin (default: 300).
- `--pressure`: target pressure in atm (default: 1.0).
- `--timestep`: integration timestep in fs (default: 4.0). 4 fs is safe with hydrogen mass repartitioning (HMR) from the system builder; use 2 fs without HMR.
- `--minimize_steps`: max minimization steps (default: 5000). Set to 0 to skip.
- `--equil_nvt_steps`: NVT equilibration steps with restraints on protein/ligand heavy atoms (default: 25000 = 100 ps at 4 fs).
- `--equil_npt_steps`: NPT equilibration steps with restraints released (default: 50000 = 200 ps).
- `--production_steps`: production NPT steps (default: 2500000 = 10 ns at 4 fs).
- `--restraint_k`: restraint force constant for equilibration in kJ/mol/nm^2 (default: 50.0).
- `--reporting_interval`: write trajectory frame every N steps (default: 5000 = 20 ps).
- `--checkpoint_interval`: write checkpoint every N steps (default: 25000).

### 3. Output files

The script produces:
- `md/run/minimized.pdb`: structure after energy minimization
- `md/run/nvt_equilibration.log`: energy/temperature log during NVT equilibration
- `md/run/npt_equilibration.log`: energy/temperature/density log during NPT equilibration
- `md/run/production.dcd`: production trajectory (DCD format)
- `md/run/production.log`: production energy/temperature/density log
- `md/run/final_state.xml`: serialized simulation state for restarts
- `md/run/md_provenance.json`: all simulation parameters and timing

### 4. Running replicates

For statistical confidence, run multiple independent replicates with different random seeds:

```bash
# Env: drugmd-agent
for i in 1 2 3; do
  python .agents/skills/drug-protein-ligand-md/scripts/run_md.py \
    --system_xml md/system/system.xml \
    --input_pdb md/system/complex_solvated.pdb \
    --production_steps 2500000 \
    --seed $((42 + i)) \
    --output_dir md/rep_${i}/
done
```

### 5. Quick validation checks

After the run, verify:
- Temperature fluctuates around the target (check production.log)
- Density is stable around 1.0 g/cm^3 for aqueous systems
- Total energy does not drift monotonically
- The ligand remains in the binding pocket (use [drug-trajectory-analysis](../drug-trajectory-analysis/SKILL.md))

## Examples

### Example: 10 ns production MD of TYK2 complex

```bash
# Env: drugmd-agent
python .agents/skills/drug-protein-ligand-md/scripts/run_md.py \
  --system_xml tyk2/md/system/system.xml \
  --input_pdb tyk2/md/system/complex_solvated.pdb \
  --temperature 300 \
  --timestep 4.0 \
  --production_steps 2500000 \
  --output_dir tyk2/md/run/
```

### Example: short 1 ns refinement for pose assessment

```bash
# Env: drugmd-agent
python .agents/skills/drug-protein-ligand-md/scripts/run_md.py \
  --system_xml md/system/system.xml \
  --input_pdb md/system/complex_solvated.pdb \
  --production_steps 250000 \
  --reporting_interval 2500 \
  --output_dir md/short_refine/
```

## Constraints

- **Environment**: Requires `drugmd-agent`.
- **GPU acceleration**: The script auto-detects CUDA GPUs. Without a GPU, simulations will run on CPU (significantly slower; consider reducing production_steps for testing).
- **Timestep**: 4 fs requires hydrogen mass repartitioning (HMR) in the system. The [drug-complex-system-builder](../drug-complex-system-builder/SKILL.md) applies HMR by default. If using a system without HMR, set `--timestep 2.0`.
- **Trajectory size**: DCD files grow ~1 MB per 1000 frames for a typical 50k-atom system. A 10 ns run at 20 ps intervals produces ~500 frames (~500 MB).
- **Restarts**: use `--restart_from` with a saved state XML to continue a simulation.

## References

- Eastman, P.; Galvelis, R.; Pelaez, R. P.; et al. OpenMM 8: Molecular Dynamics Simulation with Machine Learning Potentials. *J. Phys. Chem. B* **2024**, *128*(1), 109-116. https://doi.org/10.1021/acs.jpcb.3c06662
- Hopkins, C. W.; Le Grand, S.; Walker, R. C.; Roitberg, A. E. Long-Time-Step Molecular Dynamics through Hydrogen Mass Repartitioning. *J. Chem. Theory Comput.* **2015**, *11*, 1864-1874. https://doi.org/10.1021/ct5010406

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
