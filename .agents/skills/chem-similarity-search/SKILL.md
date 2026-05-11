---
name: chem-similarity-search
description: Find structurally similar chemical compounds using PubChem's 2D fast similarity engine via the PUG-REST API.
category: [chemistry, drug-discovery]
---

# Chemical Similarity Search

## Goal
To programmatically find chemical analogs, alternative precursors, and structurally similar compounds for a given target molecule using PubChem's "fastsimilarity_2d" endpoint. The skill retrieves lists of similar compounds ranked by sequence alignment of their 2D molecular fingerprints, providing CIDs, molecular weights, formulas, and SMILES strings.

## Instructions

### 1. Search by SMILES String
Search for similar compounds by providing the canonical or isomeric SMILES. 
Adjust the `--threshold` (similarity cutoff 0-100, default is 95) to widen or narrow the search radius. Higher threshold equals higher similarity.
Adjust `--max_records` to limit the output length.

```bash
# Env: base-agent
python .agents/skills/chem-similarity-search/scripts/similarity_search.py \
  --smiles "CC(=O)Oc1ccccc1C(=O)O" \
  --threshold 95 \
  --max_records 5 \
  --outdir research/aspirin_similar \
  --output aspirin_similar.json
```

### 2. Search by PubChem CID
Search directly using an exact compound's CID. This avoids translation steps for SMILES parsing.

```bash
# Env: base-agent
python .agents/skills/chem-similarity-search/scripts/similarity_search.py \
  --cid 2244 \
  --threshold 90 \
  --max_records 10 \
  --outdir research/aspirin_similar \
  --output cid_2244_similar.json
```

## Examples

We can test extracting highly similar analogs (Threshold 95) for Aspirin (CID: 2244 or SMILES: `CC(=O)Oc1ccccc1C(=O)O`).

```bash
# Env: base-agent
python .agents/skills/chem-similarity-search/scripts/similarity_search.py \
  --cid 2244 \
  --threshold 95 \
  --max_records 5 \
  --outdir .agents/skills/chem-similarity-search/examples/aspirin_analogs \
  --output aspirin_analogs.json
```

## Constraints
- **Rate Limiting**: PubChem PUG REST API enforces per-user throttling limits. Heavy bursts will result in `HTTP 503 Server Busy` errors. The script implements an exponential backoff retry mechanism.
- **2D Similarity**: Uses exact structural bit-vector fingerprints. Stereochemical and 3D properties do not strongly affect the score.
- **Network**: Internet access is required.

---
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
