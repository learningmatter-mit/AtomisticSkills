---
name: chem-db-mof
description: Query multiple MOF databases (QMOF via MPContribs; ARC-MOF DB7/Majumdar et al. via Materials Cloud) and download CIF structures with optional element or identifier filters.
metadata:
  category: [chemistry]
  venv: [cpu]
---

# chem-db-mof

## Goal

Provide a unified interface for retrieving Metal-Organic Framework (MOF) crystal structures from multiple curated databases. Currently supported:

| Database | Alias | Size | Access | Structures |
|---|---|---|---|---|
| Quantum MOF (QMOF) | `qmof` | ~20,000 DFT-relaxed | MPContribs API | DFT-optimized CIFs + bandgaps |
| ARC-MOF DB7 (Majumdar et al.) | `arcmof-majumdar` | 23,891 hypothetical (`ddmof_1`–`ddmof_23891`) | Materials Cloud archive | CIFs with EQeq partial charges + `mof_data.csv` metadata |

## Prerequisites

- **Environment**: `cpu` (commands run through `venv/run cpu ...`)
- **Packages**: `mpcontribs-client`, `requests`, `pandas`, `pymatgen`
- **Credentials**: `MP_API_KEY` environment variable (required for `qmof` only)

## Instructions

### Step 1: Choose a database and set filters

Decide which database to query and which element/identifier filters to apply.

**For QMOF** — best for DFT-validated, experimentally-derived MOFs:
- Use `--formula` for element filtering (e.g., `Zn` or `Cu,N,O`)
- Use `--identifier` for a specific CSD refcode (e.g., `KAXQIL`)

**For ARC-MOF DB7 (Majumdar et al.)** — best for diverse hypothetical MOFs with underrepresented inorganic SBUs:
- Use `--elements` for element filtering (e.g., `Zn`, or `Zn,F` for fluorinated Zn MOFs); by default every listed element must be present, while `--element-match any` keeps structures containing at least one of them
- Use `--identifier` for a specific structure name (e.g., `ddmof_559`); a full name matches exactly, anything else matches as a substring
- **First run**: downloads the Majumdar archive `mof_data.tar.gz` (~149 MB) from Materials Cloud to `~/.cache/arcmof/` — one-time only; subsequent runs are fast

### Step 2: Run the query

```bash
# QMOF — 10 Zn-containing MOFs
MP_API_KEY=<your_key> ${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/query_mof_db.py \
    --database qmof \
    --formula Zn \
    --max-results 10 \
    --output-dir ./research/<date>_<task>/structures/qmof
```

```bash
# ARC-MOF DB7 (Majumdar) — 20 Zn-containing hypothetical MOFs
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --elements Zn \
    --max-results 20 \
    --output-dir ./research/<date>_<task>/structures/arcmof_db7
```

```bash
# ARC-MOF DB7 — retrieve a specific structure by identifier
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --identifier ddmof_559 \
    --output-dir ./research/<date>_<task>/structures/arcmof_db7
```

### Available Arguments

| Argument | Applies to | Description |
|---|---|---|
| `--database` | both | `qmof` or `arcmof-majumdar` |
| `--formula` | qmof | Element/formula filter string (e.g., `Zn,O,C`) |
| `--elements` | arcmof-majumdar | Comma-separated elements; by default a structure must contain ALL of them |
| `--element-match` | arcmof-majumdar | `all` (default) or `any` (keep structures containing at least one listed element, e.g. a mixed-metal screening set) |
| `--identifier` | both | Specific structure name or ID substring |
| `--max-results` | both | Max CIFs to download (default: 10) |
| `--output-dir` | both | Directory for output CIF files |
| `--cache-dir` | arcmof-majumdar | Override default cache `~/.cache/arcmof/` |

### Step 3: Inspect outputs

The script saves:
- Individual `.cif` files named by structure identifier
- `majumdar_metadata.csv` (ARC-MOF only) — Majumdar `mof_data.csv` rows (building blocks, topology, volume, density, CO2 uptake) for the downloaded subset

Verify the download:
```bash
ls -lh <output-dir>/*.cif | head -20
```

## Download Behavior: ARC-MOF DB7

The first call with `--database arcmof-majumdar` performs:

1. **Archive download** (~149 MB, one-time): the Majumdar et al. `mof_data.tar.gz` from Materials Cloud (DOI 10.24435/materialscloud:yn-de), cached at `~/.cache/arcmof/majumdar_mof_data.tar.gz`
2. **Metadata**: `mof_data.csv` inside the archive lists all 23,891 structures with their building blocks and properties
3. **CIF extraction**: the nested `mof_structures.tar` is read sequentially and only the CIFs that pass the identifier/metal filters are written to disk; an exact `--identifier` stops at the first hit

Subsequent runs with the same `--output-dir` skip already-downloaded CIFs.

## Examples

**Literature-validated example: ARC-MOF DB7 `ddmof_559`** (the top post-combustion CO₂ MOF in Figure 7 of Majumdar et al. 2021). See [examples/arcmof_db7_ddmof_559/README.md](examples/arcmof_db7_ddmof_559/README.md). It retrieves the structure by exact identifier and checks its composition, Ni₄(μ₃-OH)₂ node stoichiometry, volume and density against the paper and the ARC-MOF metadata.

**Example 1: Query Zn MOFs from QMOF for CO₂ screening pre-processing**
```bash
MP_API_KEY=<your_mp_api_key> \
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/query_mof_db.py \
    --database qmof \
    --formula Zn \
    --max-results 10 \
    --output-dir ./research/2026-03-27_test/qmof_zn
```

**Example 2: Query Zn, Ni, or Mg hypothetical MOFs from ARC-MOF DB7**
```bash
# Zn-based
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --elements Zn \
    --max-results 50 \
    --output-dir ./research/2026-03-27_arcmof_zn

# Ni-based
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --elements Ni \
    --max-results 50 \
    --output-dir ./research/2026-03-27_arcmof_ni

# Mg-based
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --elements Mg \
    --max-results 50 \
    --output-dir ./research/2026-03-27_arcmof_mg
```

> **Tip:** To build a mixed-metal screening set in one query, list several metals with `--element-match any` (e.g., `--elements Zn,Ni,Mg --element-match any`), or run separate queries per metal node and combine the resulting CIF directories. With the default `all`, adding elements narrows the search (e.g., `Zn,F` returns only fluorinated Zn MOFs).

## Constraints

- **API limits**: QMOF via MPContribs has rate limits; keep `--max-results` ≤ 100 per call.
- **ARC-MOF first-run time**: Downloading the ~149 MB archive takes a few minutes depending on network speed; later runs read the cached copy.
- **ARC-MOF availability**: The Materials Cloud download server can be temporarily unavailable (HTTP 503); retry later if the first download fails.
- **Element filtering (ARC-MOF)**: Parsed from each CIF's `_atom_site_type_symbol`; all listed elements must be present unless `--element-match any` is given.
- **Existing outputs**: If `--output-dir` already holds `--max-results` CIFs, the query is skipped regardless of the filters; use a fresh directory per query.
- **Post-download**: Structures from ARC-MOF DB7 include EQeq partial charges embedded in the CIF. These can be used directly for classical force-field simulations but should be relaxed with an MLIP before running Widom insertion (see [`chem-sorption-relax`](../chem-sorption-relax/SKILL.md)).

## References

- Burner, J. et al., "ARC–MOF: A Diverse Database of Metal-Organic Frameworks with DFT-Derived Partial Atomic Charges and Descriptors for Machine Learning", *Chem. Mater.* 35, 900–916, 2023. [DOI: 10.1021/acs.chemmater.2c02485](https://doi.org/10.1021/acs.chemmater.2c02485)
- Majumdar, S., Moosavi, S.M., Jablonka, K.M., Ongari, D., Smit, B., "Diversifying Databases of Metal Organic Frameworks for High-Throughput Computational Screening", *ACS Appl. Mater. Interfaces*, 2021. [DOI: 10.1021/acsami.1c16220](https://doi.org/10.1021/acsami.1c16220); dataset: *Materials Cloud Archive* 2021.126, [DOI: 10.24435/materialscloud:yn-de](https://doi.org/10.24435/materialscloud:yn-de)
- Chung, Y.G. et al., "Computation-Ready, Experimental Metal-Organic Frameworks: A Tool To Enable High-Throughput Screening of Nanoporous Crystals", *Chem. Mater.*, 2014 (QMOF precursor). [DOI: 10.1021/cm502594j](https://doi.org/10.1021/cm502594j)
- Rosen, A.S. et al., "Machine learning the quantum-chemical properties of metal-organic frameworks for accelerated materials discovery", *Matter*, 2021 (QMOF). [DOI: 10.1016/j.matt.2021.02.015](https://doi.org/10.1016/j.matt.2021.02.015)

---

**Author:** Sauradeep Majumdar
**Contact:** [GitHub @sauradeep93](https://github.com/sauradeep93)
