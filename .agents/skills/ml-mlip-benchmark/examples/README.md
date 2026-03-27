# MLIP r2SCAN Foundation Model Benchmarking

This directory contains a complete example workflow demonstrating how to extract baseline DFT data from the Materials Project API and rapidly evaluate the fidelity of state-of-the-art Machine Learning Interatomic Potentials (MLIPs).

## Workflow Overview

1. **`fetch_r2scan.py`**: A customized Materials Project API ingestion script that combines the `thermo` and `summary` endpoints to seamlessly pair structural geometries with their uncorrected `r2SCAN` energy computations. 
2. **`run_benchmark.py`**: The main execution engine under `../scripts/` orchestrates `load_wrapper` instantiations to perform inference testing on identical structures.
3. **`plot_benchmark.py`**: Renders numerical MAE/RMSE results mapped to visual `.png` parity distributions out of the resulting prediction data arrays.

## MatPES-r2SCAN Foundation Benchmarks

We executed this complete workflow evaluating 100 random analytical r2SCAN target structures natively against four zero-temperature foundation potentials trained on the OMat/MP-r2SCAN dataset:

| Framework | Pre-Trained Foundation Potential Model | Mean Absolute Error (MAE) |
| --- | --- | --- |
| **MatGL** | `CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES` | **~65 meV/atom** |
| **MACE**  | `MACE-MATPES-R2SCAN-0`                    | **~80 meV/atom** |
| **MatGL** | `TensorNet-MatPES-r2SCAN-v2025.1-PES`     | **~150 meV/atom**|
| **MatGL** | `M3GNet-MatPES-r2SCAN-v2025.1-PES`        | **~200 meV/atom**|

*(Note: Lanthanide and Actinide elements are programmatically excluded in the fetch script to avoid global potential correlation anomalies.)*

## Running the Benchmarks

You can fully reproduce these findings by performing the following execution steps from the project root.

1. **Fetch Target Dataset**
```bash
# Env: base-agent
conda run -n base-agent python .agents/skills/ml-mlip-benchmark/examples/fetch_r2scan.py
```

2. **Evaluate Foundation Models**
Execute inference testing across each model in their respective environments:

```bash
# MACE Potential Benchmark (Env: mace-agent)
conda run -n mace-agent python .agents/skills/ml-mlip-benchmark/scripts/run_benchmark.py \
    --model MACE-MATPES-R2SCAN-0 --backend mace \
    --data_path research/2026-03-03_r2SCAN_benchmark/r2scan_data.json \
    --output research/2026-03-03_r2SCAN_benchmark/mace_results.json

# CHGNet Potential Benchmark (Env: matgl-agent)
conda run -n matgl-agent python .agents/skills/ml-mlip-benchmark/scripts/run_benchmark.py \
    --model CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES --backend matgl \
    --data_path research/2026-03-03_r2SCAN_benchmark/r2scan_data.json \
    --output research/2026-03-03_r2SCAN_benchmark/chgnet_results.json

# M3GNet Potential Benchmark (Env: matgl-agent)
conda run -n matgl-agent python .agents/skills/ml-mlip-benchmark/scripts/run_benchmark.py \
    --model M3GNet-MatPES-r2SCAN-v2025.1-PES --backend matgl \
    --data_path research/2026-03-03_r2SCAN_benchmark/r2scan_data.json \
    --output research/2026-03-03_r2SCAN_benchmark/m3gnet_results.json

# TensorNet Potential Benchmark (Env: matgl-agent)
conda run -n matgl-agent python .agents/skills/ml-mlip-benchmark/scripts/run_benchmark.py \
    --model TensorNet-MatPES-r2SCAN-v2025.1-PES --backend matgl \
    --data_path research/2026-03-03_r2SCAN_benchmark/r2scan_data.json \
    --output research/2026-03-03_r2SCAN_benchmark/tensornet_results.json
```

3. **Generate Parity Plots**
```bash
# Env: base-agent
conda run -n base-agent python .agents/skills/ml-mlip-benchmark/scripts/plot_benchmark.py \
    --results research/2026-03-03_r2SCAN_benchmark/mace_results.json \
    --output_dir .agents/skills/ml-mlip-benchmark/examples/
# (Repeat for the matgl json outputs)
```
