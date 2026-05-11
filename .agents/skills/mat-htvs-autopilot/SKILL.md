---
name: mat-htvs-autopilot
description: Domain-agnostic orchestration for HTVS research campaigns. Uses declarative task files to manage pre-flight, monitoring, and post-processing steps.
category: [materials, htvs]
---

# HTVS Auto-Pilot Orchestrator

## Goal
To provide a fully automated, end-to-end research orchestrator for high-throughput screening. This skill manages the asynchronous task lifecycle by polling HTVS databases and executing a user-defined sequence of analysis steps.

## Declarative Task Architecture
The orchestrator is now **data-driven**. Instead of writing new Python code for each research domain, you define a `workflow.json` (or pass steps via CLI) that specifies what to do before, during, and after the simulation jobs.

### Workflow Task Schema
A task file consists of:
- `pre_flight`: List of shell commands to run before monitoring (e.g., reference migration).
- `post_process`: List of shell commands to run after all jobs are complete (e.g., activity analysis).
- `vars`: (Optional) Custom variables for command interpolation.

Available interpolation variables: `{settings}`, `{group_name}`, `{research_dir}`, `{python_exe}`, and any custom variables passed via `--var_name`.

## Instructions

### 1. Launch with a Task File
The most efficient way to run the orchestrator is by providing a task file.

```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-autopilot/scripts/run_autopilot.py \
    --group_name your-group \
    --settings djangochem.settings.your_db \
    --completed_path /path/to/completed \
    --task_file your_workflow.json
```

### 2. Catalysis Recipe (Example)
To run a catalysis campaign, create a `catalysis_task.json`:

```json
{
  "pre_flight": [
    "{python_exe} .agents/skills/mat-htvs-genbindingenergy/scripts/migrate_references.py --settings {settings} --group_name {group_name} --research_dir {research_dir}"
  ],
  "post_process": [
    "{python_exe} .agents/skills/mat-htvs-genbindingenergy/scripts/generate_binding_energy.py --settings {settings} --group_name {group_name} --reaction {reaction} --output_dir {research_dir}",
    "{python_exe} .agents/skills/mat-htvs-catalysis-activity-analysis/scripts/catalysis_analysis.py --reaction {reaction} --data_file {research_dir}/{reaction}_results.json --output_dir {research_dir}"
  ]
}
```

Then run:
```bash
python .agents/skills/mat-htvs-autopilot/scripts/run_autopilot.py ... --task_file catalysis_task.json --reaction OER
```

## Constraints
- **Environment**: Requires `htvs-agent`.
- **Interpolation**: Commands use standard Python string formatting. Ensure all `{braces}` are intended for variables.


---

**Author:** Hoje Chun  
**Contact:** [GitHub @hojechun](https://github.com/hojechun)
