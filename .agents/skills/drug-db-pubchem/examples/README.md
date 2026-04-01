# Aspirin PubChem Query Example

This example demonstrates looking up aspirin by name in PubChem, retrieving its computed properties and synonyms.

## Files

- `aspirin.json`: Query result for aspirin (CID 2244), including molecular properties (MW, XLogP, TPSA, HBD/HBA), SMILES, InChI/InChIKey, and top synonyms

## How to reproduce

From the project root:

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --name "aspirin" \
  --name_type complete \
  --max_results 3 \
  --outdir .agents/skills/drug-db-pubchem/examples \
  --output aspirin.json
```

## Results

Returns CID 2244 with key properties:

| Property | Value |
|---|---|
| CID | 2244 |
| Molecular Formula | C9H8O4 |
| Molecular Weight | 180.16 |
| IUPAC Name | 2-acetyloxybenzoic acid |
| XLogP | 1.2 |
| TPSA | 63.6 |
| HBD / HBA | 1 / 4 |
| Rotatable Bonds | 3 |
