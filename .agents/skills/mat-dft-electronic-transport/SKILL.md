---
name: mat-dft-electronic-transport
description: Compute electronic transport properties (mobility, conductivity, Seebeck coefficient) using DFT and AMSET via atomate2.
category: materials
---

# mat-dft-electronic-transport

## Goal
To determine high-fidelity electronic transport properties (e.g., carrier mobility $\mu$, Seebeck coefficient $S$, and electrical conductivity $\sigma$) across various doping concentrations and temperatures using the AMSET (Ab initio Scattering and Transport) package integrated directly into an `atomate2` VASP computational flow.

## Background
Machine Learning Interatomic Potentials (MLIPs) only predict energies, forces, and stresses; they lack proper electronic wavefunction representations. True electronic transport capabilities require coupling dense Density Functional Theory (DFT) band structures with detailed scattering matrix calculations (acoustic deformation potential scattering, polar optical phonon scattering, etc.). This skill leverages `VaspAmsetMaker` to seamlessly chain these calculations natively.

## Instructions

### 1. Construct the AMSET Workflow
Use the provided script to generate the sequence (DAG) of VASP computations targeting electronic transport. This automated DAG coordinates structure relaxation, uniform band structure extraction, evaluation of the elastic tensor, and calculations of deformation potentials.

```bash
# Env: atomate2-agent
python .agents/skills/mat-dft-electronic-transport/scripts/generate_inputs.py --output amset_flow.json
```

### 2. Job Execution (via jobflow/Fireworks)
Because this workflow contains numerous sequential and parallel VASP evaluations (e.g., generating strained supercells for deformation potentials), it should be passed to your job management framework rather than run individually. The default script simply serializes the theoretical DAG to JSON.

If operating on a compute-capable node with `vasp_std` available, it can be tested locally using:
```python
import jobflow
# Assuming `flow` is the defined VaspAmsetMaker output
jobflow.run_locally(flow, create_folders=True)
```

### 3. Extract Transport Results
Once completed, the final node wraps the `AMSET` runner. Resulting transport parameters (Mobility, Conductivity) will be dumped into a structured `.json` and `amset.log` inside the final Job's folder. Parse these properties natively using standard `amset.plot` utilities.

## Examples

Run the example demonstrating the DAG generation for GaAs transport calculations.

```bash
# Env: atomate2-agent
cd .agents/skills/mat-dft-electronic-transport/examples/GaAs
python ../../scripts/generate_inputs.py --output gaas_flow.json
```

## Constraints
- **Computational Cost**: Extremely high. The dense uniform band structure and multiple deformations require significant CPU hours per material.
- **Environments**: Scripts require `atomate2-agent` with both `atomate2` and `amset` installed.
- **K-Point Convergence**: Default parameters assume qualitative screening; strict literature matching requires extremely dense k-meshes (e.g., `40x40x40`).

## References
- Ganose, A. M., et al., "Efficient calculation of carrier scattering rates from first principles", *Nature Communications*, 12, 2222 (2021). [DOI](https://doi.org/10.1038/s41467-021-22440-5)

---

**Author:** Bowen Deng  
**Contact:** [GitHub](https://github.com/bowen-bd)
