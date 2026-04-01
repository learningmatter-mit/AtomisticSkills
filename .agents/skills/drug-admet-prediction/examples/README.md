# ADMET Prediction Example

This example computes molecular descriptors and drug-likeness heuristics for three common drugs: caffeine, aspirin, and ibuprofen.

## Files

- `compounds.smi`: SMILES file with 3 compounds
- `compounds_admet.json`: Full output with descriptors, Ro5, Veber, and QED scores

## How to reproduce

Using the drugdisc MCP tool:

```python
mcp_drugdisc_compute_molecular_descriptors(
    smiles_file=".agents/skills/drug-admet-prediction/examples/compounds.smi",
    output_file="compounds_admet.json"
)
```

## Results Summary

All 3 molecules passed Lipinski's Rule of Five and Veber criteria:

| Molecule | MW | LogP | TPSA | HBD | HBA | Ro5 | Veber | QED |
|----------|------|------|------|-----|-----|-----|-------|-----|
| Caffeine | 194.19 | -1.03 | 61.82 | 0 | 6 | ✅ | ✅ | 0.54 |
| Aspirin | 180.16 | 1.31 | 63.60 | 1 | 3 | ✅ | ✅ | 0.55 |
| Ibuprofen | 206.28 | 3.07 | 37.30 | 1 | 1 | ✅ | ✅ | 0.82 |

Ibuprofen shows the highest QED (drug-likeness) score of 0.82.

Author: Matthew Cox
Contact: github username <mcox3406>
