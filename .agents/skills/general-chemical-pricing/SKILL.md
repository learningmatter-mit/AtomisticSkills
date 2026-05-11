---
name: general-chemical-pricing
description: Retrieves averaged elemental prices and provides direct vendor purchase links for elements and precursor compounds.
category: [general, materials, chemistry]
---

# General Chemical Pricing

## Goal
To programmatically query averaged bulk commodity prices for pure chemical elements (in USD/kg) and to retrieve direct chemical vendor links for ordering specific precursor compounds or elemental forms. 

## Instructions

### 1. Get Pricing and Vendor Links
Use this script to search for the pricing details of a given element or chemical compound. The script aggregates Wikipedia's USGS elemental data with PubChem's registered supplier vendor lists.

```bash
# Env: base-agent
python .agents/skills/general-chemical-pricing/scripts/get_pricing.py <Query Name or Symbol>
```

**Parameters:**
* `<Query Name or Symbol>`: The name, symbol, or full compound name (e.g., "Lithium", "Li", "Lithium carbonate", "Li2CO3"). Ensure multi-word compounds are wrapped in quotes (e.g., `"Lithium carbonate"`).

## Examples
See [examples/lithium-carbonate/README.md](examples/lithium-carbonate/README.md) for a complete run of querying elemental lithium alongside a molecular precursor.

## Constraints
- **Environments**: The script requires the **`base-agent`** Conda environment because it uses standard requests, beautifulsoup4, and pubchempy libraries. **Each code block MUST specify the environment.**
- **Price Precision**: Elemental bulk prices presented are averaged and highly dependent on market fluctuations and the reference year (scraped dynamically from Wikipedia's USGS Mineral Commodity list).
- **Vendor Links**: For compounds, live price points are not freely accessible via unauthenticated APIs. The skill provides a robust PubChem URL that aggregates active supplier links where live pricing can be interactively observed.

## References
- USGS Mineral Commodity Summaries (via Wikipedia). [Prices of chemical elements](https://en.wikipedia.org/wiki/Prices_of_chemical_elements)
- PubChem PUG REST API for retrieving CIDs. [PubChem API](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
