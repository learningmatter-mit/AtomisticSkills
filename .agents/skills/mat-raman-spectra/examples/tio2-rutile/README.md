# Example: Rutile TiO₂ Raman Spectrum — MACE-MH-1 (matpes_r2scan)

## Overview

| Property | Value |
|:---------|:------|
| Material | Rutile TiO₂ (P4₂/mnm, space group #136) |
| MP ID | mp-2657 |
| Point group | D₄h (4/mmm) |
| MLIP | MACE-MH-1, `matpes_r2scan` head |
| Supercell | 3×3×4 (216 atoms) |
| Broadening | 8.0 cm⁻¹ (Lorentzian HWHM) |
| Intensity type | Equal (MLIP tier) |

Rutile TiO₂ is a standard benchmark for Raman calculations: four Raman-active modes are well-established experimentally, and DFT-level frequencies are well-converged, making it an ideal validation target.

---

## Commands

### 1. Query and relax bulk structure

```bash
# Env: base-agent
mcp_base_search_materials_project_by_formula(formula="TiO2", save_to_file="TiO2_bulk.cif")
```

```bash
# Env: mace-agent
mcp_mace_load_model(model_name="MACE-MH-1", task_name="matpes_r2scan")
mcp_mace_relax_structure(
    structure_data="TiO2_bulk.cif",
    relax_cell=True,
    fmax=0.001,
    output_dir="TiO2_relax/"
)
```

Relaxed lattice parameters: a = b = 4.617 Å, c = 2.959 Å (experimental: a = 4.594 Å, c = 2.959 Å).

### 2. Calculate phonons

```bash
# Env: mace-agent
python .agents/skills/mat-phonon/scripts/calculate_phonon.py \
    --structure TiO2_relax/relaxed_structure.cif \
    --model_type mace \
    --model_name MACE-MH-1 \
    --model_kwargs '{"task_name": "matpes_r2scan"}' \
    --supercell_matrix '[[3,0,0],[0,3,0],[0,0,4]]' \
    --output_dir phonon/
```

No imaginary modes found at Γ — structure is mechanically stable.

### 3. Analyse Raman-active modes (MLIP tier)

```bash
# Env: base-agent
python .agents/skills/mat-raman-spectra/scripts/analyze_raman_modes.py \
    --phonon-yaml phonon/phonon.yaml \
    --structure TiO2_relax/relaxed_structure.cif \
    --output-dir raman/ \
    --broadening 8.0 \
    --freq-max 1000
```

---

## Results

### Γ-point mode summary

The script identified the D₄h point group and applied the mutual exclusion rule (gerade → Raman active). Of the 18 modes (3 acoustic + 15 optical), **5 modes** were flagged Raman active:

| Mode | Symmetry | This work (cm⁻¹) | Experiment (cm⁻¹) | Δ (cm⁻¹) | Notes |
|:-----|:---------|:-----------------:|:-----------------:|:--------:|:------|
| B1g  | Raman ✓  | **141.3**         | 143               | −1.7     | Correctly identified |
| Eg   | Raman ✓  | **444.1**         | 447               | −2.9     | Doubly degenerate |
| A1g  | Raman ✓  | **609.8**         | 612               | −2.2     | Correctly identified |
| B2g  | Raman ✓  | **821.2**         | 826               | −4.8     | Correctly identified |
| A2g  | *flagged*| 687.4             | —                 | —        | **False positive**: A2g is Raman inactive in D₄h (no Raman tensor component). The `endswith("g")` selection rule is insufficient for this representation; full character table analysis required. |

The four physically active Raman peaks (B1g, Eg, A1g, B2g) are within 5 cm⁻¹ of experiment — well within the expected MLIP accuracy for phonon frequencies.

### Literature comparison

| Mode | This work (cm⁻¹) | DFT-PBE (cm⁻¹) | DFT-LDA (cm⁻¹) | Experiment (cm⁻¹) |
|:-----|:-----------------:|:---------------:|:---------------:|:-----------------:|
| B1g  | 141.3             | 138–145         | 134–140         | 143               |
| Eg   | 444.1             | 441–449         | 430–440         | 447               |
| A1g  | 609.8             | 604–618         | 596–608         | 612               |
| B2g  | 821.2             | 814–834         | 800–820         | 826               |

MACE-MH-1 (trained predominantly on PBEsol/r2SCAN data via MatPES) reproduces frequencies closer to the DFT-PBE range than to DFT-LDA, consistent with the model's training distribution. All four peaks lie within ±5 cm⁻¹ of the experimental values, confirming the MLIP tier is suitable for peak assignment.

> [!NOTE]
> **A2g false positive**: The simplified `endswith("g")` Raman selection rule flags A2g as active. A2g transforms as a rotation (Rz) in D₄h and has a zero Raman tensor — it is experimentally silent. When comparing to experiment, the A2g peak at 687 cm⁻¹ should be disregarded. A future fix to `analyze_raman_modes.py` should exclude A2g from the centrosymmetric active set.

> [!NOTE]
> **MLIP tier intensities**: All Raman-active modes are assigned equal intensity. The simulated spectrum is useful for peak position identification only. For quantitative intensity ratios (e.g., distinguishing the strong A1g from the weaker B1g), proceed to the DFT tier (Step 4 of the SKILL.md).

---

## Output Files

| File | Description |
|:-----|:------------|
| `raman_modes.json` | Full mode table: symmetry labels, frequencies, Raman activity, intensities |
| `raman_modes_table.csv` | Same data in CSV format for spreadsheet analysis |
| `raman_spectrum.png` | Simulated Raman spectrum with Lorentzian broadening (4 modes: B1g, B1g, A1g, Eg) |

---

## References

- Porto, S.P.S. & Fleury, P.A. & Damen, T.C., "Raman Spectra of TiO₂, MgF₂, ZnF₂, FeF₂, and MnF₂", *Phys. Rev.*, **154**, 522, 1967. [DOI](https://doi.org/10.1103/PhysRev.154.522)
- Batatia et al., "A foundation model for atomistic materials chemistry", *arXiv:2401.00096*, 2024.
- Togo & Tanaka, "First principles phonon calculations in materials science", *Scr. Mater.*, **108**, 1–5, 2015. [DOI](https://doi.org/10.1016/j.scriptamat.2015.07.021)
- Montanari & Harrison, "Lattice dynamics of TiO₂ rutile: influence of gradient corrections in density functional calculations", *Chem. Phys. Lett.*, **364**, 528–534, 2002. [DOI](https://doi.org/10.1016/S0009-2614(02)01401-X)

---

**Author:** Yu Yao  
**Contact:** [GitHub @AI4SciDisc](https://github.com/AI4SciDisc)
