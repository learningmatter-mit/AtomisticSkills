# Aspirin Analogs Similarity Search

This example demonstrates how to find structurally similar compounds (analogs) to Aspirin (CID: `2244`) using PubChem's `fastsimilarity_2d` engine.

## Command

```bash
# Env: base-agent
python .agents/skills/chem-similarity-search/scripts/similarity_search.py \
  --cid 2244 \
  --threshold 95 \
  --max_records 5 \
  --outdir .agents/skills/chem-similarity-search/examples/aspirin_analogs \
  --output aspirin_analogs.json
```

## Results Overview

With a high structural similarity threshold (`95%`), the query returned 5 close analogs of Aspirin:

1. **Aspirin** (CID: 2244, MW: 180.16) - `CC(=O)OC1=CC=CC=C1C(=O)O`
2. **Salsalate** (CID: 5161, MW: 258.23) - `C1=CC=C(C(=C1)C(=O)OC2=CC=CC=C2C(=O)O)O`
3. **Methyl acetylsalicylate** (CID: 68484, MW: 194.18) - `CC(=O)OC1=CC=CC=C1C(=O)OC`
4. **Phenyl salicylate** (CID: 61159, MW: 228.24) - `CC1=CC=CC=C1OC(=O)C2=CC=CC=C2O`
5. **Aloxiprin/Polymer precursor** (CID: 10745, MW: 300.26) - `CC(=O)OC1=CC=CC=C1C(=O)OC2=CC=CC=C2C(=O)O`

All outputs were saved to `aspirin_analogs.json`.
