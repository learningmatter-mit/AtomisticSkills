---
trigger: model_decision
description: Rules to implement a skill under `.agents/skills/`
---

# Skill Standards

All modular capabilities in this project should be implemented as "Skills" within the `.agents/skills/` directory. This rule ensures consistency, discoverability, and reusability for the agent.

## Directory Structure

Each skill must reside in its own subdirectory with the following structure:
```
.agents/skills/<skill-name>/
├── SKILL.md                  # Required: Main documentation
├── scripts/                  # Optional: Helper scripts
│   ├── script1.py
│   └── script2.py
├── examples/                 # Optional: Reference input/output files
│   └── example-name/
│       ├── README.md         # Required for each example
│       ├── example_input.cif
│       └── example_output.json
└── resources/                # Optional: Config files, templates, data
    ├── config_template.yaml
    └── reference_data.json
```

## SKILL.md Format

The `SKILL.md` file must follow this standardized structure:

### 1. YAML Frontmatter
```yaml
---
name: skill-name-in-kebab-case
description: Concise one-sentence summary of the skill's purpose and outcome.
category: category-name
---
```

**Guidelines:**
- `name`: Use lowercase letters, numbers, and hyphens only (kebab-case)
- `description`: Should be clear enough for the agent to decide if this skill is relevant to a user query. **The description must state what the skill is used for, NOT how the skill works.**
- `category`: Must be one of the following (use a YAML list like `[materials, chemistry]` if multiple apply):
  - `materials`: Materials science simulation and analysis skills (prefix: `mat-`)
  - `chemistry`: Chemistry and molecular simulation skills (prefix: `chem-`)
  - `machine-learning`: MLIP training, model selection, and ML workflows (prefix: `ml-`)
  - `drug-discovery`: Drug design, docking, and molecular property prediction (prefix: `drug-`)
  - `general`: General-purpose research utilities (prefix: `general-`)

### 2. Title and Goal Section
Begin with a level-1 header matching the skill name, followed by a `## Goal` section:

```markdown
# Skill Name

## Goal
Clearly state what this skill achieves. Use precise technical language and, when applicable, include mathematical notation (e.g., "To determine the thermodynamic melting temperature ($T_m$) of a bulk material").
```

### 3. Instructions Section
Provide numbered, step-by-step instructions. Each step should:
- **State the objective clearly** (e.g., "Background Research", "Phase Preparation")
- **Provide specific commands** with environment annotations
- **Include all necessary parameters** with explanations
- **Link to related skills** when appropriate

**Format for code blocks:**
````markdown
```bash
# Env: <conda-environment-name>
python .agents/skills/<skill-name>/scripts/<script>.py [arguments]
```
````

**Format for MCP tool calls:**
````markdown
```bash
mcp_<tool_name>(
    parameter1=value,  # Comment explaining the parameter
    parameter2=value,  # Use realistic values, not placeholders
    output_dir="descriptive_name"
)
```
````

**Key principles:**
- Always specify the conda environment required
- Use absolute paths from project root for script references
- Provide inline comments explaining non-obvious parameters
- Use realistic example values instead of generic placeholders
- Cross-reference other skills using relative links (e.g., `[molecular-dynamics](../molecular-dynamics/SKILL.md)`)

### 4. Examples Section
Provide concrete, runnable examples that demonstrate typical usage.

**CRITICAL RULE:** Each distinct example should be placed in its own dedicated subdirectory within `examples/` (e.g., `examples/my-example/`) and MUST contain its own `README.md` file. This README should comprehensively document the example's goal, step-by-step instructions, and expected outputs.

**LITERATURE VALIDATION RULE:** Whenever possible, choose an example system with known, published literature reported values. In the example's `README.md`, you MUST compare the skill's execution results to the reported literature values to validate the skill's correctness, and explicitly include the literature reference citation.

> [!WARNING]
> **Artifact Retention**: Example folders are purely for structural reference and lightweight logging. NEVER commit or retain large execution artifacts such as PyTorch model checkpoints (`.pth`, `.model`), checkpoint snapshots (`.pt`), or uncompressed trajectory aggregations (`.xyz`) inside these example subdirectories.

**3D STRUCTURE RENDERING RULE:** To ensure compatibility with the documentation website's automatic 3D structure viewer (3Dmol.js), any `.cif` or `.xyz` files you want rendered MUST be written as standard markdown links (e.g., `[my_structure.cif](my_structure.cif)`). Do NOT write them merely as backticked code snippets (` `my_structure.cif` `) within tables or lists, as they will not be rendered. It is recommended to add a dedicated "## 3D Structures" section at the end of the `README.md` for these links.


```markdown
## Examples

Creating a solid-liquid interface for Aluminum:
```bash
# Env: base-agent
python .agents/skills/melting-point/scripts/create_interface.py Al_solid.cif Al_liquid.cif --axis 0 --output Al_interface.cif
```
```

### 5. Constraints Section
Document important limitations, safety rules, and requirements:

```markdown
## Constraints
- **Box Dimensions**: The lattice parameters perpendicular to the stacking axis must be identical.
- **Ensemble**: The final production run must be in the **NVE** ensemble.
- **Environments**: Scripts require specific Conda environments (e.g., `mace-agent`, `matgl-agent`). **Each code block MUST specify the environment.**
- **System Size**: Recommended for supercells with >50 atoms to reduce noise.
```

### 6. References Section
Include basic literature citations (with DOIs if available) for the methods, algorithms, or software packages the skill relies on to ensure scientific reproducibility.

```markdown
## References
- Author et al., "Paper Title", *Journal Name*, Year. [DOI](https://doi.org/...)
```

## Script Documentation Standards

All Python scripts in the `scripts/` directory must include:

### 1. Module-Level Docstring
```python
"""
Brief description of what this script does.

Usage:
    python script_name.py input.cif --option value

Requirements:
    - Conda environment: <env-name>
    - Required packages: ase, pymatgen, etc.
"""
```

### 2. Argument Parser with Help Text
```python
parser = argparse.ArgumentParser(
    description="Clear description of the script's purpose"
)
parser.add_argument("input", help="Description of input file/parameter")
parser.add_argument("--option", default=default_value, help="What this option controls")
```

### 3. Type Hints and Docstrings for Functions
```python
def process_structure(atoms: Atoms, threshold: float = 0.5) -> dict:
    """
    Brief description of what the function does.
    
    Args:
        atoms: ASE Atoms object to process
        threshold: Cutoff value for some criterion
        
    Returns:
        Dictionary containing results with keys: 'metric1', 'metric2'
    """
```

## Environment Management Standards

### 1. Explicit Specification
Every script execution in `SKILL.md` **MUST** include a `# Env: <conda-environment-name>` annotation in the code block. This ensures the agent and the user know exactly which environment to activate before running the script.

### 2. Environment Mapping
Refer to `mcp-environments.md` for the standard environment mapping:
- `base-agent`: General materials tools, Materials Project API, and parsing.
- `matgl-agent`: MatGL calculations, training, and utilities.
- `mace-agent`: MACE calculations and training.
- `fairchem-agent`: FairChem/OCP/UMA calculations.
- `atomate2-agent`: Atomate2/Jobflow workflows and DB querying.
- `smol-agent`: Cluster expansion and Monte Carlo simulations.
- `mattergen-agent`: MatterGen structure generation.
- `drugdisc-agent`: Drug discovery, docking, and molecular tools.

### 3. Documentation Consistency
The required environment must be consistent across:
- The `# Env:` annotation in `SKILL.md`.
- The `Requirements` section in the script's module-level docstring.
- The `Constraints` section of `SKILL.md`.

## Best Practices

- **Scope & Progressive Disclosure**: Target one well-defined task. Focus `SKILL.md` on workflow logic; move implementation to `scripts/`, datasets to `resources/`, and examples to `examples/`.
- **References**: Always use relative paths from `SKILL.md` when linking to scripts or other skills.
- **Environments**: Always annotate code blocks with `# Env: <env-name>` and specify requirements in the Constraints section.
- **Integration**: Prioritize existing MCP tools over custom code. If writing custom MLIP scripts, ALWAYS use `src.utils.mlips.loader.load_wrapper`.
- **Validation & Documentation**: Embed verification steps, document expected outcomes, and use concrete, reproducible parameters in examples.
- **Parameter Persistence**: Skill scripts that accept input kwargs and hyperparameters **must** save all input parameters to a **separate `input_configs.yaml`** file in the same output directory where results are written. This file must capture both user-specified values **and** the default values of any parameters that were not explicitly provided. Do **not** embed configs inside JSON output files (e.g. as a `"config"` key). This ensures results remain clean and can be fully interpreted and reproduced in the future without re-inspecting the source code or command history.

## Skill Naming Conventions

- **Purpose over Method**: Skill names should be informative of the *function or purpose* of the skill, NOT the specific computational method being used (e.g., `mat-solid-free-energy` is preferred over `mat-frenkel-ladd`).
- Use **kebab-case** for skill directory names (lowercase with hyphens)
- **Every skill name must start with a category prefix** matching its `category` field:
  - `mat-` for `materials` skills (e.g., `mat-melting-point`, `mat-diffusion-analysis`, `mat-phonon`)
  - `ml-` for `machine-learning` skills (e.g., `ml-foundation-potentials`, `ml-mlip-training`, `ml-cluster-expansion`)
  - `drug-` for `drug-discovery` skills (e.g., `drug-docking-vina`, `drug-admet-prediction`)
  - `general-` for `general` skills (e.g., `general-arxiv-search`)
- The part after the prefix should be **descriptive and concise**:
  - Good: `mat-melting-point`, `ml-mlip-speed`, `drug-protein-prep`
  - Avoid: `mat-mp`, `ml-train`, `drug-d`
- Use **noun forms** for result-oriented skills: `mat-phase-diagram`, `mat-surface-energy`
- Use **action/process names** for workflow skills: `mat-diffusion-analysis`, `ml-mlip-training`
- **Private Skills**: To create a proprietary or private skill that should not be tracked by version control, prefix the entire name with `private-` (e.g., `private-mat-proprietary-workflow`). The repository's `.gitignore` is configured to ignore all directories matching `.agents/skills/private-*/`, ensuring they remain local while still being automatically discovered by the agent.

## Example Skill Structure

See [`.agents/skills/melting-point/`](./../skills/melting-point/) for a comprehensive reference implementation demonstrating workflows, tool integration, validation, and environment handling.

### 7. Author Information

At the very end of every `SKILL.md` file, include a footer separated by a horizontal rule (`---`).

**CRITICAL NOTE:** The author and contact cannot be an AI agent. It must be the human author who initiated and pushed this change.

**GitHub contact (preferred):**
```markdown
---

**Author:** Name  
**Contact:** [GitHub @username](https://github.com/username)
```

**Email contact:**
```markdown
---

**Author:** Name  
**Contact:** [name@example.com](mailto:name@example.com)
```