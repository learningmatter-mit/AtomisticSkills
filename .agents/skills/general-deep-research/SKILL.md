---
name: general-deep-research
description: Perform iterative, deep, and comprehensive literature research on a specific materials/chemistry topic.
category: general
---

# Deep Research

## Goal
To perform an in-depth, iterative, and comprehensive literature and web research campaign to answer complex scientific questions (e.g., "What are the synthesis methods and solid-state electrolyte performance of LiInCl3?"). This skill produces a high-quality, synthesized research report with citations, significantly exceeding the depth of a single simple literature query.

## Instructions

When the user requests deep research on a topic, the agent MUST follow this multi-step iterative protocol. Do not implement this as a python script, but rather execute these steps logically using your own tool-calling capabilities.

### Step 1: Query Formulation & Planning
Break down the user's broad research topic into 3-5 specific sub-queries. 
**CRITICAL**: You must try different permutations and synonyms for the material or topic. For example, if the topic is `LiInCl3`, your queries must include variations like `LiInCl3`, `Li-In-Cl`, `Lithium Indium Chloride`, `Li3InCl6`, etc., to ensure no literature is missed.

Create a rough outline for the final research report in your task plan.

### Step 2: Iterative Literature Search
For *each* sub-query, use the `mcp_base_search_literature` tool to search the OpenAlex database. **Always set `download=True`** to attempt downloading the full text of discovered papers.

```bash
mcp_base_search_literature(
    query="Lithium Indium Chloride ionic conductivity",
    limit=50, 
    download=True
)
```

**CRITICAL**: You must NOT rely solely on the literature search tool. You must ALSO perform a general web search using the `search_web` tool for all your queries. This captures recent publications, patents, reviews, and data that OpenAlex might miss.

```bash
search_web(
    query="Li-In-Cl solid state electrolyte review"
)
```

### Step 3: Information Extraction & Synthesis
Do not just list papers. You must read the content (or the provided summaries/full texts from the MCP tool). 
Extract specific numbers, methodologies, and limitations (e.g., "Conductivity is 1.2 mS/cm at RT", "Synthesized via mechanochemical milling followed by annealing at 250C").

If gaps in knowledge remain (e.g., you found the conductivity but not the stability window), **perform another round of searching** with refined queries targeting the missing information.

### Step 4: Report Generation
Draft a comprehensive, academic-style markdown report named `deep_research_report.md` inside the active `research_dir` (which should be created via `mcp_base_create_research_dir`).

The report must include:
1. **Executive Summary**: A high-level overview of the findings.
2. **Detailed Findings**: Categorized by sub-topics (e.g., Structure, Performance, Synthesis). Include specific data points and conflicting reports if any exist. **CRITICAL: When summarizing each point, you MUST include the DOI reference or URL of the source where the info is coming from inline.**
3. **Methodologies**: Common computational or experimental methods used in the literature.
4. **Knowledge Gaps**: What remains unknown or disputed in the current literature.
5. **References**: A cited list of the papers and URLs you drew information from, mapping to your inline citations.

### Step 5: User Review
Once the report is generated, present it to the user.

```bash
notify_user(
    PathsToReview=["/absolute/path/to/research_dir/deep_research_report.md"],
    BlockedOnUser=True,
    Message="Deep research is complete. Please review the comprehensive report."
)
```

## Constraints
- **Depth Over Speed**: Take the time to run multiple tool calls to search and read. Do not stop after one search query.
- **Data Specificity**: Extract quantitative data (values, temperatures, error margins) wherever possible rather than qualitative statements.
- **Resource Utilization**: Use both `mcp_base_search_literature` and `search_web`.

## Examples

To initiate deep research:
```bash
# Agent internally executes Step 1 to Step 5.
# (No specific conda environment required since it's an agentic skill relying on MCP tools).
```

---

**Author:** Agent  
**Contact:** [GitHub @username](https://github.com/username)
