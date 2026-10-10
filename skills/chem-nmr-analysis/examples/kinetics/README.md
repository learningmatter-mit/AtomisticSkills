# Two-component NMR time series: recovering composition and rate constant

## Goal

Run `kinetics.py` on a series of eight 1H spectra (0–90 min) that change from
borneol-like to isoborneol-like, and check whether the recovered mole-fraction
trajectory and its first-order rate constant are correct.

**Type of validation.** This is a synthetic-data recovery test, not a literature
comparison. The series is a numerical mixture of two fixed spectra (see below). No
paper reports it, and no generator script, parameters or ground-truth composition were
committed with it. The ground truth is therefore reconstructed from the data
themselves, in two independent ways: a reference-free principal-component analysis
for the rate constant, and a least-squares decomposition for the composition.

## Inputs and provenance

| File | Content |
| :--- | :--- |
| `t000min.csv` … `t090min.csv` | 8 spectra at 0, 5, 10, 20, 30, 45, 60, 90 min; 1200 points on a uniform 0.80226–4.12285 ppm grid |
| `../deconvolution/borneol.csv`, `../deconvolution/isoborneol.csv` | Reference spectra (18 H each); see the [deconvolution example](../deconvolution/README.md) for their provenance |

The eight files were added with the skill in commit `b8cd591` (PR #18, re-landed in
#20) and have not changed since. No commit, PR description or workflow
(`nmr-reaction-kinetics.md`, `reaction-to-nmr-quantification.md`) says how they were
made. Their structure shows they are synthetic:

1. **Rank one.** After subtracting the mean spectrum, the 8 × 1200 matrix has one
   dominant singular value (14.54, 95.2 % of the variance). The other six non-zero
   values are flat at 1.25–1.42, the level expected for white noise
   (σ√N = 0.0385·√1200 = 1.33). Every spectrum is therefore
   w(t)·P_borneol + (1 − w(t))·P_isoborneol plus noise, for two fixed end-member
   spectra.
2. **White noise** with a constant σ = 0.037–0.041 in the signal-free window
   2.40–3.40 ppm at every time point.
3. **End members related to the shipped references.** Least squares on the two
   references plus a constant gives end-member scales s = 1.042 and 1.219 and
   baselines o = −0.653 and −0.162. The fitted offsets obey c(t) = w·o₁ + (1 − w)·o₂
   to within 0.003. The end members reconstructed from the series have the same peak
   positions as `borneol.csv` and `isoborneol.csv` (shift ≤ 0.002 ppm) but finer
   multiplet structure (correlation 0.85–0.89). The common grid starts exactly at the
   first ppm value of `borneol.csv`.

Lopansri et al. (2022), the source of the reference spectra, contain no time series.
Despite the component names, this is a numerical test series, not a measured reaction.

## Commands

All commands run from the repository root.

**1. Run A: legacy minimum subtraction (`--baseline_correct`)**, kept as the biased contrast:

```bash
K=skills/chem-nmr-analysis/examples/kinetics
R=skills/chem-nmr-analysis/examples/deconvolution
venv/run cpu python skills/chem-nmr-analysis/scripts/kinetics.py \
  --refs $R/borneol.csv $R/isoborneol.csv \
  --timepoints $K/t000min.csv $K/t005min.csv $K/t010min.csv $K/t020min.csv \
               $K/t030min.csv $K/t045min.csv $K/t060min.csv $K/t090min.csv \
  --times 0 5 10 20 30 45 60 90 --time_unit min \
  --protons 18 18 --names borneol isoborneol --baseline_correct \
  --output_dir $K/output/legacy_min
```

**2. Run B (recommended): window baseline.** The median of the signal-free
2.40–3.40 ppm window is subtracted from every time point and both references, and
negatives are clipped to 0:

```bash
K=skills/chem-nmr-analysis/examples/kinetics
R=skills/chem-nmr-analysis/examples/deconvolution
venv/run cpu python skills/chem-nmr-analysis/scripts/kinetics.py \
  --refs $R/borneol.csv $R/isoborneol.csv \
  --timepoints $K/t000min.csv $K/t005min.csv $K/t010min.csv $K/t020min.csv \
               $K/t030min.csv $K/t045min.csv $K/t060min.csv $K/t090min.csv \
  --times 0 5 10 20 30 45 60 90 --time_unit min \
  --protons 18 18 --names borneol isoborneol --baseline_window 2.40 3.40 \
  --output_dir $K/output/window_baseline
```

**3. Validation.** [validate_kinetics.py](validate_kinetics.py) builds the reference-free
and least-squares ground truth, then fits x(t) = x∞ + (x₀ − x∞)·e^(−kt) to every
trajectory:

```bash
K=skills/chem-nmr-analysis/examples/kinetics
R=skills/chem-nmr-analysis/examples/deconvolution
mkdir -p $K/output/validation
venv/run cpu python $K/validate_kinetics.py \
  --timepoints $K/t000min.csv $K/t005min.csv $K/t010min.csv $K/t020min.csv \
               $K/t030min.csv $K/t045min.csv $K/t060min.csv $K/t090min.csv \
  --times 0 5 10 20 30 45 60 90 \
  --refs $R/borneol.csv $R/isoborneol.csv --names borneol isoborneol \
  --kinetics_csv $K/output/legacy_min/kinetics.csv $K/output/window_baseline/kinetics.csv \
  --labels legacy_min window_baseline \
  --output_dir $K/output/validation | tee $K/output/validation/validation_summary.txt
```

The two ground-truth estimates:

- **Reference-free rate constant.** The PC1 scores are an affine function of w(t), so
  their first-order fit gives the time constant of the generating trajectory without
  any reference spectrum or baseline treatment. The fit residual (0.1 % of the score
  span) is below the white-noise level (σ/span ≈ 0.3 %), so the first-order form
  describes the generating trajectory to within noise.
- **Least-squares composition.** Each spectrum is regressed on the two references plus
  a constant, and the two-end-member closure a/s₁ + b/s₂ = 1 (residual ≤ 0.014) turns
  the amplitudes into the mixing weight w(t). Because the references differ from the
  true end members (smoother multiplets), the absolute values of w(t) carry about
  ±0.04 uncertainty (w(0) = 1.039); the time constant is unaffected.

Each `kinetics.py` run takes about 2 s on a CPU.

## Results

Borneol mole fraction (%), Wasserstein distance and unexplained (noise) fraction per
time point (all from `kinetics.csv`):

| t (min) | Least squares w(t) | Run A (legacy) | WD A | noise A | Run B (window) | WD B | noise B |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 103.9 | 81.2 | 0.114 | 0.380 | 97.2 | 0.045 | 0.129 |
| 5 | 89.8 | 71.9 | 0.117 | 0.388 | 85.5 | 0.045 | 0.124 |
| 10 | 77.5 | 65.5 | 0.115 | 0.382 | 75.0 | 0.043 | 0.120 |
| 20 | 59.7 | 54.1 | 0.117 | 0.389 | 59.1 | 0.039 | 0.114 |
| 30 | 47.9 | 46.5 | 0.116 | 0.375 | 46.8 | 0.045 | 0.136 |
| 45 | 35.9 | 38.9 | 0.119 | 0.391 | 35.9 | 0.047 | 0.148 |
| 60 | 30.0 | 38.2 | 0.129 | 0.427 | 33.6 | 0.047 | 0.147 |
| 90 | 24.7 | 28.5 | 0.116 | 0.373 | 25.4 | 0.047 | 0.142 |

Run B's subtracted time-point baselines (`mixture_baseline` column) run from −0.684 at
0 min to −0.284 at 90 min, within 0.011 of the least-squares offsets c(t).

First-order fits, x(t) = x∞ + (x₀ − x∞)·e^(−kt):

| Trajectory | k (min⁻¹) | k vs reference-free | x₀ | x∞ | mean / max abs. deviation from w(t) (pts) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **Reference-free (PC1 scores)** | **0.0391 ± 0.0002** (leave-one-out 0.0390–0.0393) | – | – | – | – |
| Least squares w(t) | 0.0389 ± 0.0004 | −0.6 % | 1.040 | 0.221 | – |
| Run A, legacy `--baseline_correct` | 0.0339 ± 0.0042 | −13.4 % | 0.806 | 0.279 | 9.3 / 22.7 |
| Run B, `--baseline_window 2.40 3.40` | 0.0372 ± 0.0022 | −4.8 % | 0.977 | 0.235 | 2.4 / 6.7 |

**Sensitivity to the window** (same command, other signal-free windows): 2.45–3.55 ppm
gives k = 0.0369 (−5.7 %) and 3.70–3.94 ppm gives 0.0362 (−7.4 %), each within about
1σ of the reference-free value.

- [output/validation/validation.png](output/validation/validation.png): borneol
  fraction against time for the least-squares ground truth and both runs, each with
  its first-order fit.
- [output/legacy_min/kinetics_plot.png](output/legacy_min/kinetics_plot.png): Run A.
  Fractions are compressed toward 50 %, the 45 → 60 min step stalls (38.9 → 38.2 %),
  and WD spikes to 0.129 at 60 min.
- [output/window_baseline/kinetics_plot.png](output/window_baseline/kinetics_plot.png):
  Run B. A smooth monotonic trajectory, with WD at 0.039–0.047.

`kinetics.csv` and `input_configs.yaml` in each run folder, plus `validation.json`
and `validation_summary.txt`, hold the full numbers. SVG copies are produced by the
scripts but not kept here.

**Verdict.**

- **Run A (legacy minimum subtraction): biased.** It is 23 points low at t = 0 and
  8 points high at 60 min, x∞ is 6 points high, and k is 13 % low (1.2σ). The spectra
  carry white noise (σ ≈ 0.04), so each minimum is a noise excursion about 3σ below
  the true baseline. Subtracting it leaves a positive pedestal of 0.10–0.15 under all
  1200 points, 60–70 % of the summed intensity. The deconvolution labels 37–43 % of
  the signal as noise and spreads the rest of the pedestal over both components,
  which pulls every fraction toward a 50:50 mixture. At 60 min the minimum is
  unusually deep (pedestal 0.145 against 0.10–0.12 elsewhere), which explains the WD
  spike and the stalled 45 → 60 min step. WD stays at 0.11–0.13, inside the skill's
  "acceptable" band, so WD alone does not flag the bias; the noise fraction of about
  0.4 does.
- **Run B (window baseline): passes.** k = 0.0372 ± 0.0022 min⁻¹ is within 5 % (0.9σ)
  of the reference-free 0.0391 min⁻¹. The trajectory follows w(t) to 2.4 points on
  average; the largest deviation, 6.7 points, is at t = 0, where the least-squares
  estimate itself exceeds 100 %. The plateau x∞ = 0.235 is 1.4 points above the
  least-squares 0.221. WD drops to about 0.04, the "good" band, and the noise fraction
  to 0.11–0.15 (the positive half of the clipped white noise).

  The window baseline is applied to the references as well, so their small
  digitization floor (median 0.002–0.003 in this window) is removed, while the
  synthetic end members appear to contain it. That end-member mismatch is the likely
  source of the remaining ~5 % offset in k.

**Practical guidance from this example.** For noisy spectra, pass `--baseline_window`
with a signal-free region (default median statistic), not `--baseline_correct`. Check
the noise fraction in `kinetics.csv` along with WD. Because PC1 gives a rate constant
that needs no reference spectra, it is a cheap cross-check on any deconvolved
kinetics.

## References

- B. Domżał, E. K. Nawrocka, D. Gołowicz, M. A. Ciach, B. Miasojedow,
  K. Kazimierczuk, A. Gambin, "Magnetstein: An Open-Source Tool for Quantitative
  NMR Mixture Analysis Robust to Low Resolution, Distorted Lineshapes, and Peak
  Shifts", *Anal. Chem.* **2024**, 96 (1), 188–196.
  [doi:10.1021/acs.analchem.3c03594](https://doi.org/10.1021/acs.analchem.3c03594)
- L. S. Lopansri, J. N. Letson, R. A. O'Brien, D. R. Battiste, D. C. Forbes,
  "NMR Deconvolution: Quantitative Profiling of Isomeric Mixtures",
  *World J. Chem. Educ.* **2022**, 10 (2), 51–61 (source of the reference spectra).
  [doi:10.12691/wjce-10-2-1](https://doi.org/10.12691/wjce-10-2-1)
