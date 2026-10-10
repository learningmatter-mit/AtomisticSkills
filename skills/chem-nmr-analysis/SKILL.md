---
name: chem-nmr-analysis
description: Scripts for Wasserstein deconvolution of 1H NMR mixture spectra against reference spectra, reaction product prediction, time-series kinetics, and spectral plotting.
metadata:
  category: [chemistry]
  venv: [cpu]
---

# NMR Mixture Analysis

## When to Use This Skill

The agent should use this skill's scripts when:
- A workflow (e.g., `reaction-to-nmr-quantification.md` or `nmr-reaction-kinetics.md`) calls for deconvolution, product prediction, kinetics analysis, or spectral plotting.
- The user already has reference spectra and a mixture spectrum and wants to quantify component proportions directly.
- The user has multiple time-point spectra and wants to track reaction progress via NMR.

For end-to-end workflows that chain this skill with other skills, see: `.agents/workflows/reaction-to-nmr-quantification.md` and `.agents/workflows/nmr-reaction-kinetics.md`.

## When NOT to Use This Skill

- **13C NMR, 2D NMR (COSY, HSQC, etc.), or solid-state NMR** -- this skill handles 1H solution-state NMR only.
- **Structure elucidation of unknown compounds** -- this skill requires knowing (or predicting) what compounds are in the mixture. It does not identify unknowns from scratch.
- **Pure compound characterization** -- if the user has a single pure compound and just wants to assign peaks, this skill is not appropriate. The agent should interpret the spectrum directly.
- **Mass spectrometry data** -- despite the Wasserstein algorithm's origins in mass spec, this skill operates on NMR chemical shift axes only.
- **Digitizing spectrum images** -- the agent should use the `general-plot-digitizer` skill for that step.
- **Predicting NMR spectra from SMILES** -- the agent should use the `chem-nmr-predict` skill for that step.
- **Resolving compound names to SMILES** -- the agent should use the `drug-db-pubchem` skill for that step.

---

## Scripts Reference

| Script | Purpose | Key Inputs | Key Outputs |
|---|---|---|---|
| `predict_products.py` | Predict reaction products via ReactionT5 (HuggingFace API) | `--reactant_smiles`, `--reagent_smiles` | JSON with predicted product SMILES |
| `deconvolve.py` | Wasserstein deconvolution of mixture against references | mixture file + reference files + `--protons` | proportions, Wasserstein distance, plot |
| `kinetics.py` | Time-series deconvolution across multiple time points | `--refs`, `--timepoints`, `--times` | `kinetics.csv` + `kinetics_plot.png` |
| `plot.py` | Overlay or stack NMR spectra for visual comparison | spectrum files + `--labels` | plot image |
| `spectra.py` | I/O utilities (imported by other scripts, not called directly) | -- | -- |

### predict_products.py

The agent should use this script to predict reaction products from reactant and reagent SMILES via the ReactionT5 model.

```bash
export HF_TOKEN=<token>
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/predict_products.py \
  --reactant_smiles "C1CCC(=O)C1" \
  --reagent_smiles "[BH3-]" \
  --output <research_dir>/predicted_products.json
```

### deconvolve.py

The agent should use this script to determine mole fractions of known components in a mixture spectrum via Wasserstein-distance deconvolution.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/deconvolve.py \
  mixture.csv ref_borneol.xy ref_isoborneol.xy \
  --protons 18 18 \
  --names "borneol" "isoborneol" \
  --baseline-window 3.70 3.94 \
  --ppm-range 3.50 4.10 \
  --plot <research_dir>/deconvolution_result.png \
  --json
```

Choose `--baseline-window` from the overlay plot: a stretch with no signal in the
mixture or any reference, preferably close to the peaks being quantified. Add
`--baseline-stat max` when the baseline is a one-sided floor rather than noise (e.g.
digitized spectra, whose traced flat line leaves a small positive residue). Use
`--ppm-range` to fit only a region where each component has an isolated diagnostic
signal; omit it to fit the full spectrum.

### kinetics.py

The agent should use this script when the user has crude NMR spectra recorded at multiple time points during a reaction.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/kinetics.py \
  --refs ref1.xy ref2.xy \
  --timepoints t0.csv t10.csv t20.csv \
  --times 0 10 20 \
  --time_unit min \
  --protons 18 18 \
  --names "reactant" "product" \
  --baseline_window 2.40 3.40 \
  --output_dir <research_dir>/kinetics/
```

`kinetics.py` takes the same baseline and range options as `deconvolve.py`, spelled
with underscores (`--baseline_window`, `--baseline_stat`, `--ppm_range`).
`kinetics.csv` also records the noise fraction and the subtracted baseline of every
time point.

### plot.py

The agent should use this script to overlay or stack spectra for visual inspection before or after deconvolution.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/plot.py \
  mixture.csv ref_borneol.xy ref_isoborneol.xy \
  --labels "Mixture" "borneol" "isoborneol" \
  --title "Mixture vs References" \
  --output <research_dir>/spectra_overview.png
```

---

## Key Arguments for deconvolve.py

`kinetics.py` accepts the same baseline and range options with underscores
(`--baseline_window`, `--baseline_stat`, `--ppm_range`, `--baseline_correct`).

| Argument | Required | Description |
|---|---|---|
| `--protons` | Yes | Number of 1H protons per molecule for each reference component. Critical for converting area fractions to mole fractions. The agent must look this up from the molecular formula or count from the SMILES. |
| `--names` | No | Human-readable labels matching the order of reference files. The agent should always provide these for interpretable output. |
| `--baseline-window LO HI` | Recommended | Signal-free ppm window. Its `--baseline-stat` is subtracted from the mixture and every reference, and negatives are clipped to 0. If a spectrum has no samples in the window (dropped zero runs), the points bounding the gap are used. The agent should use this for any spectrum with noise or a baseline offset. |
| `--baseline-stat` | No | `median` (default) for noisy or offset baselines; `max` for one-sided floors such as the residue of a digitized flat line, which a median only half removes. `max` subtracts about 3σ from every peak of a noisy spectrum, so do not use it there. |
| `--ppm-range LO HI` | No | Deconvolve only this range, applied after the baseline step. Use it to fit isolated diagnostic signals. |
| `--baseline-correct` | No | Legacy: shifts each spectrum so its minimum is 0. Exact only for noise-free spectra with a constant offset. On noisy spectra the minimum is several σ below the baseline, which leaves a positive pedestal and pulls fractions toward an even mixture; on a reference floor with a zero-valued minimum it removes nothing. Mutually exclusive with `--baseline-window`. |
| `--kappa` | No | Denoising penalty (default 0.25). The agent should not change this unless instructed. |
| `--plot` | No | Output plot path. The agent should always generate a plot. |
| `--json` | No | Emit machine-readable JSON output. The agent should always use this. |

---

## Interpreting Results

The deconvolution output contains proportions, a Wasserstein distance (WD) indicating fit quality, and the unexplained ("noise") signal fraction, the share of the mixture signal not assigned to any reference (printed, and `"noise"` in the JSON; the `noise_fraction` column in `kinetics.csv`).

**Check the noise fraction as well as WD.** A baseline error can give a WD in the "acceptable" band while biasing the proportions badly. In the bundled examples, legacy minimum subtraction gave WD 0.11–0.14 with noise fractions of 0.36–0.43 and fractions off by up to 23 points. If the noise fraction exceeds about 0.2, the agent should inspect the residual panel, revisit the baseline (`--baseline-window`, `--baseline-stat`), and consider `--ppm-range` before reporting proportions.

**If/Then rules for Wasserstein distance:**
- **If WD < 0.05** -- good fit. The agent should report proportions with confidence.
- **If 0.05 < WD < 0.15** -- acceptable fit. The agent should report proportions but note the fit quality and suggest possible causes (minor missing components, baseline noise).
- **If WD > 0.15** -- poor fit. The agent should:
  1. Check if a component is missing (compare overlay plot for unmatched peaks).
  2. Check if there is a ppm calibration offset between mixture and references.
  3. Ask the user if there are additional species in the mixture not accounted for.
  4. Not report proportions as reliable.

**The reported proportions are renormalized to sum to 1** over the supplied references. The "noise" fraction is reported separately; the agent should state it and explain what the unmatched signal might be (a missing component, residual baseline, distorted lineshapes).

**Verification:** After deconvolution, the agent must inspect the deconvolution plot, check the residual panel for large residuals, and verify that proportions are chemically reasonable. If results contradict known chemistry, the agent should flag this to the user rather than silently accepting.

---

## Input Format Requirements

All spectrum files must be two-column numeric data (ppm, intensity):
- `.csv` -- comma-delimited (auto-detected)
- `.xy` -- tab-delimited (auto-detected)
- `.tsv` -- tab-delimited
- No header row required; delimiter is auto-detected from content.

**If the user provides a Mnova export** -- the agent should add `--mnova` flag to `deconvolve.py`.

---

## Environment

All scripts in this skill use the `cpu` environment (created on first use by `venv/run`; no separate install).

Required packages: `numpy`, `scipy` (>= 1.7), `matplotlib`, `rdkit`, `requests`, `nmrsim`, `scikit-learn`.

**HF_TOKEN** (for ReactionT5 product prediction): the agent should check if `HF_TOKEN` is set before attempting product prediction. If not set, the agent should ask the user to provide it or provide product SMILES directly.

---

## Failure Modes

| Failure | Symptom | Agent Action |
|---|---|---|
| SPINUS returns no atoms | `chem-nmr-predict` prints FAILED for a compound | The SMILES may be invalid or the molecule too large. The agent should verify the SMILES and retry, or ask the user for a measured reference spectrum. |
| ReactionT5 returns no products | `predict_products.py` returns empty products list | The agent should use its own chemistry knowledge to suggest products and ask the user to confirm. |
| Wasserstein distance very high (> 0.15) | Deconvolution result unreliable | Missing component, ppm offset, or baseline issue. The agent should investigate and not report proportions as reliable. |
| High noise fraction (> ~0.2) with an "acceptable" WD | Proportions biased toward an even mixture or toward one component | Usually a baseline problem: legacy `--baseline-correct` on noisy spectra, or a positive floor on the references. The agent should rerun with `--baseline-window` (and `--baseline-stat max` for digitized floors), and restrict `--ppm-range` to diagnostic signals if the rest of the spectrum is distorted. |
| Proportions are all near zero except one | One component dominates | May be correct (e.g., >95% product), or may indicate missing starting material reference. The agent should check. |
| nmrsim simulation fails | Warning in `chem-nmr-predict` output | Falls back to stick spectrum (shifts only, no multiplet structure). The agent should note reduced accuracy of that reference. |
| kinetics curves are non-monotonic | Composition jumps up and down over time | Likely a mislabeled time point, phasing issue, or missing component. The agent should investigate individual spectra. |

---

## Examples

- [Camphor reduction: borneol/isoborneol ratio from a crude spectrum](examples/deconvolution/README.md) — `deconvolve.py --baseline-window --ppm-range` gives 13:87 (direct integral 12.6:87.4; 17:83 reported by Lopansri et al. 2022); legacy `--baseline-correct` gives 6:94.
- [Two-component time series: composition and rate constant](examples/kinetics/README.md) — `kinetics.py --baseline_window` on a synthetic series recovers the reference-free first-order k within 5 % (0.9σ); legacy `--baseline_correct` is 13 % low.

---

## References

- Ciach, M. et al., "Masserstein: linear resampling of mass spectra by optimal transport", *Rapid Commun. Mass Spectrom.*, 2020.
- Domzal, B. et al., "Magnetstein: Wasserstein-distance NMR mixture analysis", *Anal. Chem.*, 2024.
- Sagawa, Y. et al., "ReactionT5: a large-scale pretrained model towards chemical reaction prediction", *arXiv*, 2023.
- Lopansri, S. et al., "NMR Deconvolution: Quantitative Profiling of Isomeric Mixtures", *World J. Chem. Educ.* 10(2), 51–61, 2022. [DOI](https://doi.org/10.12691/wjce-10-2-1)

---

**Author:** Jesus Diaz Sanchez
**Contact:** [GitHub @jdsanc](https://github.com/jdsanc)
