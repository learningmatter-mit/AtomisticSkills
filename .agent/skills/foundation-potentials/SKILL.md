---
name: foundation-potentials
description: Guide for selecting the most appropriate foundation MLIP model based on simulation requirements.
---

# Foundation Potentials Selection

## Goal
Select the appropriate machine learning interatomic potential (MLIP) for a given atomistic simulation task, balancing accuracy, computational cost, and material composition.

## Model Selection Guide

> [!NOTE]
> This list is not exhaustive. For a full list of available pre-trained checkpoints, refer to the `load_model` function documentation for each respective MCP server.

### MatGL Models
**Environment:** `matgl-agent`

- **CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES**:
  - Use for r2SCAN-level inorganic materials simulation.
  - Recommended when charge information and magnetic moments are involved (e.g., calculating transition metal valence states).
- **CHGNet-MPtrj-2023.12.1-2.7M-PES**:
  - Use for compatibility with standard Materials Project (GGA/GGA+U) data.
  - Recommended when working with legacy MP data.
- **TensorNet-MatPES-r2SCAN-v2025.1-PES**:
  - Use for r2SCAN-level inorganic materials simulation.
  - Smaller and faster than CHGNet, suitable for dynamic simulations (MD, NEB, phonons).

### FAIRCHEM Models
**Environment:** `fairchem-agent`

- **uma-s-1p1**:
  - Use for organic and inorganic simulations.
  - **Note:** UMA models are typically slower and more expensive. Avoid for dynamic simulations with systems >500 atoms.
- **uma-m-1p1**:
  - Use for organic and inorganic simulations with <100 atoms.
- **esen-md-direct-all-omol**:
  - Use for organic ionic relaxation (ground state calculations).

### MACE Models
**Environment:** `mace-agent`

- **MACE-MH-1**:
  - Latest multi-head foundation model. Use as default for most tasks.
  - `omat_pbe` head (default): General materials, balanced performance.
  - `matpes_r2scan` head: High-accuracy materials simulation.
  - `omol` head: Molecular systems, organic chemistry, organometallics.
  - `spice_wB97M` head: Molecular systems and organic chemistry.
  - `oc20_usemppbe` head: Surface catalysis, adsorbates.
- **MACE-MATPES-r2SCAN-0**:
  - Specialized for r2SCAN-level inorganic systems.
- **MACE-OMAT-0-small**:
  - Small, efficient model for materials.

## Selection Criteria

Prioritize criteria in the following order:

### 1. User Explicit Request
If the user explicitly mentions a model name or framework (e.g., "MACE model", "fine-tuned MACE", "CHGNet", "UMA"), use that model/framework.
- Detect frameworks from keywords like: "MACE", "CHGNet", "TensorNet", "UMA", "ESEN", "FAIRCHEM", "MatGL".

### 2. Calculation Expense
If the simulation involves dynamic or expensive calculations (Molecular Dynamics, NEB, Phonons, Diffusion, Melting Temperature):
- **Prioritize smaller/cheaper models:** structure
  - `TensorNet-MatPES-r2SCAN-v2025.1-PES`
  - `MACE-MATPES-r2SCAN-0` (or MACE small variants)
- **Avoid UMA models** for dynamic simulations due to higher cost, unless the system is very small.

### 3. System Composition
Consider the chemical elements present in the system:
- **Organic (C, H, N, O, P, S)**:
  - Use **UMA models** or **MACE-MH-1** with `omol` head.
- **Inorganic**:
  - Use **MatGL**, **MACE models**, or **UMA** with `omat` head.
- **For Phase Diagrams & Thermodynamic Stability**:
  - It is highly recommended to use **MatPES-r2SCAN** trained checkpoints (e.g., `CHGNet-MatPES-r2SCAN`, `MACE-MATPES-r2SCAN`). These offer superior energy accuracy for phase stability and bypass messy energy compatibility corrections in GGA (see [mp2020-compatibility](../mp2020-compatibility/SKILL.md)).

### 4. Default
For general materials where no specific constraints apply:
- Use **MACE-MH-1** with `omat_pbe` head.

## Performance Benchmark

For detailed inference speed and memory usage of various MLIPs, refer to the dedicated **[mlip-speed](../mlip-speed/SKILL.md)** skill. This skill provides automatic benchmarks to help you choose the most efficient model for your simulation scale.
