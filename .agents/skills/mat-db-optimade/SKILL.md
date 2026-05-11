---
name: mat-db-optimade
description: Query the Crystallography Open Database (COD) and other OPTIMADE-compliant databases for experimental crystal structures.
category: materials
---

# mat-db-optimade

## Goal
To query experimental crystal structures (e.g. from the Crystallography Open Database - COD, NOMAD) using the standardized REST API provided by OPTIMADE, and to extract the structural data and metadata in a JSON format.

## Instructions

### Step 1. Querying an OPTIMADE Database

Use the `query_optimade.py` script to fetch structure data based on standard OPTIMADE query language filters.

```bash
# Env: base-agent
python .agents/skills/mat-db-optimade/scripts/query_optimade.py \
    results.json \
    --filter 'elements HAS ALL "Na", "Cl"' \
    --provider cod \
    --max_results 5
```

Parameters:
- `output`: Path to the output JSON file where results will be stored.
- `--filter`: The OPTIMADE filter string. (e.g., `elements HAS ALL "O", "Ti"`).
- `--provider`: Comma-separated list of database providers. Defaults to `cod`.
- `--max_results`: Maximum number of structures to pull per provider. Defaults to 10.

### Supported Database Providers (Common short IDs)
When using the `--provider` parameter, you can provide the following short string identifiers for well-known databases:
- **`cod`**  – **Crystallography Open Database**: The largest open-access collection of experimentally determined crystal structures.
- **`nmd`**  – **NOMAD**: Comprehensive repository of both theoretical methods and experimental configurations.
- **`aflow`** – **AFLOW**: Automatic-FLOW Computational Materials Data Repository.
- **`mp`**   – **Materials Project**: Well-known theoretical stable/unstable materials repository based on DFT.
- **`oqmd`** – **Open Quantum Materials Database**: High-throughput DFT database of thermodynamic and structural properties.
- **`jarvis`** – **JARVIS**: Joint Automated Repository for Various Integrated Simulations.

## Constraints
- **Environments**: The scripts require the `base-agent` Conda environment.
- **Provider Status**: Sometimes specific providers (like Aflow or NOMAD) may experience API downtime. If a provider fails, the `optimade` client will log warnings.

## References
- Andersen, C. W., et al. "OPTIMADE, an API for exchanging materials data." *Scientific Data*, 8, 217 (2021). [DOI](https://doi.org/10.1038/s41597-021-00974-z)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
