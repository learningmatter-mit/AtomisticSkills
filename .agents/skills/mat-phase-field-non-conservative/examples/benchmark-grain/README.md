# Grain Growth Benchmark

This repository demonstrates canonical Phase-Field simulation of capillarity-driven interface shrinking (Grain Growth) using the Allen-Cahn equation.

## Theory

The Allen-Cahn equation characterizes the diffusion-less transformation governed by structural transformation:
$$ \frac{\partial \phi}{\partial t} = M \left( \epsilon^2 \nabla^2 \phi - \frac{\partial f(\phi)}{\partial \phi} \right) $$

For a phase separating a single circular grain, the local curvature $K$ causes morphological boundary migration. The classic mathematical proof of Allen-Cahn states that the interface migrates with a normal velocity proportional to the mean curvature $v_n = M \gamma K$, which for 2D circles translates to a linearly shrinking area.

## Literature Validation

Our simulated results successfully recover the exact analytical metrics of 2D curvature-driven boundary migration proven for the Allen-Cahn formulation:
- **Curvature Velocity Law:** The theoretical normal border velocity is $v_n = M \gamma K$. For a shrinking 2D circular boundary, this prescribes that the boundary rate of change $dR/dt \propto -1/R$. 
- **Area Decay Metric:** Integrating this velocity yields a strictly linear decay in the total grain area: $A(t) = A_0 - 2 \pi M \gamma t$. Our provided metric output, `grain_growth_area_decay.png`, precisely plots the topological boundary phase area sweeping linearly to zero with a constant slope $dA/dt = \text{const}$. Validating this strict linear metric is the classical gold standard for calibrating capillarity forces in phase-field frameworks.

**Reference:**
> Allen, S. M., & Cahn, J. W. (1979). A macroscopic theory for antiphase boundary motion and its application to antiphase domain coarsening. *Acta Metallurgica*, 27(6), 1085-1095.

## Output

Below is the expected canonical Grain Shrinkage behavior output produced by our FiPy script:

![Grain Growth Shrinkage](classic_shrinking_grain.gif)

## Implementation Note: Double-Well Potential
The thermodynamic driving force in Allen-Cahn is the exact gradient of the local free energy $f(\phi) = W\phi^2(1-\phi)^2$. Its derivative acts as the restorative force enforcing rigid phase barriers: $\frac{\partial f}{\partial \phi} = 2W\phi(1-\phi)(1-2\phi)$.
A known implementation failure is mistakenly omitting the mathematical negative sign applied to the force (yielding essentially an inverted "double barrier" potential). If the restorative potential erroneously repels phases towards an arbitrary $0.5$ midpoint rather than binding them strictly to $0$ and $1$, the interface completely loses all sharp spatial constraints and destructively smears into a diffuse Gaussian mass, eliminating tracking of boundary metrics. By definitively locking the mathematical source formulation and verifying strict double-well boundary clamping, local curvature integrity is stably preserved across physical timescales.

## Reproduction

Run the following command from the project root using the `phasefield-agent` environment:

```bash
python .agents/skills/mat-phase-field-non-conservative/scripts/run_grain_growth.py \
    --grid-size 50 \
    --radius 15 \
    --steps 150 \
    --dt 0.1 \
    --output .agents/skills/mat-phase-field-non-conservative/examples/benchmark-grain/grain_growth.gif
```
