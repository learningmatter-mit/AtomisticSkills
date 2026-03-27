# Ethanol BDE Example — UMA-s omol

## Usage

```bash
# Env: fairchem-agent
python .agents/skills/chem-bond-dissociation/scripts/calculate_bde.py \
    --smiles CCO \
    --all_bonds \
    --include_h_bonds \
    --model_type fairchem \
    --model_name uma-s-1p1 \
    --task_name omol \
    --output_dir .agents/skills/chem-bond-dissociation/examples/ethanol_uma_s_omol
```

## Results (UMA-s-1p1, omol head)

| Bond | UMA-s omol (kcal/mol) | MACE-OFF23 (kcal/mol) | Exp. (kcal/mol) |
|:---|:---|:---|:---|
| C(1)–H methylene | 106.7–107.4 | 104.5 | ~95 |
| C(1)–O | 122.5 | 83.9 | ~92 |
| C(0)–H methyl | 122.8–123.5 | 116.9–117.6 | ~101 |
| C(0)–C(1) | 131.4 | 104.0 | ~85 |
| O(2)–H | 139.8 | 107.9 | ~104 |

## Notes

- UMA-s omol **systematically overestimates** all BDEs by ~12–36 kcal/mol.
- A likely cause: radical fragments default to **spin multiplicity = 1** (singlet), but the true ground state is doublet (spin = 2). UMA issues a warning about this but has no way to fix it without user-supplied spin info.
- **Ranking**: methylene C–H (106.7) < methyl C–H (122.8) is qualitatively correct, but the gap is larger than experiment.
- **MACE-OFF23-small gives closer absolute BDE values** for this system.
- Both models correctly identify C–H bonds as weaker than C–C/C–O/O–H bonds.
