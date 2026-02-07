# HTVS Query Skill

**Goal**: Query and retrieve data from the HTVS Django database, including DFT calculation results, structure models, and job statuses.

## When to use HTVS Query

Use these tools when:
1.  **Retrieving Results**: You need the energy, forces, or stress from completed DFT calculations (`Calc` records).
2.  **Accessing Models**: You need to retrieve relaxed structures or target configurations (`Geom` / `Species` records).
3.  **Monitoring Status**: You need to check the progress of submitted jobs by project (group) or UUID.
4.  **Dataset Collection**: You are gathering high-fidelity labels for MLIP fine-tuning.

## Available Tools

### Specialized Querying
- **`query_htvs_calcs(group_name, formula=None, limit=10)`**: Explicitly retrieve DFT results (`Calc` records) for a specific project. Returns energy, configuration, and completion time.
- **`query_htvs_geoms(group_name, formula=None, limit=10)`**: Retrieve structure models (`Geom` records) produced by jobs in a specific project.

### General Querying & Status
- **`query_htvs_structures(group_name, structure_type='Crystal')`**: Query higher-level objects (`Crystal`, `Surface`, `Species`).
- **`get_htvs_job_status(job_uuids=None, group_name=None)`**: Check if jobs are `pending`, `running`, or `done`.
- **`get_htvs_job_results(job_uuids)`**: Get comprehensive details for specific jobs, including their configuration and associations.

## Guidelines

1.  **Group Filtering**: Always specify a `group_name` to narrow down results to your specific project.
2.  **Formula Search**: Use the `formula` argument (e.g., "LiFePO4") to filter for specific chemistries within a group.
3.  **Env Verification**: Ensure you are in the `htvs-agent` environment to access the database.

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
