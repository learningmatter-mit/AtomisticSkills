---
name: mat-db-nist-janaf
description: Query the NIST Chemistry WebBook (which includes JANAF thermochemical tables) for standard experimental thermochemistry properties.
category: materials
---

# mat-db-nist-janaf

## Goal
To query experimental temperature-dependent thermodynamic properties and standard states (e.g. Standard Enthalpy of Formation $\Delta_f H^\circ_{298}$, Standard Entropy $S^\circ_{298}$, and $C_p$) from the NIST Chemistry WebBook and JANAF tables for benchmarking against DFT/MLIP calculations.

## Instructions

### Step 1. Query Thermochemistry Data

Use the `query_janaf.py` script to fetch thermodynamic data for a given chemical formula. The script automatically searches the WebBook for the closest matching standard element or compound and parses the HTML tables to extract the gas-phase or condensed-phase standard thermochemistry values.

```bash
# Env: base-agent
python .agents/skills/mat-db-nist-janaf/scripts/query_janaf.py <formula> <output_json>
```

Parameters:
- `formula`: The chemical formula to query (e.g., `CH4`, `CO2`, `H2O`).
- `output_json`: Path to the output JSON file where results will be stored.

## Constraints
- **Environments**: The scripts require the `base-agent` Conda environment.
- **Scraping Dependability**: This script utilizes HTML scraping (`beautifulsoup4`). If the NIST WebBook layout changes in the future, the table selectors may need to be updated.
- **Isotopes**: By default, the script skips explicitly isotopically-labelled variants (unless it's the only match) to return the standard natural-abundance compound.

## References
- Linstrom, P.J. and Mallard, W.G., Eds., *NIST Chemistry WebBook, NIST Standard Reference Database Number 69*, National Institute of Standards and Technology, Gaithersburg MD. [URL](https://webbook.nist.gov)
- Chase, M.W., Jr., *NIST-JANAF Thermochemical Tables, Fourth Edition*, J. Phys. Chem. Ref. Data, Monograph 9, 1998, 1-1951.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
