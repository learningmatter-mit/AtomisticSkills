---
description: An end-to-end generative AI workflow for discovering novel high-conductivity solid-state electrolytes (SSEs), specifically mapped for halide lithium-ion conductors.
---

# Generative Discovery of Halide Solid-State Electrolytes

This workflow documents the explicit steps required to transition from a conceptual material class (e.g., Li-M-X halides) to highly verified, novel superionic solid-state electrolytes (SSEs) using generative AI, ML interatomic potentials (MLIPs), and literature checks.

## 1. Initial Research & Target Framing
- **Goal**: Discover fast-ion conducting Solid-State Electrolytes (SSEs).
- **Setup**: Create an active task directory via the `create_research_dir` MCP tool (e.g., `research/YYYY-MM-DD_halide_sse_generative_search`).
- **Chemical Spaces**: Focus on ternary systems (e.g., `Li-Y-Cl`, `Li-Sc-Br`, `Li-In-Cl`, `Li-Hf-Cl`, `Li-Zr-Cl`, `Li-Er-Br`). The spaces should be selected to ensure varied polyhedral configurations and lattice volumes conducive to high Li-ion mobility.

## 2. Generative Candidate Creation (MatterGen)
Generate purely hypothetical, chemically plausible structures using a diffusion-based generative model.
- **Skill Reference**: `ml-generative-mattergen`
- **Execution**: Apply MatterGen's `chemical_system` conditioning to generate structures containing exactly the elements requested. 
- *Crucial Note*: MatterGen does not strictly fix formula proportions under chemical system conditioning; generate large batches (e.g., 50 structures per system) and post-process to strip out un-desired binaries/elementals. 
- Keep all valid CIF outputs in a `mattergen_candidates/` subdirectory.

## 3. Thermodynamic Stability Pre-Screening ($E_{hull}$)
Since generative models output varying levels of stability, rigorously filter out candidates that decompose exothermically.
- **Relaxation**: Relax all generated CIFs fully using an MLIP (e.g., `mcp_fairchem_relax_structure` with `uma-s-1p1` or MatGL). Save the relaxed CIFs to `candidate_relaxations/`.
- **Competitor Sourcing**: Query the Materials Project (`mat-db-mp`) to download CIFs of all known stable phases associated within the targeted chemical spaces.
- **Unified MLIP Energy Scale**: Relax the known MP competitors using the exact same MLIP used for the novel candidates to ensure apples-to-apples energy comparisons.
- **Phase Diagram Construction**: Use `mat-stability` and `pymatgen.analysis.phase_diagram` to compute $E_{hull}$ for all generated candidates against the newly constructed MLIP convex hull.
- *Filter Rule*: Discard candidates with $E_{hull} > 50$ meV/atom. Highly stable candidates ($E_{hull} \le 10$ meV/atom) proceed to dynamical validation.

## 4. High-Throughput Diffusion Molecular Dynamics (MD)
Use Molecular Dynamics to evaluate and predict the ionic conductivity of the top structurally stable candidates.
- **Execution**: Run NVT ensemble MD through the MLIP server (e.g., `mcp_matgl_run_md`).
- **Temperatures**: Run a temperature ladder (e.g., 400K, 500K, 600K, 700K, 800K, 900K).
- **MD Parameters**: 
  - Ensure supercells are sufficiently expanded (min 10Å side length).
  - Use a timestep of 2fs (`timestep: 2.0`).
  - Progressively scale the number of steps to ensure statistical convergence at lower temperatures (e.g., 10,000 steps at 900K up to 320,000 steps at 400K).
- **Auto-Monitoring**: Enable diffusion and explosion tracking monitors (via `src/utils/mlips/md_utils.py`) to automatically snapshot Mean Square Displacement (`diffusion_Li.json` & `msd_Li.png`) after equilibration passes.

## 5. Arrhenius Extrapolation & Ranking
- Use the PyMatgen `DiffusionAnalyzer` workflow (as seen in `mat-diffusion-analysis`) to ingest the aggregated multi-temperature `diffusion_Li.json` files for each structure.
- **Metrics**: 
  - Fit the exact activation energy ($E_a$).
  - Calculate extrapolated room temperature (300K) isotropic ionic conductivity ($\sigma_{RT}$) in mS/cm using cell volumes from the parent candidate CIF.
- *Filter Rule*: Highlight materials exhibiting superionic conductivities ($> 1$ mS/cm) and realistic barriers ($E_a \approx 0.1 - 0.5$ eV).

## 6. Structural & Chemical Literature Novelty Verification
Validate whether the generated and highly conductive structures are true discoveries.
- **Structural Duplication check**: Pass the highly stable generated formulas through `mat-structure-novelty` (`pymatgen.analysis.structure_matcher`) against identical formulas found on the Materials Project.
- **Experimental Verification**: Execute the OpenAlex literature database query (`mcp_base_search_literature`) for the formulas alongside keywords (e.g., `["Li3ErCl6", "solid electrolyte"]`).
  - If identical papers return matches, verify if the computational structural predictions accurately hit the experimental bounds.
  - If no matches exist, it constitutes a fully novel AI-driven material discovery ready for experimental synthesis.

## 7. Comprehensive Result Amalgamation
Finally, merge all properties (Generation source, Space Group, $E_{hull}$, Formation Energy, $E_a$, Conductivity $\sigma_{RT}$, and Literature Citations) into a master CSV DataFrame to deliver the holistic dataset for publication or lab transition.
