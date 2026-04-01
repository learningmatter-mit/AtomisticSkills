---
description: End-to-end workflow for predicting reaction products and quantifying them via Wasserstein deconvolution of a crude 1H NMR spectrum.
---

# Reaction Description to NMR Quantification

This workflow guides the agent through computationally identifying and quantifying the components of a reaction mixture when the starting point is a textual description of a chemical reaction and a crude 1H NMR spectrum (numeric data or an image).

**Scientific Problem:**
After running a synthetic reaction, chemists routinely acquire a crude 1H NMR spectrum of the unpurified mixture to assess conversion, selectivity, and purity. Interpreting such spectra is error-prone when multiple overlapping components are present (reactants, products, isomers, solvents, reagents). This workflow automates the process by (1) predicting what species should be present, (2) generating simulated reference spectra for each, and (3) performing Wasserstein-distance deconvolution to extract mole fractions.

## Step-by-Step Methodology

### Optional Step 0: Digitize Spectrum Image
If the user provides an image of a spectrum rather than a numeric data file.

- **Skill:** Use the `general-plot-digitizer` skill.
- **Action:** Follow the digitizer's full VLM + CV pipeline to extract a two-column `.csv` (ppm, intensity) from the image.
- **Output:** A numeric `.csv` or `.xy` spectrum file ready for downstream steps.
- **Decision:** If the digitized spectrum shows artifacts (axis labels captured as peaks, grid lines), re-run with adjusted parameters before proceeding.

### Step 1: Identify All NMR-Relevant Species
Parse the user's reaction description and compile a complete list of compounds whose signals may appear in the crude NMR.

- **Action:** The agent should use its chemistry knowledge and the reference file at `.agents/skills/chem-nmr-analysis/reference/named_reactions.json` to identify reactants, products, solvents, NMR-visible reagents, and byproducts. The agent must distinguish reactants (transformed, go to ReactionT5) from reagents (facilitate, go to ReactionT5 as `--reagent_smiles`) from solvents (do NOT go to ReactionT5, but may need NMR references).
- **Decision:** If the reaction name is ambiguous about the specific reagent or solvent used, ask the user before proceeding.

### Step 2: Resolve Compound Names to SMILES
Convert each compound name to a canonical SMILES string.

- *Skill Reference:* `drug-db-pubchem`
- **Action:** Query PubChem for each species and extract `CanonicalSMILES`. If a user provides SMILES directly, use as-is.

### Step 3: Predict Reaction Products
Use ML forward prediction to determine what products formed.

- *Skill Reference:* `chem-nmr-analysis` (`predict_products.py`)
- **Action:** Pass reactant SMILES and reagent SMILES to ReactionT5 via the `predict_products.py` script. Requires `HF_TOKEN`.
- **Output:** JSON file with predicted product SMILES.
- **Decision:** If ReactionT5 returns no products or implausible results, the agent should suggest likely products from its own chemistry knowledge and ask the user to confirm.

### Step 4: Generate NMR Reference Spectra
Predict 1H NMR spectra for all identified species (reactants + products + solvents + NMR-visible reagents).

- *Skill Reference:* `chem-nmr-predict`
- **Action:** Pass all collected SMILES to `predict_nmr.py`. Match `--field_mhz` to the user's spectrometer if known.
- **Output:** One `.xy` reference spectrum and one `_signals.csv` signal table per compound.

### Step 5: Visual Inspection
Overlay the crude spectrum with all references to verify alignment before deconvolution.

- *Skill Reference:* `chem-nmr-analysis` (`plot.py`)
- **Action:** Generate an overlay plot and inspect it. Check that reference peaks align with mixture peaks and that no major mixture peaks are unaccounted for.
- **Decision:** If peaks don't align, ask the user about ppm referencing. If major peaks are unmatched, revisit Step 1 for missing components.

### Step 6: Deconvolution
Quantify component mole fractions via Wasserstein-distance deconvolution.

- *Skill Reference:* `chem-nmr-analysis` (`deconvolve.py`)
- **Action:** Run `deconvolve.py` with the crude spectrum, all reference spectra, proton counts, and component names. Always use `--plot` and `--json`.
- **Output:** Estimated mole fractions, Wasserstein distance (fit quality), and a multi-panel deconvolution plot.
- **Decision:** Review the Wasserstein distance. If WD > 0.15, the fit is poor — check for missing components or ppm offsets before trusting the proportions. If the proportions contradict known chemistry, flag this to the user.

## References
- Ciach, M. et al., "Masserstein: linear resampling of mass spectra by optimal transport", *Rapid Commun. Mass Spectrom.*, 2020.
- Domzal, B. et al., "Magnetstein: Wasserstein-distance NMR mixture analysis", *Anal. Chem.*, 2024.
- Sagawa, Y. et al., "ReactionT5: a large-scale pretrained model towards chemical reaction prediction", *arXiv*, 2023.
