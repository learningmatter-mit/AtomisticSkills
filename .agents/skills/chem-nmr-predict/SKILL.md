---
name: chem-nmr-predict
description: Predict 1H NMR spectra from SMILES strings via NMRdb.org SPINUS neural network prediction and nmrsim quantum mechanical spin simulation.
category: chemistry
---

# 1H NMR Spectrum Prediction

## When to Use This Skill

The agent should use this skill when:
- A SMILES string is known and the agent needs a predicted 1H NMR spectrum (ppm vs intensity) for that compound.
- The agent needs a signal list (chemical shifts, multiplicities, coupling constants, proton counts) for a compound.
- Reference spectra are needed for mixture deconvolution (called by the `chem-nmr-analysis` skill).
- The user wants to compare a predicted spectrum against an experimental one for structure confirmation.

## When NOT to Use This Skill

- **The user already has an experimental or digitized spectrum file** — no prediction is needed; the agent should use the existing file directly.
- **The user has a compound name but not a SMILES** — the agent should first resolve the name to SMILES using the `drug-db-pubchem` skill, then call this skill.
- **13C NMR prediction** — this skill predicts 1H NMR only. The NMRdb.org SPINUS endpoint does not support 13C.
- **Polymers, organometallics, or molecules with >50 heavy atoms** — the SPINUS neural network may not produce reliable predictions, and nmrsim QM simulation is limited to ~11 coupled spins per spin system.
- **The user asks about reaction products or mixture composition** — the agent should use `chem-nmr-analysis` instead, which calls this skill internally.

---

## Workflow: SMILES → Predicted 1H NMR

### Step 1 — Ensure SMILES Are Available

If the user provides compound names instead of SMILES, the agent should first resolve them:

```bash
# Env: base-agent
python .agents/skills/drug-db-pubchem/scripts/query_pubchem.py \
  --name "camphor" --outdir <research_dir>/pubchem/
```

The agent should extract `CanonicalSMILES` from the JSON output.

**If PubChem returns no results**, the agent should try alternate names or ask the user to provide the SMILES directly.

### Step 2 — Predict NMR Spectra

```bash
# Env: nmr-agent
python .agents/skills/chem-nmr-predict/scripts/predict_nmr.py \
  --smiles "<smiles_1>" "<smiles_2>" \
  --names "compound1" "compound2" \
  --field_mhz 400 \
  --output_dir <research_dir>/nmr_predictions/
```

**Arguments:**
- `--smiles` (required): one or more SMILES strings.
- `--names`: human-readable labels for filenames. If omitted, defaults to `comp0`, `comp1`, etc. The agent should always provide meaningful names.
- `--field_mhz`: spectrometer frequency in MHz (default: 400). The agent should match the field strength of the user's experimental spectrum if known.
- `--linewidth`: Lorentzian FWHM in Hz (default: 1.0). The agent should increase this (e.g., 2.0–5.0) if the user's experimental spectrum has broad lines.
- `--n_points`: spectrum resolution (default: 8192). The agent should not change this unless the user requests higher resolution.
- `--output_dir`: where to save results.

**Outputs per compound:**
- `<name>.xy` — two-column tab-separated file (ppm, intensity), descending ppm. Compatible with all NMR processing tools and the `chem-nmr-analysis` deconvolution scripts.
- `<name>_signals.csv` — signal table with columns: `shift_ppm`, `multiplicity`, `J_Hz`, `nH`.
- `predictions.json` — manifest listing all found/failed compounds and parameters.

### Step 3 — Verify Predictions

After prediction, the agent must:

1. **Check the manifest** (`predictions.json`) for any failed compounds.
2. **Read the signal table** (`_signals.csv`) and verify it is chemically reasonable:
   - The total number of protons across all signals should match the molecular formula.
   - Chemical shifts should be in expected ranges (e.g., alkyl 0–2 ppm, aromatic 6–8 ppm, aldehyde 9–10 ppm).
3. **If the user has an experimental spectrum**, the agent should overlay them using `chem-nmr-analysis`'s `plot.py` for visual comparison.

**If SPINUS returns no atoms for a SMILES** → the SMILES may be invalid, the molecule may lack hydrogen atoms (e.g., CCl4), or the molecule may be too complex. The agent should:
1. Verify the SMILES is valid (try parsing with RDKit).
2. Check if the molecule actually has hydrogen atoms.
3. If valid but SPINUS fails, inform the user that prediction is unavailable for this compound.

**If nmrsim simulation fails** → the script falls back to a stick spectrum (chemical shifts only, no multiplet structure). The agent should note this in its response — the predicted spectrum will lack splitting patterns but chemical shifts will still be approximate.

---

## If/Then: Field Strength Matching

- **If the user's experimental spectrum was recorded at 300 MHz** → the agent should set `--field_mhz 300`. Second-order effects are more pronounced at lower field, and nmrsim handles these correctly.
- **If the user's experimental spectrum was recorded at 600 MHz** → the agent should set `--field_mhz 600`. Peaks will be better resolved.
- **If the field strength is unknown** → the agent should use the default (400 MHz) and note this assumption.

## If/Then: Linewidth

- **If the user's spectrum shows sharp, well-resolved peaks** → use default `--linewidth 1.0`.
- **If the user's spectrum shows broad peaks** (e.g., viscous sample, paramagnetic species) → increase to `--linewidth 3.0` or higher.
- **If predicting for deconvolution against a digitized reference** → use `--linewidth 1.0` (digitized spectra typically have natural linewidths).

---

## Failure Modes

| Failure | Symptom | Agent Action |
|---|---|---|
| Invalid SMILES | Script prints FAILED with "Invalid SMILES" | The agent should verify the SMILES with RDKit and correct it. |
| SPINUS returns no atoms | "SPINUS returned no atoms" error | Molecule may lack H atoms or be too complex. The agent should check and inform the user. |
| SPINUS network timeout | HTTP timeout error | The agent should retry once. If it fails again, NMRdb.org may be down. The agent should inform the user. |
| nmrsim QM simulation fails | WARNING in output, falls back to stick spectrum | Spin system too large (>11 spins) or numerical issue. The agent should note reduced accuracy. |
| Total nH in signals does not match molecular formula | Signal table has wrong proton count | Grouping heuristic may have failed. The agent should flag this to the user. |

---

## Environment

```bash
mamba activate nmr-agent
```

Install: `conda-envs/nmr-agent/install.sh`

Required packages: `numpy`, `rdkit`, `requests`, `nmrsim`.

---

## References

- Banfi, D. & Patiny, L., "www.nmrdb.org: Resurrecting and processing NMR spectra on-line", *Chimia*, 2008.
- Aires-de-Sousa, J. et al., "SPINUS: prediction of 1H NMR spectra by neural networks", *J. Chem. Inf. Model.*, 2002.
- Sametz, G., "nmrsim: a Python library for NMR simulation", [github.com/sametz/nmrsim](https://github.com/sametz/nmrsim).

---

**Author:** Jesus Diaz Sanchez  
**Contact:** [GitHub @jdsanc](https://github.com/jdsanc)
