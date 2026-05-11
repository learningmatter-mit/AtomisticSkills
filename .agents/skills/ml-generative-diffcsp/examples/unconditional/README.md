# Unconditional (Ab Initio) Generation

Example of generating crystal structures unconditionally from the MP-20 training distribution.

## Run

```bash
# Env: diffcsp-agent
python .agents/skills/ml-generative-diffcsp/scripts/unconditional_generate.py \
    --model mp_gen \
    --num_structures 5 \
    --output_dir research/diffcsp_gen
```

## Expected Results

- 5 CIF files with diverse compositions and space groups sampled from MP-20
- **Generation time**: ~4 minutes (includes ~3 min data loading + ~20s diffusion)
- Structures may contain any elements and space groups present in the training set

> **Note**: First run loads the full MP-20 training dataset for atom type distributions.
> This is a one-time cost from DiffCSP++'s generation pipeline.

## Files

- [structure_0000.cif](structure_0000.cif) — Example generated structure
- `generation_metadata.json` — Generation parameters
