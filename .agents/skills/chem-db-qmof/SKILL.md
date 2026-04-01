---
name: chem-db-qmof
description: Query the Quantum MOF (QMOF) database via Materials Project's MPContribs platform for DFT-computed properties (bandgap) and optimized crystal structures of Metal-Organic Frameworks.
category: [materials, chemistry]
---

# chem-db-qmof

## Goal

To retrieve computational data and relaxed crystal structures (.cif) for roughly 20,000 Metal-Organic Frameworks (MOFs) that have been thoroughly characterized using DFT. QMOF is hosted by the Materials Project under the "MPContribs" project (`qmof`). This skill allows you to retrieve relaxed CIF structures by reference name, CSD refcode, or specific structural/electronic properties like bandgap.

## Prerequisites

- **Dependency**: `mpcontribs-client` must be installed.
- **Environment**: Execution happens in the `base-agent` environment.
- **Credentials**: Requires the standard Materials Project API key exported as `MP_API_KEY`.

## Instructions

1. **Query Database**: Use the provided script `query_qmof.py` to search by formula or identifier.

```bash
# Env: base-agent
python .agents/skills/chem-db-qmof/scripts/query_qmof.py \
    --formula "Zn" \
    --max-results 5 \
    --output-dir ./research/qmof_results
```

### Available Arguments:
- `--formula`: Search by chemical formula or elements (e.g., `Zn,O,C`).
- `--identifier`: Search by specific CSD refcode or MOF common name (e.g., `KAXQIL`).
- `--max-results`: Maximum number of structures to download (default: 5).
- `--output-dir`: Directory to save the resulting `.cif` files.

## Examples

**Example 1: Automated testing script (Zinc MOF)**
```bash
# Env: base-agent
bash .agents/skills/chem-db-qmof/examples/test_qmof.sh
```

**Example 2: Query for 5 MOFs containing Zinc manually**
```bash
# Env: base-agent
python .agents/skills/chem-db-qmof/scripts/query_qmof.py \
    --formula "Zn" \
    --max-results 5 \
    --output-dir ./results/qmof_zn
```

**Example 2: Retrieve a specific MOF by identifier**
```bash
# Env: base-agent
python .agents/skills/chem-db-qmof/scripts/query_qmof.py \
    --identifier "KAXQIL" \
    --max-results 1 \
    --output-dir ./results/qmof_kaxqil
```

## Constraints

- **API Limits**: The Materials Project/MPContribs API has rate limits. Do not use extremely large values for `--max-results` unless necessary.
- **Availability**: If you cannot find a MOF in QMOF via the script, or if the API query is overly complex, you can also search the QMOF database manually through the Materials Project web interface under the "Contributions" section.

---

**Author:** Bowen Deng
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
