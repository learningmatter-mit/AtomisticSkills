# UMA-s Thermochemistry Benchmarks

This directory contains benchmark results for the **UMA-s-1p1** model using the `omol` (organic molecules) task.

**Model:** `uma-s-1p1`
**Task:** `omol`
**Date:** 2026-02-18

## Execution

Benchmarks were run using the `chem-thermochemistry` skill:

```bash
python .agents/skills/chem-thermochemistry/scripts/run_benchmarks.py
```

This script internally calls `calculate_thermochemistry.py` with arguments:
`--model_type fairchem --model_name uma-s-1p1 --task omol`

## Results Summary

| Reaction | ΔH Calc (kJ/mol) | ΔH Ref (NIST) | Error (ΔH) | ΔG Calc (kJ/mol) | ΔG Ref (NIST) | Error (ΔG) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Water Formation** | -611.10 | -483.65 | **127.45** | -584.86 | -457.22 | **127.64** |
| **Ammonia Synthesis** | -100.87 | -91.80 | **9.07** | -42.04 | -32.90 | **9.14** |
| **Methanol Synthesis** | -94.18 | -90.20 | **3.98** | -28.86 | -24.80 | **4.06** |
| **Methane Combustion** | -1062.42 | -802.30 | **260.12** | -1060.94 | -800.90 | **260.04** |

## Directory Structure

Each directory corresponds to a benchmark reaction and contains:
- `species_<name>/`: Directory for each species in the reaction.
    - `relax.log`: LBFGS relaxation log.
    - `vib/`: Vibrational analysis cache files.
- `thermochemistry_results.json`: Detailed JSON output including:
    - Species properties (Energy, ZPE, Enthalpy, Entropy, Gibbs).
    - Reaction thermodynamics (ΔH, ΔS, ΔG).
    - Model metadata.

