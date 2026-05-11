---
name: mat-raman-spectra
description: Calculate Raman-active phonon mode frequencies and simulate Raman spectra from MLIP phonon calculations; optionally compute full Raman intensities with DFT Born charges via atomate2.
category: [materials]
---

# Raman Spectra Calculation

## Goal
To calculate the Raman spectrum of a crystalline material by:
1. Identifying Raman-active phonon modes via group-theory symmetry analysis of Γ-point phonons (MLIP-only path)
2. Optionally computing full Raman scattering intensities using DFT-level Born effective charges and dielectric tensors (DFT path)

**Physical background:** Raman scattering intensity of mode $\nu$ is proportional to $|(\hat{e}_i \cdot \alpha_\nu \cdot \hat{e}_s)|^2$, where $\alpha_\nu = d\boldsymbol{\alpha}/dQ_\nu$ is the Raman tensor (derivative of polarizability with respect to mode coordinate $Q_\nu$). Computing $\alpha_\nu$ requires DFT-level dielectric calculations; phonon frequencies alone can be obtained with MLIPs.

> [!IMPORTANT]
> **Two-tier approach:**
> - **MLIP tier (Step 1–3):** Predicts Raman peak *positions* (frequencies). Intensities are set equal as a placeholder. Sufficient for peak assignment and comparison with experiment when known structure is available.
> - **DFT tier (Step 4):** Computes actual Raman *intensities* via Born charges and dielectric tensor from VASP DFPT. Required for quantitative intensity matching.

## Prerequisites

- Pymatgen, phonopy installed in `base-agent` (for symmetry analysis and plotting)
- MLIP environment (`mace-agent`, `matgl-agent`, or `fairchem-agent`) for phonon calculation

## Instructions

### 1. Relax Structure

Before computing phonons, ensure the structure is fully relaxed. Use the MCP tool for your chosen MLIP:

```bash
# Env: mace-agent
mcp_mace_load_model(model_name="MACE-MH-1")
mcp_mace_relax_structure(
    structure_data="input_structure.cif",
    relax_cell=True,
    fmax=0.001,       # tight convergence for phonons
    output_dir="relaxation/"
)
```

> [!IMPORTANT]
> Use a tight force convergence (`fmax ≤ 0.001 eV/Å`) for phonon calculations. Poorly relaxed structures produce imaginary frequencies that indicate a false structural instability.

### 2. Calculate Phonons (MLIP)

Use the [mat-phonon](../mat-phonon/SKILL.md) skill to compute Γ-point phonons. The output `phonon.yaml` is the required input for this skill.

```bash
# Env: mace-agent
python .agents/skills/mat-phonon/scripts/calculate_phonon.py \
    --structure relaxation/relaxed_structure.cif \
    --model_type mace \
    --model_name MACE-MH-1 \
    --supercell_matrix '[[2,0,0],[0,2,0],[0,0,2]]' \
    --output_dir phonon_results/
```

Verify the output: check `phonon_results/phonon.yaml` exists and there are no large imaginary modes at Γ.

### 3. Analyse Raman-Active Modes and Simulate Spectrum (MLIP Tier)

```bash
# Env: base-agent
python .agents/skills/mat-raman-spectra/scripts/analyze_raman_modes.py \
    --phonon-yaml phonon_results/phonon.yaml \
    --structure relaxation/relaxed_structure.cif \
    --output-dir raman_results/ \
    --broadening 5.0 \
    --freq-max 1000
```

**Parameters:**

| Parameter | Description | Default |
|:----------|:------------|:--------|
| `--phonon-yaml` | Path to `phonon.yaml` from mat-phonon | required |
| `--structure` | Relaxed structure file (CIF/POSCAR) | required |
| `--output-dir` | Output directory | `./raman_results` |
| `--broadening` | Lorentzian half-width at half-maximum (cm⁻¹) | `5.0` |
| `--freq-max` | Maximum frequency for spectrum plot (cm⁻¹) | `1000` |
| `--laser-wavelength` | Laser wavelength in nm (for intensity pre-factor, if using DFT intensities) | `532` |

**Output files:**
- `raman_modes.json` — table of all Γ-point modes with symmetry label, frequency, and Raman-activity classification
- `raman_spectrum.png/svg` — simulated spectrum (MLIP tier uses equal intensities; DFT tier uses computed intensities)
- `raman_modes_table.csv` — CSV table for further analysis

> [!NOTE]
> **On Raman intensity accuracy:** The MLIP tier assigns equal intensity to all Raman-active modes. Peak positions are reliable; relative intensities are not. For quantitative comparison with experiment, proceed to Step 4.

### 4. Compute Full Raman Intensities (DFT Tier — Optional)

This step uses VASP DFPT via atomate2 to obtain Born effective charges and the macroscopic dielectric tensor, then combines them with MLIP phonon eigenvectors to compute Raman tensors.

**4a. Run VASP DFPT for Born charges + dielectric tensor:**

```bash
# Env: atomate2-agent
mcp_atomate2_submit_vasp_job(
    structure_path="relaxation/relaxed_structure.cif",
    job_type="dfpt_dielectric",     # computes LEPSILON + Born charges
    vasp_settings_json='{"EDIFF": 1e-8, "ENCUT": 520}',
    output_dir="vasp_dfpt/"
)
```

Wait for the job to complete, then retrieve results:

```bash
# Env: atomate2-agent
mcp_atomate2_get_task_result(
    task_id="<task_id>",
    output_dir="vasp_dfpt/results/"
)
```

**4b. Compute Raman intensities:**

```bash
# Env: base-agent
python .agents/skills/mat-raman-spectra/scripts/analyze_raman_modes.py \
    --phonon-yaml phonon_results/phonon.yaml \
    --structure relaxation/relaxed_structure.cif \
    --born-charges vasp_dfpt/results/OUTCAR \
    --output-dir raman_dft_results/ \
    --broadening 5.0
```

When `--born-charges` is provided, the script computes Raman tensors from the Born charges and dielectric tensor and uses the resulting intensities instead of equal weights.

### 5. Compare with Experiment (Optional)

If experimental Raman data is available as an image, use [general-plot-digitizer](../general-plot-digitizer/SKILL.md) or [chem-db-spectra](../chem-db-spectra/SKILL.md) to extract peak positions and overlay with computed results.

## Examples

### Example: Rutile TiO₂

Rutile TiO₂ (point group D₄h) has 4 Raman-active modes at ~143, ~235, ~447, 612 cm⁻¹ experimentally.

```bash
# 1. Relax with MACE
mcp_mace_load_model(model_name="MACE-MH-1")
mcp_mace_relax_structure(structure_data="TiO2_rutile.cif", relax_cell=True, fmax=0.001, output_dir="relax/")

# 2. Phonons
python .agents/skills/mat-phonon/scripts/calculate_phonon.py \
    --structure relax/relaxed_structure.cif --model_type mace --model_name MACE-MH-1 \
    --supercell_matrix '[[3,0,0],[0,3,0],[0,0,4]]' --output_dir phonon/

# 3. Raman analysis
python .agents/skills/mat-raman-spectra/scripts/analyze_raman_modes.py \
    --phonon-yaml phonon/phonon.yaml --structure relax/relaxed_structure.cif \
    --output-dir raman/ --freq-max 800 --broadening 8.0
```

Expected: the script should identify B1g, Eg, A1g, and B2g modes (all Raman active in D₄h) with frequencies near experimental values.

## Constraints

- **Tight relaxation first**: Use `fmax ≤ 0.001 eV/Å`. Large residual forces produce spurious imaginary modes.
- **Supercell size**: A 2×2×2 supercell (or larger) is recommended. The script reads pre-computed force constants from `phonon.yaml`; the supercell size affects the quality of Γ-point eigenvectors.
- **MLIP tier intensities**: Equal intensities are used as a placeholder. Do not compare intensities from the MLIP tier quantitatively with experiment.
- **Acoustic modes**: The three acoustic modes at Γ (near 0 cm⁻¹) are always excluded from the Raman spectrum.
- **Environments**: Step 2 (phonon calculation) requires `mace-agent` (or `matgl-agent`/`fairchem-agent`); Step 3 (analysis and plotting) runs in `base-agent`.

## References

- Togo & Tanaka, "First principles phonon calculations in materials science", *Scr. Mater.*, 2015. [DOI](https://doi.org/10.1016/j.scriptamat.2015.07.021)
- Lazzeri & Mauri, "First-principles calculation of vibrational Raman spectra in large systems", *Phys. Rev. Lett.*, 2003. [DOI](https://doi.org/10.1103/PhysRevLett.90.036401)
- Batatia et al., "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields", *NeurIPS*, 2022.

---

**Author:** Yu Yao  
**Contact:** [GitHub @AI4SciDisc](https://github.com/AI4SciDisc)
