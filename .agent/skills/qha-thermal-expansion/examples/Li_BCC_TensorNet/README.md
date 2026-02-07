# Li BCC QHA Example

This example demonstrates a Quasi-Harmonic Approximation (QHA) calculation for bulk Lithium (BCC) using the TensorNet MatPES r2SCAN model.

## Command
```bash
conda activate matgl-agent
python .agent/skills/qha/scripts/calculate_qha.py \
    --structure tests/Li.cif \
    --model_type matgl \
    --model_name TensorNet-MatPES-r2SCAN-v2025.1-PES \
    --eos vinet \
    --output_dir research/Li_qha
```

## Included Outputs
- `qha_results.json`: Summary of the QHA calculation parameters.
- `gibbs_temperature.dat`: Gibbs free energy as a function of temperature.
- `thermal_expansion.dat`: Volumetric thermal expansion coefficient as a function of temperature.
