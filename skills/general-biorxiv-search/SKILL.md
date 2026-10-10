---
name: general-biorxiv-search
description: Search and retrieve preprint metadata from bioRxiv and medRxiv APIs for biological and medical research.
metadata:
  category: [general]
  venv: [cpu]
---

# bioRxiv / medRxiv Search

## Goal
Search and retrieve preprint metadata (title, authors, abstract, DOI, category, etc.) from bioRxiv and medRxiv using the official REST API. Supports keyword filtering, subject category filtering, date-range search, and DOI lookup.

## Instructions

### 1. Keyword Search (Recent Papers)
Search last 30 days for papers matching keywords in title/abstract.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/biorxiv_search.py "protein folding" --max_results 5 --output protein_folding.json
```

### 2. Date Range Search
Retrieve preprints posted in a specific date range, with optional keyword/category filter.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/biorxiv_search.py "CRISPR" --start 2025-01-01 --end 2025-06-01 --max_results 10 --output crispr_2025.json
```

### 3. Category Filter
Filter by subject category (use shortcuts or full names).

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/biorxiv_search.py --category neuroscience --days 14 --max_results 10
```

**Supported Category Shortcuts:**
- `biochemistry`, `bioinformatics`, `biophysics`
- `cancer` → cancer_biology
- `cell-bio` → cell_biology
- `dev-bio` → developmental_biology
- `ecology`, `epidemiology`, `evolution`
- `genetics`, `genomics`, `immunology`
- `microbiology`, `molecular-bio` → molecular_biology
- `neuroscience`, `pharmacology`, `physiology`
- `plant-bio` → plant_biology
- `synthetic-bio` → synthetic_biology
- `systems-bio` → systems_biology

### 4. Search medRxiv
Use `--server medrxiv` for medical preprints.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/biorxiv_search.py "COVID vaccine efficacy" --server medrxiv --max_results 5 --output covid_vaccine.json
```

### 5. DOI Lookup
Retrieve metadata for a specific preprint by DOI.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/biorxiv_search.py --doi 10.1101/2021.01.01.000000 --output paper.json
```

## Examples

Verified examples, each with its command, raw output and a field-by-field comparison against the official record:

- [DOI lookup: AlphaFold-Multimer and ESM-2](examples/doi_lookup/README.md) checks title, authors, version, posting date, category and the published-journal DOI against the bioRxiv API version list, Crossref and Europe PMC.
- [Date-range search, 2021-10-01 to 2021-10-07](examples/date_range_search/README.md) runs a keyword search and a keyword + multi-word category search over a fixed past window, with an independent recount of the matches and spot-checks against Crossref.

### Recent Neuroscience Papers
```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/biorxiv_search.py --category neuroscience --days 7 --max_results 5
```

### Genomics Papers with Keyword Filter
```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/biorxiv_search.py "single cell sequencing" --category genomics --start 2024-01-01 --end 2024-12-31 --max_results 10 --output scrna_2024.json
```

## Constraints
- **No official rate limit** specified by bioRxiv API; script includes 0.5s delay per request as courtesy.
- **Pagination**: API returns 30 results per page; script paginates automatically up to `--max_results`.
- **Keyword filtering**: Done client-side (API lacks full-text search); date range must be broad enough to surface relevant papers.
- **Environment**: Requires the `cpu` environment.
- **Dependencies**: Uses `requests`.
- **Metadata fields**: DOI, URL, title, authors, abstract, date, category, server, version, license, published journal (if available).

---

**Author:** mlederbauer
**Contact:** [GitHub @learningmatter-mit](https://github.com/learningmatter-mit)
