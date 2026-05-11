# Molecular DFT calculation Example

This example demonstrates how to calculate the electronic energy of a water molecule with different ORCA.

## Test your system

You can first make sure that your system is setup properly by running `validate_orca.py` and
`validate_multicore_orca.py` if you plan on using multiple CPU cores.

## Usage

Run the following command from the project root:

```bash
# Env: orca-agent
python .agents/skills/chem-dft-orca-singlepoint/scripts/run_singlepoint.py \
    --structure .agents/skills/chem-dft-orca-singlepoint/example/h2o.xyz \
    --functional PBE0 \
    --basis_set def2-TZVP \
    --dispersion D3BJ \
    --compute_gradients \
    --solvation CPCM \
    --solvent ethanol \
    --nprocs 4 \
    --output_dir .agents/skills/chem-dft-orca-singlepoint/example
```

## Expected Results

- **singlepoint_results.json**: Summary of the calculated quantities
- **input_structure.xyz**: XYZ files of the calculated structure
- ***-*-*-*/orca_calc.***: Directory with ORCA input and output files for each calculation
