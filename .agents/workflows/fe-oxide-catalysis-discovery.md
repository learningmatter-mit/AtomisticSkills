---
description: Master autonomous campaign for discovering high-activity Fe-binary oxide catalysts using parallel MLIP/DFT benchmarking and zero-touch orchestration.
---

# Fe-Oxide Catalyst Discovery Workflow

This workflow guides you through an end-to-end high-throughput screening campaign for Fe-binary oxide catalysts, specifically optimized for identifying Oxygen Evolution Reaction (OER) activity.

**Scientific Problem:** Efficient water splitting and fuel cell technologies require high-activity catalysts. Mixed-metal and binary oxides offer a vast chemical space, but identifying the optimal surface termination and reaction intermediate energetics requires thermodynamically consistent, multi-scale screening to balance speed and first-principles accuracy.

## Methodology

### 1. Bulk Structure Discovery
- **Action**: Query the Materials Project (MP) for Fe-O binary systems.
- **Criteria**: $E_{hull} < 0.05$ eV/atom (Thermodynamic stability) and documented magnetism.
- **Environment**: `base-agent`
- **Skill**: `mat-db-mp`
- **Scientist's Note**: Fe-oxides often exhibit complex magnetic ordering (AFM/FiM). Ensure the retrieved structures include initial magnetic moment metadata.

### 2. Symmetry-Aware Surface Extraction
- **Action**: For each bulk, extract (100), (110), and (111) planes using symmetry-based termination deduplication.
- **Parameters**: Vacuum > 15Å, Slab thickness > 12Å, periodic distance > 8.0Å.
- **Environment**: `htvs-agent`
- **Skill**: `mat-htvs-cutcleansurface`
- **Technical Nuance**: Use the `SurfaceHelper` to identify chemically distinct terminations (e.g., Fe-top vs O-top). Standardize the lattice to be as orthogonal as possible to improve VASP convergence.

### 3. High-Precision Optimization (DFT+U)
- **Goal**: Establish ground-truth electronic baselines.
- **DFT Settings**: 
    - **Functional**: PBE+U.
    - **U-Corrections**: $U_{eff}(Fe) = 4.3$ eV (standard MP value).
    - **NSW**: 200.
    - **Magnetism**: Set `ISPIN=2` and initialize `MAGMOM` based on bulk ordering.
- **Environment**: `htvs-agent`
- **Skill**: `htvs-vasp-jobs` (via `prepare_vasp_job_details`)
- **Job Config**: Use `pbe_u_paw_spinpol_opt_surf_vasp` as the standard configuration for pristine surfaces.
- **CAUTION**: Non-magnetic initialization of Fe-oxides will lead to incorrect binding energies. Always use `magnetism_scheme="afm"` or `"fm"`.
- **Metadata Tracking**: The underlying `Method` object (e.g. `dft_u_paw_spinpol_gga_pbe`) MUST be explicitly attached to the generated `Job` and `Surface` records to prevent orphaned entries in the database during parsing.

### 4. Site-Specific Adsorbate Placement
- **Action**: Generate O*, OH*, and OOH* intermediates strictly on the **relaxed** pristine surfaces.
- **CRITICAL RULE**: You MUST wait for the pristine slab optimization (`pbe_u_paw_spinpol_opt_surf_vasp`) to complete, and apply `add_adsorbate` to the resulting *optimized* `Surface` object, NOT the unoptimized surface cut directly from the bulk. Generating adsorbates from unoptimized surfaces creates inaccurate reaction lineages and wastes compute resources.
- **Algorithm**: Utilize site discovery to place adsorbates at the most coordinatively unsaturated Fe sites.
- **Environment**: `htvs-agent`
- **Skill**: `mat-htvs-addadsorbate`
- **Metadata Tracking**: The generated adsorbate `Surface` and its corresponding `Job` must inherit the `Method` object from their parent pristine bulk/surface to ensure accurate lineage during downstream VASP parsing.

### 5. Declarative Campaign Orchestration
- **Action**: Initialize the **HTVS Auto-Pilot** orchestrator using a declarative task file.
- **Pre-flight**: Automated reference energy migration ($\mu_{H2}$, $\mu_{H2O}$) from the `orgel` master database and provenance logging.
- **Bulk Constraint**: The standard Autopilot halts the pipeline until *all* pristine jobs in a group finish before starting the `post_process` step.
- **Priority Sub-Queue**: For campaigns exceeding 100+ jobs, deploy a continuous daemon monitor (e.g., `monitor_top3.py`) to bypass the bulk-waiting bottleneck. This daemon polls specific top-candidate UUIDs and instantly pushes their adsorbate calculations to the cluster the moment their pristine DFT finishes.
- **Environment**: `htvs-agent`
- **Skill**: `mat-htvs-autopilot`

### 6. Parallel MLIP/DFT Validation
- **Goal**: Accelerate screening while maintaining DFT accuracy.
- **Action**: Run the same campaign in parallel using Machine Learning Interatomic Potentials (MLIPs).
- **Technical Nuance**: Use the **un-optimized geometry** as the common ancestor for both DFT and MLIP branches. Since MLIP and DFT use different energy scales, always correct MLIP binding energies using DFT-calculated molecule reference energies (H2, H2O) before comparative analysis.
- **Skill**: `mat-htvs-mlip-relax`

### 7. Autonomous Activity Mapping
- **Action**: Analyze the 4-step OER mechanism and generate Volcano Plots.
- **Correction**: Apply molecule reference shifts (e.g., VASP-PBE scale) to MLIP results for thermodynamic consistency.
- **Output**: 
    - `oer_results.json`: Thermodynamic overpotentials for all terminations.
    - `oer_volcano.png`: Activity ranking across the Fe-oxide chemical space.
- **Skill**: `mat-htvs-catalysis-activity-analysis`

## Execution Guide

### 1. Prepare VASP Details (Example for Fe2O3 with adsorbate potential)
Use `prepare_vasp_job_details` with Hubbard U and AFM magnetism:
```python
details = mcp_htvs_prepare_vasp_job_details(
    structure_file="Fe2O3_110.cif",
    preset_type="matpes-pbe",
    calculation_type="relaxation",
    custom_settings={"LDAUU": {"Fe": 4.3, "O": 0, "H": 0}, "LDAUJ": {"Fe": 0, "O": 0, "H": 0}, "LDAUTYPE": 2},
    magnetism=True,
    magnetism_scheme="afm"
)
```

### 2. Autopilot Task (`fe_catalysis_task.json`)
```json
{
  "vars": {
    "reaction": "OER"
  },
  "pre_flight": [
    "{python_exe} .agents/skills/mat-htvs-genbindingenergy/scripts/migrate_references.py --settings {settings} --djangochem {djangochem_dir} --group_name {group_name} --research_dir {research_dir}"
  ],
  "post_process": [
    "{python_exe} .agents/skills/mat-htvs-genbindingenergy/scripts/generate_binding_energy.py --settings {settings} --djangochem {djangochem_dir} --group {group_name} --reaction {reaction} --output_dir {research_dir}",
    "{python_exe} .agents/skills/mat-htvs-catalysis-activity-analysis/scripts/catalysis_analysis.py --reaction {reaction} --data_file {research_dir}/{reaction}_results.json --output_dir {research_dir}"
  ]
}
```

### 3. Priority Sub-Queue Monitor Strategy
To decouple top candidates from the bulk orchestrator waiting period:
1. Identify the Job UUIDs of the highest-activity surfaces from the parallel MLIP run.
2. Run a continuous background daemon that specifically checks those Job UUIDs against the HTVS parsed database.
3. Upon detecting a `done` status, immediately trigger `mat-htvs-addadsorbate` and submit the new jobs directly.
4. Ensure the parser operates exclusively by reading the UUID inside `job_info.json` within the remote cluster folder to guarantee 1:1 data integrity.

## References
- Tran et al., "The Open Catalyst 2020 (OC20) Dataset and Community Challenges", *ACS Catalysis*, 2020. [DOI](https://doi.org/10.1021/acscatal.0c04525)
- Jain et al., "The Materials Project: A General Strategy for Predicting the Lattice Parameters of Compounds", *APL Materials*, 2013.