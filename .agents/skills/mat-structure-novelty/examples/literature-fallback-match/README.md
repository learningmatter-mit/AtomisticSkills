# Example: Literature Fallback Matching

This example demonstrates how the `mat-structure-novelty` skill handles a material that **does not exist** in the Materials Project or ICSD structural databases, but **has** been reported in literature.

In this case, we use `Li2ZrCl6` (LZC)—a known halide solid-state electrolyte (e.g., from arXiv:2403.08237) that currently has 0 entries in the Materials Project.

## Run Instructions

1. Attempting to search MP for candidate structures would fail or yield no candidates. But you can run the matcher on the target structure anyway. We provide [Li2ZrCl6.cif](Li2ZrCl6.cif) as the test structure.

2. Run the script:

```bash
# Env: base-agent
# You don't need to pass a second argument. It will automatically query MP. The API will find 0 polymorphs, triggering the literature fallback.
python ../../scripts/match_structure.py Li2ZrCl6.cif --output fallback_match.json
```

3. **Expected Output:**
The script will output `match_found: false` regarding structural similarity. However, it will automatically extract the symmetry space group of the provided structure (`P-31m (trigonal)` in this example). It then queries the OpenAlex literature database for the formula **AND** the symmetry (e.g. `"Li2ZrCl6" AND ("P-31m" OR "trigonal")`), ensuring the reported material is the exact same polymorph as the provided structure. It will successfully identify that this polymorph is "literature reported" by returning the DOIs of up to 5 experimental or computational papers mentioning it. This result is also saved in the output JSON.
