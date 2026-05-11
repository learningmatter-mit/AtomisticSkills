# Lithium Pricing and Ordering Example

## Goal
To demonstrate how to look up the bulk averaged price of elemental Lithium, and obtain a vendor ordering link for the precursor compound "Lithium carbonate".

## Instructions

```bash
# Env: base-agent
python .agents/skills/general-chemical-pricing/scripts/get_pricing.py Lithium
```

### Expected Output
```text
Searching pricing information for: Lithium

=== Elemental Bulk Pricing ===
Averaged bulk price for Lithium: $81.4–85.6/kg (Year: 2020)
(Source: USGS Mineral Commodity Summaries via Wikipedia)

=== Compound / Precursor Vendor Link ===
PubChem CID: 3028194
SMILES: [Li]
Vendor Order Link: https://pubchem.ncbi.nlm.nih.gov/compound/3028194#section=Chemical-Vendors
Note: Follow the link to see a list of commercial suppliers and purchase the compound.
```

To look up pricing vendor links for a specific compound precursor:
```bash
# Env: base-agent
python .agents/skills/general-chemical-pricing/scripts/get_pricing.py "Lithium carbonate"
```

### Expected Output
```text
Searching pricing information for: Lithium carbonate

=== Compound / Precursor Vendor Link ===
PubChem CID: 11125
SMILES: C(=O)(O)O.[Li].[Li]
Vendor Order Link: https://pubchem.ncbi.nlm.nih.gov/compound/11125#section=Chemical-Vendors
Note: Follow the link to see a list of commercial suppliers and purchase the compound.
```

## Literature Validation
The fetched bulk elemental price for Lithium from this run accurately mirrors the historical tracking reported in the USGS Mineral Commodity Summaries for recent years, which places Lithium carbonate bounds consistently in the high tens-to-hundreds of thousands of dollars per metric ton (extrapolating to ~$80/kg depending on battery-grade purity).
