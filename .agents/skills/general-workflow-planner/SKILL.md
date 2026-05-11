---
name: general-workflow-planner
description: Hierarchically decompose high-level scientific workflows (from literature or user-proposed) into executable sequences of existing SKILLs and MCP tools for the research plan.
category: [general]
---

# General Workflow Planner

## Goal
To decompose high-level scientific workflows (either sourced from literature or proposed directly by the user) into a concrete, executable sequence. This skill parses the objective and outputs a chronological "Detailed Action Plan" that feeds directly into the `research_plan.md` artifact, in accordance with `.agents/rules/research-standards.md`. Do not overcomplicate the output; it should be a straightforward list of steps.

## Prerequisites
- A high-level scientific workflow proposed by the user or derived from literature review.
- Access to the `.agents/skills/` registry and available MCP tools.

## Instructions

1. **Objective Parsing**
   Analyze the high-level workflow to determine the key scientific steps (e.g., Structure Generation $\rightarrow$ Relaxation $\rightarrow$ Stability $\rightarrow$ Dynamics).

2. **Skill Registry Mapping**
   Scan the repository's capabilities. Map each conceptual step to existing project tools by searching the `.agents/skills/` directory and available MCP tools (e.g., `mcp_mace_run_md`, `mcp_matgl_relax_structure`).

3. **Dependency Construction**
   Map the dependencies between the identified SKILLs and MCP tools:
   - Identify **data dependencies**: The output of Step A must act as the input for Step B (e.g., the `mat-db-mp` skill outputs a `.cif`, which serves as the input for the `mcp_mace_relax_structure` MCP tool).
   - Identify parallelization opportunities if applicable.

4. **Feasibility Analysis**
   - Verify that there is a continuous line of data flowing from the initial state to the target objective using only existing tools.
   - If missing steps exist, flag them explicitly so the user knows where custom scripting or new skills are required.

5. **Detailed Action Plan Generation**
   Output a concrete, chronological list of steps required to execute the workflow. List the proposed hyperparameters for each SKILL and MCP tool (e.g., `temperature`, `steps`, `supercell_min_length`). This list is directly inserted into the `Detailed Action Plan` section of `research_plan.md`.

## Examples

For an example of decomposing a high-level goal into a Detailed Action Plan using existing skills and MCP tools, see the [Solid-State Electrolyte Discovery](examples/sse-discovery/README.md) example.

## Constraints
- **Skill Hallucination**: NEVER invent or hallucinate skill names. Every step must map to a verifiable directory inside `.agents/skills/` or a documented MCP tool.
- **Simplicity**: Do not overcomplicate the output. Produce a linear or simple branching Action Plan suited for `research_plan.md`.

## See Also
- [general-deep-research](../general-deep-research/SKILL.md)
- [general-peer-review](../general-peer-review/SKILL.md)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @Bowen-BD](https://github.com/Bowen-BD)
