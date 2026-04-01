---
description: End-to-end workflow for extracting reaction kinetics (mole fraction vs time) from time-series crude 1H NMR spectra via Wasserstein deconvolution.
---

# NMR Time-Series Reaction Kinetics

This workflow extends the single-point NMR quantification workflow (`reaction-to-nmr-quantification.md`) to a time series: given crude 1H NMR spectra recorded at multiple time points during a reaction, it produces mole-fraction-vs-time kinetics curves.

**Scientific Problem:**
Monitoring reaction progress by NMR is routine in synthetic chemistry, but extracting quantitative kinetics from crude spectra with overlapping signals is tedious and error-prone. This workflow chains reference spectrum acquisition (via product prediction and NMR simulation) with Wasserstein-distance deconvolution at each time point to produce kinetics curves, enabling assessment of conversion, selectivity, and rate behavior without manual peak integration.

## Step-by-Step Methodology

### Steps 0–5: Obtain Reference Spectra
Follow Steps 0–5 of the `reaction-to-nmr-quantification.md` workflow to identify all species, resolve names to SMILES, predict products, generate NMR reference spectra, and verify alignment against a representative crude spectrum. If the user provides images instead of numeric files, digitize each time-point image individually using the `general-plot-digitizer` skill.

### Step 6: Run Time-Series Kinetics
Perform Wasserstein deconvolution at each time point and assemble kinetics curves.

- *Skill Reference:* `chem-nmr-analysis` (`kinetics.py`)
- **Action:** Pass all reference spectra, all time-point crude spectra (in chronological order), corresponding time values, proton counts, and component names to `kinetics.py`.
- **Output:** `kinetics.csv` (mole fractions + Wasserstein distance per time point) and `kinetics_plot.png` (mole fraction vs time + fit quality vs time).
- **Decision:** Inspect the kinetics plot. If curves are non-monotonic or a Wasserstein distance spike occurs at a single time point, that spectrum likely has baseline or phasing issues — consider excluding it and re-running. If all WD values exceed 0.15, the fit is poor across the board; revisit reference alignment (Step 5) before trusting the kinetics.

## Summary Checklist for the Agent
When tasked with "extract kinetics from NMR time series":
1. [ ] Digitize spectrum images if needed. (`general-plot-digitizer`)
2. [ ] Identify all NMR-relevant species (reactants, products, solvents, reagents).
3. [ ] Resolve names to SMILES. (`drug-db-pubchem`)
4. [ ] Predict products via ReactionT5. (`chem-nmr-analysis` `predict_products.py`)
5. [ ] Generate reference spectra. (`chem-nmr-predict`)
6. [ ] Visual inspection of overlay. (`chem-nmr-analysis` `plot.py`)
7. [ ] Run kinetics deconvolution. (`chem-nmr-analysis` `kinetics.py`)
8. [ ] Inspect kinetics plot and verify chemical plausibility.

## References
- Ciach, M. et al., "Masserstein: linear resampling of mass spectra by optimal transport", *Rapid Commun. Mass Spectrom.*, 2020.
- Domzal, B. et al., "Magnetstein: Wasserstein-distance NMR mixture analysis", *Anal. Chem.*, 2024.
