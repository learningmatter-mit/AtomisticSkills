# AtomisticSkills

## Overview
**AtomisticSkills** is a composable framework for AI-driven atomistic materials research. Built on the **hierarchical decomposition** of complex scientific tasks into **Workflows** → **Skills** → **Tools**, it enables coding AI agents to autonomously conduct multi-stage materials simulations by combining modular, reusable capabilities.

The framework integrates state-of-the-art Machine Learning Interatomic Potentials (MLIPs) with DFT calculations, data augmentation, and property calculations through the Model Context Protocol (MCP), making advanced materials research accessible to AI copilots like Google Antigravity, Cursor, and Claude Code.





---

## Hierarchical Research Framework

**AtomisticSkills** constructs complex scientific tasks from three abstraction levels: **Tools** → **Skills** → **Workflows**. This hierarchy enables AI agents to tackle materials research problems by composing modular capabilities.

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
[**Browse Skills →**](.agents/skills)

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
- [**MLIP Training**](.agents/skills/ml-mlip-training/SKILL.md): Benchmark and fine-tune MLIPs using data augmentation
- [**Melting Point**](.agents/skills/mat-melting-point/SKILL.md): Calculate melting temperature via solid-liquid coexistence
- [**Diffusion Analysis**](.agents/skills/mat-diffusion-analysis/SKILL.md): Compute diffusion coefficients and activation energies
- [**Material Stability**](.agents/skills/mat-stability/SKILL.md): Calculate 0K thermodynamic stability and $E_{hull}$

---

### 🎯 Workflows (High-Level Research Objectives)
[**Browse Workflows →**](.agents/workflows)

Workflows represent **complete, high-level research goals** that may span multiple skills and require strategic planning. They provide a research roadmap for the agent to follow. Workflows are not necessarily constrained to the currently available tools and skills. They can be a summary of a research paper, or a research idea generated during a informal chat.

**Key Characteristics:**
- **High-Level Roadmaps**: Multi-stage research campaigns requiring decision-making
- **Flexible Scope**: Workflows can be **detailed** (specifying every skill and tool step) or **vague** (providing only the goal, requiring the agent to independently determine the complete skill composition and execution strategy)

**Examples:**
- Search for novel MOF sorption materials in the Li-N-O chemical space
- Explore solid-state conductors compatible with LiFePO₄ cathodes
- Design thermally stable perovskites for high-temperature applications

---

### Example Composition Hierarchy
```
Workflow: "Find stable Li-ion conductors"
  ├── Skill: "Fine-tune MLIP for accuracy"
  │     ├── Tool: Sample off-equilibrium structures (Skill Script)
  │     ├── Tool: Label with DFT (MCP)
  │     └── Tool: Fine-tune model (MCP)
  ├── Skill: "Calculate 0K stability"
  │     ├── Tool: Load structure from Materials Project (MCP)
  │     ├── Tool: Relax structure with MLIP (MCP)
  │     └── Tool: Calculate formation energy (Skill Script)
  ├── Skill: "Compute ionic diffusion"
  │     ├── Tool: Run MD simulation (MCP)
  │     └── Tool: Analyze MSD and fit diffusivity (Skill Script)
```

---

## Key Features
[**Browse all skills →**](.agents/skills)

### 1. Simulation Infrastructure
Multi-framework MLIP support (MACE, MatGL, FAIRCHEM) with unified relaxation, MD, and fine-tuning APIs. DFT integration for VASP input/output and electronic structure for periodic systems and ORCA input/output for molecular systems. HPC job management via Atomate2. Lattice-level cluster expansion and Monte Carlo via SMOL.

### 2. Database APIs
Materials Project, ChEMBL, PDB, PubChem, and ArXiv search — query structures, properties, bioactivity data, and literature from external databases.

### 3. Property Evaluation
Stability ($E_{hull}$), phase diagrams, phonons, QHA thermal expansion, equation of state, elastic tensor, melting point, ionic diffusion, NEB barriers, surface energy & adsorption, intercalation voltage, Pourbaix diagrams, magnetic density, vibrational spectra, and amorphization.

### 4. Experimental Tools
Synthesis recommendation from text-mined literature, XRD spectrum calculation, Pourbaix diagrams, protein preparation, molecular docking (AutoDock Vina), ADMET prediction, and molecular fingerprints.

### 5. Machine Learning Tools
MatterGen (generative crystal design), MEGNet bandgap prediction, MLIP fine-tuning & benchmarking, foundation potential selection guide, cluster expansion training, and atomic feature extraction.

---

## Environment Setup
The project uses separate MCP servers running in different conda environments to manage conflicting MLIP dependencies.

| MCP Server | Conda Environment | Purpose |
|------------|-------------------|---------|
| `base` | `base-agent` | Materials Project queries, VASP I/O, structure visualization |
| `mace` | `mace-agent` | MACE models (MP, OMAT, MATPES, Multi-Head) |
| `matgl` | `matgl-agent` | MatGL models (CHGNet, M3GNet, TensorNet), bandgap prediction |
| `fairchem` | `fairchem-agent` | FairChem models (UMA, ESEN) |
| `atomate2` | `atomate2-agent` | Remote DFT job management via Jobflow-remote |
| `smol` | `smol-agent` | Cluster expansion training and Monte Carlo |
| `drugdisc` | `drugdisc-agent` | Drug discovery tools (ADMET, fingerprints, docking prep) |
| `mattergen` | `mattergen-agent` | MatterGen generative crystal design |

> [!TIP]
> You only need to install the environments for the MCP servers you plan to use. For example, if you only work with MACE and Materials Project queries, install `base-agent` and `mace-agent` only.

### Installation
```bash
# Clone the repository
git clone git@github.com:bowen-bd/AtomisticSkills.git
cd AtomisticSkills

# Patch mcp_config.json with your local paths
python configure_mcp.py

# Setup environments (run only the ones you need)
bash conda-envs/base-agent/install.sh
bash conda-envs/mace-agent/install.sh
bash conda-envs/matgl-agent/install.sh
bash conda-envs/fairchem-agent/install.sh
bash conda-envs/atomate2-agent/install.sh
bash conda-envs/smol-agent/install.sh
bash conda-envs/drugdisc-agent/install.sh
bash conda-envs/mattergen-agent/install.sh
bash conda-envs/orca-agent/install.sh
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

#Required for running molecular DFT calculations with ORCA
ORCA_BINARY_PATH: /path/to/orca_directory/orca
```

### 2. Environment Variables
Alternatively, set variables in your shell (takes precedence over YAML):
```bash
export MP_API_KEY="your_key"
export ATOMATE2_REMOTE_PROJECT="remote_perlmutter"
export ORCA_BINARY_PATH="/path/to/orca_directory/orca"
```

---

## Server-Specific Setup

This project runs as a collection of MCP servers. Some require specific setup:

### 1. [base-server](src/mcp_server/base_server.py)
*   **Purpose**: Querying structure databases (Materials Project) and VASP I/O.
*   **Requirements**: `MP_API_KEY` must be set.

### 2. [atomate2](src/mcp_server/atomate2_server.py)
*   **Purpose**: Managing remote VASP calculations and workflows.
*   **Requirements**:
    *   `ATOMATE2_REMOTE_PROJECT` env var (e.g., `remote_perlmutter`).
    *   SSH Setup for NERSC (sshproxy).
    *   **Detailed Setup Guide**: [Remote Worker Setup (NERSC)](conda-envs/atomate2-agent/atomate2_remote_worker_setup.md)

### 3. MLIP Agents (Mace, MatGL, FairChem)
*   **Purpose**: Running ML potentials.
*   **Requirements**: [MLIP Environment Rules](.agents/rules/mcp-environments.md).
    *   These agents run in isolated conda environments.
    *   [MACE Setup](conda-envs/mace-agent/README.md)
    *   [MatGL Setup](conda-envs/matgl-agent/README.md)
    *   [FairChem Setup](conda-envs/fairchem-agent/README.md)
    *   [Smol Setup](conda-envs/smol-agent/README.md)

### MCP Server Configuration
The project is configured to run as a set of MCP servers. The base configuration is provided in [mcp_config.json](mcp_config.json).

#### Adapting Paths to Your Machine
The shipped `mcp_config.json` contains placeholder paths. Run the configure script to rewrite all `command` and `PYTHONPATH` entries to match your local setup:

```bash
# Auto-detects your conda/mamba base directory
python configure_mcp.py

# Or provide the conda base path explicitly
python configure_mcp.py /path/to/miniforge3
```

#### Integrating with Antigravity
To use these tools within Antigravity, you need to merge the server configurations into your local Antigravity MCP config:

1. Locate your Antigravity MCP configuration file (typically at `~/.gemini/antigravity/mcp_config.json`).
2. Copy the `mcpServers` definitions from this project's [mcp_config.json](mcp_config.json).
3. Paste them into your local configuration file.
4. Restart Antigravity to load the new tools.

> [!TIP]
> If you skip `configure_mcp.py`, ensure the `PYTHONPATH` in the `env` section of each server points to your absolute project path (e.g., `/path/to/AtomisticSkills`).

---

## Agent Intelligence & Automation
This project is optimized for use with coding AI copilots like **Antigravity**. It includes specialized instructions and pre-defined workflows to automate complex research tasks.

### The `.agents/` Directory
- **Rules (`.agents/rules/`)**: Contains project-specific standards, scientific constraints, and modeling guidelines. Antigravity automatically parses these to ensure all simulations and code follow best practices.
- **Workflows (`.agents/workflows/`)**: Defines standardized research procedures (e.g., calculating melting points or fine-tuning alloys). Antigravity can execute these step-by-step, managing the complex transitions between different conda environments and simulation stages.
- **Skills (`.agents/skills/`)**: Modular, reusable capabilities for complex tasks like melting point calculations, diffusion analysis, and MLIP training. Each skill is self-documented with instructions, scripts, and resources.

---

## Developer Guide

See [docs/developer_guide.md](docs/developer_guide.md) for architecture details, core components, development workflow, and troubleshooting.

---

## Best Practice for Users

1. Fork this repo and clone to local (preferable on a machine with local GPU resources so cheap MLIP tasks can be executed locally).
2. Open this repo through opening a new project in agentic IDEs like Antigravity / Cursor / Claude Code.
3. Setup conda envs, MCPs, make sure the agentic IDEs have access to the MCP tools, rules and SKILLs.
4. For customization, add your own SKILL / MCP tool / and Workflow to the project.
5. If you think your own tool / SKILL is beneficial (this requires the tool and implementation to be clean and open-sourced) to the public, please make a PR to the main branch. We will acknowledge all contributors.

---

## Contributing
**AtomisticSkills** is developed as an open framework for automated atomistic research. Contributions to new potentials, sampling methods, simulation workflows, or skills are welcome.


### Guidelines
- Follow the coding standards in `.agents/rules/coding-standards.md`
- Add tests for new functionality
- Update documentation (README, SKILL.md files)
- Ensure all MCP tools return clean JSON (no stdout pollution)

---

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
