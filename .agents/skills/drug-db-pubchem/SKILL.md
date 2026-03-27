---
name: drug-db-pubchem
description: Query PubChem via PUG-REST to retrieve CIDs, computed properties, synonyms, and 2D/3D SDF structures.
category: [drug-discovery]
---

# PubChem Database Query

## Goal
To programmatically query the PubChem Compound database using the PUG-REST API and retrieve:
- PubChem Compound IDs (CIDs) from names, SMILES, InChI, InChIKey, or molecular formulas,
- computed molecular properties (e.g., molecular weight, XLogP, TPSA, HBD/HBA),
- optional synonyms (names/identifiers),
- optional structure files (SDF), preferring 3D records when available.

This skill is designed for reproducible, rate-limited queries suitable for automation workflows.

## Instructions

### 1. Search by Compound Name
Look up a compound by its common name. Use `--name_type complete` (default) for exact match or `--name_type word` for partial matching.

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --name "aspirin" \
  --name_type complete \
  --max_results 5 \
  --outdir research/pubchem/aspirin \
  --output aspirin.json
```

For partial name matching (can be noisier):

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --name "atorvastatin" \
  --name_type word \
  --max_results 10 \
  --outdir research/pubchem/atorvastatin \
  --output atorvastatin_word.json
```

### 2. Search by SMILES
SMILES may contain characters reserved by URL syntax; this script uses HTTP POST to avoid common failures.

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --smiles "CC(=O)Oc1ccccc1C(=O)O" \
  --max_results 5 \
  --outdir research/pubchem/aspirin_smiles \
  --output aspirin_smiles.json
```

### 3. Search by CID
Most unambiguous lookup method.

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --cid 2244 \
  --outdir research/pubchem/CID_2244 \
  --output cid_2244.json
```

### 4. Search by InChI or InChIKey
InChI uses HTTP POST (like SMILES) to avoid URL syntax issues.

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --inchikey "BSYNRYMUTXBXSQ-UHFFFAOYSA-N" \
  --outdir research/pubchem/aspirin_inchikey \
  --output aspirin_inchikey.json
```

### 5. Search by Molecular Formula
Uses `fastformula` for synchronous molecular formula search. Optionally allow additional elements for broader results.

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --formula "C9H8O4" \
  --max_results 10 \
  --outdir research/pubchem/C9H8O4 \
  --output formula_results.json
```

Allow other elements (broader search):

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --formula "C6H12O6" \
  --allow_other_elements \
  --max_results 10 \
  --outdir research/pubchem/C6H12O6_allow_other \
  --output formula_allow_other.json
```

### 6. Download SDF Structures (2D/3D)
PubChem 3D records are computationally generated and may be unavailable for some CIDs; the script falls back to 2D by default.

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --name "ibuprofen" \
  --download_sdf \
  --sdf_record_type 3d \
  --outdir research/pubchem/ibuprofen \
  --output ibuprofen.json
```

### 7. Disable Synonyms
Synonyms require extra API calls; disable them for high-throughput workflows.

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --cid 2244 \
  --no_synonyms \
  --outdir research/pubchem/CID_2244_minimal \
  --output cid_2244_minimal.json
```

## Examples

Caffeine (download 3D SDF if available):

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --name "caffeine" \
  --download_sdf \
  --sdf_record_type 3d \
  --outdir research/pubchem/caffeine \
  --output caffeine.json
```

## Constraints
- **Rate Limiting**: PubChem enforces per-user limits (~5 requests/sec, plus per-minute limits). Exceeding limits triggers HTTP 503 responses. The script rate-limits via a sliding window and retries with exponential backoff. It also adapts to PubChem's dynamic throttling feedback via the `X-Throttling-Control` header.
- **Request Time Limit**: PUG-REST is intended for short synchronous requests (server timeouts ~30 seconds). Keep `--max_results` small for interactive use.
- **3D Structures**: PubChem 3D SDF records are computed (not necessarily experimental) and may not exist for all compounds; the script falls back to 2D when needed.
- **Synonyms**: Synonyms may be numerous and are optional; disable them with `--no_synonyms` for high-throughput workflows.
- **Environment**: Requires `base-agent` conda environment.
- **Dependencies**: Standard library only (`urllib`, `json`, `argparse`).

---
---

**Author:** Matthew Cox  
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
