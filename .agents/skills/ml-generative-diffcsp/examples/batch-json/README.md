# Batch JSON Generation

Example of generating multiple structures from a JSON specification file.

## Run

```bash
# Env: diffcsp-agent
python .agents/skills/ml-generative-diffcsp/scripts/batch_generate.py \
    --json_file .agents/skills/ml-generative-diffcsp/examples/example.json \
    --model mp_csp \
    --output_dir research/diffcsp_batch
```

## Input

The example JSON (`../example.json`) specifies two structures:
1. **MnLiO** — Spacegroup 58, Wyckoff 2a+2d+4g
2. **TmNiAs** — Spacegroup 194, Wyckoff a+b+f+f

## Expected Results

- 2 CIF files generated (one per JSON entry)
- **Generation time**: ~5 seconds on GPU
- Each structure satisfies the specified symmetry constraints exactly

## Files

- `structure_0000.cif` — MnLiO (spacegroup 58)
- `structure_0001.cif` — TmNiAs (spacegroup 194)
- `generation_metadata.json` — Generation parameters
