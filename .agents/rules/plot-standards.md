---
trigger: model_decision
description: Rules for plotting scientific figures, including plot size and fonts
---

# Plotting Standards

To maintain visual consistency and publication-quality aesthetics across all generated plots in AtomisticSkills, the following matplotlib standards **MUST** be applied to all plotting scripts.

## Global Matplotlib Settings
Aesthetics should be set globally at the top of the plotting script or before creating figures:
```python
plt.rcParams.update({'font.size': 14})
```

## Figure Size and Layout
- **Aspect Ratio & Size**: 
  - **Rectangular Plots (Standard Landscape)**: MUST use `figsize=(6, 5)`.
  - **Square Plots (Correlations / Parity)**: MUST use `figsize=(5, 5)`.
- **Layout**: Always enforce tight bounding boxes before saving to prevent cut-off labels: 
  `plt.tight_layout()` and `plt.savefig(..., bbox_inches="tight")`.

## Data Series and Line Styles
- **Line Widths**: Default line widths for major data series MUST be `linewidth=2.5`.
- **Grids**: Grids should be enabled but kept subtle so they don't overpower the data:
  `ax.grid(True, linestyle='--', alpha=0.6)`
- **Legends**: Legends should generally not have a bounding box frame unless it is required to obscure messy data underneath it:
  `ax.legend(frameon=False)`

## Font Weights and Labels
- **Axes Labels**: X and Y axes labels MUST use bold fonts to improve readability:
  `ax.set_xlabel('Label Here', fontweight='bold')`

## Output format
- **Vector Graphics**: Always generate and save a `.svg` formatted plot alongside any `.png` outputs.

By applying these standardized dimensions and typographic weights, our outputs remain universally predictable and polished across all MLIP models and tasks.
