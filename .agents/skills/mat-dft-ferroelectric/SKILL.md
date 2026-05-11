---
name: mat-dft-ferroelectric
description: Calculate the spontaneous ferroelectric polarization across a non-polar to polar structure transition using the Berry Phase method.
category: materials
---

# mat-dft-ferroelectric

## Goal
To calculate the spontaneous polarization ($P_s$) of a ferroelectric material. Because bulk polarization is a multi-valued quantum quantity (only differences in polarization are well-defined), this skill evaluates the continuous evolution of the Berry phase starting from a high-symmetry (centrosymmetric, non-polar) reference state and progressing via linear interpolation to the low-symmetry (polar) state.

## Background
Material spontaneous polarization arises when positive and negative charge centers separate, breaking inversion symmetry. By linearly mixing the atomic positions between a cubic (non-polar) and tetragonal (polar) phase, we calculate the Berry phase for electrons across the geometric path. `FerroelectricMaker` automates the generation of these intermediate supercells, runs VASP with `LCALCPOL=True`, and stitches the branches together to avoid quantum jump discontinuities.

## Instructions

### 1. Construct the Ferroelectric Workflow
Use the provided script to generate the sequence of calculation jobs evaluating the polarization across interpolated intermediate structures.

```bash
# Env: atomate2-agent
python .agents/skills/mat-dft-ferroelectric/scripts/generate_inputs.py --output ferroelectric_flow.json
```

### 2. Job Execution
The default script simply serializes the theoretical Directed Acyclic Graph (DAG) for structural reference. Run it locally via `jobflow.run_locally(flow)` if VASP is available, or dispatch it to Fireworks.

### 3. Parse Polarization
The final job merges the electronic polarization and ionic dipoles for each intermediate image, tracing the quantum branches. Extract the total `polarization` (in $\mu\text{C}/\text{cm}^2$) from the terminal task document.

## Examples

Run the example demonstrating the DAG generation for Barium Titanate (BaTiO$_3$).

```bash
# Env: atomate2-agent
cd .agents/skills/mat-dft-ferroelectric/examples/BaTiO3
python ../../scripts/generate_inputs.py --output batio3_flow.json
```

## Constraints
- **Environments**: Scripts require the `atomate2-agent` environment.
- **Reference State Requirement**: The user *must* provide both a chemically identical polar and non-polar (reference) structure.
- **Continuous Mapping**: The atoms in the polar structure must map one-to-one to the non-polar structure without crossing periodic boundaries incorrectly. Large arbitrary translations will break the Berry phase continuity assumption.

## References
- King-Smith, R. D., & Vanderbilt, D. "Theory of polarization of crystalline solids", *Phys. Rev. B*, 47, 1651 (1993). [DOI](https://doi.org/10.1103/PhysRevB.47.1651)

---

**Author:** Bowen Deng  
**Contact:** [GitHub](https://github.com/bowen-bd)
