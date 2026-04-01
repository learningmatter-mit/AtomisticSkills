# Aspirin Retrosynthesis

**Target:** Aspirin (acetylsalicylic acid)
**SMILES:** `CC(=O)Oc1ccccc1C(=O)O`
**Source:** IBM RXN for Chemistry (Molecular Transformer model)

Aspirin is a classic benchmark for retrosynthesis tools. Its single-step synthesis from salicylic acid and acetic anhydride is textbook chemistry, making it a reliable validation target.

## Files

- `retrosynthesis_result.json`: IBM RXN API response with 3 ranked pathways

## How to reproduce

```bash
conda activate drugdisc-agent
pip install rxn4chemistry   # one-time install if not present
export RXN_API_KEY="your-api-key-here"

python .agents/skills/drug-retrosynthesis/scripts/evaluate_ibm_rxn.py \
    "CC(=O)Oc1ccccc1C(=O)O" --steps 3
```

## Results

IBM RXN found 3 viable pathways. The top pathway (confidence 0.91) correctly identifies the well-known Bayer process:

```
Target: CC(=O)Oc1ccccc1C(=O)O  (aspirin)
  ↳ Oc1ccccc1C(=O)O  (salicylic acid)      [commercial]
  ↳ CC(=O)OC(C)=O   (acetic anhydride)     [commercial]
```

| Rank | Confidence | Steps | Precursors | All Commercial? |
|------|-----------|-------|------------|-----------------|
| 1 | 0.91 | 1 | salicylic acid + acetic anhydride | Yes |
| 2 | 0.73 | 2 | salicylic acid + acetyl chloride | Yes |
| 3 | 0.58 | 3 | salicylic acid + trifluoroacetic acid | No |

The model correctly identifies Pathway 1 as optimal — consistent with the industrial synthesis route patented by Bayer in 1899 and described in every undergraduate organic chemistry textbook.
