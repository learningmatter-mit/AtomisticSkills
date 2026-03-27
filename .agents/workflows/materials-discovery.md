---
description: An end-to-end workflow for high-throughput materials discovery, screening, and synthesizability assessment.
---

# Materials Discovery Workflow

This workflow provides a generalized, hierarchical approach to discovering new materials. It covers starting from initial candidate generation to evaluating thermodynamic stability, screening target properties, and finally assessing novelty and experimental synthesizability.

## 1. Initial Research Setup
Follow the initialization protocol defined in `@.agents/rules/research-standards.md`.
- **Workspace**: Create a dedicated timestamped directory for the project (e.g., `research/YYYY-MM-DD_project_name`).
- **Objective**: Clearly define the target application, chemical space, and the critical properties needed for success (e.g., high ionic conductivity, appropriate bandgap, or strong magnetic moment).

## 2. Candidate Generation
Generate or retrieve a diverse set of initial candidate structures. Select the approach based on whether you are exploring known chemical spaces or searching for entirely novel frameworks.

- **Database Mining**: Query existing databases for initial structural prototypes or materials that naturally meet basic constraints.
  - *Skill Reference*: `mat-db-mp` (Materials Project querying)
  
- **Generative AI Methods**: Use machine learning generative models to create novel hypothetical structures.
  - *Skill Reference*: `ml-generative-mattergen` (Diffusion-based generation, optionally conditioned on properties/systems)
  - *Skill Reference*: `ml-generative-diffcsp` (Constrained generation using space groups and Wyckoff positions)
  - *Skill Reference*: `ml-generative-adit` (Unified generation of periodic structures)
  
- **Heuristics & Substitutions**: Formulate new candidates by mimicking or scrambling known prototypes.
  - *Skill Reference*: `mat-ionic-substitution` (Data-mined ionic substitution rules)
  - *Skill Reference*: `mat-random-structure-search` (AIRSS-style generation for specific compositions)
  - *Skill Reference*: `mat-disorder` (Generate ordered supercells from disordered structures)

## 3. Candidate Documentation and Tracking
Maintain a centralized record of all candidates to track their progress through the screening funnel.
- Create a primary DataFrame or CSV table in the research directory (e.g., `candidates_tracking.csv`).
- **Required Columns**: `candidate_id`, `formula`, `source/generation_method`, `space_group`.
- **Property Columns**: Add columns for downstream calculated metrics (e.g., `e_above_hull`, `bandgap`, `bulk_modulus`) to easily query and filter the best performers later.

## 4. Stability Determination
Before investing in expensive property calculations, screen out inherently unstable candidates. 

- **0K Thermodynamic Stability (Required)**: Calculate the energy above the convex hull ($E_{\text{hull}}$) to ensure the material won't spontaneously phase-separate.
  - *Skill Reference*: `mat-stability`
  - *Skill Reference*: `mat-elemental-energies` and `mat-mp2020-compatibility` (for standardizing reference energies)

- **Dynamical and Thermal Stability (Optional)**: Check for imaginary phonon modes or melting point behavior if high-temperature operation is required.
  - *Skill Reference*: `mat-phonon` (Vibrational properties and dynamical stability)
  - *Skill Reference*: `mat-qha-thermal-expansion` (Free energy contributions at finite temperatures)
  - *Skill Reference*: `mat-melting-point` (Predict melting temperatures)

- **Environmental & Electrochemical Stability (Optional)**: Determine operational stability in specific environments (e.g., batteries, fuel cells).
  - *Skill Reference*: `mat-pourbaix-diagram` (Aqueous/pH stability)
  - Note: Electrochemical stability windows can often be derived using similar grand-canonical approaches.

## 5. Property Calculation and Screening
Evaluate functional properties to find the best candidates for your specific application. Depending on the objective, invoke the corresponding property calculation workflows:

- **Electronic/Band Structure**: `mat-electronic-structure`
- **Mechanical/Elasticity**: `mat-elasticity`, `mat-equation-of-state`
- **Thermal Transport**: `mat-lattice-thermal-conductivity`
- **Magnetic Properties**: `mat-magnetic-density`
- **Ion Transport**: `mat-diffusion-analysis`, `mat-intercalation-voltage`
- **Surfaces and Defects**: `mat-surface-energy`, `mat-surface-adsorption`, `mat-defect-energy`

*Update the tracking table (from step 3) continuously as properties are calculated.*

## 6. Structure Novelty Check
Once the top-performing candidates are identified, confirm that they are genuinely new discoveries. 
- *Skill Reference*: `mat-structure-novelty` (Compare candidate structures against known theoretical and experimental databases like MP or ICSD to filter out duplicates or heavily researched materials).

## 7. Synthesizability Report
For the final list of highly promising and novel candidates, assess how easily they can be synthesized in a lab setting:
- Provide recommendations on the best possible synthesis conditions and precursors.
- *Skill Reference*: `mat-reaction-network` (Predict thermodynamically optimal solid-state synthesis pathways)
- *Skill Reference*: `mat-synthesis-recommendation` (Query text-mined literature datasets for historical recipes on related chemical systems)

Summarize the results in a concise final report within the research directory.
