---
trigger: model_decision
description: Rules to implement a skill under `.agent/skills/`
---

# Skill Standards

All modular capabilities in this project should be implemented as "Skills" within the `.agent/skills/` directory. This rule ensures consistency, discoverability, and reusability for the agent.

## Directory Structure

Each skill must reside in its own subdirectory with the following structure:
```
.agent/skills/<skill-name>/
├── SKILL.md                  # Required: Main documentation
├── scripts/                  # Optional: Helper scripts
│   ├── script1.py
│   └── script2.py
├── examples/                 # Optional: Reference input/output files
│   ├── example_input.cif
│   └── example_output.json
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
---
```

**Guidelines:**
- `name`: Use lowercase letters, numbers, and hyphens only (kebab-case)
- `description`: Should be clear enough for the agent to decide if this skill is relevant to a user query

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
python .agent/skills/<skill-name>/scripts/<script>.py [arguments]
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
Provide concrete, runnable examples that demonstrate typical usage:

```markdown
## Examples

Creating a solid-liquid interface for Aluminum:
```bash
# Env: base-agent
python .agent/skills/melting-point/scripts/create_interface.py Al_solid.cif Al_liquid.cif --axis 0 --output Al_interface.cif
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
- `matgl-agent`: MatGL calculations, training, and utilities.
- `mace-agent`: MACE calculations and training.
- `fairchem-agent`: FairChem/OCP/UMA calculations.
- `base-agent`: General materials tools, Materials Project API, and parsing.
- `atomate2-agent`: Atomate2/Jobflow workflows and DB querying.

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

### 5. Integration with MCP Tools
- Clearly distinguish between MCP tool calls and local script execution
- Provide explicit output paths for MCP tools to avoid ambiguity
- Document expected return values and how to use them in subsequent steps

### 6. Validation and Quality Checks
- Include verification steps within the workflow (e.g., phase verification in melting-point skill)
- Specify expected outcomes and how to interpret them
- Provide guidance on what to do when results don't match expectations

## Skill Naming Conventions

- Use **kebab-case** for skill directory names (lowercase with hyphens)
- Choose **descriptive, action-oriented names** that clearly indicate the skill's purpose:
  - Good: `melting-point`, `diffusion-analysis`, `mlip-training`
  - Avoid: `mp`, `calc_diff`, `train`
- Prefer **gerund forms** (verb + -ing) for process-oriented skills:
  - `training-mlip`, `analyzing-diffusion`, `calculating-properties`
- Use **noun forms** for result-oriented skills:
  - `melting-point`, `phase-diagram`, `band-structure`

## Example Skill Structure

See [`.agent/skills/melting-point/`](./../skills/melting-point/) for a comprehensive reference implementation that demonstrates:
- Multi-step workflow with clear progression
- Integration of MCP tools and local scripts
- Environment-specific annotations
- Cross-references to related skills
- Validation and quality checks embedded in the workflow
- Realistic examples with concrete parameters

### 7. Author Information

At the very end of every `SKILL.md` file, you MUST include the author's contact information in the following format:

```text
Author: Bowen Deng
Contact: github username <bowen-bd>
```

If an email is provided, use:
```text
Author: Bowen Deng
Contact: email <name@gmail.com>
```