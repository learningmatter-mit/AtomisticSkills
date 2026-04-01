---
description: High-throughput screening for alkaline-stable Li-Ion Conductors
---

# Hierarchical Screening for Alkaline-Stable Li-Ion Conductors

## Overview

This workflow implements a hierarchical high-throughput computational screening methodology to identify materials that are stable in alkaline environments. Originally developed for discovering alkaline-stable Li-ion conductors (NASICON and garnet structures) for Li-air batteries with humid air, this approach can be generalized to screen for materials stable under harsh chemical conditions.

**Reference**: Li, Z., Jun, K., Deng, B., & Ceder, G. (2025). Hierarchical high-throughput screening of alkaline-stable lithium-ion conductors combining machine learning and first-principles calculations. arXiv:2511.20964.

## Key Concept

The workflow uses a **two-stage hierarchical screening** approach:
1. **Pre-screening with uMLIP** (e.g., CHGNet): Fast evaluation of 100k+ candidates
2. **DFT refinement**: High-fidelity calculations on promising candidates

This enables exploration of vast chemical spaces (320k+ compositions) that would be computationally prohibitive with DFT alone.

---

## Workflow Steps

### 1. Define Chemical Space and Generate Candidates

**Objective**: Systematically enumerate candidate compositions within target crystal frameworks.

**Actions**:
- Choose crystal framework (e.g., NASICON: `Lix(M M')2(A O4)3`, garnet: `LixLa3(M M')2O12`)
- Define substitution sites and allowed elements
- Enumerate compositions:
  - Vary Li content (x) in steps (e.g., 0.5)
  - Systematically substitute cations with different oxidation states
  - Ensure charge neutrality with appropriate polyanion groups
- **Output**: List of candidate compositions (e.g., 313k NASICON + 6.8k garnet)

**MCP Tools**:
- Use `atomate2` or `materials_project` tools to query similar existing structures for reference

---

### 2. MLIP Pre-Screening (Stage 1)

**Objective**: Rapidly filter candidates using machine learning potentials.

**Actions**:
a. **Structure Relaxation**
   - Relax all candidate structures using pretrained uMLIP (e.g., CHGNet, M3GNet)
   - **MCP Tool**: `matgl.relax_structure()` or `mace.relax_structure()`

b. **Synthesizability Filter**: Calculate energy above convex hull (Ehull)
   - Compare relaxed energies with Materials Project competing phases
   - Filter: Keep candidates with `Ehull < 100 meV/atom`
   - **MCP Tool**: Use `materials_project.get_phase_diagram()` to construct convex hull

c. **Electrochemical Stability**: Calculate oxidation (Vox) and reduction (Vred) limits
   - Evaluate voltage window for battery operation
   - Filter: Requires stability within target range (e.g., 2.0-4.2 V vs Li/Li+)

d. **Chemical Stability**: Compute reaction energy (ΔErex) with environmental species
   - Evaluate reactivity with H2O and LiOH
   - Filter: `ΔErex > threshold` (e.g., > -0.1 eV/atom)

e. **Alkaline Stability**: Construct Pourbaix diagrams
   - Calculate grand Pourbaix decomposition energy (max Δφpbx) for pH = 12-15
   - Calculate passivation index (PI) = fraction of domains with solid decomposition products
   - Filter: Low max Δφpbx and high PI

**Output**: Filtered subset (~1-2k candidates) passing pre-screening criteria

---

### 3. DFT Refinement (Stage 2)

**Objective**: High-fidelity re-evaluation of promising candidates.

**Actions**:
a. **DFT Relaxation**
   - Re-relax structures from stage 1 using DFT (VASP)
   - **MCP Tool**: `materials_tools.prepare_vasp_inputs()` to generate input files
  
b. **Re-calculate Stability Metrics**
   - Energy above hull: Tighter filter (`Ehull < 25 meV/atom`)
   - Electrochemical stability (Vox, Vred)
   - Chemical stability (ΔErex vs H2O and LiOH)
   - Alkaline stability (max Δφpbx, PI) using DFT-relaxed energies

c. **Final Downselection**
   - Apply stricter screening criteria (see Table in reference)
   - Categorize materials:
     - **SSE** (Solid-State Electrolyte): Redox-inactive within voltage window
     - **MIEC** (Mixed Ionic-Electronic Conductor): Redox-active within 2.0-4.2 V

**Output**: Final candidate list (~100-200 materials)

---

### 4. Property Evaluation (Optional)

**Objective**: Evaluate functional properties of final candidates.

**Actions**:
a. **Li-ion Conductivity**
   - Fine-tune MLIP on DFT data for target materials
   - Run MD simulations (NVT at 300-800 K) to calculate diffusivity
   - **MCP Tools**: 
     - `matgl.fine_tune_model()` or `mace.fine_tune_model()`
     - `matgl.run_md()` to perform MD simulations
   - Use pymatgen diffusion analyzer to extract Li-ion conductivity and activation energy

b. **Electronic Conductivity** (for MIECs)
   - Estimate via polaron hopping between mixed-valence states
   - Or use DFT+U to calculate band gap and DOS

**Output**: Property predictions (conductivity, activation energy) for final candidates

---

## Screening Criteria Summary

| Stage | Metric | Threshold |
|-------|--------|-----------|
| **Pre-screening (MLIP)** | Ehull | < 100 meV/atom |
| | Vox (oxidation limit) | Within battery window |
| | Vred (reduction limit) | Within battery window |
| | ΔErex (vs H2O, LiOH) | > -0.1 eV/atom (example) |
| | max Δφpbx (alkaline stability) | Low values preferred |
| | PI (passivation index) | High values preferred (> 0.8) |
| **DFT Refinement** | Ehull | < 25 meV/atom |
| | All above metrics | Stricter thresholds |

---

## Key Insights

**From the reference paper:**
1. **Garnet vs NASICON stability**:
   - Garnets: More stable against reduction and LiOH, better for Li-metal anodes
   - NASICONs: More stable against oxidation and H2O, better for high-voltage applications

2. **Passivation capability**:
   - Early transition metals and lanthanides have high PI (~1.0)
   - Alkaline earths and first-row 3d metals have low PI (~0)
   - Co-substitution can enhance overall PI

3. **Trade-offs**:
   - High Li content (x) increases conductivity but decreases thermodynamic stability (higher Ehull)
   - Need to balance synthesizability, electrochemical stability, chemical stability, and conductivity

---

## Customization for Other Systems

This workflow can be adapted for other research questions:
- **Target property**: Change from alkaline stability to other environmental conditions (e.g., high temperature, oxidizing atmosphere)
- **Crystal frameworks**: Substitute different structure types
- **Filtering criteria**: Adjust based on application requirements (e.g., broader voltage windows for multivalent-ion batteries)
- **uMLIP choice**: Use MACE, CHGNet, M3GNet, or UMA depending on chemistry and accuracy requirements

---

## Computational Requirements

- **Pre-screening**: ~1-10 GPU-hours for 100k candidates (depending on uMLIP)
- **DFT refinement**: ~1000-10000 CPU-hours for 1k-2k candidates
- **MD simulations**: ~10-100 GPU-hours per composition for conductivity

**Recommendation**: Use NERSC or HPC clusters for DFT calculations, local GPU for MLIP pre-screening.