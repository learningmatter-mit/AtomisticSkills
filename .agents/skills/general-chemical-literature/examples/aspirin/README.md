# Aspirin Literature and Patent Mapping

This example extracts cross-references mapping Aspirin (CID: `2244`) to published literature and intellectual property.

## Command

```bash
# Env: base-agent
python .agents/skills/general-chemical-literature/scripts/get_xrefs.py \
  --cid 2244 \
  --limit 50 \
  --outdir .agents/skills/general-chemical-literature/examples/aspirin \
  --output xrefs_aspirin.json
```

## Results Overview

As expected for a ubiquitous commercial drug, Aspirin yields massive returns:
- **PubMed Articles Found**: > 26,000 hits
- **Patents Found**: > 110,000 hits

The script surfaces actionable verification links:
- `https://pubmed.ncbi.nlm.nih.gov/10027656/`
- `https://patents.google.com/patent/AR-043444-A1/en`

To prevent massive JSON files during automated pipelines, the saved array of IDs in `xrefs_aspirin.json` is capped via the `--limit` argument (set to 50 here limit).
