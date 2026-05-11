---
name: general-chemical-literature
description: Retrieve extensive literature (PubMed) and patent associated with a specific chemical compound via PubChem.
category: [general, chemistry, drug-discovery, materials]
---

# Chemical Literature and Patent Mapping

## Goal
To programmatically check if a specific chemical compound exists in recent literature or patent databases. This skill uses PubChem's PUG-REST XRefs endpoint to extract an exhaustive list of associated PubMed IDs and Patent numbers. 

This is incredibly useful as an autonomous "novelty check" for generated molecules.

## Instructions

### 1. Extract Literature and Patents by CID
Provide the CID of the target molecule. By default, the script will output the absolute total number of hits but limits the JSON save array to `1000` to prevent memory flooding for ubiquitous molecules (like Aspirin, which has over 100,000 patents). Adjust `--limit` as needed.

```bash
# Env: base-agent
python .agents/skills/general-chemical-literature/scripts/get_xrefs.py \
  --cid 2244 \
  --limit 50 \
  --outdir research/aspirin_literature \
  --output xrefs_aspirin.json
```

## Examples

We can pull cross-references for Aspirin (CID: 2244), saving the top 50 identifiers.

```bash
# Env: base-agent
python .agents/skills/general-chemical-literature/scripts/get_xrefs.py \
  --cid 2244 \
  --limit 50 \
  --outdir .agents/skills/general-chemical-literature/examples/aspirin \
  --output xrefs_aspirin.json
```

## Constraints
- **Novelty Assessment Limitation**: If 0 PMIDs or Patents are returned, it strongly implies the molecule is highly novel (or purely computational), but it does not guarantee absolute non-existence.
- **Link Generation**: The script automatically prints actionable links (`pubmed.ncbi.nlm.nih.gov/` and `patents.google.com/patent/`) for the top 5 results for immediate verification.
- **Network Limits**: Handled internally via standard exponential backoff.

---
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
