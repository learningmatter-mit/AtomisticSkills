# LiCoO2 Synthesis Recommendations

This example demonstrates synthesis recipe recommendations for lithium cobalt oxide (LiCoO2), the first commercialized lithium-ion battery cathode material (used in Sony's 1991 battery).

## Query Command

```bash
# Env: base-agent
python .agents/skills/mat-synthesis-recommendation/scripts/recommend_synthesis.py "LiCoO2" --limit 5 --output synthesis_recipes.json
```

## Results Summary

The Materials Project database contains **20+ synthesis recipes** for LiCoO2. The top 5 recipes include:

### 1. LiOH·H₂O + Co(OH)₂ (800°C, Solid-State)
- **Precursors**: 2 components
- **Advantages**: Simple, highly pure product
- **Temperature**: 400°C (pre-heating) → 800°C (main reaction)
- **Reference**: *Mater. Res. Bull.* (1980) - DOI: 10.1016/0025-5408(80)90012-4

### 2. Li₂CO₃ + Co₃O₄ (900°C, Solid-State)
- **Precursors**: 2 components
- **Advantages**: Most common industrial route
- **Temperature**: 900°C (24 hours)
- **Note**: Requires intermediate grinding for homogeneity
- **Reference**: *J. Solid State Chem.* (1981) - DOI: 10.1016/0022-4596(81)90077-1

### 3. LiNO₃ + Co(NO₃)₂ (700°C, Sol-Gel)
- **Precursors**: 2 components
- **Advantages**: Better homogeneity, smaller particle size
- **Temperature**: 80°C (gelation) → 700°C (calcination)
- **Reference**: *Solid State Ionics* (1996) - DOI: 10.1016/S0167-2738(96)00444-6

### 4. LiOH + CoCl₂ (600°C, Hydrothermal + Annealing)
- **Precursors**: 2 components
- **Advantages**: Lower calcination temperature
- **Temperature**: 180°C (hydrothermal) → 600°C (annealing)
- **Reference**: *J. Power Sources* (2004) - DOI: 10.1016/j.jpowsour.2004.01.007

### 5. Acetates + Oxalic Acid (750°C, Co-precipitation)
- **Precursors**: 3 components (Li acetate, Co acetate, oxalic acid)
- **Advantages**: Good morphology control
- **Temperature**: 450°C (decomposition) → 750°C (calcination)
- **Reference**: *J. Power Sources* (1999) - DOI: 10.1016/S0378-7753(99)00199-8

## Critical Synthesis Considerations

### 1. Oxidizing Atmosphere Required
LiCoO2 requires air or O₂ atmosphere during calcination to maintain Co³⁺ oxidation state:
- **Air atmosphere**: Standard for most routes
- **Pure O₂**: Sometimes used for better stoichiometry
- **Avoid reducing atmospheres**: Will form Co²⁺ and degrade performance

### 2. Li Stoichiometry
Slight Li excess (Li₁.₀₅CoO₂) often used to compensate for Li volatilization at high temperatures.

### 3. Crystallinity vs. Temperature
- **700-800°C**: Good balance of crystallinity and Li retention
- **>900°C**: Better crystallinity but Li loss risk
- **<600°C**: Poor crystallinity, lower capacity

## Electrochemical Performance

Well-synthesized LiCoO2 typically shows:
- **Capacity**: ~140 mAh/g (theoretical: 274 mAh/g, practical limit: ~160 mAh/g)
- **Voltage**: ~3.9 V vs. Li/Li⁺
- **Cycle life**: >500 cycles at moderate rates

## Related Skills

- Calculate intercalation voltage: [mat-intercalation-voltage](../../mat-intercalation-voltage/SKILL.md)
- Check phase stability: [mat-stability](../../mat-stability/SKILL.md)
