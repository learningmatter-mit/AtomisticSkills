# Developer Guide

## Architecture Overview

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

---

## Core Components

### 1. MCP Servers (`src/mcp_server/`)

Each MCP server is a standalone Python module that exposes tools via the FastMCP framework:

| Server | Environment | Primary Functionality |
|--------|-------------|----------------------|
| [mace_server.py](../src/mcp_server/mace_server.py) | `mace-agent` | MACE model loading, prediction, relaxation, MD, fine-tuning |
| [matgl_server.py](../src/mcp_server/matgl_server.py) | `matgl-agent` | CHGNet/M3GNet/TensorNet operations, bandgap prediction |
| [fairchem_server.py](../src/mcp_server/fairchem_server.py) | `fairchem-agent` | UMA/ESEN models |
| [base_server.py](../src/mcp_server/base_server.py) | `base-agent` | Materials Project queries, VASP I/O, research directory management |
| [atomate2_server.py](../src/mcp_server/atomate2_server.py) | `atomate2-agent` | Query remote DFT databases, job status monitoring |
| [smol_server.py](../src/mcp_server/smol_server.py) | `smol-agent` | Cluster expansion training and Monte Carlo simulations |
| [drugdisc_server.py](../src/mcp_server/drugdisc_server.py) | `drugdisc-agent` | Molecular descriptors, standardization, PDBQT conversion |
| [mattergen_server.py](../src/mcp_server/mattergen_server.py) | `mattergen-agent` | MatterGen generative crystal design |

### 2. Utility Modules (`src/utils/`)

Supporting libraries shared across MCP servers:

| Module | Purpose |
|--------|---------|
| `mlips/` | Unified MLIP wrappers (MACE, MatGL, FairChem, MatterGen) with common predict / relax / MD / fine-tune interface |
| `dft/` | VASP input generation and output parsing via Pymatgen |
| `drugdisc_utils.py` | RDKit-based molecular descriptors, standardization, and PDBQT conversion |
| `structure_utils.py` | Convert between ASE Atoms, Pymatgen Structure, and dict formats |
| `structure_viz.py` | Crystal structure visualization and rendering |
| `disordered_material/` | Order-disorder sampling for partial-occupancy structures |
| `mlips/md_utils.py` | MD monitors (explosion, volume, melting, equilibration detection) |
| `config_utils.py` | Global configuration and API key management |

### 3. Skills (`.agents/skills/`)

Skills are **modular, self-contained capabilities** that combine multiple tools and scripts to accomplish complex research tasks. Each skill lives in its own directory with a standardized structure:

```
.agents/skills/<skill-name>/
├── SKILL.md              # Instructions and documentation
├── scripts/              # Python/Bash helper scripts
├── examples/             # Reference input/output files
└── resources/            # Configuration files, templates
```

**How Skills Work**:
1. The agent reads `SKILL.md` to understand the task
2. Follows step-by-step instructions
3. Executes scripts from the `scripts/` directory in the appropriate environment
4. Uses resources and examples as templates

> [!TIP]
> To create a new skill, follow the guidelines in [skill-standards.md](../.agents/rules/skill-standards.md).

---

## Development Workflow

### Adding a New MCP Tool

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

### Implementing a New Skill

1. Create the skill directory: `.agents/skills/<skill-name>/`
2. Write `SKILL.md` following the [standards](../.agents/rules/skill-standards.md)
3. Add helper scripts to `scripts/` (specify required conda environment)
4. Provide examples and resources as needed
5. Test the skill end-to-end with Antigravity

### Running Tests

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

## Important Technical Details

### Environment Isolation
- Each MCP server runs in a **dedicated conda environment** to avoid dependency conflicts
- The `PYTHONPATH` must point to the project root for all servers
- When debugging, **always activate the correct environment** before importing modules

### Stdout/Stderr Handling
All MCP servers use centralized output redirection (see `src/utils/mcp_utils.py`) to prevent:
- Print statements from polluting MCP responses
- Training logs from breaking the JSON protocol
- Debugging output from interfering with tool calls

For a complete guide on how AtomisticSkills mitigates this execution noise issue across heterogeneous infrastructures, see the [MCP STDIO Redirection Guide](mcp_stdio_redirection.md).

> [!WARNING]
> Never use raw `print()` in MCP tool functions expecting the user to read them cleanly. Use proper `logging`. Legacy outputs are automatically routed to standard error by the server.

### Research Directory Management
Every research task should:
1. Call `create_research_dir(research_topic)` to establish a timestamped directory
2. Save all results (structures, plots, logs) to this directory
3. Document findings in the research directory

---

## Troubleshooting

### MCP Server Not Loading
- Check `mcp_config.json` for correct Python paths
- Verify `PYTHONPATH` points to project root
- Restart Antigravity after configuration changes

### Import Errors in Scripts
- Ensure correct conda environment is activated
- Check that `PYTHONPATH` includes project root: `export PYTHONPATH=/path/to/AtomisticSkills`
- Use absolute imports: `from src.utils.mlips.mace_wrapper import MACEWrapper`

### Fine-Tuning Fails
- Verify stress units are in eV/Å³ (see [stress-units.md](../.agents/rules/stress-units.md) for details)
- Check training data format matches expected structure
- For small datasets (<500 structures), use `freeze_backbone=True`

### MD Simulation Explodes
- Enable MD monitors: `monitor=True, monitor_type=["explosion", "volume"]`
- Reduce timestep (default: 1fs, try 0.5fs)
- Check initial structure is relaxed with `fmax < 0.05 eV/Å`
