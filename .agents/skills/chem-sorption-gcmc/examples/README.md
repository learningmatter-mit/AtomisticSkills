# Chem-Sorption-GCMC Examples

This directory contains example scripts and outputs demonstrating adsorption isotherm modelling using Grand Canonical Monte Carlo (GCMC) simulations via `run_gcmc.py` and `run_gcmc_multi.py`.

## Directory Structure

```
examples/
├── README.md
├── test_gcmc.sh                          # The main test script
├── test_structure_supercell.relaxed.cif  # Pre-relaxed framework input
├── single_gas/                           # Outputs for single-component GCMC
│   ├── gcmc_results.json                 
│   ├── input_configs.yaml
│   ├── nmols.png                         
│   └── energy.png                        
└── multi_gas/                            # Outputs for multi-component competitive GCMC
    ├── multi_gcmc.json                   
    ├── input_configs.yaml
    ├── nmols_CO2.png                     
    ├── nmols_N2.png                      
    └── energy.png                        
```

## Examples by Category

### 1. Single-Component GCMC (`single_gas/`)
**Script**: `test_gcmc.sh` (Line 4)  
**Function**: Simulates pure-gas uptake (CO2) at 1.0 bar and 298 K using UMA-S-1p1.

**Input**: `test_structure_supercell.relaxed.cif`  
**Outputs**:
- `gcmc_results.json` (Uptake capacity, Qst, and convergence metrics)
- `input_configs.yaml` (Simulation hyperparameters)
- `nmols.png`, `energy.png` (Trace plots)

### 2. Multi-Component GCMC (`multi_gas/`)
**Script**: `test_gcmc.sh` (Line 17)  
**Function**: Simulates competitive mixture uptake (15% CO2, 85% N2) at 1.0 bar and 298 K.

**Input**: `test_structure_supercell.relaxed.cif`  
**Outputs**:
- `multi_gcmc.json` (Molar uptake for each species and selectivity traces)
- `input_configs.yaml`
- `nmols_CO2.png`, `nmols_N2.png`, `energy.png`

```bash
cd .agents/skills/chem-sorption-gcmc/examples
bash test_gcmc.sh
```

## Requirements

- `fairchem-agent` conda environment activated
- Pre-relaxed `.cif` structure (typically from `chem-sorption-relax`)
- UMA-S-1p1 model downloaded and configured

## Notes

- Tests default to 100 steps for rapid validation. Production-grade GCMC typically requires >10,000 steps to fully equilibrate in the grand canonical ensemble.
- Plotting outputs (`*.png`) allow rapid visual validation of Monte Carlo convergence (or lack thereof).
