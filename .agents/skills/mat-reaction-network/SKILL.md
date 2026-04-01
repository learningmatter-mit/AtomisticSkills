---
name: mat-reaction-network
description: Predict thermodynamically optimal solid-state inorganic synthesis pathways and tabulates basic reactions.
category: [materials]
---

# Material Reaction Network Prediction

## Goal
To predict the optimal sequence of thermodynamically favorable chemical reactions (pathways) needed to synthesize a target generic solid-state material from a set of starting precursors. This skill enumerates large, competitive reaction networks and solves for minimum-energy paths using the `materialsproject/reaction-network` code and Materials Project API thermodynamics data.

## Instructions

### 1. Reaction Enumeration
Explore the landscape of competing reactions within a specific chemical system by explicitly generating balanced equations.

```bash
# Env: base-agent
python .agents/skills/mat-reaction-network/scripts/enumerate_reactions.py --chemsys Ba-Ti-O --enumerator-type basic_open --open-phases O2 --temperature 1000 --limit 10
```
- `--chemsys`: The chemical system to restrict search to.
- `--enumerator-type`: The algorithm used to propose reactions (`basic`, `basic_open`, `minimize_gibbs`, `minimize_grand_potential`).
- `--open-phases`: (Specific to `basic_open`) allow materials to be freely consumed or produced from an infinite reservoir (like environmental O2).
- `--temperature`: Synthesis temperature (Kelvin), affects Gibbs adjustments.
- `--limit`: Maximum number of elementary reactions to print.

### 2. Pathfinding and Solving Syntheses
To resolve a complete list of step-by-step reactions that convert specific starting precursors into a target compound, use the pathway solver script.

```bash
# Env: base-agent
python .agents/skills/mat-reaction-network/scripts/find_pathways.py --target BaTiO3 --precursors BaO TiO2 --temperature 1000 --k-paths 5
```
- `--target`: The desired final functional material.
- `--precursors`: One or more starting materials (e.g., oxides or carbonates).
- `--byproducts`: Optional allowed volatile byproducts (e.g., `CO2`, `H2O`) escaping into the atmosphere.
- `--k-paths`: Number of different candidate elementary pathways to yield.

## Examples

Finding pathways to synthesize Yttrium Manganite from carbonates and chlorides:
```bash
# Env: base-agent
python .agents/skills/mat-reaction-network/scripts/find_pathways.py \
    --target YMnO3 \
    --precursors YCl3 Mn2O3 Li2CO3 \
    --byproducts LiCl CO2 \
    --temperature 923 \
    --k-paths 5
```

## Constraints
- **Environments**: The scripts require the `base-agent` conda environment where `reaction-network` and `mp-api` are installed. **Each execution MUST specify this environment.**
- **Network Extent**: Highly constrained chemical systems (e.g., >5 elements) without sensible stability filtering (`--stability-tol`) can generate massive reaction networks taking >10 minutes and >16GB memory to solve.
- **Open Phases**: Synthesis in air or controlled atmospheres must be modeled appropriately by declaring oxygen/nitrogen as open phases.

## References
- McDermott, M. J., et al. "A graph-based approach to predicting solid-state synthesis pathways". *Nature Communications* (2021). [DOI](https://doi.org/10.1038/s41467-021-23339-x)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
