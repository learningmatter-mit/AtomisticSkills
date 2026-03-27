# Cu Elastic Tensor Example

Example elastic tensor calculation for FCC copper using MACE-OMAT-0-small.

## Run

```bash
# Env: mace-agent
python .agents/skills/mat-elasticity/scripts/calculate_elasticity.py \
    --structure .agents/skills/mat-elasticity/examples/Cu/Cu.cif \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir research/elasticity/Cu
```

## Expected Results

| Property | MLIP (approx.) | Experimental |
|----------|:---------:|:------------:|
| Bulk modulus (GPa) | ~130–145 | 137 |
| Shear modulus (GPa) | ~45–55 | 48 |
| Young's modulus (GPa) | ~120–140 | 130 |
| Poisson's ratio | ~0.33–0.36 | 0.34 |
