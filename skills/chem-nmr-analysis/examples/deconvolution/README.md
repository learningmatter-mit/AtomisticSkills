# Camphor reduction: borneol/isoborneol ratio from a crude 1H NMR spectrum

## Goal

Quantify the two diastereomeric alcohols formed by NaBH4 reduction of camphor,
borneol (endo-OH, minor) and isoborneol (exo-OH, major), from the crude 1H NMR
spectrum by Wasserstein deconvolution against the spectra of the two separated
products, and compare the ratio with the value reported for the same spectra by
Lopansri et al., *World J. Chem. Educ.* 2022.

Both alcohols are C10H18O (18 H), so `--protons 18 18` and the mole fraction
equals the signal fraction. The diagnostic signals are the carbinol H2
multiplets: borneol H2-exo near 4.0 ppm, isoborneol H2-endo near 3.6 ppm.

## Inputs and provenance

| File | Content |
| :--- | :--- |
| `crude.csv` | Crude reaction mixture, 0.75–4.05 ppm, 264 points (0.005 ppm grid, zero-baseline runs removed) |
| `borneol.csv` | Borneol-enriched sample (the "minor" product), 0.80–4.12 ppm, 591 points |
| `isoborneol.csv` | Isoborneol sample (the "major" product), 0.75–4.12 ppm, 648 points |

All three files were added with the skill in commit `b8cd591` (PR #18, re-landed in
#20). Neither the commit nor the PR records where they came from. They appear to be
digitized from **Figure 6 of Lopansri et al. (2022)**, the stacked 1H spectra of the
"crude reaction mixture", "isoborneol (major)" and "borneol (minor)" samples
(CC BY 4.0). Four things point that way: the same three samples, the same 0.8–4.1 ppm
window, the same features (including the small 3.6 ppm isoborneol peak inside the
borneol-enriched trace), and smooth lineshapes on a coarse 0.005 ppm grid. This is an
inference, not documented provenance. Two properties of the digitized data matter
below:

- The two reference traces carry a non-zero floor of 0.002–0.006 intensity units
  (at most 0.0063 in the signal-free regions; 7–9 % of each trace's summed
  intensity). This is the residue of a traced flat baseline. The crude trace has an
  exact-zero baseline. `--baseline-correct` subtracts only the minimum (≈0), so it
  leaves this floor in place. The floor is one-sided and non-random (a sawtooth
  between about 0.0027 and 0.0063), so a window *median* removes only part of it;
  `--baseline-stat max` subtracts its upper envelope.
- The "borneol" sample is *enriched*, not pure. 7.2 % of its H2 signal sits at the
  isoborneol position (3.6 ppm). In the crude trace the aliphatic peaks (0.8–1.9 ppm)
  of the published figure run past the panel and overlap the traces above it, so
  that region of the digitized crude is distorted.

The World J. Chem. Educ. 2022 article that reports these borneol/isoborneol spectra
and their ratio is Lopansri et al., which the skill's References list cites.

## Commands

All commands run from the repository root. Each run takes about 1 s on a CPU.

**1. Visual inspection.** Overlay the crude spectrum with the references:

```bash
venv/run cpu python skills/chem-nmr-analysis/scripts/plot.py \
  skills/chem-nmr-analysis/examples/deconvolution/crude.csv \
  skills/chem-nmr-analysis/examples/deconvolution/borneol.csv \
  skills/chem-nmr-analysis/examples/deconvolution/isoborneol.csv \
  --labels "Crude mixture" "borneol (enriched)" "isoborneol" \
  --title "Crude camphor reduction vs references" \
  --output skills/chem-nmr-analysis/examples/deconvolution/output/overlay/spectra_overview.png
```

The overlay shows a signal-free stretch between the two H2 multiplets
(3.70–3.94 ppm), next to the diagnostic window, which is used below for the baseline.

**2. Run A: legacy minimum subtraction (`--baseline-correct`)**, kept as the biased contrast:

```bash
D=skills/chem-nmr-analysis/examples/deconvolution
mkdir -p $D/output/legacy_min
venv/run cpu python skills/chem-nmr-analysis/scripts/deconvolve.py \
  $D/crude.csv $D/borneol.csv $D/isoborneol.csv \
  --protons 18 18 --names borneol isoborneol --baseline-correct --json \
  --plot $D/output/legacy_min/deconvolution_result.png \
  | grep '^JSON:' | cut -c7- > $D/output/legacy_min/deconvolve_result.json
```

**3. Run B: full range, window baseline.** The `max` of 3.70–3.94 ppm is subtracted
from the crude and from both references. The crude has no samples there (its
zero-intensity runs were dropped), so its estimate comes from the zero-valued points
bounding the gap.

```bash
D=skills/chem-nmr-analysis/examples/deconvolution
mkdir -p $D/output/full_range
venv/run cpu python skills/chem-nmr-analysis/scripts/deconvolve.py \
  $D/crude.csv $D/borneol.csv $D/isoborneol.csv \
  --protons 18 18 --names borneol isoborneol \
  --baseline-window 3.70 3.94 --baseline-stat max --json \
  --plot $D/output/full_range/deconvolution_result.png \
  | grep '^JSON:' | cut -c7- > $D/output/full_range/deconvolve_result.json
```

**4. Run C (recommended): the 3.50–4.10 ppm diagnostic window** (the region Lopansri
et al. integrate), with the same baseline:

```bash
D=skills/chem-nmr-analysis/examples/deconvolution
mkdir -p $D/output/h2_window
venv/run cpu python skills/chem-nmr-analysis/scripts/deconvolve.py \
  $D/crude.csv $D/borneol.csv $D/isoborneol.csv \
  --protons 18 18 --names borneol isoborneol \
  --baseline-window 3.70 3.94 --baseline-stat max --ppm-range 3.50 4.10 --json \
  --plot $D/output/h2_window/deconvolution_result.png \
  | grep '^JSON:' | cut -c7- > $D/output/h2_window/deconvolve_result.json
```

**5. Reference-free check.** Integrate the two H2 multiplets of the digitized crude
directly (uniform 0.005 ppm grid, so sums are proportional to areas):

```bash
awk -F, '$1>=3.95 && $1<=4.06 {b+=$2} $1>=3.57 && $1<=3.67 {i+=$2}
  END {printf "borneol %.2f %%\n", 100*b/(b+i)}' \
  skills/chem-nmr-analysis/examples/deconvolution/crude.csv
```

## Results

| Run | Range | Baseline | borneol (%) | isoborneol (%) | WD | Unexplained (noise) fraction |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| A (legacy) | 0.75–4.12 ppm | minimum | 5.8 | 94.2 | 0.140 | 0.358 |
| B | 0.75–4.12 ppm | max of 3.70–3.94 ppm | 11.7 | 88.3 | 0.096 | 0.217 |
| C (recommended) | 3.50–4.10 ppm | max of 3.70–3.94 ppm | 13.1 | 86.9 | 0.003 | 0.000 |
| Direct H2 integral of `crude.csv` | 3.57–3.67 / 3.95–4.06 | none | 12.6 | 87.4 | – | – |

Subtracted baselines (Runs B and C): crude 2×10⁻⁶, borneol 0.0047, isoborneol 0.0063,
as recorded in `deconvolve_result.json`.

**Sensitivity to the baseline choice** (same commands, other options):
`--baseline-stat median` leaves about half of the one-sided floor and gives 9.5 % (B)
and 11.9 % (C). The max of the farther window 2.40–3.40 ppm, where the floor is
lower, gives 10.4 % and 12.4 %. The 3.70–3.94 ppm window sits next to the diagnostic
peaks, so its floor level is the one that matters there.

- [output/overlay/spectra_overview.png](output/overlay/spectra_overview.png): the
  H2 multiplets of the crude line up with the references at 4.0 and 3.6 ppm. The
  crude aliphatic envelope does not match either reference closely.
- [output/legacy_min/deconvolution_result_fit.png](output/legacy_min/deconvolution_result_fit.png):
  Run A. The fit reproduces the 3.6 ppm peak but leaves 36 % of the crude signal
  unassigned, mostly in the 0.8–1.8 ppm envelope.
- [output/full_range/deconvolution_result_fit.png](output/full_range/deconvolution_result_fit.png):
  Run B. The borneol signals at 4.0 and 2.3 ppm now match the crude in height.
- [output/h2_window/deconvolution_result.png](output/h2_window/deconvolution_result.png)
  and [output/h2_window/deconvolution_result_fit.png](output/h2_window/deconvolution_result_fit.png):
  Run C. Both multiplets are reproduced and the residual is small.

`deconvolve_result.json` (proportions, WD, noise fraction and subtracted baselines) and
`input_configs.yaml` in each `output/` subfolder record the result and the full
argument set. The scripts also write SVG copies, and for Runs A and B the
component-panel PNG. Those files are not kept here, to keep the example small.

## Literature comparison

| Source | Method | borneol : isoborneol |
| :--- | :--- | :--- |
| Lopansri et al. 2022, Fig. 7 | 1H integration of the crude H2 multiplets (integrals 0.20 : 1.00) | 17 : 83 |
| Lopansri et al. 2022, Fig. 9 | 13C band deconvolution of the crude: 77.38/79.92, 45.01/45.07, 20.09/20.18 ppm pairs | 18 : 82, 20 : 80, 19 : 81 |
| Lopansri et al. 2022, text | stated composition, 1H and 13C | "approximately 1:4" |
| Alves & Victor 2010 | GC-FID; NaBH4 in methanol / in ethanol | ≈ 1 : 6 (≈ 14 : 86) / 1 : 3 (25 : 75) |
| **This example, Run C** | Wasserstein deconvolution, 3.50–4.10 ppm, window baseline | **13 : 87** |
| This example, Run A | legacy `--baseline-correct`, full range | 6 : 94 |

**Verdict.**

- **Run A (legacy minimum subtraction): fails validation.** It gives 5.8 % borneol,
  against 17 % from the paper's own 1H integration of the same sample. The WD of
  0.140 falls in the "acceptable" band (0.05–0.15), so WD alone does not flag the
  result. The 36 % unexplained-signal fraction and the comparison with known
  selectivity do. The cause is the reference floor: the minimum is about 0, so
  nothing is removed, and the floor, spread over the whole axis, absorbs signal the
  crude does not have. The window baseline (Run B) doubles the borneol estimate.
- **Run C is consistent with the input and with the literature range.** It gives
  13.1 % borneol, within 0.5 points of the direct integral of the same digitized
  crude (12.6 %), so the deconvolution recovers what the input contains. The
  remaining 4-point gap to the paper's 17 % is already present in the input: the
  borneol 4.0 ppm multiplet is about a tenth of the height of the 3.6 ppm peak in
  the small stacked trace of Fig. 6, and its digitized area is smaller than the
  integral the authors measured on the expanded spectrum (Fig. 7). Correcting for the
  7.2 % isoborneol content of the borneol-enriched reference would lower Run C to
  about 12 %. Run C and the direct integral sit 1–1.5 points below the 14–25 %
  borneol range that Alves & Victor report for NaBH4 reductions (GC); the paper's own
  17–20 % lies inside that range.

**Practical guidance from this example.** Use `--baseline-window` on a signal-free
stretch close to the peaks being quantified. Use `--baseline-stat max` for one-sided
floors such as digitization residue, and the default `median` for noisy spectra.
When each component has an isolated diagnostic signal, restrict the fit with
`--ppm-range`. Do not rely on WD alone: check the unexplained (noise) fraction and
compare with known chemistry.

## References

- L. S. Lopansri, J. N. Letson, R. A. O'Brien, D. R. Battiste, D. C. Forbes,
  "NMR Deconvolution: Quantitative Profiling of Isomeric Mixtures",
  *World J. Chem. Educ.* **2022**, 10 (2), 51–61.
  [doi:10.12691/wjce-10-2-1](https://doi.org/10.12691/wjce-10-2-1)
- P. B. Alves, M. M. Victor, "Reação da cânfora com boroidreto de sódio: uma
  estratégia para o estudo da estereoquímica da reação de redução",
  *Quím. Nova* **2010**, 33 (10), 2274–2278.
  [doi:10.1590/S0100-40422010001000042](https://doi.org/10.1590/S0100-40422010001000042)
- B. Domżał, E. K. Nawrocka, D. Gołowicz, M. A. Ciach, B. Miasojedow,
  K. Kazimierczuk, A. Gambin, "Magnetstein: An Open-Source Tool for Quantitative
  NMR Mixture Analysis Robust to Low Resolution, Distorted Lineshapes, and Peak
  Shifts", *Anal. Chem.* **2024**, 96 (1), 188–196.
  [doi:10.1021/acs.analchem.3c03594](https://doi.org/10.1021/acs.analchem.3c03594)
