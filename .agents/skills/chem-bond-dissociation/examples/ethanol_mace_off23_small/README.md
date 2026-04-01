# Ethanol BDE Example

## Usage

```bash
# Env: mace-agent
python .agents/skills/chem-bond-dissociation/scripts/calculate_bde.py \
    --smiles CCO \
    --all_bonds \
    --include_h_bonds \
    --model_type mace \
    --model_name MACE-OFF23-small \
    --output_dir .agents/skills/chem-bond-dissociation/examples/ethanol
```

## Results (MACE-OFF23-small)

All single bonds in ethanol (CH₃CH₂OH), sorted by BDE:

| Bond | Computed BDE (kcal/mol) | Exp. BDE (kcal/mol) |
|:---|:---|:---|
| C(1)–O(2) | 83.9 | ~92 |
| C(0)–C(1) | 104.0 | ~85 |
| C(1)–H methylene | 104.5 | ~95 |
| O(2)–H | 107.9 | ~104 |
| C(0)–H methyl | 116.9–117.6 | ~101 |

Experimental values from Blanksby & Ellison, *Acc. Chem. Res.* **2003**, 36, 255.

## Notes

- **C–H ranking is qualitatively correct**: methylene C–H (104.5) < methyl C–H (116.9–117.6).
- **O–H BDE** (107.9 kcal/mol) is close to the experimental value (~104 kcal/mol).
- **C–C vs C–O ranking is inverted** compared to experiment. This reflects the known limitation that MLIPs are "electron-agnostic" and may not correctly capture differences in radical stability.
- BDE **ranking** is more reliable than absolute BDE values with general-purpose MLIPs.

## Output Files

- `bde_results.json` — Full results in JSON format
- `intact_relaxed.xyz` — Relaxed intact ethanol
- `frag_bondN_1.xyz`, `frag_bondN_2.xyz` — Relaxed radical fragments
