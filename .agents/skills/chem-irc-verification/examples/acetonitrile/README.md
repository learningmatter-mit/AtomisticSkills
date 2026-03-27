# CH3CN <-> CH3NC IRC Verification Example

IRC verification for acetonitrile/isocyanomethane isomerization using an already saddle-point-optimized TS.

## Reaction

```text
CH3CN (reactant)  <->  TS  <->  CH3NC (product)
```

## Files

| File | Description |
|------|-------------|
| `reactant_optimized.xyz` | Optimized reactant reference |
| `product_optimized.xyz` | Optimized product reference |
| `ts_optimized.xyz` | Saddle-point-optimized TS input |
| `run_example.sh` | Reproducible run script |
| `output/irc_forward.traj` | Forward IRC trajectory |
| `output/irc_reverse.traj` | Reverse IRC trajectory |
| `output/irc_forward_endpoint.xyz` | Final forward-direction endpoint |
| `output/irc_reverse_endpoint.xyz` | Final reverse-direction endpoint |
| `output/irc_verification_results.json` | Endpoint assignment, RMSD/connectivity checks, pass/fail |

## Model

| Setting | Value |
|---------|-------|
| Backend | `fairchem` |
| Model | `uma-s-1p1` |
| Task head | `omol` |
| `fmax` | `0.02` eV/A |
| IRC steps | `400` per direction |
| RMSD threshold | `0.20 A` |
| Relax endpoints | `true` |

## Usage

```bash
micromamba run -n fairchem-agent bash .agents/skills/chem-irc-verification/examples/acetonitrile/run_example.sh
```

## Example Results

| Property | Value |
|----------|-------|
| Selected mapping | `forward -> product`, `reverse -> reactant` |
| Forward-to-product RMSD | `0.1509 A` |
| Reverse-to-reactant RMSD | `0.1617 A` |
| Connectivity checks | both `true` |
| Verification passed | `true` |

## Pass Criterion

This example is considered successful when both mapped endpoint-target pairs satisfy:

- `connectivity_match = true`
- `rmsd_angstrom <= 0.20`

and the final `verification_passed` flag is `true`.
