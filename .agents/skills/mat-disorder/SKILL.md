---
name: mat-disorder
description: Generate ordered structures from disordered starting points with partial occupancies.
category: [materials]
---

# Disordered Material

## Goal
To generate clean, ordered atomic configurations from disordered starting structures (e.g., experimental structures with fractional occupancies). These ordered candidates can be used for ground-state property calculations, phase stability analysis, or as starting points for MLIP training.

## Instructions

1.  **Identify Disordered Structures**: Ensure your input structure (typically a CIF file) contains fractional occupancies or partial site occupancies.
2.  **Generate Ordered Candidates**: Use the ranking and sampling strategy based on Ewald energy to pick configurations that satisfy stoichiometry while minimizing electrostatic repulsion.

    ```bash
    # Env: base-agent
    python .agents/skills/mat-disorder/scripts/run_ordering.py disordered.cif \
        --n_structures 50 --target_atoms 50 --output_dir ordered_results
    ```

### Strategy: Ewald Energy Ranking
The script uses `pymatgen`'s `OrderDisorderedStructureTransformation` with a fast Ewald-based solver (`ALGO_FAST`). It generates a large pool of candidates, ranks them by Ewald energy, and samples across the spectrum to ensure both low-energy (ground-state-like) and higher-energy (excited-state-like) configurations are captured.

### Supercell Expansion
For structures with very few atoms per cell or complex stoichiometry, the script automatically searches for a supercell expansion that:
1.  Is close to the `--target_atoms` (default: 50).
2.  Maintains valid stoichiometry (total counts must be integers).
3.  Is as cubic as possible to avoid long, thin cells.

- **Limit**: Avoid setting `--target_atoms` too high (>120) if you plan to follow up with DFT calculations.

## Standalone Usage (Python API)

```python
from .agents.skills.mat_disorder.scripts.order_disorder_sampler import OrderDisorderSampler
from ase.io import read

atoms = read("disordered.cif")
sampler = OrderDisorderSampler(
    atoms=atoms,
    n_structures=20,
    target_atoms=60,
    include_perturbation=1
)
ordered_structures = sampler.sample()
```

## Iterative Cluster Expansion Training

For more accurate Cluster Expansions, use the iterative training workflow which cycles between structure generation, relaxation, model fitting, and Monte Carlo sampling to fully explore the configuration space.

> [!TIP]
> **Train your CE model first**: Please refer to the [ml-cluster-expansion](../ml-cluster-expansion/SKILL.md) skill to train a robust Cluster Expansion model. This skill focuses on using that trained model for simulations.

```bash
# Env: smol-agent
python .agents/skills/mat-disorder/scripts/iterative_ce_training.py \
    primordial.cif \
    --iterations 5 \
    --n_samples 20 \
    --mlip_model mace \
    --output_dir ce_results
```

### Workflow
1.  **Initial Sampling**: Generates random ordered structures from the primordial structure.
2.  **Relaxation**: Relaxes structures using an MLIP (MACE or CHGNet) to get accurate energies.
3.  **Mapping Check**: Verifies if relaxed structures still map to the initial lattice configuration.
4.  **Training**: Fits a Cluster Expansion model to the valid training data.
5.  **Active Learning**: Runs Monte Carlo simulations with the current model to find new low-energy configurations.
6.  **Coverage Check**: Identifies if MC-sampled structures are "new" (uncovered by training set) and adds them to the next iteration loop.

## Constraints
- **Environment**: 
    - `base-agent` for basic sampling.
    - `smol-agent` for iterative training and smol-based analysis.
- **Fractional Occupancies**: The input must be a format that carries occupancy information (like CIF with `_atom_site_occupancy`).
- **Algorithm**: Uses `ALGO_FAST` for efficiency; while fast, it may not find the global Ewald minimum for extremely large cells.
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
