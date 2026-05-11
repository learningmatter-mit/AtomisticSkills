# Example: Querying COD for Halite (NaCl)

This example demonstrates how to use the `query_optimade.py` script to query the Crystallography Open Database (COD) for sodium chloride structures containing 8 sites (a conventional FCC unit cell).

## Instructions

Run the query script:
```bash
# Env: base-agent
python ../../scripts/query_optimade.py \
    results.json \
    --filter 'elements HAS ALL "Na", "Cl"' \
    --provider cod \
    --max_results 5
```

## Expected Output

You should see a `results.json` file generated, containing the structure data directly from the OPTIMADE API.
The `results.json` output will contain a list of dictionaries with structure metadata (e.g. `chemical_formula_descriptive`, `elements`, `cartesian_site_positions`).

## Validation

NaCl typically forms in the Fm-3m (225) space group (Halite). In COD, queries for exactly 8 sites will usually retrieve the standard conventional unreduced cell containing 4 Na and 4 Cl atoms. You can inspect the json output's `cartesian_site_positions` to verify the characteristic FCC lattice atomic arrangements.
