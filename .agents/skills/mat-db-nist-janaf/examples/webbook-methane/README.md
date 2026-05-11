# Example: Querying NIST WebBook for Methane Thermochemistry

This example demonstrates how to use the `query_janaf.py` script to retrieve standard experimental gas-phase thermochemistry values for Methane ($CH_4$).

## Instructions

Run the query script:
```bash
# Env: base-agent
python ../../scripts/query_janaf.py CH4 methane_thermo.json
```

## Expected Output

You should see a `methane_thermo.json` file generated, containing the parsed experimental values for quantities like $\Delta_f H^\circ$ (Standard enthalpy of formation) and $S^\circ$ (Entropy).

## Validation

According to the NIST-JANAF tables and standard compilation references (e.g. Chase 1998, Prosen and Rossini 1945), the experimental standard enthalpy of formation ($\Delta_f H^\circ_{gas}$) for Methane is approximately `-74.8 kJ/mol`. You can inspect the `methane_thermo.json` output to ensure the parsed `value` field closely aligns with this established literature standard.
