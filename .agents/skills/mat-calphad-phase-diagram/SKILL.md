---
name: mat-calphad-phase-diagram
description: Calculate and plot multi-component temperature-composition phase diagrams from Thermodynamic Database (.tdb) files using CALPHAD methods.
category: materials
---

# mat-calphad-phase-diagram

## Goal
To plot macroscopic metallurgical Temperature-composition ($T-x$) binary phase diagrams using the CALPHAD methodology from pre-fitted `.tdb` thermodynamic databases. This enables the prediction of solidus/liquidus lines, miscibility gaps, and invariant reactions (e.g. eutectics).

## Instructions

### 1. Identify Thermodynamic Database
You must obtain a legitimate `.tdb` (Thermodynamic Data Base) file for the chemical system of interest. 
- You can find databases in published literature or open repositories (like PyCalphad's databases).

### 2. Plot the Phase Diagram
Use the provided python script to generate the $T-x$ boundary plot.

```bash
# Env: calphad-agent
python .agents/skills/mat-calphad-phase-diagram/scripts/plot_phase_diagram.py path/to/database.tdb --elements Element1 Element2 --t-range 300 1000 10 --output research_dir/phase_diagram.png
```

- `--elements`: The two chemical symbols to plot. The script computes the binary system.
- `--t-range`: `START STOP STEP` in Kelvin. It is recommended to use a step of 10 for reasonable trade-offs between calculation speed and curve smoothness.

### 3. Verification
Use a visual inspection tool to verify the resulting `phase_diagram.png`. Ensure that phase labels are clearly visible and there are no overlapping disjoint calculation artifacts (indicative of a database convergence issue).

## Examples

Plotting the classic Aluminum-Zinc Phase Diagram (Mey 1993):
```bash
# Env: calphad-agent
python .agents/skills/mat-calphad-phase-diagram/scripts/plot_phase_diagram.py .agents/skills/mat-calphad-phase-diagram/examples/Al-Zn/alzn_mey.tdb --elements Al Zn --t-range 300 1000 10 --output Al-Zn_diagram.png
```

## Constraints
- **Databases**: This skill strictly requires a valid `.tdb` file. 
- **Environments**: Scripts require the `calphad-agent` Conda environment because it isolates `pycalphad`.
- **Multicomponent**: This specific plotting script focuses on Binary Systems. Ternary isotherms require a separate script not yet implemented.

## References
- Richard Otis and Zi-Kui Liu. "pycalphad: CALPHAD-based Computational Thermodynamics in Python." *Journal of Open Research Software* 5.1 (2017). [DOI](https://doi.org/10.5334/jors.140)
- S. Mey, "Re-evaluation of the Al-Zn system", *Z. Metallkd.* 84(7) (1993) 451-455.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
