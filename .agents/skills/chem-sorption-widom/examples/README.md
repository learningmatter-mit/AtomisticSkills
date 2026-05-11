# Chem-Sorption-Widom Examples

This directory contains example scripts and outputs demonstrating infinite-dilution property predictions (Henry coefficients, Heat of Adsorption) using `run_widom.py`.

## Directory Structure

```
examples/
├── README.md
├── test_widom.sh                         # The main test script
├── input_configs.yaml                    # Captured configuration parameters
├── test_structure_supercell.relaxed.cif  # Pre-relaxed framework input
└── widom_results.json                    # Full insertion results
```

## Examples by Category

### 1. Widom Insertion (`test_widom.sh`)
**Script**: `test_widom.sh`  
**Function**: Calculates the Henry coefficient and isosteric heat of adsorption of CO2 via random Widom test particle insertions in an MLIP surrogate model.

**Input**: `test_structure_supercell.relaxed.cif` (A pre-relaxed porous framework)  
**Outputs**:
- `widom_results.json` (~2KB)
- `input_configs.yaml`

**Properties**: henry_coefficient_mol_kg_Pa, heat_of_adsorption_kJ_mol, T_K

```bash
cd .agents/skills/chem-sorption-widom/examples
bash test_widom.sh
```

## Requirements

- `fairchem-agent` conda environment activated
- Pre-relaxed `.cif` structure (typically from `chem-sorption-relax`)
- UMA-S-1p1 model downloaded and configured

## Notes

- 5,000 insertions typically take ~5-10 minutes on an NVIDIA GPU (e.g., A100/H100) using UMA.
- `widom_results.json` strictly contains simulation observables, while hyperparameter tracking is isolated to `input_configs.yaml`.
