---
name: neb-barrier
description: Calculate activation barrier using Nudged Elastic Band (NEB) method with MLIPs.
---

# NEB Barrier Calculation

This skill provides tools to calculate the activation energy barrier for atomic migration (e.g., diffusion) using the Nudged Elastic Band (NEB) method with various Machine Learning Interatomic Potentials (MLIPs).

## Tools

### 1. `calculate_barrier.py`

Performs the NEB calculation between two endpoint structures.

**Usage:**

### Use with MACE
```bash
# Env: mace-agent
python .agent/skills/neb-barrier/scripts/calculate_barrier.py \
    --start_structure <path_to_start.cif> \
    --end_structure <path_to_end.cif> \
    --model_type mace \
    --n_images 5 \
    --fmax 0.05 \
    --output_dir <output_directory>
```

### Use with FairChem
```bash
# Env: fairchem-agent
python .agent/skills/neb-barrier/scripts/calculate_barrier.py \
    --start_structure <path_to_start.cif> \
    --end_structure <path_to_end.cif> \
    --model_type fairchem \
    --n_images 5 \
    --fmax 0.05 \
    --output_dir <output_directory>
```

### Use with MatGL
```bash
# Env: matgl-agent
python .agent/skills/neb-barrier/scripts/calculate_barrier.py \
    --start_structure <path_to_start.cif> \
    --end_structure <path_to_end.cif> \
    --model_type matgl \
    --n_images 5 \
    --fmax 0.05 \
    --output_dir <output_directory>
```

**Arguments:**
- `--start_structure`: Path to the initial stable structure (CIF/POSCAR).
- `--end_structure`: Path to the final stable structure (CIF/POSCAR).
- `--model_type`: Type of MLIP to use (`mace`, `fairchem`, `matgl`).
- `--model_name`: Specific model name/path (optional, uses default if not specified).
- `--n_images`: Number of intermediate images (default: 7).
- `--fmax`: Force convergence criterion in eV/Å (default: 0.02).
- `--interpolation`: Method for initial path generation. Options: `linear`, `idpp` (default). **Recommended** to use `idpp` for dense systems.
- `--climb`: Use Climbing Image NEB (CI-NEB) (default: True).
- `--output_dir`: Directory to save results and plots.

**Outputs:**
- `neb_trajectory.traj`: ASE trajectory of the optimized path.
- `neb_barrier_plot.png`: Plot of energy vs reaction coordinate.
- `neb_results.json`: JSON file containing barrier energy and forces.

## Model Recommendations

For accurate barrier calculations, the choice of foundation potential is critical.

- **Recommended**:
    - **OMAT**: 
        - `MACE-OMAT-0-small`
        - `MACE-MH-1` (head: `omat_pbe`)
        - `uma-s-1p1` (head: `omat`)
    - **MatPES**: 
        - `MACE-MATPES-r2SCAN-0`
        - `MACE-MH-1` (head: `matpes_r2scan`)
        - `CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES`
        - `TensorNet-MatPES-r2SCAN-v2025.1-PES`
    - These models are trained on datasets including transition states or diverse structures (OMat24, MatPES), making them more reliable for NEB.

- **Discouraged**:
    - **MPtrj** trained models (e.g., `M3GNet-MP-2021`, `CHGNet-MPtrj-2023.12.1-2.7M-PES`)
    - These are primarily trained on ground-state or near-equilibrium structures and may underestimate barriers or fail to converge for high-energy transition states.

## Prerequisites

- Ensure the appropriate environment is active for the chosen model type (see `mcp_config.json`).
- **CRITICAL**: The start and end structures **MUST** be pre-relaxed using the *same* MLIP model used for the NEB calculation.
    - Use `relax_cell=False` (fixed volume) to ensure consistency between endpoints.
    - Use `fmax=0.02` eV/Å for tight convergence.
    - You can use the `relax_structure` tool from the corresponding MCP server for this.

## Examples

See `examples/` directory for sample inputs and outputs.


Author: Bowen Deng
Contact: github username <bowen-bd>
