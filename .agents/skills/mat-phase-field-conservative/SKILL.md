---
name: mat-phase-field-conservative
description: Simulate conservative phase-fields (spinodal decomposition and phase separation) using the Cahn-Hilliard equation.
category: materials
---

# Conservative Phase-Field: Cahn-Hilliard

## Goal
To simulate the morphological evolution of spinodal decomposition (phase separation) in a binary alloy system using the Cahn-Hilliard equation. This skill solves the 4th-order partial differential equation to track the conservative concentration field $c(\mathbf{r}, t)$ over time.

## Instructions

### 1. Mathematical Formulation
The Cahn-Hilliard equation describes the evolution of a conserved concentration field $c$ down a free energy gradient:
$$ \frac{\partial c}{\partial t} = \nabla \cdot \left( M \nabla \frac{\delta F}{\delta c} \right) $$
Where $M$ is the mobility, and $F$ is the Ginzburg-Landau free energy functional incorporating a double-well local potential $f(c) = a c^2(1-c)^2$ and a gradient energy penalty $\frac{\kappa}{2} |\nabla c|^2$.

### 2. Running the Spinodal Decomposition Simulation
Use the provided script to set up a 2D grid and solve the Cahn-Hilliard equation using FiPy.

```bash
# Env: phasefield-agent
python .agents/skills/mat-phase-field-conservative/scripts/run_spinodal_decomposition.py \
    --grid-size 100 \
    --dx 0.25 \
    --steps 100 \
    --dt 0.01 \
    --output spinodal_output.gif
```

**Parameters:**
- `--grid-size`: Number of grid points per dimension (e.g., `100` for a 100x100 2D grid).
- `--dx`: Size of each grid cell.
- `--steps`: Total number of time steps to run.
- `--dt`: Time step size. Use small values for stability unless using fully implicit solvers.
- `--output`: Filepath to save the resulting `.gif` animation or final `.png` image.

## Examples

### Classic Spinodal Decomposition
To benchmark the solver and reproduce the classic interconnected "worm-like" bicontinuous morphology of spinodal decomposition:

```bash
# Env: phasefield-agent
python .agents/skills/mat-phase-field-conservative/scripts/run_spinodal_decomposition.py \
    --grid-size 100 \
    --steps 200 \
    --dt 1e-2 \
    --output examples/benchmark-spinodal/classic_spinodal.gif
```

See the `examples/benchmark-spinodal/README.md` for the expected output.

## Constraints
- **Environments**: Scripts require the `phasefield-agent` Conda environment. **Each code block MUST specify the environment.**
- **Conservation**: The Cahn-Hilliard PDE inherently conserves the global integral of $c$. If using explicit time-stepping with too large of a `dt`, numerical instability may break conservation.

## References
- Cahn, J. W., & Hilliard, J. E., "Free Energy of a Nonuniform System. I. Interfacial Free Energy", *The Journal of Chemical Physics*, 1958. [DOI](https://doi.org/10.1063/1.1744102)
- Guyer, J. E., Wheeler, D., & Warren, J. A., "FiPy: Partial Differential Equations with Python", *Computing in Science & Engineering*, 2009. [DOI](https://doi.org/10.1109/MCSE.2009.52)

---

**Author:** Bowen Deng
