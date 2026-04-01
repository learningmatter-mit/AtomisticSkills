---
name: ml-mlip-benchmark
description: Benchmark MLIP accuracy against a labeled dataset — compute MAE/RMSE for energy/atom and forces, and generate parity plots.
category: [machine-learning]
---

# Benchmark Machine Learning Interatomic Potentials (MLIP)

This skill evaluates the accuracy of a given MLIP against an existing ground-truth dataset (e.g., DFT calculations or a higher-fidelity foundation potential). It computes the Mean Absolute Error (MAE) and Root Mean Square Error (RMSE) for both energy (per atom) and atomic forces, and optionally stress. It also generates parity plots for visual inspection of the model's correlation.

## Prerequisites
1. **Model Loaded**: An MLIP must be currently active via a `load_model` MCP tool call (e.g., `mcp_mace_load_model`, `mcp_fairchem_load_model`, `mcp_matgl_load_model`).
2. **Labeled Data**: A JSON dataset where each entry contains a structural dictionary under `"structure"`, along with scalar/vector ground truth values for `"energy"`, `"forces"`, and optionally `"stress"`. This is identical to the format used in `ml-mlip-training`. (Data can be generated using Atomate2 MongoDB queries or MD sampling + labeling).

## Instructions

### 1. Run Benchmark metrics
Use the `.agents/skills/ml-mlip-benchmark/scripts/run_benchmark.py` script to perform inference across the dataset and compute global error metrics.

**Environment requirement**: This script instantiates the MLIP models directly and thus **must be executed within the target model's conda environment** (e.g., `mace-agent`, `fairchem-agent`, or `matgl-agent`). Run this using the `run_command` via `conda run -n <model_agent> python ...`.

```bash
conda run -n <MODEL-AGENT-ENV> python .agents/skills/ml-mlip-benchmark/scripts/run_benchmark.py \
    --data_path <path_to_labeled_data.json> \
    --model <model_name_or_path> \
    --backend <mace|fairchem|matgl> \
    --output <path_to_save_benchmark_results.json>
```
*Note: The script utilizes `src.utils.mlips.loader.load_wrapper` to abstract backend details.*

### 2. Generate Parity Plots
Once `run_benchmark.py` finishes, it writes a comprehensive JSON file containing original targets alongside the model's predictions and numerical metrics. Visualize these using the plotting script.

**Environment requirement**: It is safe to use `base-agent` for the plotting script.

```bash
conda run -n base-agent python .agents/skills/ml-mlip-benchmark/scripts/plot_benchmark.py \
    --results <path_to_benchmark_results.json> \
    --output_dir <path_to_save_plots>
```

This generates `energy_parity.png`, `forces_parity.png`, and (if stress was present) `stress_parity.png`.

### 3. Interpret Results
When presenting the plotted benchmarks to the user, consult the following rough heuristics for MLIP performance:
- **Energy MAE**: Excellent (< 5 meV/atom), Good (5-20 meV/atom), Poor (> 50 meV/atom)
- **Forces MAE**: Excellent (< 20 meV/Å), Good (20-50 meV/Å), Poor (> 100 meV/Å)

If the model is performing poorly on the labeled data, suggest fine-tuning it utilizing the `ml-mlip-training` skill.

## Examples

Evaluating state-of-the-art MatPES-r2SCAN Foundation Models directly against f-block filtered analytical DFT data from the Materials Project:

```bash
# Env: base-agent
# Fetch 100 random r2SCAN structures from MP API (excluding Lanthanides/Actinides)
python .agents/skills/ml-mlip-benchmark/examples/fetch_r2scan.py

# Env: mace-agent
# Benchmark MACE foundation potential
conda run -n mace-agent python .agents/skills/ml-mlip-benchmark/scripts/run_benchmark.py \
    --data_path research/2026-03-03_r2SCAN_benchmark/r2scan_data.json \
    --model MACE-MATPES-R2SCAN-0 \
    --backend mace \
    --output research/2026-03-03_r2SCAN_benchmark/mace_results.json

# Env: base-agent
# Plot the evaluation statistics
conda run -n base-agent python .agents/skills/ml-mlip-benchmark/scripts/plot_benchmark.py \
    --results research/2026-03-03_r2SCAN_benchmark/mace_results.json \
    --output_dir research/2026-03-03_r2SCAN_benchmark/plots_mace
```

### Resulting Parity Plots (Filtered R2SCAN Data)
![MACE-MATPES-R2SCAN-0 Parity Plot](/home/bdeng/projects/AtomisticSkills/.agents/skills/ml-mlip-benchmark/examples/mace_parity.png)
![CHGNet-MatPES-r2SCAN-2025.2.10-2.7M Parity Plot](/home/bdeng/projects/AtomisticSkills/.agents/skills/ml-mlip-benchmark/examples/chgnet_parity.png)
![M3GNet-MatPES-r2SCAN-v2025.1 Parity Plot](/home/bdeng/projects/AtomisticSkills/.agents/skills/ml-mlip-benchmark/examples/m3gnet_parity.png)
![TensorNet-MatPES-r2SCAN-v2025.1 Parity Plot](/home/bdeng/projects/AtomisticSkills/.agents/skills/ml-mlip-benchmark/examples/tensornet_parity.png)

## Typical Combinations
- Use `mat-sample-pes-by-md` to generate un-labeled configurations.
- Use `atomate2` MCP tools or VASP to evaluate configurations and produce a labeled dataset JSON.
- Use `ml-mlip-training` if the benchmark metric thresholds are unsatisfactory.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
