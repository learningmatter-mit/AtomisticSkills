# H2O Vibration Analysis Example

## Setup
- Molecule: H2O (water, from ASE built-in database)
- Model: MACE-OMAT-0-small
- Relaxation: fmax = 0.001 eV/Å (converged in 4 steps)
- Delta: 0.01 Å, nfree: 2

## Command
```bash
# Env: mace-agent
python .agents/skills/chem-vibration/scripts/calculate_vibrations.py \
    --molecule H2O --model_type mace --model_name MACE-OMAT-0-small \
    --output_dir .agents/skills/chem-vibration/examples/H2O
```

## Results

H2O is a nonlinear molecule with 3 atoms → 3 vibrational modes expected.

| Mode | Description | MLIP (cm⁻¹) | Experimental (cm⁻¹) | Error |
|------|-------------|-------------|---------------------|-------|
| ν₂ | Bending | 1631.8 | 1595 | +2.3% |
| ν₁ | Symmetric stretch | 3630.2 | 3657 | -0.7% |
| ν₃ | Asymmetric stretch | 3764.2 | 3756 | +0.2% |

- **Zero-point energy**: 0.563 eV (562.9 meV)
- **Translation/rotation modes**: 5 (correctly near zero)
- **Imaginary modes**: 1 small artifact at 52.2i cm⁻¹ (negligible)

## Reference

Experimental vibrational frequencies (1595, 3657, 3756 cm⁻¹) from:
- T. Shimanouchi, "Tables of Molecular Vibrational Frequencies Consolidated Volume I", National Bureau of Standards, 1972, 1-160.
- Available via NIST Computational Chemistry Comparison and Benchmark Database (CCCBDB): https://cccbdb.nist.gov/expvibs1x.asp (search for H2O)

