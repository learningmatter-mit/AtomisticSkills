# Molecular DFT calculation Example

This example demonstrates how to calculate the electronic energy of a water molecule with different ORCA.

## Test your system

You can first make sure that your system is setup properly by running `../../chem-dft-orca-singlepoint/example/validate_orca.py` and
`../../chem-dft-orca-singlepoint/example/validate_multicore_orca.py` if you plan on using multiple CPU cores.

## Usage

Create a valid ORCA input file called `orca_calc.inp` based on the user input
and the [ORCA manual](https://www.faccts.de/docs/orca/6.0/manual/).

Run the following command from the project root:

```bash
# Env: orca-agent
python .agents/skills/chem-dft-orca-advanced-calculation/scripts/run_orca_input.py \
    --input_file orca_calc.inp
```

## Expected Results

- **calculation_results.json**: Summary of some standard quantities that are automatically parsed. More exotic quantities might have to be parsed from `orca_calc.property.txt` or `orca_calc.out`
- **orca_calc.***: Various ORCA input and output files for each calculation
