# Hypothetical Testing Examples

This module allows you to cleanly test the Generalized Catalysis Activity Framework using hypothetical theoretical data subsets, purely isolated from any HTVS database access. 

This is incredibly useful for validating that proper scaling relationships and thermodynamic offsets are rendering correctly before plugging in complex experimental payloads.

## Included Standard Baselines

The hypothetical subset provides standard generic binding energy values (derived mathematically relative to standard intermediate offsets) for five common screening surfaces across $OER$:
- `Pt(111)`
- `IrO2(110)`
- `RuO2(110)`
- `NiFeOx(001)`
- `Co3O4(311)`

## Execution Instructions

To execute a test run and visualize how the Volcano plotting algorithms automatically scale and map these reference data values, simply run:

```bash
# Env: htvs-agent
python test_hypothetical.py --reaction OER --output_dir ./test_out
```

### Outputs
- **`test_out/[rxn]_volcano.png`**: Inspect the resulting analytical model demonstrating automated scaling fits applied across the dummy geometries.
- **`test_out/[rxn]_free_energy_steps.png`**: Inspect the step-diagram to ensure the thermodynamic cascades correctly traverse the equilibrium bounds for your requested `--reaction`.
