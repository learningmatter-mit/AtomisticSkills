# Imatinib Bioactivity Assay Search

This example demonstrates how to find target proteins and bioassays where Imatinib (CID: `5291`) exhibited active biological behavior in PubChem.

## Command

```bash
# Env: base-agent
python .agents/skills/drug-bioactivity-assay/scripts/get_assays.py \
  --cid 5291 \
  --active_only \
  --limit 20 \
  --outdir .agents/skills/drug-bioactivity-assay/examples/imatinib \
  --output assays_imatinib_active.json
```

## Results Overview

Imatinib is a famous tyrosine kinase inhibitor (Gleevec). 
Filtering strictly for "Active" outcomes returned massive evidence of target specific activity (1105 positive assays).

The JSON output contains details including:
- **AID**: PubChem Assay ID (e.g., `1433`: Kinase Inhibitor Selectivity Profiling Assay)
- **Target GeneID**: The specific human gene targeted (e.g., `3815` corresponding to KIT proto-oncogene)
- **Activity Value**: Confirmed IC50/Ki values in micromolar (`uM`), with values ranging heavily in the low nanomolar space (`0.014 uM`).

All JSON records are compiled directly in `assays_imatinib_active.json`.
