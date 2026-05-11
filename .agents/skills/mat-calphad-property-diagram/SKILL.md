---
name: mat-calphad-property-diagram
description: Calculate temperature-dependent thermodynamic properties like Equilibrium Phase Fractions for a specific alloy composition using CALPHAD models.
category: materials
---

# mat-calphad-property-diagram

## Goal
To predict the equilibrium phase stability, phase fractions, and other extensive thermodynamic properties for a fixed multi-component alloy at different temperatures using PyCalphad. Very useful for modeling solidification, heat treatment paths, and precipitation sequences.

## Instructions

### 1. Identify Thermodynamic Database
You must obtain a legitimate `.tdb` (Thermodynamic Data Base) file for the chemical system.

### 2. Plot Equilibrium Phase Fractions
Calculate what phases are present, and their molar fractions, across a cooling/heating schedule for a fixed composition.

```bash
# Env: calphad-agent
python .agents/skills/mat-calphad-property-diagram/scripts/plot_phase_fractions.py path/to/database.tdb --elements Element1 Element2 --composition Element2 0.3 --t-range 300 1000 10 --output research_dir/phase_fractions.png
```

- `--composition`: The solute element and its molar fraction (e.g. `Zn 0.3` means 30 mol% Zn).
- `--t-range`: `START STOP STEP` in Kelvin. Ensure solving across liquidus and solidus.

## Examples

Evaluating phase fractions for an Al-40%Zn alloy as it cools:
```bash
# Env: calphad-agent
python .agents/skills/mat-calphad-property-diagram/scripts/plot_phase_fractions.py .agents/skills/mat-calphad-phase-diagram/examples/Al-Zn/alzn_mey.tdb --elements Al Zn --composition Zn 0.4 --t-range 300 900 10 --output phase_fractions.png
```

## Constraints
- **Environments**: Scripts require the `calphad-agent` Conda environment.
- Only plots equilibrium step (lever-rule). For non-equilibrium fast solidification (Scheil), custom scripting is required.

## References
- Richard Otis and Zi-Kui Liu. "pycalphad: CALPHAD-based Computational Thermodynamics in Python." *Journal of Open Research Software* (2017).

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
