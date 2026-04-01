# CH3CN <-> CH3NC TS Optimization Example

Transition-state optimization for acetonitrile/isocyanomethane isomerization using Sella with FAIRChem UMA (`omol`).

## Reaction

```text
CH3CN (acetonitrile)  <->  CH3NC (isocyanomethane)
```

## Files

| File | Description |
|------|-------------|
| `reactant_ch3cn.xyz` | Reactant reference geometry (CH3CN) |
| `product_ch3nc.xyz` | Product reference geometry (CH3NC) |
| `ts_guess.xyz` | Initial TS guess used by Sella |
| `run_example.sh` | Reproducible run script |
| `output/ts_optimized.xyz` | Optimized TS geometry |
| `output/ts_opt.traj` | TS optimization trajectory |
| `output/ts_opt.log` | Optimizer log |
| `output/ts_optimization_results.json` | Frequency analysis + TS pass/fail summary |

## Model

| Setting | Value |
|---------|-------|
| Backend | `fairchem` |
| Model | `uma-s-1p1` |
| Task head | `omol` |
| `fmax` | `0.02` eV/A |
| Steps | `500` |
| Imaginary cutoff | `< -50 cm^-1` |

## Usage

```bash
micromamba run -n fairchem-agent bash .agents/skills/chem-ts-optimization/examples/acetonitrile/run_example.sh
```

## Example Results

| Property | Value |
|----------|-------|
| Sella converged | `true` |
| Optimization steps | `52` |
| Max force | `0.00345` eV/A |
| Imaginary modes below `-50 cm^-1` | `1` |
| Lowest mode | `-424.53 cm^-1` |
| First-order saddle | `true` |

## Pass Criterion

This example is considered successful when `output/ts_optimization_results.json` reports:

- `n_imag_below_cutoff = 1`
- `is_first_order_saddle = true`
