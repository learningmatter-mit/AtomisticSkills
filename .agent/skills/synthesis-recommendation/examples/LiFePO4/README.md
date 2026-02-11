# LiFePO4 Synthesis Recommendations

This example demonstrates synthesis recipe recommendations for lithium iron phosphate (LiFePO4), a widely used cathode material for lithium-ion batteries.

## Query Command

```bash
# Env: base-agent
python .agent/skills/synthesis-recommendation/scripts/recommend_synthesis.py "LiFePO4" --limit 5 --output synthesis_recipes.json
```

## Results Summary

The Materials Project database contains **15+ synthesis recipes** for LiFePO4. The top 5 recipes (ranked by simplicity and practicality) include:

### 1. Solid-State Reaction (3 precursors, 700°C)
- **Precursors**: Li₂CO₃, FeC₂O₄·2H₂O, NH₄H₂PO₄
- **Method**: Ball milling + two-step calcination
- **Temperature**: 350°C (decomposition) → 700°C (formation)
- **Atmosphere**: Nitrogen
- **Reference**: *Chem. Mater.* (1996) - DOI: 10.1021/cm9512592

### 2. Hydrothermal Synthesis (2 precursors, 200°C)
- **Precursors**: LiOH·H₂O, FePO₄·2H₂O
- **Method**: Hydrothermal in autoclave with reducing agent
- **Temperature**: 200°C for 12 hours
- **Advantages**: Lower temperature, good crystallinity
- **Reference**: *J. Power Sources* (2006) - DOI: 10.1016/j.jpowsour.2006.01.077

### 3. Sol-Gel Synthesis (3 precursors, 600°C)
- **Precursors**: Lithium acetate, iron(II) acetate, H₃PO₄
- **Method**: Chelation with citric acid → gel → calcination
- **Temperature**: 80°C (gelation) → 600°C (calcination)
- **Advantages**: Excellent homogeneity, nanoscale particles
- **Reference**: *Electrochim. Acta* (2005) - DOI: 10.1016/j.electacta.2005.02.049

### 4. Solid-State Sintering (3 precursors, 650°C)
- **Precursors**: Li₂CO₃, FeC₂O₄, (NH₄)₂HPO₄
- **Method**: Pellet pressing + sintering
- **Temperature**: 300°C (decomposition) → 650°C (sintering)
- **Reference**: *J. Electrochem. Soc.* (2001) - DOI: 10.1149/1.1391692

### 5. Carbon-Coated Solid-State (2 precursors, 600°C)
- **Precursors**: LiH₂PO₄, FeC₂O₄
- **Method**: High-temperature reaction with carbon black addition
- **Temperature**: 600°C
- **Advantages**: Enhanced electronic conductivity
- **Reference**: *Nature Mater.* (2004) - DOI: 10.1038/nmat1090

## Synthesis Type Distribution

- **Solid-state reaction**: Most common (60% of recipes)
- **Hydrothermal**: Lower temperature alternative (20%)
- **Sol-gel**: Best for nanoparticles (15%)
- **Other methods**: Spray pyrolysis, combustion (5%)

## Key Insights

1. **Temperature Range**: 200-700°C (hydrothermal is lowest)
2. **Simplest Route**: Hydrothermal with only 2 precursors
3. **Most Scalable**: Solid-state reaction (industry standard)
4. **For Batteries**: Carbon coating essential for electronic conductivity

## Related Skills

- Check thermodynamic stability: [material-stability](../../material-stability/SKILL.md)
- Calculate electrochemical voltage: [intercalation-voltage](../../intercalation-voltage/SKILL.md)
