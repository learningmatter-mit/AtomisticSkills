# Si Lattice Thermal Conductivity Example

This example demonstrates the step three in lattice thermal conductivity calculation for bulk Silicon (Diamond) using the MACE OMAT small model.

## Command
```bash
# Env: mace-agent
conda activate mace-agent
python .agents/skills/mat-lattice-thermal-conductivity/scripts/calculate_thermal_conductivity.py \
    --structure tests/Si.cif \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --supercell_matrix '[[2,0,0],[0,2,0],[0,0,2]]' \
    --output_dir research/Si_thermal_conductivity
```

## Included Outputs
- `lattice_thermal_conductivity_results.json`: Summary of thermodynamic properties.
- `phonon3.yaml`: Third order force constants and supercell data.
