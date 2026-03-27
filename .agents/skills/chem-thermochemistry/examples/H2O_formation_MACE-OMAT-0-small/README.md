# H₂O Formation Reaction Example

## Reaction

**2H₂(g) + O₂(g) → 2H₂O(g)** at 298.15 K, 1 atm

## Command

```bash
# Env: mace-agent
python .agents/skills/chem-thermochemistry/scripts/calculate_thermochemistry.py \
    --reaction "2H2 + O2 -> 2H2O" \
    --temperature 298.15 \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir .agents/skills/chem-thermochemistry/examples/H2O_formation
```

## Results vs NIST-JANAF Reference

### Per-Species Entropy

| Species | MLIP S° (J/mol·K) | NIST S° (J/mol·K) | Error |
|:--------|:-------------------|:-------------------|:------|
| H₂      | 130.41             | 130.68             | 0.2%  |
| O₂      | 205.61             | 205.15             | 0.2%  |
| H₂O     | 188.91             | 188.84             | <0.1% |

### Reaction Thermodynamics

| Quantity | MLIP Value | NIST Value | Note |
|:---------|:-----------|:-----------|:-----|
| ΔH       | −392.02 kJ/mol | −483.65 kJ/mol | ~19% difference |
| ΔS       | −88.62 J/(mol·K) | −88.73 J/(mol·K) | 0.1% difference |
| ΔG       | −365.60 kJ/mol | −457.22 kJ/mol | ~20% difference |

### Observations

- **Entropy**: Per-species entropies match NIST values with errors ≤ 0.2%.
- **Energy**: Reaction enthalpy (ΔH) and Gibbs free energy (ΔG) show deviations of ~19-20% from NIST reference values.

## Model

- **MLIP**: MACE-OMAT-0-small (PBE-level)
- **Relaxation**: fmax = 0.01 eV/Å
- **Hessian**: Finite-difference, δ = 0.01 Å, nfree = 2
