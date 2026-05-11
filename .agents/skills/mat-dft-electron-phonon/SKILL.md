---
name: mat-dft-electron-phonon
description: Computes electron-phonon coupling to calculate temperature-dependent bandgap renormalization using atomate2.
category: materials
---

# mat-dft-electron-phonon

## Goal
To determine the impact of electron-phonon coupling on the electronic eigenstates of a solid. At $T=0$ K, quantum fluctuations (zero-point motion) slightly perturb the geometric symmetry of a perfectly static lattice, causing a contraction known as zero-point renormalization (ZPR). As temperature increases, higher phonon modes dictate further eigenenergy shifts.

## Background
Standard DFT predicts bandgaps under the Born-Oppenheimer limit (fixed infinite massive ions). Computing true temperature-dependent optical properties (photoluminescence shifting, exciton broadening) mandates adding back the phonon response. The `ElectronPhononMaker` calculates phonon modes first (via `phonopy`), generates properly thermalized stochastic structural snapshots respecting the true classical/quantum Bose-Einstein occupancies, and computes the static gap for each snapshot.

## Instructions

### 1. Construct the Electron-Phonon Workflow
Generating the inputs uses the `ElectronPhononMaker`. You only need to provide the target primitive structure and the temperature list you want dynamically sampled.

```bash
# Env: atomate2-agent
python .agents/skills/mat-dft-electron-phonon/scripts/generate_inputs.py --output elph_flow.json
```

### 2. Job Execution
The default script serializes the Directed Acyclic Graph (DAG) logic. Because calculating robust phonon displacements involves constructing potentially hundreds of large supercell single-point DFT calculations, ensure you map this to an established HPC worker infrastructure (`jobflow` or Fireworks) rather than executing interactively locally.

### 3. Parse Output
The termination node evaluates the mean and variance of the bandgap/band edges from all stochastically distributed geometric snapshots at a given temperature, returning the renormalized gap.

## Examples

Run the DAG generation for pristine primitive Silicon.

```bash
# Env: atomate2-agent
cd .agents/skills/mat-dft-electron-phonon/examples/silicon
python ../../scripts/generate_inputs.py --output si_flow.json
```

## Constraints
- **Environments**: Scripts require the `atomate2-agent` environment containing `phonopy`.
- **Phase Stability**: The material must be strictly stable. If imaginary modes exist in the phonon branch, thermal displacement mapping will fail catastrophically since occupations of negative frequencies diverge.
- **Supercells**: Accuracy is critically bound to taking a large enough supercell (`supercell_matrix`) to capture long-wavelength phonons correctly.

## References
- Zacharias, M., & Giustino, F. "One-shot calculation of temperature-dependent optical spectra and phonon-induced band-gap renormalization", *Phys. Rev. B*, 94, 075125 (2016). [DOI](https://doi.org/10.1103/PhysRevB.94.075125)

---

**Author:** Bowen Deng  
**Contact:** [GitHub](https://github.com/bowen-bd)
