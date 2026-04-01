---
name: mat-xrd-refinement
description: Perform Rietveld refinement from experimental XRD patterns using DARA (BGMN).
category: [materials]
---

# Rietveld Refinement

## Goal

Perform quantitative Rietveld refinement of powder X-ray diffraction (XRD) patterns using DARA (Data-driven Automated Rietveld Analysis) with BGMN. Use when you have an experimental (or theoretical) pattern in `.xy` format and candidate phase CIFs.

## Requirements

- Conda environment: `xrd-agent` (see [conda-envs/xrd-agent](../../../conda-envs/xrd-agent)).
- Dependencies: `dara-xrd`, `pymatgen`. Optional: `kaleido` for PNG export (use `kaleido>=0.2.1,<0.3` to avoid needing Chrome).
- BGMN: DARA uses BGMN; ensure it is installed. On HPC without network, set `--bgmn_dir` or `DARA_BGMN_DIR` to a local BGMN directory.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/refine.py` | Run Rietveld refinement with known phases; writes plots and summary under `refinement_results/`. |
| `scripts/convert_xrd_to_xy.py` | Convert XRD from JSON (xrd-spectrum) or DIF to `.xy` for DARA. |
| `scripts/dara_utils.py` | Helpers (e.g. `load_xrd_file`); used by other scripts. |

## Instructions

### 1. Prepare XRD data (`.xy` format)

Two columns (2θ and intensity), space-separated. Options:

- **From xrd-spectrum JSON**: use `convert_xrd_to_xy.py` with `--input_file your_xrd.json`. Output is written next to the input as `your_xrd.xy`.
- **From experimental DIF**: use `convert_xrd_to_xy.py` with `--input_file your_data.txt` (or `.dif`). Format is auto-detected if the file contains a header with `2-THETA` and `INTENSITY`.

```bash
# From JSON (e.g. xrd-spectrum output)
python .agents/skills/mat-xrd-refinement/scripts/convert_xrd_to_xy.py --input_file path/to/xrd.json

# From DIF
python .agents/skills/mat-xrd-refinement/scripts/convert_xrd_to_xy.py --input_file path/to/scan.txt
```

**Convert arguments:**
- `--input_file`: Path to JSON or DIF file.
- `--format`: `auto` (default), `json`, or `dif` to force format.

### 2. Run refinement (`refine.py`)

Refinement uses DARA’s `do_refinement_no_saving` (no BGMN working files left on disk). Output is written to **`refinement_results/`** under the **same directory as the XRD file** (no `--output_dir` argument).

**Refine arguments:**
- `--xrd_data`: (Required.) Path to the `.xy` pattern. **Quote the path in the shell if it contains parentheses or spaces**, e.g. `--xrd_data "./path/with(Chem).xy"`.
- `--cifs`: (Optional.) List of CIF paths. If omitted, CIFs are **auto-discovered**: first from a **`cifs/`** subfolder next to the XRD file, then from the XRD directory. Example layout: `examples/LiFePO4/LiFePO4_xrd.xy` and `examples/LiFePO4/cifs/LiFePO4.cif`, `Li3PO4.cif`.
- `--instrument_profile`: Default `Aeris-fds-Pixcel1d-Medipix3`.
- `--phase_params`: Path to a JSON file with phase refinement parameters (e.g. `lattice_range`, `b1`, `k1`, `gewicht`). See [DARA tutorial](https://cedergrouphub.github.io/dara/notebooks/automated_refinement.html).
- `--refinement_params`: Path to JSON for refinement options (e.g. `wmin`, `wmax`).
- `--bgmn_dir`: Local BGMN directory (avoids download). Or set `DARA_BGMN_DIR`.
- `--quiet`: Suppress progress output.

**Normalized intensity:** If the pattern’s maximum intensity is &lt; 10, the script scales intensities to ~1000 before refinement so Rwp is comparable to the DARA tutorial; the applied scale is printed and stored in `refinement_result.json` as `intensity_scale_applied`.

## Output files (`refine.py`)

All under **`<xrd_directory>/refinement_results/<stem>/`** (e.g. `refinement_results/LiFePO4/`):

| File | Description |
|------|-------------|
| `refinement_result.json` | Rwp, instrument_profile, phase_params, refinement_params, phases (lattice, gewicht), paths to plots and peak_data, optional `intensity_scale_applied`. |
| `<stem>_refinement.html` | Interactive Plotly refinement plot (observed, calculated, difference). |
| `<stem>_refinement.png` | Static plot (requires `kaleido`). |
| `<stem>_peak_data.csv` | Simulated peaks (2θ, intensity, h, k, l, phase, etc.). |

No BGMN working files (`.str`, `.par`, `.lst`, etc.) are saved; DARA runs in a temporary directory.

## Examples

### Example 1: LiFePO4 (CIFs in `cifs/` subfolder)

Layout: `examples/LiFePO4/LiFePO4_xrd.xy` and `examples/LiFePO4/cifs/LiFePO4.cif`, `Li3PO4.cif`. No `--cifs` needed.

```bash
# Env: xrd-agent
python .agents/skills/mat-xrd-refinement/scripts/refine.py \
  --xrd_data .agents/skills/mat-xrd-refinement/examples/LiFePO4/LiFePO4_xrd.xy
```

Results: `examples/LiFePO4/refinement_results/LiFePO4/` (refinement_result.json, HTML/PNG, peak_data CSV).

### Example 2: CaNi(PO3)4 (path with parentheses — must quote)

```bash
# Env: xrd-agent. Quote the path because of (PO3), (OH), (NH4).
python .agents/skills/mat-xrd-refinement/scripts/refine.py \
  --xrd_data ".agents/skills/mat-xrd-refinement/examples/CaNi(PO3)4_800_240_Ca(OH)2_(NH4)2HPO4_NiO/CaNi(PO3)4_800_240_Ca(OH)2_(NH4)2HPO4_NiO.xy"

# If your shell or conda run still has trouble with parentheses in the path,
# you can invoke the environment's Python explicitly instead of using `conda run`:
/home/USER/.conda/envs/xrd-agent/bin/python .agents/skills/mat-xrd-refinement/scripts/refine.py \
  --xrd_data ".agents/skills/mat-xrd-refinement/examples/CaNi(PO3)4_800_240_Ca(OH)2_(NH4)2HPO4_NiO/CaNi(PO3)4_800_240_Ca(OH)2_(NH4)2HPO4_NiO.xy"
```

CIFs are taken from `examples/CaNi(PO3)4_.../cifs/` (NiO_225_sym.cif, CaNi(PO3)4_15_sym.cif). Results under that example’s `refinement_results/`.

### Example 3: Explicit CIFs and optional parameters

```bash
python .agents/skills/mat-xrd-refinement/scripts/refine.py \
  --xrd_data pattern.xy \
  --cifs phase1.cif phase2.cif \
  --phase_params phase_params.json \
  --refinement_params refinement_params.json
```

### Standalone Plotting (`plot.py`)

If you want to adjust the visualization (e.g. dimensions, font sizes, legend position) without re-running the heavy DARA refinement process, you can use the standalone `plot.py` script. This script reads the `*_curve_data.csv` exported by `refine.py`.

```bash
python .agents/skills/mat-xrd-refinement/scripts/plot.py \
  --data_dir refinement_results/my_pattern \
  --output refinement_results/my_pattern/reformatted_plot
```

You can independently edit `plot.py` directly to adjust any of the `matplotlib`/`plotly` formatting rules.


## Constraints

- **BGMN**: Must be installed and on PATH, or provide `--bgmn_dir` / `DARA_BGMN_DIR` on restricted networks.
- **Paths**: In the shell, quote any path that contains `( )` or spaces.
- **Rwp**: Good fits often &lt; 15%. High Rwp with a good-looking plot can occur if the pattern is normalized (low intensity); the script auto-scales in that case. You can also try `--phase_params` (e.g. lattice_range, b1, k1, gewicht) per the [DARA tutorial](https://cedergrouphub.github.io/dara/notebooks/automated_refinement.html).
- **Instrument profile**: Default is `Aeris-fds-Pixcel1d-Medipix3`; change with `--instrument_profile` if needed for your diffractometer.

## Related skills

- **`mat-xrd-digitizer`**:
  - Use this skill to digitize an image or screenshot of an XRD plot into an `.xy` file if you do not have raw experimental data.
- **[mat-xrd-calculator](../mat-xrd-calculator/SKILL.md)**:
  - Calculate theoretical XRD patterns from crystal structures.
- **[foundation-potentials](../foundation-potentials/SKILL.md)**:
  - Relax structures before XRD for better agreement with experiment.

---

**Author:** Nofit Segal  
**Contact:** [GitHub @nofitsegal](https://github.com/nofitsegal)
