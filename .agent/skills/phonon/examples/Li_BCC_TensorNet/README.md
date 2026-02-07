# Li BCC Phonon Example

This example demonstrates a phonon calculation for bulk Lithium (BCC) using the TensorNet MatPES r2SCAN model.

## Command
```bash
conda activate matgl-agent
python .agent/skills/phonon/scripts/calculate_phonon.py \
    --structure tests/Li.cif \
    --model_type matgl \
    --model_name TensorNet-MatPES-r2SCAN-v2025.1-PES \
    --supercell_matrix '[[3,0,0],[0,3,0],[0,0,3]]' \
    --output_dir research/Li_phonon
```

## Included Outputs
- `phonon_results.json`: Summary of thermodynamic properties.
- `phonon.yaml`: Force constants and supercell data.
- `band_structure.yaml`: Frequencies along high-symmetry paths.
- `total_dos.dat`: Total phonon density of states.
