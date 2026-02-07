---
name: arxiv-search
description: Search and retrieve research papers from ArXiv API for scientific research.
---

# ArXiv Search

## Goal
To search for and retrieve metadata (title, authors, summary, DOI, etc.) of research papers from the ArXiv database using the official ArXiv API. This skill supports keyword, author, category, and title-based searches.

## Instructions

### 1. Simple Keyword Search
Search for papers containing specific keywords across all fields (title, abstract, authors, etc.).

```bash
# Env: base-agent
python .agent/skills/arxiv-search/scripts/arxiv_search.py "machine learning interatomic potential" --max_results 5 --output mlip_papers.json
```

### 2. Advanced Search (Authors, Categories, Title)
Combine multiple criteria to narrow down search results.

```bash
# Env: base-agent
python .agent/skills/arxiv-search/scripts/arxiv_search.py --authors "Ceder" --categories mtrl-sci --max_results 10 --output ceder_papers.json
```

**Supported Category Shortcuts:**
- `mtrl-sci`: cond-mat.mtrl-sci (Materials Science)
- `mes-hall`: cond-mat.mes-hall (Mesoscale and Nanoscale Physics)
- `comp-phys`: physics.comp-ph (Computational Physics)
- `chem-phys`: physics.chem-ph (Chemical Physics)
- `ml`: cs.LG (Machine Learning)
- `ai`: cs.AI (Artificial Intelligence)

### 3. Search in Title
Restrict the search to only the paper titles.

```bash
# Env: base-agent
python .agent/skills/arxiv-search/scripts/arxiv_search.py --title "perovskite stability" --max_results 5
```

## Examples

### Retrieval of Recent MACE Related Papers
```bash
# Env: base-agent
python .agent/skills/arxiv-search/scripts/arxiv_search.py "MACE force field" --max_results 3 --output mace_results.json
```

### Searching for Specific Authors in Materials Science
```bash
# Env: base-agent
python .agent/skills/arxiv-search/scripts/arxiv_search.py --authors "Boris Kozinsky" --categories mtrl-sci --max_results 5
```

## Constraints
- **Rate Limiting**: The ArXiv API requires a minimum of 3 seconds between requests. This script includes a small delay, but frequent calls should be avoided.
- **Environment**: Requires `base-agent` conda environment.
- **Dependencies**: Uses `feedparser` and `urllib`.
- **Metadata**: Results include ID, URL, Title, Authors, Summary, Publication Date, and DOI (if available).
