# Example: Querying NOMAD via OPTIMADE

This example demonstrates how to use the `query_optimade.py` script to fetch structures from the NOMAD database. 
NOMAD is registered under the provider short-id `nmd`.

## Instructions

Run the query script:
```bash
# Env: base-agent
python ../../scripts/query_optimade.py results_nomad.json --filter 'elements HAS ALL "Na", "Cl" AND nelements=2' --provider nmd
```

## Expected Output

The script successfully returns matching structures directly from the `nomad-lab.eu` base URL. 

*Note: NOMAD is highly optimized and returns matching configurations quickly.*
