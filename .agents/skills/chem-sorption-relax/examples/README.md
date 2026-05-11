# Chem-Sorption-Relax Examples

This directory contains example scripts and outputs demonstrating framework structure relaxation using `relax_structure.py` and `build_supercell.py`.

## Directory Structure

```
examples/
├── README.md
├── test_relax.sh                         # The main test script
├── test_structure.cif                    # The initial unrelaxed framework input
├── test_structure_supercell.cif          # The intermediate unrelaxed supercell
├── test_structure_supercell.relaxed.cif  # The final relaxed supercell
├── input_configs.yaml                    # Captured configuration parameters
└── relax_results.json                    # Full energy, forces, and optimization log
```

## Examples by Category

### 1. Framework Relaxation (`test_relax.sh`)
**Script**: `test_relax.sh`  
**Function**: Builds a supercell to satisfy minimum interplanar distance requirements, then optimization via Fairchem/UMA.

**Input**: `test_structure.cif` (an unrelaxed porous framework)  
**Outputs**:
- `test_structure_supercell.cif`
- `test_structure_supercell.relaxed.cif`
- `relax_results.json`
- `input_configs.yaml`

**Properties**: converged, n_atoms, energy_initial_eV, energy_final_eV

```bash
cd .agents/skills/chem-sorption-relax/examples
bash test_relax.sh
```

## Requirements

- `fairchem-agent` conda environment activated
- `base-agent` conda environment for supercell generation
- UMA-S-1p1 model downloaded and configured

## Notes

- The relaxation uses `LBFGS` optimizer by default convergence of 0.05 eV/A.
- Resulting `.relaxed.cif` files are typically used as input for downstream GCMC and Widom calculations.
