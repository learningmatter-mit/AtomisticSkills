---
name: drug-db-chembl
description: Query ChEMBL web services for targets, molecules, and curated bioactivity measurements (IC50, Ki, EC50, etc.).
category: [drug-discovery]
---

# db-chembl

## Goal
To programmatically query the ChEMBL database web services and retrieve reproducible, model-ready datasets of **targets**, **molecules**, and **bioactivities**, while preserving provenance (assay/document IDs) and enabling common curation filters (e.g., **pChEMBL**, standardized units, handling censoring operators, assay type).

ChEMBL activity data is curated and standardized, but downstream modeling still requires careful selection/filters to avoid mixing incompatible assay formats or censored measurements.

## Instructions

### 1. Search for candidate targets by name (broad recall)
Use this when you only have a gene/protein string and want candidate ChEMBL target IDs.

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --target "EGFR" \
  --max_results 20 \
  --output egfr_targets.json
```

### 2. Resolve target by UniProt accession (higher precision)
If you know a UniProt accession, this reduces ambiguity compared to free-text searching.

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --uniprot "P00533" \
  --target_type "SINGLE PROTEIN" \
  --max_results 10 \
  --output egfr_targets_uniprot.json
```

### 3. Retrieve bioactivity data for a target (recommended "model-ready" defaults)
ChEMBL web services are **paginated** (limit/offset + page_meta); this script automatically iterates pages up to `--max_results`.

Recommended for many QSAR/ML use cases:

* use standardized fields (`standard_*`)
* prefer binding assays (`--assay_type B`) when you want binding potency
* restrict to equality relations (`--standard_relation "="`) to avoid mixing censored labels
* restrict to nM for consistency (`--standard_units nM`)
* require/compute pChEMBL (comparable negative log molar potency)

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --target_id "CHEMBL203" \
  --activity_type "IC50" \
  --assay_type "B" \
  --standard_relation "=" \
  --standard_units "nM" \
  --require_pchembl \
  --pchembl_min 5.0 \
  --max_results 200 \
  --output egfr_ic50_pchembl.json
```

### 4. Look up a molecule record (ChEMBL ID or InChIKey)
Prefer **ChEMBL ID** or **InChIKey** for exact identity.

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --chembl_id "CHEMBL25" \
  --output aspirin_record.json
```

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --inchi_key "BSYNRYMUTXBXSQ-UHFFFAOYSA-N" \
  --output aspirin_record_by_inchikey.json
```

### 5. Chemical search by SMILES (similarity or substructure)
SMILES strings often differ by canonicalization; similarity/substructure search is usually more robust than "exact SMILES match."

Similarity search (default cutoff 70):

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --smiles "CC(=O)Oc1ccccc1C(=O)O" \
  --smiles_mode similarity \
  --similarity 80 \
  --max_results 10 \
  --output aspirin_similarity.json
```

Substructure search:

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --smiles "CC(=O)Oc1ccccc1C(=O)O" \
  --smiles_mode substructure \
  --max_results 10 \
  --output aspirin_substructure.json
```

### 6. Export as CSV for quick inspection

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --target_id "CHEMBL203" \
  --activity_type "IC50" \
  --assay_type "B" \
  --standard_relation "=" \
  --standard_units "nM" \
  --require_pchembl \
  --max_results 200 \
  --output egfr_ic50_pchembl.csv
```

## Examples

EGFR binding-potency dataset (IC50) with comparable pChEMBL values:

```bash
# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py --target "EGFR" --max_results 10 --output egfr_targets.json

# Env: base-agent
python .agents/skills/drug-db-chembl/scripts/query_chembl.py \
  --target_id "CHEMBL203" \
  --activity_type "IC50" \
  --assay_type "B" \
  --standard_relation "=" \
  --standard_units "nM" \
  --require_pchembl \
  --pchembl_min 5.0 \
  --max_results 200 \
  --output egfr_ic50_pchembl.json
```

## Constraints

* **Pagination**: ChEMBL web services return results in pages (`limit/offset`) with `page_meta`. Use `--max_results` to cap downloads.
* **Rate limiting / etiquette**: This script inserts a small delay between requests; you can adjust it with `--delay`.
* **Data comparability**:
  * Prefer standardized fields (`standard_type/value/units/relation`) and pChEMBL for comparable potency where appropriate.
  * Do **not** mix censored relations (`>`, `<`) into regression labels unless you explicitly model censoring.
* **Target mapping confidence**: ChEMBL assigns a 0-9 confidence score to assay-to-target mappings; consider using it when building high-precision datasets.
* **Environment**: Requires `base-agent` conda environment.
* **Dependencies**: Standard library only (`urllib`, `json`, `csv`, etc.).

---
---

**Author:** Matthew Cox  
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
