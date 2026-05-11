---
name: chem-db-mof
description: Query multiple MOF databases (QMOF via MPContribs; ARC-MOF DB7/Majumdar et al. via Zenodo) and download CIF structures with optional element or identifier filters.
category: chemistry
---

# chem-db-mof

## Goal

Provide a unified interface for retrieving Metal-Organic Framework (MOF) crystal structures from multiple curated databases. Currently supported:

| Database | Alias | Size | Access | Structures |
|---|---|---|---|---|
| Quantum MOF (QMOF) | `qmof` | ~20,000 DFT-relaxed | MPContribs API | DFT-optimized CIFs + bandgaps |
| ARC-MOF DB7 (Majumdar et al.) | `arcmof-majumdar` | 12,316 hypothetical | Zenodo stream | CIFs with REPEAT partial charges |

## Prerequisites

- **Environment**: `base-agent`
- **Packages**: `mpcontribs-client`, `requests`, `pandas`, `pymatgen`
- **Credentials**: `MP_API_KEY` environment variable (required for `qmof` only)

## Instructions

### Step 1: Choose a database and set filters

Decide which database to query and which element/identifier filters to apply.

**For QMOF** — best for DFT-validated, experimentally-derived MOFs:
- Use `--formula` for element filtering (e.g., `Zn` or `Cu,N,O`)
- Use `--identifier` for a specific CSD refcode (e.g., `KAXQIL`)

**For ARC-MOF DB7 (Majumdar et al.)** — best for diverse hypothetical MOFs with underrepresented inorganic SBUs:
- Use `--elements` for element filtering (e.g., `Zn,O,C`)
- Use `--identifier` for a specific structure ID (e.g., `DB7_00042`)
- **First run**: downloads `geometric_properties.csv` (~110 MB) to `~/.cache/arcmof/` — one-time only; subsequent runs are fast

### Step 2: Run the query

```bash
# Env: base-agent
# QMOF — 10 Zn-containing MOFs
MP_API_KEY=<your_key> python .agents/skills/chem-db-mof/scripts/query_mof_db.py \
    --database qmof \
    --formula Zn \
    --max-results 10 \
    --output-dir ./research/<date>_<task>/structures/qmof
```

```bash
# Env: base-agent
# ARC-MOF DB7 (Majumdar) — 20 Zn,O,C hypothetical MOFs
python .agents/skills/chem-db-mof/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --elements Zn,O,C \
    --max-results 20 \
    --output-dir ./research/<date>_<task>/structures/arcmof_db7
```

```bash
# Env: base-agent
# ARC-MOF DB7 — retrieve a specific structure by identifier
python .agents/skills/chem-db-mof/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --identifier DB7_00042 \
    --output-dir ./research/<date>_<task>/structures/arcmof_db7
```

### Available Arguments

| Argument | Applies to | Description |
|---|---|---|
| `--database` | both | `qmof` or `arcmof-majumdar` |
| `--formula` | qmof | Element/formula filter string (e.g., `Zn,O,C`) |
| `--elements` | arcmof-majumdar | Comma-separated required elements; ALL must be present |
| `--identifier` | both | Specific structure name or ID substring |
| `--max-results` | both | Max CIFs to download (default: 10) |
| `--output-dir` | both | Directory for output CIF files |
| `--cache-dir` | arcmof-majumdar | Override default cache `~/.cache/arcmof/` |

### Step 3: Inspect outputs

The script saves:
- Individual `.cif` files named by structure identifier
- `arcmof_db7_metadata.csv` (ARC-MOF only) — geometric properties for the downloaded subset

Verify the download:
```bash
ls -lh <output-dir>/*.cif | head -20
```

## Download Behavior: ARC-MOF DB7

The first call with `--database arcmof-majumdar` performs:

1. **Metadata download** (~110 MB, one-time): `geometric_properties.csv` cached at `~/.cache/arcmof/`
2. **DB7 filtering**: identifies the 12,316 Majumdar structures from the full 288k-entry CSV
3. **CIF streaming**: streams the ARC-MOF tarball (`ARCMOF_20241004.tar.gz`, ~670 MB) and extracts only the requested CIFs — the stream is read once but only matching files are written to disk

Subsequent runs with the same `--output-dir` skip already-downloaded CIFs.

## Examples

**Example 1: Query Zn MOFs from QMOF for CO₂ screening pre-processing**
```bash
# Env: base-agent
MP_API_KEY=<your_mp_api_key> \
python .agents/skills/chem-db-mof/scripts/query_mof_db.py \
    --database qmof \
    --formula Zn \
    --max-results 10 \
    --output-dir ./research/2026-03-27_test/qmof_zn
```

**Example 2: Query Zn, Ni, or Mg hypothetical MOFs from ARC-MOF DB7**
```bash
# Env: base-agent
# Zn-based
python .agents/skills/chem-db-mof/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --elements Zn,O,C \
    --max-results 50 \
    --output-dir ./research/2026-03-27_arcmof_zn

# Ni-based
python .agents/skills/chem-db-mof/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --elements Ni,O,C \
    --max-results 50 \
    --output-dir ./research/2026-03-27_arcmof_ni

# Mg-based
python .agents/skills/chem-db-mof/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --elements Mg,O,C \
    --max-results 50 \
    --output-dir ./research/2026-03-27_arcmof_mg
```

> **Tip:** You can expand diversity by adding more elements to `--elements` (e.g., `Zn,Ni,O,C,N` to retrieve MOFs containing all of those elements simultaneously), or run separate queries per metal node and combine the resulting CIF directories for a broader screening campaign.

## Constraints

- **API limits**: QMOF via MPContribs has rate limits; keep `--max-results` ≤ 100 per call.
- **ARC-MOF first-run time**: Downloading the metadata CSV (~110 MB) takes ~1–2 min; streaming the tarball for CIF extraction adds ~5–15 min depending on how many structures are requested and network speed.
- **ARC-MOF CIF fallback**: If some DB7 structures are not found in `ARCMOF_20241004.tar.gz`, they may reside in `all_structures_1.tar.gz` or `all_structures_2.tar.gz`. Update `ARCMOF_STRUCTURES_NAME` in the script if needed.
- **Element filtering (ARC-MOF)**: Requires a `formula` or `chemical_formula` column in `geometric_properties.csv`. If the column is absent, all DB7 entries are returned without element filtering.
- **Post-download**: Structures from ARC-MOF DB7 include REPEAT partial charges embedded in the CIF. These can be used directly for classical force-field simulations but should be relaxed with an MLIP before running Widom insertion (see [`chem-sorption-relax`](../chem-sorption-relax/SKILL.md)).

## References

- Raza, A. et al., "ARC–MOF: A Diverse Database of Metal-Organic Frameworks with DFT-Derived Partial Atomic Charges and Descriptors for Machine Learning", *Chem. Mater.*, 2022. [DOI: 10.1021/acs.chemmater.2c02485](https://doi.org/10.1021/acs.chemmater.2c02485)
- Majumdar, S., Moosavi, S.M., Jablonka, K.M., Ongari, D., Smit, B., "Diversifying Databases of Metal Organic Frameworks for High-Throughput Computational Screening", *ACS Appl. Mater. Interfaces*, 2021. [DOI: 10.1021/acsami.1c16220](https://doi.org/10.1021/acsami.1c16220); dataset: *Materials Cloud Archive* 2021.126, [DOI: 10.24435/materialscloud:yn-de](https://doi.org/10.24435/materialscloud:yn-de)
- Chung, Y.G. et al., "Computation-Ready, Experimental Metal-Organic Frameworks: A Tool To Enable High-Throughput Screening of Nanoporous Crystals", *Chem. Mater.*, 2014 (QMOF precursor). [DOI: 10.1021/cm502594j](https://doi.org/10.1021/cm502594j)
- Rosen, A.S. et al., "Machine learning the quantum-chemical properties of metal-organic frameworks for accelerated materials discovery", *Matter*, 2021 (QMOF). [DOI: 10.1016/j.matt.2021.02.015](https://doi.org/10.1016/j.matt.2021.02.015)

---

**Author:** Sauradeep Majumdar
**Contact:** [GitHub @sauradeep93](https://github.com/sauradeep93)
