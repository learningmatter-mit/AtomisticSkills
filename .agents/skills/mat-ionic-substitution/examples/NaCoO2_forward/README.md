# NaCoO₂ — Forward Ionic Substitution

## Goal

Propose all high-probability ion-substituted variants of NaCoO₂, a layered cathode material. This demonstrates how ionic substitution can systematically discover materials like LiCoO₂ from its Na analogue.

## Command

```bash
# Env: base-agent
python .agents/skills/mat-ionic-substitution/scripts/propose_substitutions.py \
    --structure NaCoO2.cif \
    --threshold 0.001 \
    --output_dir examples/NaCoO2_forward/
```

Source structure: NaCoO₂ from Materials Project (mp-1279953).

## Results

- **47 substituted variants** proposed from 96 substitution maps (filtered for charge balance)
- Includes single, double, and multi-ion substitutions

### Top Substitutions

| # | Formula | Substitution | Probability |
|---|---------|-------------|-------------|
| 0 | NaFeO₂ | Co³⁺→Fe³⁺ | 0.0162 |
| 1 | NaScO₂ | Co³⁺→Sc³⁺ | 0.0114 |
| 2 | NaCrO₂ | Co³⁺→Cr³⁺ | 0.0104 |
| 3 | NaAlO₂ | Co³⁺→Al³⁺ | 0.0101 |
| 4 | NaMnO₂ | Co³⁺→Mn³⁺ | 0.0081 |
| 5 | NaVO₂ | Co³⁺→V³⁺ | 0.0075 |
| 6 | NaNiO₂ | Co³⁺→Ni³⁺ | 0.0058 |
| 9 | KFeO₂ | Co³⁺→Fe³⁺, Na⁺→K⁺ | 0.0032 |
| 10 | KCoO₂ | Na⁺→K⁺ | 0.0027 |
| 13 | LiFeO₂ | Co³⁺→Fe³⁺, Na⁺→Li⁺ | 0.0026 |
| **16** | **LiCoO₂** | **Na⁺→Li⁺** | **0.0021** |

### Key Observations

- All known layered transition-metal oxide cathodes (LiCoO₂, NaFeO₂, NaMnO₂, NaNiO₂) are correctly predicted
- **LiCoO₂ appears at rank 16** — the Na⁺→Li⁺ substitution that defines the original discovery
- Double substitutions like KFeO₂ (Co³⁺→Fe³⁺ + Na⁺→K⁺) are also captured

## Output Files

- `*.cif` — 47 substituted structure files
- `substitution_manifest.json` — full metadata (substitution map, probability, multi-swap flag)
