# EGFR ChEMBL Query Example

This example demonstrates querying ChEMBL for human EGFR (Epidermal Growth Factor Receptor) targets and their binding IC50 data with pChEMBL filtering.

## Files

- `egfr_targets.json`: Target search results for "EGFR" (single proteins only)
- `egfr_ic50_activities.json`: Curated IC50 binding activities for human EGFR (CHEMBL203), filtered to equality relations, nM units, and pChEMBL >= 5.0

## How to reproduce

From the project root:

```bash
# Env: base-agent
# Step 1: Search for EGFR targets
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --target "EGFR" \
  --target_type "SINGLE PROTEIN" \
  --max_results 5 \
  --output .agents/skills/drug-db-chembl/examples/egfr_targets.json

# Step 2: Get IC50 binding activities for human EGFR
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --target_id "CHEMBL203" \
  --activity_type "IC50" \
  --assay_type "B" \
  --standard_relation "=" \
  --standard_units "nM" \
  --require_pchembl \
  --pchembl_min 5.0 \
  --max_results 5 \
  --output .agents/skills/drug-db-chembl/examples/egfr_ic50_activities.json
```

## Results

Step 1 returns 2 EGFR single-protein targets (human and mouse):

| ChEMBL ID | Organism | UniProt |
|---|---|---|
| CHEMBL203 | Homo sapiens | P00533 |
| CHEMBL3608 | Mus musculus | Q01279 |

Step 2 returns 5 IC50 binding records for human EGFR with pChEMBL values ranging from 5.03 to 7.39 (i.e., IC50 from ~41 nM to ~9300 nM).
