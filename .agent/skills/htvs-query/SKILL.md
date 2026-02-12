# HTVS Query Skill

**Goal**: Query and retrieve data from the HTVS Django database, including DFT calculation results, structure models, and job statuses.

## When to use HTVS Query

Use these tools when:
1.  **Retrieving Results**: You need the energy, forces, or stress from completed DFT calculations (`Calc` records).
2.  **Accessing Models**: You need to retrieve relaxed structures or target configurations (`Geom` / `Species` records).
3.  **Monitoring Status**: You need to check the progress of submitted jobs by project (group) or UUID.
4.  **Dataset Collection**: You are gathering high-fidelity labels for MLIP fine-tuning.

## Available Tools

### Core MCP Tools (General Purpose)
Use these tools for programmatic access within agent workflows:
- **`query_htvs_results(group_name, settings_module, ...)`**: Query detailed calc results (energy, forces, stress) - **USE THIS** for retrieving DFT calculation data.
- **`get_htvs_job_status(settings_module, job_uuids=None, group_name=None, limit=10)`**: Check job progress.
- **`get_htvs_job_results(job_uuids, settings_module)`**: Get comprehensive associations for specific jobs.

### Database Management Tools
- **`save_htvs_crystals`**, **`save_htvs_surfaces`**: Save atomic structures to DB.
- **`create_htvs_group`**: Create new project groups.
- **`inspect_chem_config`**: Review VASP job templates.
- **`request_htvs_job`, `build_htvs_job`, `parse_htvs_job`**: Core job lifecycle tools.

### Specialized Queries → Use Skill Scripts

> [!IMPORTANT]
> **Specialized detailed queries (surfaces, crystals, jobs) have been moved to skill scripts** for better maintainability and to keep the MCP server focused on core functionality.

For detailed queries with structure metadata:
- **Surfaces with Miller indices** → Use `scripts/query_surfaces.py`
- **Crystals with space groups** → Use `scripts/query_crystals.py`
- **Jobs with timing data** → Use `scripts/query_jobs.py`

All query tools include the database `id` for every record retrieved.

## Guidelines

1.  **Automatic Setup**: Database configuration is handled automatically by the tools. You don't need to manually call `setup_htvs_django` unless working outside the MCP framework.
2.  **Group Filtering**: Always specify a `group_name` to narrow down results to your specific project.
3.  **Formula Search**: Use the `formula` argument (e.g., "LiFePO4") to filter for specific chemistries within a group.
4.  **Env Verification**: Ensure you are in the `htvs-agent` environment when using standalone scripts.

> **Note**: The HTVS tools use a modular utility structure (`src/utils/htvs/`) with separate modules for configuration, job handling, database operations, and VASP utilities. All inline script logic has been extracted into reusable functions for better maintainability.

## Examples

### Querying DFT Energies
```python
# Select "done" calculations for a specific project
calcs = query_htvs_calcs(group_name="LFP_stability", formula="LiFePO4")
# Each record contains 'final_energy' and 'uuid'
```

### Retrieving Geometries
```python
# Get relaxed geometries
geoms = query_htvs_geoms(group_name="surface_sampling", limit=50)
```

## Utility Scripts

The skill includes a standalone script `query_results.py` for batch retrieval and saving of results.

### Save results to JSON/CSV
Navigate to the skill's scripts directory or use the full path:
```bash
conda activate htvs-agent
python .agent/skills/htvs-query/scripts/query_results.py --group "LFP_stability" --output lfp_results.json
```

### Query surfaces cut from bulk
Find surfaces associated with a specific group and their parent bulk structures:
```bash
conda activate htvs-agent
python .agent/skills/htvs-query/scripts/query_surfaces.py --group "perovskite" --limit 10 --output surfaces.json
```

### Query Crystals
Retrieve crystal structures and their space groups:
```bash
conda activate htvs-agent
python .agent/skills/htvs-query/scripts/query_crystals.py --group "perovskite" --limit 10 --output crystals.json
```

### Native MCP Tool Queries (Recommended)
You can call these tools directly via the LLM agent or MCP client:

```python
# Query results with for a group
query_htvs_results(group_name="perovskite", settings_module="djangochem.settings.orgel")

# Query jobs with status filtering
query_htvs_jobs_detailed(group_name="perovskite", status="done")
```

All native tools support the `output_file` argument to save results directly to a JSON file.

### CLI Standalone Scripts
For manual CLI use, standalone scripts are available in `.agent/skills/htvs-query/scripts/`. These scripts automatically resolve the HTVS path from `mcp_config.json` by importing the setup logic directly from the `htvs_server` module.

### Switching Databases
All scripts support the `--db` argument to switch between different HTVS databases (standard choices are `orgel` and `toy`):
```bash
# Query the toy database
python .agent/skills/htvs-query/scripts/query_results.py --group "test_group" --db "toy"
```

**Common Arguments**:
- `--group`: (Required) Name of the HTVS project group.
- `--db`: Database settings module name (e.g., "orgel", "toy"). Defaults to "orgel".
- `--limit`: Max number of records to retrieve.
- `--output`: Path to the output file.

**Specific Arguments for `query_results.py`**:
- `--formula`: Filter results by chemical formula (e.g., "LiFePO4").

Author: Hoje Chun
Contact: github username <HojeChun>
