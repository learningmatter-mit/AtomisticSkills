# Example: Querying AFLOW via OPTIMADE

This example demonstrates how to use the `query_optimade.py` script to fetch structures from the AFLOW database.

## Instructions

Run the query script:
```bash
# Env: base-agent
python ../../scripts/query_optimade.py results_aflow.json --filter 'elements HAS ALL "Na", "Cl"' --provider aflow
```

## Potential Limitations

*Note: Large OPTIMADE databases like AFLOW can sometimes experience endpoint instabilities or Internal Server Errors (Error 500) during heavily loaded traffic periods.* If the standard OPTIMADE query repeatedly fails or returns 0 results for AFLOW, you may need to either wait or use AFLOW's native REST APIs instead of the OPTIMADE endpoint.
