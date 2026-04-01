---
trigger: model_decision
description: Rules to implement a workflow under `.agents/workflows/`
---

# Workflow Standards

All high-level research objectives in this project should be implemented as "Workflows" within the `.agents/workflows/` directory. This rule ensures consistency, discoverability, and reusability for the agent when addressing complex user requests.

## What is a Workflow?

Workflows are distinct from individual SKILLs or MCP tools in several key ways:

1. **High-Level Objective:** Workflows describe a high-level research goal, such as "discover a novel oxide-based Li-ion cathode" or "Is MOF-xxx a good direct air capture material?".
2. **Scientific Scope:** The scope of a workflow is similar to the scope of a scientific journal article. It must include a clear definition of the scientific problem and the specific steps required to solve it.
3. **Flexibility:** Compared to SKILLs and MCP tools, workflows can be much more flexible. They can be a summarized methodology from a literature paper, or a curated sequence of SKILLs and MCP tool calls arranged so that the AtomisticSkill agent is ready to execute them end-to-end.

## Directory Structure

Workflows are typically maintained as single markdown files in the `.agents/workflows/` directory:

```
.agents/workflows/
├── hierarchical-screening-alkaline-stability.md
├── sorption-discovery.md
└── benchmark-finetuning.md
```

## Workflow File Format

Each workflow file must follow a standardized structure, using Markdown with YAML frontmatter.

### 1. YAML Frontmatter
```yaml
---
description: Concise one-sentence summary of the workflow's research objective.
---
```

**Guidelines:**
- `description`: Should be clear enough for the agent or user to understand the goal (e.g., "Workflow for benchmarking, fine-tuning, and distilling Machine Learning Interatomic Potentials (MLIPs)").

### 2. Title and Problem Definition
Begin with a description of the goal and the scientific problem being solved.

```markdown
This workflow guides you through [High-level objective].

**Scientific Problem:** [Provide context on why this workflow exists and what it attempts to solve, similar to an abstract of a paper].
```

### 3. Step-by-Step Methodology
Provide a numbered sequence of steps. Each step should represent a conceptual phase of the research.

- Reference existing SKILLs using their exact names (e.g., `mat-sample-pes-by-md`, `ml-mlip-training`).
- Specify when to use specific MCP tools.
- Provide instructions on decision-making (e.g., "If accuracy is not satisfied, repeat sampling...").


## References

If the workflow is data-mined from or based on specific literature, include a literature reference section. This ensures scientific traceability and proper attribution.

```markdown
## References
- Author et al., "Paper Title", *Journal Name*, Year. [DOI](https://doi.org/...)
```