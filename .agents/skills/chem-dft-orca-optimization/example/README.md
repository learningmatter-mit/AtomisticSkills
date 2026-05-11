# DFT based optimization of molecules

This example demonstrates how to optimize molecules into an energy minimum or transition state based on DFT calculations with ORCA.

## Test your system

You can first make sure that your system is setup properly by running `../../chem-dft-orca-singlepoint/example/validate_orca.py` and
`../../chem-dft-orca-singlepoint/example/validate_multicore_orca.py` if you plan on using multiple CPU cores.

# Minimization

## Usage

Run the following command from the project root:

```bash
# Env: orca-agent
python .agents/skills/chem-dft-orca-optimization/scripts/run_optimization.py \
    --structure .agents/skills/chem-dft-orca-optimization/example/h2o.xyz \
    --functional PBE \
    --basis_set def2-SVP \
    --nprocs 4 \
    --calculator_settings '{"enforce_scf_criterion": true}' \
    --optimizer_settings '{"convergence_delta_value": 1e-6}' \
    --output_dir .agents/skills/chem-dft-orca-optimization/example
```

## Expected Results

- **optimization_results.json**: Summary of the optimization.
- **input_structure.xyz**: XYZ file for guess structure.
- **optimized_structure.xyz**: XYZ file for optimized structure.
- **opt/opt.opt.trj.xyz**: Multi XYZ file of the optimization trajectory.
- ***-*-*-*/orca_calc.***: Directory with ORCA input and output files.

# TS Optimization

## Usage

Run the following command from the project root:

```bash
# Env: orca-agent
python .agents/skills/chem-dft-orca-optimization/scripts/run_optimization.py \
    --structure .agents/skills/chem-dft-orca-optimization/example/ts_guess.xyz \
    --opt_type ts \
    --functional PBE \
    --basis_set def2-SVP \
    --charge -1 \
    --nprocs 4 \
    --calculator_settings '{"enforce_scf_criterion": true}' \
    --optimizer_settings '{"convergence_delta_value": 1e-6, "optimizer": "bofill"}' \
    --output_dir .agents/skills/chem-dft-orca-optimization/example
```

## Expected Results

- **optimization_results.json**: Summary of the optimization.
- **input_structure.xyz**: XYZ file for guess structure.
- **optimized_structure.xyz**: XYZ file for optimized structure.
- **tsopt/tsopt.tsopt.trj.xyz**: Multi XYZ file of the optimization trajectory.
- ***-*-*-*/orca_calc.***: Directory with ORCA input and output files.

