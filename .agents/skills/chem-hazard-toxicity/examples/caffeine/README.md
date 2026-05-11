# Caffeine Hazard and Toxicity Logging

This example demonstrates how to retrieve the GHS Hazard, Hazard Classes, and Toxicity logging items for Caffeine (CID: `2519`) using the PubChem PUG VIEW API.

## Command

```bash
# Env: base-agent
python .agents/skills/chem-hazard-toxicity/scripts/get_safety_data.py \
  --cid 2519 \
  --outdir .agents/skills/chem-hazard-toxicity/examples/caffeine \
  --output safety_caffeine.json
```

## Results Overview

The agent recovered a comprehensive safety profile:
- **GHS Strings**: 14 items (e.g. `H302: Harmful if swallowed [Warning Acute toxicity, oral]`)
- **Hazard Classes**: 8 items (e.g. `Acute Tox. 4 (99.85%)`)
- **Toxicity Records**: 50 items (ranging from oral to intravenous acute toxicity tests in multiple species like rats, mice, and rabbits).

All texts are compiled directly in `safety_caffeine.json`.
