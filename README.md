# AtomisticSkills

## Overview
**AtomisticSkills** is a composable framework for AI-driven atomistic materials research. Built on the **hierarchical decomposition** of complex scientific tasks into **Workflows** → **Skills** → **Tools**, it enables coding AI agents to autonomously conduct multi-stage materials simulations by combining modular, reusable capabilities.

The framework integrates state-of-the-art Machine Learning Interatomic Potentials (MLIPs) with DFT calculations, data augmentation, and property calculations through the Model Context Protocol (MCP), making advanced materials research accessible to AI copilots like Antigravity.





---

## Hierarchical Research Framework

**AtomisticSkills** decomposes complex scientific tasks into three abstraction levels: **Tools** → **Skills** → **Workflows**. This hierarchy enables AI agents to tackle materials research problems by composing modular capabilities.

---

### ⚙️ Tools (Low-Level Research Primitives)
[**View MCP Tools**](src/mcp_server)

Tools are **strictly structured, fundamental operations** exposed as Python functions through MCP servers. They have **fixed input/output types** and must match function call signatures exactly—similar to standard library APIs.

**Key Characteristics:**
- **Strict Type Checking**: Input and output types must match Python function signatures precisely
- **Battle-Tested**: Optimized, reliable implementations for core operations
- **Direct Callable**: The agent invokes tools directly via MCP protocol

**Tool Categories:**

1. **MCP Tools** (General-purpose primitives):
   - Structure relaxation (geometry optimization)
   - Molecular dynamics (NVT, NPT, NVE ensembles)
   - Monte Carlo simulation (cluster expansion)
   - MLIP fine-tuning and prediction
   - DFT input preparation and output parsing

2. **Skill-Specific Scripts** (Specialized helpers):
   - Phase identification for melting point calculations
   - Parity plot generation for MLIP benchmarking
   - Diffusion coefficient fitting from MSD data

---

### 🔧 Skills (Mid-Level Research Tutorials)
[**Browse Skills →**](.agent/skills)

Skills are **flexible tutorials** that combine multiple tool calls to solve focused research problems. Unlike tools, skills have **no fixed input/output type constraints**—the agent handles all data conversion and orchestration between steps.

**Key Characteristics:**
- **Flexible Composition**: Tutorials showing "how to combine tools" for specific tasks
- **Agent-Managed**: The agent handles data format conversions between tool calls
- **Self-Documented**: Each skill includes instructions (`SKILL.md`), helper scripts, and examples

**Examples:**
- Calculate 0K thermodynamic stability of a material
- Fine-tune a machine learning interatomic potential
- Compute ionic diffusion coefficients from MD trajectories
- Calculate melting temperature via solid-liquid coexistence

**Featured Skills:**
- [**MLIP Training**](.agent/skills/mlip-training/SKILL.md): Benchmark and fine-tune MLIPs using data augmentation
- [**Melting Point**](.agent/skills/melting-point/SKILL.md): Calculate melting temperature via solid-liquid coexistence
- [**Diffusion Analysis**](.agent/skills/diffusion-analysis/SKILL.md): Compute diffusion coefficients and activation energies
- [**Material Stability**](.agent/skills/material-stability/SKILL.md): Calculate 0K thermodynamic stability and $E_{hull}$

---

### 🎯 Workflows (High-Level Research Objectives)
[**Browse Workflows →**](.agent/workflows)

Workflows represent **complete, high-level research goals** that may span multiple skills and require strategic planning. They provide a non-detailed research roadmap for the agent to follow. Workflows are not necessarily constrained to the currently available tools and skills. They can be a summary of a research paper, or a research idea generated during a informal chat.

**Key Characteristics:**
- **High-Level Roadmaps**: Multi-stage research campaigns requiring decision-making
- **Flexible Detail Level**: Workflows can be **detailed** (specifying every skill and tool step) or **vague** (providing only the goal, requiring the agent to independently determine the complete skill composition and execution strategy)
- **Flexible Scope**: May exceed current tool/skill coverage; serve as targets for the agent to work toward

**Examples:**
- Search for novel MOF sorption materials in the Li-N-O chemical space
- Explore solid-state conductors compatible with LiFePO₄ cathodes
- Design thermally stable perovskites for high-temperature applications

---

### Example Composition Hierarchy
```
Workflow: "Find stable Li-ion conductors"
  ├── Skill: "Fine-tune MLIP for accuracy"
  │     ├── Tool: Sample off-equilibrium structures (MCP)
  │     ├── Tool: Label with DFT (MCP)
  │     └── Tool: Fine-tune model (MCP)
  ├── Skill: "Calculate 0K stability"
  │     ├── Tool: Load structure from Materials Project (MCP)
  │     ├── Tool: Relax structure with MLIP (MCP)
  │     └── Tool: Calculate formation energy (MCP)
  └── Skill: "Compute ionic diffusion"
        ├── Tool: Run MD simulation (MCP)
        └── Tool: Analyze MSD and fit diffusivity (Skill Script)
```

---

## Key Features

### 1. Multi-Framework MLIP Support
The project provides unified wrappers for the three leading MLIP frameworks, each running in its specialized conda environment:
- **MACE**: Supports MACE-MP, MACE-MATPES, and MACE-MH (Multi-Head) models.
- **MatGL**: Supports CHGNet, M3GNet, and TensorNet models.
- **FAIRCHEM**: Supports UMA (Universal) and ESEN (Organic/Catalysis) models.

### 2. High-Level Property Calculations
Expose complex simulation tasks as simple tools:
- **Structural Relaxation**: Geometry optimization using various optimizers (FIRE, BFGS, LBFGS).
- **Molecular Dynamics**: NVT, NPT, and NVE ensembles with various thermostats and barostats.
- **Barrier Calculations**: Nudged Elastic Band (NEB) for reaction pathways.
- **Thermal Properties**: Phonon calculations and Quasi-Harmonic Approximation (QHA).

### 3. Data Augmentation & Sampling
Generate robust training data for fine-tuning:
- **Off-Equilibrium Sampling**: MD-based sampling with clustering.
- **Near-Equilibrium Sampling**: Targeted sampling around ground states.
- **Order-Disorder Sampling**: Generating ordered structures from disordered inputs.

### 4. Automated Fine-tuning Pipeline
Fine-tune foundation models on custom datasets:
- Automatic conversion of structures and labels (energy, forces, stress).
- Backwards propagation of metrics and training history.
- Automatic generation of training visualization plots.

### 5. DFT Integration
Bridge the gap between MLIPs and first-principles calculations:
- **VASP Preparation**: Automatically generate INCAR, KPOINTS, POSCAR, and POTCAR files with sensible defaults.
- **VASP Parsing**: Extract energy, forces, and stress from VASP outputs for labeling.
- **Mock DFT**: Use high-accuracy MLIPs (like UMA) to simulate DFT results for rapid testing.

### 6. Cluster Expansion (SMOL)
Train and run Monte Carlo simulations using cluster expansion models:
- **Training**: Automatically fit cluster expansions from DFT or MLIP-labeled structures.
- **Simulations**: Run canonical or semigrand canonical Monte Carlo simulations.

### 7. Atomate2 Integration
Query and retrieve calculation results from remote Atomate2 databases:
- **Query by Formula/System**: Search for materials by chemical formula or system.
- **Extract Training Data**: Automatically retrieve and format DFT results for MLIP fine-tuning.
- **Job Status Monitoring**: Track remote calculation status and results.

---

## Environment Setup
The project uses separate conda environments to manage conflicting MLIP dependencies.

| Environment | Purpose | Python Path |
|------------|---------|-------------|
| `base-agent` | Materials tools, general utilities | `<conda_base>/envs/base-agent/bin/python` |
| `matgl-agent` | MatGL (CHGNet, M3GNet, TensorNet) | `<conda_base>/envs/matgl-agent/bin/python` |
| `mace-agent` | MACE models | `<conda_base>/envs/mace-agent/bin/python` |
| `fairchem-agent` | FairChem (UMA, ESEN) | `<conda_base>/envs/fairchem-agent/bin/python` |
| `atomate2-agent` | Atomate2 and Jobflow-remote | `<conda_base>/envs/atomate2-agent/bin/python` |
| `smol-agent` | Cluster expansion (SMOL) | `<conda_base>/envs/smol-agent/bin/python` |

### Installation
```bash
# Clone the repository
git clone git@github.com:bowen-bd/AtomisticSkills.git
cd AtomisticSkills

# Setup environments
# Run the install scripts for each agent you need
bash conda-envs/base-agent/install.sh
bash conda-envs/matgl-agent/install.sh
bash conda-envs/mace-agent/install.sh
bash conda-envs/fairchem-agent/install.sh
bash conda-envs/atomate2-agent/install.sh
bash conda-envs/smol-agent/install.sh
```

---

## Configuration & API Keys

### 1. Global Configuration
The agent is configured via environment variables or a YAML configuration file.
Recommended: Create `~/.atomistic_skills.yaml` in your home directory.

**Example `~/.atomistic_skills.yaml`:**
```yaml
# Materials Project API Key (Required for base-server)
MP_API_KEY: "your_mp_api_key_here"

# Atomate2 Remote Project (Required for remote job monitoring)
ATOMATE2_REMOTE_PROJECT: "remote_perlmutter"
```

### 2. Environment Variables
Alternatively, set variables in your shell (takes precedence over YAML):
```bash
export MP_API_KEY="your_key"
export ATOMATE2_REMOTE_PROJECT="remote_perlmutter"
```

---

## Server-Specific Setup

This project runs as a collection of MCP servers. Some require specific setup:

### 1. [base-server](src/mcp_server/materials_server.py)
*   **Purpose**: Querying structure databases (Materials Project) and VASP I/O.
*   **Requirements**: `MP_API_KEY` must be set.

### 2. [atomate2](src/mcp_server/atomate2_server.py)
*   **Purpose**: Managing remote VASP calculations and workflows.
*   **Requirements**:
    *   `ATOMATE2_REMOTE_PROJECT` env var (e.g., `remote_perlmutter`).
    *   SSH Setup for NERSC (sshproxy).
    *   **Detailed Setup Guide**:
        *   [Remote Worker Setup (NERSC)](docs/atomate2_remote_worker_setup.md)
        *   [Remote Submission Guide](docs/remote_submission_setup.md)

### 3. MLIP Agents (Mace, MatGL, FairChem)
*   **Purpose**: Running ML potentials.
*   **Requirements**: [MLIP Environment Rules](.agent/rules/mcp-environments.md).
    *   These agents run in isolated conda environments.
    *   [MACE Setup](conda-envs/mace-agent/README.md)
    *   [MatGL Setup](conda-envs/matgl-agent/README.md)
    *   [FairChem Setup](conda-envs/fairchem-agent/README.md)
    *   [Smol Setup](conda-envs/smol-agent/README.md)

### MCP Server Configuration
The project is configured to run as a set of MCP servers. The base configuration is provided in [mcp_config.json](mcp_config.json).

#### Integrating with Antigravity
To use these tools within Antigravity, you need to merge the server configurations into your local Antigravity MCP config:

1. Locate your Antigravity MCP configuration file (typically at `~/.gemini/antigravity/mcp_config.json`).
2. Copy the `mcpServers` definitions from this project's [mcp_config.json](mcp_config.json).
3. Paste them into your local configuration file.
4. Restart Antigravity to load the new tools.

> [!TIP]
> Ensure the `PYTHONPATH` in the `env` section of each server points to your absolute project path (e.g., `/path/to/AtomisticSkills`).

---

## Agent Intelligence & Automation
This project is optimized for use with coding AI copilots like **Antigravity**. It includes specialized instructions and pre-defined workflows to automate complex research tasks.

### The `.agent/` Directory
- **Rules (`.agent/rules/`)**: Contains project-specific standards, scientific constraints, and modeling guidelines. Antigravity automatically parses these to ensure all simulations and code follow best practices.
- **Workflows (`.agent/workflows/`)**: Defines standardized research procedures (e.g., calculating melting points or fine-tuning alloys). Antigravity can execute these step-by-step, managing the complex transitions between different conda environments and simulation stages.
- **Skills (`.agent/skills/`)**: Modular, reusable capabilities for complex tasks like melting point calculations, diffusion analysis, and MLIP training. Each skill is self-documented with instructions, scripts, and resources.

---

## Developer Guide

### Architecture Overview

**AtomisticSkills** follows a **modular, multi-environment architecture** designed to isolate dependencies and expose functionality through the Model Context Protocol (MCP):


```
┌─────────────────────────────────────────────────────────┐
│                    Antigravity Agent                    │
│             (Coding AI Copilot Interface)               │
└────────────────────┬────────────────────────────────────┘
                     │ MCP Protocol
          ┌──────────┴──────────┬───────────┬─────────────┐
          │                     │           │             │
     ┌────▼────┐         ┌──────▼──┐   ┌───▼───┐   ┌─────▼─────┐
     │  MACE   │         │ MatGL   │   │  Fair │   │Materials  │
     │ Server  │         │ Server  │   │ Chem  │   │Tools      │
     │         │         │         │   │Server │   │Server     │
     └────┬────┘         └────┬────┘   └───┬───┘   └─────┬─────┘
          │                   │            │             │
     ┌────▼────────┐    ┌─────▼──────┐ ┌──▼─────┐  ┌────▼──────┐
     │mace-agent   │    │matgl-agent │ │fairchem│  │base-agent │
     │environment  │    │environment │ │-agent  │  │environment│
     └─────────────┘    └────────────┘ └────────┘  └───────────┘
```

### Core Components

#### 1. MCP Servers (`src/mcp_server/`)

Each MCP server is a standalone Python module that exposes tools via the FastMCP framework:

| Server | Environment | Primary Functionality |
|--------|-------------|----------------------|
| [mace_server.py](src/mcp_server/mace_server.py) | `mace-agent` | MACE model loading, prediction, relaxation, MD, fine-tuning |
| [matgl_server.py](src/mcp_server/matgl_server.py) | `matgl-agent` | CHGNet/M3GNet/TensorNet operations, bandgap prediction |
| [fairchem_server.py](src/mcp_server/fairchem_server.py) | `fairchem-agent` | UMA/ESEN models, mock DFT capability |
| [materials_server.py](src/mcp_server/materials_server.py) | `base-agent` | Materials Project queries, VASP I/O, research directory management |
| [atomate2_server.py](src/mcp_server/atomate2_server.py) | `atomate2-agent` | Query remote DFT databases, job status monitoring |
| [smol_server.py](src/mcp_server/smol_server.py) | `smol-agent` | Cluster expansion training and Monte Carlo simulations |

**Key Pattern**: Each server imports a corresponding wrapper class (e.g., `MACEWrapper`, `MatGLWrapper`) that encapsulates the MLIP-specific logic.

#### 2. MLIP Wrappers (`src/utils/mlips/`)

Wrapper classes provide a **unified interface** for different MLIP frameworks:

```python
# Example: MACE Wrapper
from src.utils.mlips.mace_wrapper import MACEWrapper

wrapper = MACEWrapper(model_name="MACE-OMAT-0-small", device="cuda")
result = wrapper.predict(structure_data)
# Returns: {'energy': float, 'forces': array, 'stress': array}
```

**Common Methods**:
- `load_model(model_name, device)`: Load a specific MLIP model
- `predict(structure_data)`: Get energy, forces, and stress
- `relax_structure(structure, fmax, steps)`: Geometry optimization
- `run_md(structure, temperature, steps, ensemble)`: Molecular dynamics
- `fine_tune_model(training_data_path, epochs, lr)`: Model fine-tuning

> [!IMPORTANT]
> All wrappers use **eV/Å³ for stress** internally, following ASE conventions. See [stress-units.md](.agent/rules/stress-units.md) for details.

#### 3. Utilities (`src/utils/`)

Supporting modules for common tasks:
- **structure_utils.py**: Convert between ASE Atoms, Pymatgen Structure, and dictionary formats
- **dft_utils.py**: VASP input generation and output parsing using Pymatgen
- **md_utils.py**: MD monitors (explosion, volume, equilibration detection)
- **sampling_utils.py**: Off-equilibrium and near-equilibrium sampling strategies

#### 4. Skills (`.agent/skills/`)

Skills are **modular, self-contained capabilities** that combine multiple tools and scripts to accomplish complex research tasks. Each skill lives in its own directory with a standardized structure:

```
.agent/skills/<skill-name>/
├── SKILL.md              # Instructions and documentation
├── scripts/              # Python/Bash helper scripts
├── examples/             # Reference input/output files
└── resources/            # Configuration files, templates
```

**Available Skills**:
- **[mlip-training](.agent/skills/mlip-training/SKILL.md)**: Benchmark and fine-tune MLIPs using data augmentation
- **[melting-point](.agent/skills/melting-point/SKILL.md)**: Calculate melting temperature using solid-liquid coexistence
- **[diffusion-analysis](.agent/skills/diffusion-analysis/SKILL.md)**: Compute diffusion coefficients from MD trajectories
- **[molecular-dynamics](.agent/skills/molecular-dynamics/SKILL.md)**: Best practices for running stable MLIP MD simulations

**How Skills Work**:
1. The agent reads `SKILL.md` to understand the task
2. Follows step-by-step instructions
3. Executes scripts from the `scripts/` directory in the appropriate environment
4. Uses resources and examples as templates

> [!TIP]
> To create a new skill, follow the guidelines in [skill-standards.md](.agent/rules/skill-standards.md).

---

### Development Workflow

#### Adding a New MCP Tool

1. **Choose the appropriate server** based on dependencies
2. **Define the tool function** with type hints and docstrings:
   ```python
   @mcp.tool()
   def my_new_tool(
       structure_data: dict,
       parameter1: float = 1.0,
       parameter2: str = "default"
   ) -> dict:
       """
       Brief description of what this tool does.
       
       Args:
           structure_data: Structure in dictionary format.
           parameter1: Description of parameter.
           parameter2: Another parameter.
           
       Returns:
           Dictionary with results.
       """
       # Implementation logic
       return results
   ```

3. **Test the tool** by restarting the MCP server:
   ```bash
   # Stop the server in Antigravity
   # Then restart it manually for debugging:
   export PYTHONPATH=/path/to/AtomisticSkills
   conda activate <appropriate-env>
   python -m src.mcp_server.<server_name>
   ```

#### Implementing a New Skill

1. Create the skill directory: `.agent/skills/<skill-name>/`
2. Write `SKILL.md` following the [standards](.agent/rules/skill-standards.md)
3. Add helper scripts to `scripts/` (specify required conda environment)
4. Provide examples and resources as needed
5. Test the skill end-to-end with Antigravity

#### Running Tests

The project uses `pytest` with environment-specific test directories:

```bash
# Test a specific environment
conda activate mace-agent
pytest tests/mace/

# Run all tests (requires all environments)
pytest tests/
```

Test organization:
```
tests/
├── base/           # General utilities (base-agent)
├── mace/           # MACE-specific tests (mace-agent)
├── matgl/          # MatGL-specific tests (matgl-agent)
├── fairchem/       # FairChem-specific tests (fairchem-agent)
└── integration/    # Cross-tool integration tests
```

---

### Important Technical Details

#### Environment Isolation
- Each MCP server runs in a **dedicated conda environment** to avoid dependency conflicts
- The `PYTHONPATH` must point to the project root for all servers
- When debugging, **always activate the correct environment** before importing modules

#### Stdout/Stderr Handling
All MCP servers use centralized output redirection (see `src/utils/mcp_utils.py`) to prevent:
- Print statements from polluting MCP responses
- Training logs from breaking the JSON protocol
- Debugging output from interfering with tool calls

> [!WARNING]
> Never use raw `print()` in MCP tool functions. Use logging or the `RedirectIO` context manager.

#### Data Flow for Fine-Tuning
1. **Input**: JSON file with structure, energy, forces, and stress (in eV/Å³)
2. **Conversion**: Wrapper converts to framework-specific format
3. **Training**: Model fine-tuning with history logging
4. **Output**: Training history JSON + saved model checkpoint

#### Research Directory Management
Every research task should:
1. Call `create_research_dir(research_topic)` to establish a timestamped directory
2. Save all results (structures, plots, logs) to this directory
3. Document findings in the research directory

---

### Troubleshooting

#### MCP Server Not Loading
- Check `mcp_config.json` for correct Python paths
- Verify `PYTHONPATH` points to project root
- Restart Antigravity after configuration changes

#### Import Errors in Scripts
- Ensure correct conda environment is activated
- Check that `PYTHONPATH` includes project root: `export PYTHONPATH=/path/to/AtomisticSkills`
- Use absolute imports: `from src.utils.mlips.mace_wrapper import MACEWrapper`

#### Fine-Tuning Fails
- Verify stress units are in eV/Å³ (see [stress-units.md](.agent/rules/stress-units.md))
- Check training data format matches expected structure
- For small datasets (<500 structures), use `freeze_backbone=True`

#### MD Simulation Explodes
- Enable MD monitors: `monitor=True, monitor_type=["explosion", "volume"]`
- Reduce timestep (default: 1fs, try 0.5fs)
- Check initial structure is relaxed with `fmax < 0.05 eV/Å`

---

## Project Structure
```
AtomisticSkills/
├── src/
│   ├── mcp_server/          # MCP server implementations
│   │   ├── mace_server.py
│   │   ├── matgl_server.py
│   │   ├── fairchem_server.py
│   │   ├── materials_server.py
│   │   ├── atomate2_server.py
│   │   └── smol_server.py
│   └── utils/               # Utility modules
│       ├── mlips/           # MLIP wrappers
│       │   ├── mace_wrapper.py
│       │   ├── matgl_wrapper.py
│       │   └── fairchem_wrapper.py
│       ├── structure_utils.py
│       ├── dft_utils.py
│       ├── md_utils.py
│       └── sampling_utils.py
├── .agent/
│   ├── rules/               # Coding standards, scientific rules
│   ├── workflows/           # Step-by-step research procedures
│   ├── skills/              # Modular capabilities
│   └── test/                # Temporary test/validation files
├── conda-envs/              # Environment YAML files
├── tests/                   # Unit and integration tests
├── research/                # Research results and logs
├── mcp_config.json          # MCP server configuration
└── README.md
```

---

## Contributing
**AtomisticSkills** is developed as an open framework for automated atomistic research. Contributions to new potentials, sampling methods, simulation workflows, or skills are welcome.


### Guidelines
- Follow the coding standards in `.agent/rules/coding-standards.md`
- Add tests for new functionality
- Update documentation (README, SKILL.md files)
- Ensure all MCP tools return clean JSON (no stdout pollution)

---

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
