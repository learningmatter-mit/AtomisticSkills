---
name: chem-hazard-toxicity
description: Extract explicit safety warnings, GHS classifications, and LD50 profiles from PubChem PUG VIEW.
category: [chemistry, drug-discovery]
---

# Chemical Hazard and Toxicity Profiling

## Goal
To programmatically extract critical safety information from the PubChem PUG-VIEW API. This skill pulls GHS Classifications, Hazard Classes, and Toxicological properties (like LD50/LC50 experimental animal records) for a given compound based on its CID.

## Instructions

### 1. Extract Safety Profile by CID
Provide the precise CID of the molecule targeting the specific record to query safety metadata. The output is a JSON array of natural language texts sourced from chemical vendors, safety data sheets, and literature.

```bash
# Env: base-agent
python .agents/skills/chem-hazard-toxicity/scripts/get_safety_data.py \
  --cid 2519 \
  --outdir research/caffeine_safety \
  --output safety_caffeine.json
```

## Examples

We can test the extraction for Caffeine (CID: 2519), a well documented compound.

```bash
# Env: base-agent
python .agents/skills/chem-hazard-toxicity/scripts/get_safety_data.py \
  --cid 2519 \
  --outdir .agents/skills/chem-hazard-toxicity/examples/caffeine \
  --output safety_caffeine.json
```

## Constraints
- **Data Availability**: This relies exclusively on experimental or reported data listed in PubChem. Some newly generated molecules or obscure reagents may have empty safety profiles.
- **Network Limits**: PubChem PUG VIEW can be rate-limited under heavy load. The script automatically handles standard `HTTP 503` blocking via exponential backoff.

---
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
