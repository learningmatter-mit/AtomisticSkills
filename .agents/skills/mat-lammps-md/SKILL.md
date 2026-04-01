---
name: mat-lammps-md
description: Build and run LAMMPS molecular dynamics with isolated MLIP-specific binaries (MACE, MatGL/CHGNet, FairChem) to avoid Python and Torch stack conflicts.
category: [materials]
---

# LAMMPS Molecular Dynamics with MLIPs

## Goal
Run GPU-accelerated LAMMPS molecular dynamics with MLIP backends using three isolated binaries (MACE, MatGL/CHGNet, FairChem) so Python embedding through `ML-IAP`/`mliappy` remains stable and reproducible.

## Instructions

1. **Select the MLIP backend and model family first** using the foundation-potential guide:
   - [ml-foundation-potentials](../ml-foundation-potentials/SKILL.md)
   - This determines which conda env and which LAMMPS binary you must use.

2. **Check system prerequisites**.
```bash
# Env: base-agent
nvidia-smi
nvcc --version
g++ --version
cmake --version
mpicxx --version
```

3. **Identify GPU compute capability and set Kokkos arch flag**.
```bash
# Env: base-agent
nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader
```
- Example mapping:
  - `8.0` -> `Kokkos_ARCH_AMPERE80`
  - `8.6` -> `Kokkos_ARCH_AMPERE86`
  - `8.9` -> `Kokkos_ARCH_ADA89`
  - `9.0` -> `Kokkos_ARCH_HOPPER90`

4. **Build the environment-matched LAMMPS binary** (choose one of the three paths below).

   **Path A: MACE**
```bash
# Env: base-agent
bash conda-envs/mace-agent/install.sh
KOKKOS_ARCH_FLAG=Kokkos_ARCH_AMPERE86 \
LAMMPS_REF="stable_2Aug2023_update2" \
bash conda-envs/mace-agent/install_lammps.sh
```
   - Binary: `./lammps/mace-agent/lmp`
   - Runtime env: `mace-agent`

   **Path B: MatGL/CHGNet**
```bash
# Env: base-agent
bash conda-envs/matgl-agent/install.sh
KOKKOS_ARCH_FLAG=Kokkos_ARCH_AMPERE86 \
LAMMPS_REF="stable_2Aug2023_update2" \
bash conda-envs/matgl-agent/install_lammps.sh
```
   - Binary: `./lammps/matgl-agent/lmp`
   - Runtime env: `matgl-agent`

   **Path C: FairChem**
```bash
# Env: base-agent
bash conda-envs/fairchem-agent/install.sh
KOKKOS_ARCH_FLAG=Kokkos_ARCH_AMPERE86 \
LAMMPS_REF="stable_2Aug2023_update2" \
bash conda-envs/fairchem-agent/install_lammps.sh
```
   - Binary: `./lammps/fairchem-agent/lmp`
   - Runtime env: `fairchem-agent`

5. **Run the selected binary with its matching conda environment**.
```bash
# Env: mace-agent (example; switch env/binary pair as needed)
conda activate mace-agent
./lammps/mace-agent/lmp -h
```

6. **Launch MD with the same binary-env pair used during build**; do not cross-run binaries between MLIP stacks.

## Examples

See [scripts/three-backends-build-check/README.md](scripts/three-backends-build-check/README.md) for a minimal build/verification matrix across MACE, MatGL, and FairChem.
See the respective README.md files under [examples/mace/](examples/mace/), [examples/matgl/](examples/matgl/), and [examples/fairchem/](examples/fairchem/) for model-specific run scripts.

## Constraints
- **Strict binary-env pairing**: each LAMMPS binary must run only with its own conda env.
- **No stack mixing**: never run MACE binary in `matgl-agent`/`fairchem-agent`, etc.
- **GPU arch alignment**: choose `KOKKOS_ARCH_*` from actual `compute_cap` output.
- **Python-coupled mode**: this workflow targets `ML-IAP`/`mliappy` usage.

## References
- Thompson et al., "LAMMPS - A flexible simulation tool for particle-based materials modeling at the atomic, meso, and continuum scales", *Computer Physics Communications*, 2022. [DOI](https://doi.org/10.1016/j.cpc.2021.108171)
- LAMMPS Manual, ML-IAP package documentation. [Link](https://docs.lammps.org/Packages_details.html#pkg-ml-iap)
- Batatia et al., "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields". [arXiv](https://arxiv.org/abs/2206.07697)
- Deng et al., "CHGNet as a pretrained universal neural network potential for charge-informed atomistic modelling". [arXiv](https://arxiv.org/abs/2302.14231)
- FairChem documentation and model zoo. [Link](https://fair-chem.github.io/)

---

**Author:** Jurģis Ruža  
**Contact:** [GitHub @JurgisR](https://github.com/JurgisR)
