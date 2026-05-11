---
name: drug-bioactivity-assay
description: Fetch biological assays and target proteins a chemical has been tested against via PubChem.
category: [drug-discovery]
---

# Bioactivity and Assay Data Retrieval

## Goal
To programmatically retrieve the testing history of a specific chemical compound against biological targets using PubChem's Assay Summary endpoint. This skill allows filtering for "Active" outcomes, providing assay IDs (AIDs), target GeneIDs, and micromolar activity values to assess a compound's promiscuity or target specificity.

## Instructions

### 1. Extract All Assays
Retrieve all assays for a given compound (CID), regardless of outcome:

```bash
# Env: base-agent
python .agents/skills/drug-bioactivity-assay/scripts/get_assays.py \
  --cid 2244 \
  --limit 50 \
  --outdir research/aspirin_assays \
  --output aspirin_all_assays.json
```

### 2. Extract Only 'Active' Results
Use the `--active_only` flag to strictly return assays where the compound was marked as "Active" or showed positive binding/inhibition.

```bash
# Env: base-agent
python .agents/skills/drug-bioactivity-assay/scripts/get_assays.py \
  --cid 5291 \
  --active_only \
  --limit 50 \
  --outdir research/imatinib_assays \
  --output imatinib_active_assays.json
```

**Parameters**:
* `--cid`: PubChem CID of the target molecule (e.g., 5291 for Imatinib).
* `--outdir`: Directory to save the resulting JSON file.
* `--active_only`: (Optional) Flag to strictly filter results to assays where the test outcome was "Active".
* `--limit`: (Optional) Maximum number of assays to retrieve (default: 1000) to keep JSON sizes manageable.
* `--output`: (Optional) Output filename (default: `assay_summary.json`).

## Examples

We can test extracting known active targets for the cancer drug Imatinib (CID: 5291).

```bash
# Env: base-agent
python .agents/skills/drug-bioactivity-assay/scripts/get_assays.py \
  --cid 5291 \
  --active_only \
  --limit 20 \
  --outdir .agents/skills/drug-bioactivity-assay/examples/imatinib \
  --output assays_imatinib_active.json
```

## Constraints
- **Assay Availability**: Compounds with no biological testing history in PubChem will return 0 results.
- **Reporting Variations**: High-throughput screening (HTS) assay results often lack explicit target GeneIDs or quantitative Activity Values compared to confirmatory literature assays. The script retrieves whatever is available natively in the column.
- **Network Limits**: PubChem can sporadically drop connections when rendering very large assay summaries. The script automatically handles connection drops and `HTTP 503` blocking via exponential backoff.

---
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
