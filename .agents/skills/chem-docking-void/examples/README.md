# `chem-docking-void` Example

This example demonstrates how to perform molecular docking into a porous material using the `chem-docking-void` skill.

## Overview
- **Host Material**: Chabazite (CHA) Zeolite
- **Guest Molecule**: N,N,N-trimethyladamantan-1-aminium (TMAda)
- **SMILES**: `C[N+](C)(C)C12CC3CC(C1)CC(C2)C3`

## Running the Example
Make sure you have the `void-agent` conda environment installed and activated. Run the provided script from this directory:

```bash
conda activate void-agent
bash ./run_example.sh
```

## Expected Output
The script will output localized guest conformer positions into the `./example_output` directory in standard CIF format. It will also produce a `docking_results.json` mapping the geometric parameters, RDKit conformer energies, and structural metrics.
