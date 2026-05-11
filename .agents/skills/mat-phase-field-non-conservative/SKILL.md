---
name: mat-phase-field-non-conservative
description: Simulate non-conservative phase-fields (grain growth and phase transformations) using the Allen-Cahn equation.
category: materials
---

# Non-Conservative Phase-Field: Allen-Cahn

## Goal
To simulate the morphological evolution of structural transformations (like solidification, melting, or curvature-driven grain growth) using the Allen-Cahn (time-dependent Ginzburg-Landau) equation. This tracks a non-conservative order parameter $\phi$ which distinguishes between phases (e.g., solid vs. liquid).

## Instructions

### 1. Mathematical Formulation
The Allen-Cahn equation describes the evolution of a non-conserved order parameter $\phi$ down a free energy gradient:
$$ \frac{\partial \phi}{\partial t} = -M \frac{\delta F}{\delta \phi} = M \left( \epsilon^2 \nabla^2 \phi - \frac{\partial f(\phi)}{\partial \phi} \right) $$
Where $M$ is the mobility, $\epsilon$ is the gradient energy coefficient controlling the interface thickness, and $f(\phi) = W \phi^2(1-\phi)^2$ is the double-well potential barrier between the two phases ($\phi=0$ and $\phi=1$). 

Unlike Cahn-Hilliard, Allen-Cahn does not conserve the integral of $\phi$. It naturally drives systems to reduce their total interfacial area, resulting in curvature-driven boundary migration.

### 2. Running Curvature-Driven Grain Growth
Use the provided script to set up a 2D grid containing a circular solid grain in a liquid matrix and observe its capillarity-driven shrinkage.

```bash
# Env: phasefield-agent
python .agents/skills/mat-phase-field-non-conservative/scripts/run_grain_growth.py \
    --grid-size 100 \
    --radius 30 \
    --steps 200 \
    --dt 0.1 \
    --output grain_growth.gif
```

**Parameters:**
- `--grid-size`: Number of grid points per dimension (e.g., `100` for a 100x100 2D grid).
- `--radius`: Initial radius of the circular grain in grid units.
- `--steps`: Total number of time steps to run.
- `--dt`: Time step size.
- `--output`: Filepath to save the resulting `.gif` animation or `.png`.

## Examples

### Classic Shrinking Circular Grain
A universal mathematical benchmark for the Allen-Cahn equation is proving that a circular domain shrinks at a rate proportional to its curvature (the $v = M \gamma K$ law). The area of the circle must decrease linearly with time.

```bash
# Env: phasefield-agent
python .agents/skills/mat-phase-field-non-conservative/scripts/run_grain_growth.py \
    --grid-size 100 \
    --radius 35 \
    --steps 300 \
    --dt 0.5 \
    --output examples/benchmark-grain/classic_shrinking_grain.gif
```

See the `examples/benchmark-grain/README.md` for the expected output.

## Constraints
- **Environments**: Scripts require the `phasefield-agent` Conda environment. **Each code block MUST specify the environment.**
- **Interface Thickness**: The spatial resolution `dx` must be small enough to resolve the diffuse interface (typically requiring at least 4-5 grid points across the interface controlled by $\epsilon$).

## References
- Allen, S. M., & Cahn, J. W., "A macroscopic theory for antiphase boundary motion and its application to antiphase domain coarsening", *Acta Metallurgica*, 1979. [DOI](https://doi.org/10.1016/0001-6160(79)90196-2)

---

**Author:** Bowen Deng
