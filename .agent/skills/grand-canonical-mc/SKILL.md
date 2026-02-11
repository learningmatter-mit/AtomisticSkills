---
name: grand-canonical-mc
description: Run Grand Canonical Monte Carlo (GCMC) simulations with cluster expansion models to map composition-temperature phase diagrams via chemical potential sweeps.
---

# Grand Canonical Monte Carlo

## Goal

To perform Grand Canonical Monte Carlo (GCMC) simulations using cluster expansion models to study composition-dependent thermodynamics and generate temperature-composition (T-x) phase diagrams. GCMC allows the system composition to vary by controlling the chemical potential ($\mu$) instead of fixing composition directly.

## Background

In the **canonical ensemble** (fixed N, V, T), Monte Carlo simulations explore configurational space at a fixed composition. In contrast, the **grand canonical** (or **semigrand canonical**) ensemble allows composition to fluctuate in response to specified chemical potentials. This is particularly useful for:

- Mapping phase diagrams (composition vs. temperature)
- Identifying miscibility gaps and phase transitions
- Studying composition-dependent thermodynamics
- Exploring equilibrium compositions at different chemical potentials

For binary alloys (e.g., Cu-Ag), we typically control the **chemical potential difference** Δμ = μ_A - μ_B by setting one species to μ = 0 and varying the other.

## Workflow

### Step 1: Load a Trained Cluster Expansion

Start with a trained cluster expansion model. You can train one using the [cluster-expansion](../cluster-expansion/SKILL.md) skill or use an existing model.

```python
# Load the cluster expansion
from smol.cofe import ClusterExpansion

ce = ClusterExpansion.load("path/to/cluster_expansion.json")
print(f"Loaded CE with {len(ce.cluster_subspace)} clusters")
```

### Step 2: Run Chemical Potential Sweep

Use the `run_gcmc_sweep.py` script to perform systematic sweeps of chemical potential at different temperatures.

```bash
# Env: smol-agent
python .agent/skills/grand-canonical-mc/scripts/run_gcmc_sweep.py \
    --ce_file cluster_expansion.json \
    --supercell 3 3 3 \
    --temperatures 400 600 800 1000 \
    --mu_min -0.4 \
    --mu_max 0.4 \
    --num_mu_points 20 \
    --steps 50000 \
    --equilibration_steps 10000 \
    --element Ag \
    --output_dir gcmc_results/
```

**Key Parameters:**
- `--ce_file`: Path to the trained cluster expansion JSON file
- `--supercell`: Supercell size (e.g., `3 3 3` for a 3×3×3 supercell)
- `--temperatures`: List of temperatures (K) to simulate
- `--mu_min`, `--mu_max`: Chemical potential range (eV)
- `--num_mu_points`: Number of chemical potential points to sample
- `--steps`: Number of MC steps per simulation
- `--equilibration_steps`: Initial burn-in steps (discarded)
- `--element`: Species to control (the other is set to μ=0)
- `--output_dir`: Directory to save results

**Output:**
- `gcmc_results/results_summary.json`: Composition and energy data
- `gcmc_results/T{temp}_mu{mu:.3f}.h5`: Trajectory files (HDF5)
- `gcmc_results/T{temp}_mu{mu:.3f}_final.cif`: Final structures

### Step 3: Analyze Results and Generate Phase Diagrams

Use the analysis script to visualize the results and create phase diagrams.

```bash
# Env: smol-agent
python .agent/skills/grand-canonical-mc/scripts/analyze_gcmc_results.py \
    --results_file gcmc_results/results_summary.json \
    --output_dir gcmc_results/ \
    --element Ag
```

**Output:**
- `mu_vs_composition.png`: Chemical potential vs. composition at each temperature
- `phase_diagram.png`: Temperature-composition (T-x) phase diagram
- `energy_vs_mu.png`: Energy per atom vs. chemical potential

## Examples

### Cu-Ag Alloy Phase Diagram

Using the pre-trained Cu-Ag cluster expansion:

```bash
# Env: smol-agent
python .agent/skills/grand-canonical-mc/scripts/run_gcmc_sweep.py \
    --ce_file .agent/skills/cluster-expansion/examples/CuAg_CE/cluster_expansion.json \
    --supercell 4 4 4 \
    --temperatures 300 400 500 600 700 800 900 1000 \
    --mu_min -0.3 \
    --mu_max 0.3 \
    --num_mu_points 15 \
    --steps 30000 \
    --equilibration_steps 5000 \
    --element Ag \
    --output_dir .agent/skills/grand-canonical-mc/examples/CuAg/gcmc_results/
```

Then analyze:

```bash
# Env: smol-agent
python .agent/skills/grand-canonical-mc/scripts/analyze_gcmc_results.py \
    --results_file .agent/skills/grand-canonical-mc/examples/CuAg/gcmc_results/results_summary.json \
    --output_dir .agent/skills/grand-canonical-mc/examples/CuAg/ \
    --element Ag
```

## Constraints

- **Equilibration**: Always include sufficient equilibration steps (typically 10-20% of total steps) to allow the system to reach equilibrium before collecting statistics.
- **Convergence**: Monitor composition vs. MC step to ensure equilibration. If composition is still drifting, increase equilibration steps.
- **System Size**: Larger supercells reduce finite-size effects but increase computational cost. For phase diagram mapping, 3×3×3 to 5×5×5 is typically sufficient.
- **Temperature Range**: Choose temperatures relevant to your system. For alloys, consider the experimental phase diagram temperature range.
- **Chemical Potential Range**: The range should span the full composition space (0 to 1 mole fraction). Start with ±0.5 eV and adjust based on results.
- **Environment**: Scripts require the `smol-agent` conda environment with smol, pymatgen, matplotlib, and numpy.
- **Cluster Expansion Quality**: Ensure your CE has low RMSE (<10 meV/atom) for accurate phase diagram predictions.

## Theory Notes

### Semigrand Canonical Ensemble

In the semigrand canonical ensemble for a binary alloy A-B:
- Temperature T is fixed
- Volume V is fixed
- Total number of sites N is fixed
- Chemical potential difference Δμ = μ_A - μ_B is controlled

The probability of a configuration depends on:
$$P(\sigma) \propto \exp\left[-\frac{E(\sigma) - \Delta\mu \cdot N_A}{k_B T}\right]$$

where $N_A$ is the number of A atoms in configuration $\sigma$.

### Composition-Chemical Potential Relationship

At equilibrium, the composition $x_A$ (mole fraction of A) is related to Δμ through the free energy:
$$\Delta\mu = \frac{\partial F}{\partial N_A}\bigg|_{T,V}$$

By sweeping Δμ, we can map out the entire compositional range and identify:
- **Single-phase regions**: Smooth variation of x vs. Δμ
- **Two-phase regions**: Discontinuous jumps in composition (phase coexistence)
- **Spinodal points**: Inflection points in free energy

## Tips for Success

1. **Start with a quick test**: Run a single temperature with coarse Δμ spacing to verify the setup.
2. **Check for equilibration**: Plot composition vs. MC step for a few representative points.
3. **Refine Δμ spacing**: Near phase transitions, use finer spacing to resolve phase boundaries.
4. **Compare with experiments**: If available, validate against experimental phase diagrams.
5. **Multiple runs**: For critical regions, run multiple independent simulations to check reproducibility.


Author: Bowen Deng
Contact: github username <bowen-bd>
