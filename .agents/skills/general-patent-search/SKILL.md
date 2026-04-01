---
name: general-patent-search
description: Search for patents by keyword, material name, or assignee using free data sources (Google Patents).
category: general
---

# general-patent-search

## Goal
To retrieve patent information (titles, assignees, dates, and snippets) for specific materials, chemicals, or technologies to assess novelty, freedom-to-operate, and existing intellectual property landscapes. This skill uses Google Patents for free, global, no-key-required patent querying.

## Instructions

### 1. Identify Target and Scope
Determine exactly what you are searching for.
- Are you looking for a specific chemical? (e.g., "tetrafluoropropene")
- Are you looking for a specific company's IP? (e.g., assignee "SK Innovation")

### 2. Search Strategy (Google Patents)
Use the python script to query Google Patents. It will return global patents matching your query string.

```bash
# Env: base-agent
python .agents/skills/general-patent-search/scripts/query_google_patents.py "query string" --limit 10
```

## Examples

Searching for recent global patents on a novel refrigerant by chemical name:
```bash
# Env: base-agent
python .agents/skills/general-patent-search/scripts/query_google_patents.py "tetrafluoropropene OR HFO-1234yf" --limit 5
```

Searching for global patents assigned to SK Innovation regarding electrolytes:
```bash
# Env: base-agent
python .agents/skills/general-patent-search/scripts/query_google_patents.py "assignee:(SK Innovation) AND electrolyte" --limit 5
```

## Constraints
- **Environments**: The script requires the `base-agent` Conda environment.
- **Google Patents Limits**: The scraping script is sensitive to IP rate-limiting. Do not set `--limit` excessively high (keep under 50).
- **Chemical Structures**: This tool performs **text-based** searches. It does not perform exact Substructure or Tanimoto similarity searches natively. You must provide textual synonyms (e.g., IUPAC names, trade names) for accurate chemical retrieval.

## References
- Google Patents: https://patents.google.com/

---

**Author:** Sathya Edamadaka  
**Contact:** [GitHub @snme](https://github.com/snme)
