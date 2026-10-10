---
name: general-arxiv-search
description: Search and retrieve research papers from ArXiv API for scientific research.
metadata:
  category: [general]
  venv: [cpu]
---

# ArXiv Search

## Goal
To search for and retrieve metadata (title, authors, summary, DOI, etc.) of research papers from the ArXiv database using the official ArXiv API. This skill supports keyword, author, category, and title-based searches.

## Instructions

### 1. Simple Keyword Search
Search for papers containing specific keywords across all fields (title, abstract, authors, etc.).

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/arxiv_search.py "machine learning interatomic potential" --max_results 5 --output mlip_papers.json
```

### 2. Advanced Search (Authors, Categories, Title)
Combine multiple criteria to narrow down search results.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/arxiv_search.py --authors "Ceder" --categories mtrl-sci --max_results 10 --output ceder_papers.json
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
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/arxiv_search.py --title "perovskite stability" --max_results 5
```

## Examples

Verified examples, each with its command, raw output and a comparison against the official arXiv record:

- [Title search: the MACE paper](examples/title_search_mace/README.md) finds arXiv:2206.07697 and checks ID, authors, submission dates, categories, DOI and journal reference against its arXiv abstract page.
- [Keyword + category search: MLIPs in cond-mat.mtrl-sci](examples/keyword_category_mlip/README.md) checks that the top 10 results are all on-topic, spot-checks two of them against their abstract pages, and documents the query-construction fix.

### Retrieval of Recent MACE Related Papers
```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/arxiv_search.py "MACE force field" --max_results 3 --output mace_results.json
```

### Searching for Specific Authors in Materials Science
```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/arxiv_search.py --authors "Boris Kozinsky" --categories mtrl-sci --max_results 5
```

## Constraints
- **Query Semantics**: Every word of the keyword and `--title` strings must match (AND); wrap a phrase in double quotes inside the string to match it verbatim (e.g. `'"machine learning" potential'`). Each `--authors` name is matched as a phrase, and several `--categories` are OR-ed.
- **Rate Limiting**: The ArXiv API requires a minimum of 3 seconds between requests. This script includes a small delay, but frequent calls should be avoided.
- **Environment**: Requires the `cpu` environment.
- **Dependencies**: Uses `feedparser` and `urllib`.
- **Metadata**: Results include ID, URL, Title, Authors, Summary, Publication Date, and DOI (if available).
---

**Author:** Bowen Deng
**Contact:** [GitHub @learningmatter-mit](https://github.com/learningmatter-mit)
