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
- `description`: Should be clear enough for the agent to decide if this skill is relevant to a user query
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

> [!WARNING]
> **Artifact Retention**: Example folders are purely for structural reference and lightweight logging. NEVER commit or retain large execution artifacts such as PyTorch model checkpoints (`.pth`, `.model`), checkpoint snapshots (`.pt`), or uncompressed trajectory aggregations (`.xyz`) inside these example subdirectories.

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
Include literature references for the methods, algorithms, or datasets that the skill is based on. This ensures scientific reproducibility and gives proper attribution.

```markdown
## References
- Author et al., "Paper Title", *Journal Name*, Year. [DOI](https://doi.org/...)
- Author et al., "Another Paper", *Journal*, Year. [DOI](https://doi.org/...)
```

**Guidelines:**
- Cite the **original paper** describing the method or algorithm used
- Include DOI links when available
- If the skill wraps a software package, cite the package's canonical reference
- For skills based on well-known textbook methods, a brief description of the method origin is acceptable in lieu of a formal citation

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

### 1. Skill Scope
- **Single Responsibility**: Each skill should target one well-defined task
- **Composability**: Skills should work well together (e.g., molecular-dynamics skill referenced by melting-point skill)
- **Reusability**: Design skills to be applicable across different materials or systems

### 2. Progressive Disclosure
- Keep `SKILL.md` focused on the workflow and high-level logic
- Move complex implementation details into `scripts/`
- Store reference data, templates, or large datasets in `resources/`
- Use `examples/` to demonstrate typical inputs and expected outputs

### 3. Path and Environment Management
- **Script References**: Always use relative paths from the `SKILL.md` file
  - Good: `[plot.py](scripts/plot.py)`
  - Bad: `/absolute/path/to/plot.py`
- **Skill Cross-References**: Use relative paths between skills
  - Good: `[molecular-dynamics](../molecular-dynamics/SKILL.md)`
  - Bad: Absolute paths or external links
- **Environment Specification**: Always annotate which conda environment is required
  - Use `# Env: <env-name>` comments in code blocks
  - Specify environments in the Constraints section when multiple environments are needed

### 4. Documentation Quality
- **Clarity**: Use clear, technical language appropriate for scientific computing
- **Completeness**: Include all necessary parameters and explain their significance
- **Examples**: Provide realistic, working examples with actual filenames and values
- **Error Prevention**: Document common pitfalls and validation steps (e.g., "Verify coexistence before production run")

### 5. Integration with MCP Tools and MLIPs
- Clearly distinguish between MCP tool calls and local script execution
- Provide explicit output paths for MCP tools to avoid ambiguity
- Document expected return values and how to use them in subsequent steps
- **MLIP Usage**: When a skill involves Machine Learning Interatomic Potentials (MLIPs), prioritize using existing MCP tools. If writing a custom script is necessary, ALWAYS import and use the centralized `src.utils.mlips.loader.load_wrapper` function to load models consistently.

### 6. Validation and Quality Checks
- Include verification steps within the workflow (e.g., phase verification in melting-point skill)
- Specify expected outcomes and how to interpret them
- Provide guidance on what to do when results don't match expectations

## Skill Naming Conventions

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

## Example Skill Structure

See [`.agents/skills/melting-point/`](./../skills/melting-point/) for a comprehensive reference implementation that demonstrates:
- Multi-step workflow with clear progression
- Integration of MCP tools and local scripts
- Environment-specific annotations
- Cross-references to related skills
- Validation and quality checks embedded in the workflow
- Realistic examples with concrete parameters

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