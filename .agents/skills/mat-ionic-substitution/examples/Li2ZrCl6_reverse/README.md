# Li₂ZrCl₆ — Reverse Ionic Substitution

## Goal

Find all crystal structures that can be ion-substituted to produce Li₂ZrCl₆, a promising solid-state Li-ion conductor.

## Command

```bash
# Env: base-agent
python .agents/skills/mat-ionic-substitution/scripts/find_structures_for_composition.py \
    --composition Li2ZrCl6 \
    --threshold 0.001 \
    --max_precursors 42 \
    --output_dir examples/Li2ZrCl6_reverse/
```

## Results

- **Direct MP matches:** 0 (Li₂ZrCl₆ not in Materials Project)
- **Substitution-derived:** 26 structures from 10 precursor systems
- **Total structures:** 26

### Top Precursors

| Precursor | Substitution | Probability | # Structures |
|-----------|-------------|-------------|---:|
| Li₂ZrF₆ | F⁻→Cl⁻ | 0.0045 | 3 |
| Rb₂ZrCl₆ | Rb⁺→Li⁺ | 0.0021 | 1 |
| Na₂ZrF₆ | Na⁺→Li⁺, F⁻→Cl⁻ | 0.0019 | 1 |
| Li₂SnO₆ | Sn⁴⁺→Zr⁴⁺, O²⁻→Cl⁻ | — | 1 |
| Li₂FeF₆ | Fe³⁺→Zr⁴⁺, F⁻→Cl⁻ | 0.0012 | 4 |
| Li₂TiF₆ | Ti⁴⁺→Zr⁴⁺, F⁻→Cl⁻ | 0.0011 | 1 |
| Li₂MnF₆ | Mn³⁺→Zr⁴⁺, F⁻→Cl⁻ | 0.0011 | 13 |
| Li₂SnF₆ | Sn⁴⁺→Zr⁴⁺, F⁻→Cl⁻ | — | 1 |
| Cs₂ZrCl₆ | Cs⁺→Li⁺ | — | 1 |

### Key Observations

- The highest-probability route to Li₂ZrCl₆ is via **Li₂ZrF₆** (halide swap F⁻→Cl⁻)
- Several **double substitutions** were found (e.g., Na₂ZrF₆ ← Na⁺→Li⁺ + F⁻→Cl⁻)
- Li₂MnF₆ dominates the count (13 structures) because it has many polymorphs in MP

## Output Files

- `*.cif` — 26 substitution-derived candidate structures
- `structure_manifest.json` — full provenance (precursor ID, substitution map, probability)

## Next Steps

1. Relax all 26 candidates with an MLIP
2. Rank by energy and check for duplicates with `StructureMatcher`
3. Evaluate thermodynamic stability with `mat-stability` (E_hull)
