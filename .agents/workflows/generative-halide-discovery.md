---
description: An end-to-end generative AI workflow for discovering novel high-conductivity solid-state electrolytes (SSEs), specifically mapped for halide lithium-ion conductors.
---

# Generative Discovery of Halide Solid-State Electrolytes

This workflow documents the explicit steps required to transition from a conceptual material class (e.g., Li-M-X halides) to highly verified, novel superionic solid-state electrolytes (SSEs) using a hierarchical screening strategy involving generative AI, ML interatomic potentials (MLIPs), and high-fidelity DFT verification.

## 1. Initial Research & Target Framing
- **Goal**: Discover fast-ion conducting halide Solid-State Electrolytes (SSEs).
- **Setup**: Create an active task directory via the `create_research_dir` MCP tool (e.g., `research/YYYY-MM-DD_halide_sse_generative_search`).
- **Chemical Spaces**: Focus on ternary systems (e.g., `Li-Y-Cl`, `Li-Sc-Br`, `Li-In-Cl`, `Li-Hf-Cl`, `Li-Zr-Cl`, `Li-Er-Br`). These are selected to ensure varied polyhedral configurations and lattice volumes conducive to high Li-ion mobility.

## 2. Generative Candidate Creation (MatterGen)
Generate hypothetical, chemically plausible structures using a diffusion-based generative model.
- **Skill Reference**: `ml-generative-mattergen`
- **Execution**: Apply MatterGen's `chemical_system` conditioning to generate structures containing exactly the elements requested. 
- **Filtering**: Generate large batches (e.g., 500 structures) and post-process to strip out un-desired binaries/elementals or invalid compositions (e.g., resulting in ~350 unique candidates).

## 3. Tier 1: Fast MLIP Stability Screening ($E_{hull}$)
Since generative models output varying levels of stability, rigorously filter out candidates using a unified MLIP scale.
- **Relaxation**: Relax all generated CIFs fully using **FairChem UMA** (`uma-s-1p1` or `uma-s-1p2`).
- **Competitor Sourcing**: Query the Materials Project (`mat-db-mp`) and relax known MP competitors using the exact same MLIP to ensure apples-to-apples energy comparisons.
- **Phase Diagram Construction**: Use `mat-stability` to compute $E_{hull}$ for all generated candidates against the MLIP convex hull.
- **Filter**: Narrow down to top candidates (e.g., top 10-20) with $E_{hull} \le 50$ meV/atom.

## 4. Tier 2: High-Fidelity DFT Refinement
Refine the stability of the top candidates using accurate DFT to confirm synthesizability.
- **Skill Reference**: `mat-dft-vasp`
- **Execution**: Run VASP static calculations or relaxations via `mcp_atomate2_run_atomate2_vasp_calculation` with the `matpes-pbe` preset.
- **Refinement**: Re-calculate $E_{hull}$ using DFT energies. Only strictly stable or near-stable candidates (e.g., top 5-9) proceed to electrochemical analysis.

## 5. Electrochemical Stability & Window Analysis
Assess the potential range of operation against Li metal.
- **Skill Reference**: `mat-electrochemical-window`
- **Calculation**: Calculate the intrinsic electrochemical stability window ($V_{red}$ and $V_{ox}$) against $Li/Li^+$. Priority is given to materials with windows overlapping the target cathode/anode ranges.

## 6. High-Throughput Diffusion Molecular Dynamics (MD)
Use Molecular Dynamics to evaluate and predict the ionic conductivity of the top structurally stable candidates.
- **Execution**: Run NVT ensemble MD through the **FairChem** server (`mcp_fairchem_run_md`).
- **Model Choice**: Use **uma-s-1p1** or **uma-s-1p2**.
- **Temperatures**: Run a temperature ladder (e.g., 400K, 500K, 600K, 700K, 800K, 900K).
- **Auto-Monitoring**: Enable the `diffusion` monitor to stop simulations once MSD has converged.

## 7. Transport Analysis & Visualization
- **Arrhenius Analysis**: Use the `mat-diffusion-analysis` skill to ingest the aggregated multi-temperature `diffusion_Li.json` files and fit the activation energy ($E_a$).
- **Probability Density**: For top conductors, use `mat-md-probability-density` to visualize the Li-ion diffusion pathways and identify the dimensionality of conduction (1D, 2D, or 3D).

## 8. Structural Novelty & Literature Verification
- **Structural Match**: Pass the final candidates through `mat-structure-novelty` to ensure they are not duplicates of known Materials Project entries.
- **Literature Search**: Execute OpenAlex/PubMed queries for the specific formulas to confirm if the material has been experimentally synthesized or computationally predicted before.

## 9. Comprehensive Result Amalgamation
Deliver the holistic dataset (Generation source, Space Group, DFT $E_{hull}$, Electrochemical Window, $E_a$, Conductivity $\sigma_{RT}$, and Novelty status) for experimental validation.