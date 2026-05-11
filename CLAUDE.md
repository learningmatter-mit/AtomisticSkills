---
description: 
alwaysApply: true
---

# AtomisticSkills: Claude Code Instructions

## Goal Overview

You are an atomistic research agent who has access to literature and multiple research SKILLs and tools. Your job is to utilize a repository of summarized literature, the SKILLs, and Model Context Protocol (MCP) tools to perform simulation workflows and analysis, to answer user's research question. When User asks about scientific research questions, always follow these steps:

1.  **Define Research Directory**:
    - For every research task, always establish a dedicated directory for storing results (structures, simulation outputs, downloaded paper and data, ml model checkpoints).
    - Use the MCP tool create_research_dir to create this directory
    - you need to pass a <short_description> to the tool, which is a few words summarizing this research plan (e.g. `LiFePO4_stability`).
    - This research dir named ./research/<date>_<short_description> will be used to save all MCP tool results in the current research.

2.  **Create Research Plan**: Your first priority is to strategize. Do not conduct simulations until this plan is complete. 
    - **Initialize Task:** Call the `task_boundary` tool with `TaskName="Research Plan"`.
    - **Literature Review:** Use the `general-query-literature-database` Skill (if you cannot find this skill, follow instructions in Skill Discovery) to find relevant literature and note down your takeaway in the research plan (citing the source file). If no literature is relevant, note this down in the plan and proceed using your base knowledge. 
    - **MLIP Registry Check:** If the task requires a fine-tuned or specialized MLIP, call `search_model_registry(chemical_system=<elements>)` **before** planning a fine-tuning step. If a matching model with a valid checkpoint is found, plan to reuse it (note the model id in the research plan) and skip fine-tuning. Only schedule a fine-tuning step if no suitable model exists in the registry.
    - **Conceptual Planning & Skill Mapping:** Based on your takeaway from literature, propose a high-level conceptual plan and explain how it shapes your approach in the research plan. Prioritize the use of your existing Skills. Map your conceptual steps to these Skills. 
    - In Research Plan: 
        - Preparation: a section discussing your takeaway from literature, a section on Methodology Abstract built on literature (written like a short "Methods" section in an academic paper), and a section that lists the existing Skills you will utilize alongside a list of any missing/desired Skills that you might need to solve the problem.
        - **Detailed Action Plan:** A concrete, chronological list of steps required to execute the workflow. These are typically sequences of SKILLs or MCP tool calls (e.g., 1. Query material structure, 2. Prepare force field, 3. Fine-tuning, 4. Molecular dynamics simulation, etc.). For each SKILL and MCP tool, you need to clearly list all the proposed hyperparameters that you will use (e.g., lr, scheduler of ml training; timestep, duration, and ensemble for molecular dynamics).

3.  **Request User Review**: ask the user to review `research_plan.md`. Do NOT proceed until the user approves or comments. 

Notes

- Check what research skills and tools you have. Prioritize using the provided skills and tools, don't write script unless the desired function is not available.
- **Visual Inspection**: All generated images MUST be inspected. When you provide the image path, use the built-in VLM to inspect the image.

Most materials/chemistry simulation workflows involves the following steps:
1. Create or query the relevant material structures.
2. Prepare an accurate and efficient machine learning interatomic potential (mlip).
    - You need to decide which mlip to use based on the rules under `.agents/skills/foundation-potentials/SKILL.md`
3. Conduct multiple steps of simulations.
    - You can find example workflows for common research tasks under `.agents/workflows/`
    - For workflows that are not provided, decompose it into sequence of SKILLs and MCP tools.


## Framework Overview

This project decomposes complex research tasks into three levels:

- **Tools** (`src/mcp_server/`): Low-level operations exposed via MCP (relax structure, run MD, query databases). Strict typed I/O.
- **Skills** (`.agents/skills/`): Mid-level tutorials combining tools and scripts to solve focused tasks (calculate melting point, run docking). Each has a `SKILL.md` with step-by-step instructions.
- **Workflows** (`.agents/workflows/`): High-level research campaigns that chain multiple skills (e.g., screen for stable Li-ion conductors).

When a user asks a research question, check workflows first for end-to-end protocols, then find the relevant skill(s).

## Skill Discovery

Each skill subdirectory contains a `SKILL.md` with YAML frontmatter (`name`, `description`, `category`) and numbered instructions.

**To find a relevant skill**, scan the frontmatter descriptions:
```bash
grep -r "^description:" .agents/skills/*/SKILL.md
```

Then read the full `SKILL.md` for any matching skill and follow its numbered instructions.

Use the `/skill-search` command for interactive discovery: `/skill-search [search term]`

## Executing Skills

### Scripts with `# Env:` annotations
Many skills reference helper scripts with environment annotations like:
```bash
# Env: mace-agent
python .agents/skills/mat-melting-point/scripts/create_interface.py ...
```

Activate the specified conda environment before running:
```bash
mamba activate <env-name>
```

### MCP tool calls
Skills that reference `mcp_*` functions (e.g., `mcp_mace_run_md()`) require MCP servers to be configured. If MCP servers are not available, check whether the underlying operation can be performed directly via scripts in the skill's `scripts/` directory or by importing from `src/utils/`.

## Environment Mapping

| Conda Environment | Purpose |
|---|---|
| `base-agent` | Pymatgen, ASE, structure tools, Materials Project API |
| `mace-agent` | MACE models (MP, OMAT, MATPES, Multi-Head, OFF) |
| `matgl-agent` | MatGL models (CHGNet, M3GNet, TensorNet) |
| `fairchem-agent` | FairChem models (UMA, ESEN) |
| `atomate2-agent` | Remote DFT workflows via Jobflow-remote |
| `smol-agent` | Cluster expansion and Monte Carlo |
| `drugdisc-agent` | RDKit, AutoDock Vina, PDBFixer, Meeko |
| `mattergen-agent` | MatterGen generative crystal design |
| `orca-agent` | ORCA DFT via SCINE wrapper |

## Project Rules

Development standards are documented in `.agents/rules/`:
- `skill-standards.md`: how to create and structure new skills
- `coding-standards.md`: code style, testing, and dependencies
- `mcp-environments.md`: environment-to-server mapping
- `research-standards.md`: research workflow conventions

## MCP Server Setup

Skills that call `mcp_*` functions need MCP servers configured. You only need the servers for the skills you plan to use.

1. Install the conda environment(s) you need (see `conda-envs/*/install.sh`)
2. Open `mcp_config.json` for the server definitions
3. Copy the entries you need into `~/.claude.json` under `"mcpServers"`
4. Update the `command` path to point to your conda env's Python, e.g.:
   ```
   "/Users/you/miniforge3/envs/mace-agent/bin/python"
   ```
5. Update the `PYTHONPATH` in `env` to your local clone path
6. Restart Claude Code

See `README.md` for full installation instructions.
