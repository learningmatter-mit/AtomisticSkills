# Silicon Equation of State Example

This example demonstrates calculating the equation of state for crystalline Silicon using MACE-OMAT-0-small.

## Structure

The Silicon structure ([Si.cif](Si.cif)) was obtained from Materials Project (mp-149), representing the diamond cubic structure with lattice parameter a = 5.43 Å.

## Calculation

Run the EOS calculation with:

```bash
# Env: mace-agent
python .agents/skills/mat-equation-of-state/scripts/calculate_eos.py \
    --structure .agents/skills/mat-equation-of-state/examples/Si/Si.cif \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --n_points 7 \
    --max_abs_strain 0.08 \
    --output_dir eos_output
```

## Results

The calculation applies 7 volumetric strain points (±8%) and fits the Birch-Murnaghan equation of state:

- **Bulk Modulus**: 96.43 GPa
- **Equilibrium Volume**: 39.99 ų
- **Equilibrium Energy**: -10.83 eV
- **R² Score**: 0.999988

The equilibrium volume and energy are the Birch-Murnaghan minimum (v0, e0), not the
volume or energy of any single scan point. The 2-atom primitive cell at 39.99 ų
corresponds to a = 5.426 A, against the experimental 5.431 A. The scan itself is in
[energies_volumes.dat](energies_volumes.dat), and under `energy_volume_curve` in
[eos_results.json](eos_results.json), so the fit can be reproduced independently.

### Comparison with Experiment

- **Experimental bulk modulus**: ~98 GPa
- **MACE-OMAT prediction**: 96.43 GPa
- **Error**: ~2% (excellent agreement)

## Notes

- The calculation took approximately 7 strain points × relaxation time
- MACE-OMAT-0-small provides accurate bulk modulus predictions for elemental semiconductors
- The high R² score (0.999988) indicates excellent fit quality to the Birch-Murnaghan EOS
