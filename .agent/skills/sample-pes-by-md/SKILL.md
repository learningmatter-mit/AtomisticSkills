---
name: sample-pes-by-md
description: Sample off-equilibrium potential energy surface (PES), used for benchmarking and fine-tuning MLIPs.
---

# Sample PES by MD

## Goal
To generate diverse and representative atomic configurations from a starting structure to augment training data for Machine Learning Interatomic Potentials (MLIPs). This is achieved through MD-based sampling with crystal feature clustering (for off-equilibrium states) or Ewald-sum based ordering (for disordered structures).

## Instructions

1.  **Prepare a Foundation Potential**: Select an appropriate MLIP model for sampling.
    - **Recommended**: `M3GNet-MP-2021.2.8-PES` (MatGL) or `MACE-MP-small` (MACE) for general inorganic materials.
2.  **Off-Equilibrium Sampling (MD-Clustering)**:
    - Use the unified sampling script to run a short MD trajectory and pick representative configurations via K-Means clustering of latent features.
    
    Using MatGL (CHGNet):
    ```bash
    # Env: matgl-agent
    python .agent/skills/sample-pes-by-md/scripts/run_sampling.py input.cif \
        --model_type matgl --model_name CHGNet-MatPES-PBE-2025.2.10-2.7M-PES \
        --total_steps 2000 --temperature 1000 --n_clusters 10 --output_dir sampling_results
    ```

    Using MACE:
    ```bash
    # Env: mace-agent
    python .agent/skills/sample-pes-by-md/scripts/run_sampling.py input.cif \
        --model_type mace --model_name MACE-OMAT-0-small \
        --total_steps 2000 --temperature 1000 --n_clusters 10 --output_dir sampling_results
    ```

### Supercell Expansion
The script automatically expands small cells (e.g., primitive cells) to supercells containing ~50 atoms (close-to-cubic) before simulation. This ensures adequate system size and local environment diversity.

- **Customize**: Set `--target_atoms` in the script call (recommended: **40-70 atoms** for VASP efficiency).
- **Limit**: Maximum atoms capped at **120** to prevent OOM in subsequent DFT calculations.

## Standalone Usage (Python API)
For integration into other Python workflows, use the `OffEquilibriumSampler` class directly.

```python
from .agent.skills.sample_pes_by_md.scripts.sampler import OffEquilibriumSampler
from .agent.skills.sample_pes_by_md.scripts.feature_calculators import MatGLCrystalFeatureCalculator
from matgl import load_model

# Setup calculator
model = load_model("M3GNet-MP-2021.2.8-PES")
calc = MatGLCrystalFeatureCalculator(potential=model)

# Initialize and run sampler
sampler = OffEquilibriumSampler(
    calculator=calc, 
    atoms=initial_atoms,
    total_steps=1000,
    temperature=800,
    n_clusters=20
)
structures, metadata = sampler.sample()
```

## Examples

### High-Temperature Sampling of LiMnO2 (MatGL-CHGNet)
Sampling 10 representative configurations from a 10 ps MD trajectory of LiMnO2 at 2000K.
- **Script**: [sample_limno2_matgl.py](examples/LiMnO2/sample_limno2_matgl.py)
- **Results saved in**: `LiMnO2_matgl_results/`

## Constraints
- **Environments**:
    - **Off-Equilibrium (MatGL)**: Requires `matgl-agent` conda environment.
    - **Off-Equilibrium (MACE)**: Requires `mace-agent` conda environment.
- **Time Step**: Automatically set to **5.0 fs** for stability, or **2.0 fs** if Hydrogen is detected.
- **Clustering**: Requires `scikit-learn` in the environment.
