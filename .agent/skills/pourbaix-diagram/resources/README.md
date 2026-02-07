# Pourbaix Diagram Resources

This directory contains pre-made reference molecule structures for water correction calculations.

## Reference Molecules

### H2O.cif
Water molecule in 15Å cubic cell
- Geometry: O-H bond ~0.96 Å, H-O-H angle ~104.5°
- Use: Calculate E(H₂O) for water correction

### H2.cif  
Hydrogen molecule in 15Å cubic cell
- Geometry: H-H bond ~0.74 Å
- Use: Calculate E(H₂) for water correction

### O2.cif
Oxygen molecule in 15Å cubic cell
- Geometry: O-O bond ~1.21 Å  
- Use: Calculate E(O₂) for water correction

## Usage

Relax these molecules with your chosen MLIP (UMA recommended):

```python
mcp_fairchem_load_model(model_name="uma-m-1p1")

mcp_fairchem_relax_structure(
    structure_data=".agent/skills/pourbaix-diagram/resources/H2O.cif",
    fmax=0.001,  # Tight convergence
    steps=500,
    output_dir="./relaxed_molecules/H2O/"
)
# Repeat for H2.cif and O2.cif
```

Then use the relaxed energies in `calculate_water_correction.py`.

## Notes

- **Large cell size (15Å)**: Prevents periodic boundary interactions
- **Tight convergence (fmax ≤ 0.001)**: Critical for accurate water correction
- **Same MLIP**: Use the same model for molecules AND solids
