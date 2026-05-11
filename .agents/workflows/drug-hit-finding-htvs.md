---
description: An end-to-end workflow for noncovalent, small-molecule structure-based virtual screening, from target retrieval through docking, pose validation, MD refinement, and ADMET filtering to identify drug-like hits.
---

# Drug Hit-Finding by High-Throughput Virtual Screening

This workflow chains database retrieval, structure preparation, docking, pose validation, molecular dynamics refinement, trajectory analysis, and ADMET filtering into a progressive funnel. Each stage eliminates compounds, so that expensive refinement is applied only to the most promising candidates.

**Scope**: This workflow covers **noncovalent, small-molecule HTVS** by default. Covalent targets (warhead-based docking, e.g. CovDock) and metalloprotein active sites (metal-coordination scoring) require specialized handling that is outside this protocol. If the target falls into either category, branch to the appropriate specialized workflow before proceeding.

**Where this workflow starts and stops**: It begins *after* target selection (target identification, validation, and druggability assessment are out of scope) and ends at a shortlist of compounds ready for experimental validation. Lead optimization, SAR campaigns, and preclinical profiling are downstream of this workflow.

**Library size fit**: This workflow is designed for libraries of roughly 10^3 to 10^5 compounds after pre-filtering. For ultra-large libraries (>10^7 compounds, e.g., the full Enamine REAL or ZINC-22), the sequential docking approach in Stage 5 is computationally infeasible. Use fragment-based combinatorial approaches (e.g., V-SYNTHES) or ML-accelerated screening methods that do not require exhaustive docking, then hand the surviving compounds back to this workflow at Stage 6 onward.

## Minimum Inputs

**Required:**
- A target protein structure (experimental holo/apo PDB preferred; AlphaFold prediction acceptable but marks the campaign as lower-confidence).
- A compound library to screen (from a database query, a focused analog set, or a vendor catalog).

**Optional, but each one enables additional workflow features:**
- **Co-crystal ligand in the target PDB**: enables self-docking validation (Stage 3) and automatic binding-box definition (Stage 2). Without it, the box must be defined manually from known active-site residues.
- **Known actives and inactives (or property-matched decoys)**: enables retrospective enrichment at the validation gate (Stage 3). Without them, the gate falls back to self-docking only, which tests geometric reproducibility but not discriminative power.
- **Multiple relevant holo structures**: enables ensemble docking (Stages 2 and 5) and cross-docking validation (Stage 3). Without them, docking proceeds against a single rigid receptor.
- **Target-class interaction knowledge** (e.g., kinase hinge motif, protease catalytic interaction): enables the target-specific interaction filter in Stage 6.

The workflow degrades gracefully when optional inputs are missing, but each missing input reduces confidence in the final hit list. Log which optional inputs were available in `inputs.json` at the top of the research directory so downstream confidence can be weighted accordingly.

## Stage Contracts (Agent Provenance)

Every stage in this workflow must emit structured outputs for reproducibility and audit:
- `inputs.json`: input files and their checksums
- `params.json`: all parameters used (no silent defaults for anything that changes scientific meaning)
- `survivors.csv`: compounds passing the stage, with `parent_compound_id` and `microstate_id` columns
- `rejected.csv`: compounds eliminated, each with a `reason_code`
- `manifest.json`: summary counts and file paths

Missing binding-site atoms, ambiguous receptor state, unsupported ligand elements, failed parameterization, or validation-gate failure must trigger explicit escalation to the user rather than auto-repair. Stages should support checkpoint/resume behavior for large campaigns.

## 1. Initial Research Setup

Follow the initialization protocol defined in `@.agents/rules/research-standards.md`.
- **Workspace**: Create a dedicated timestamped directory (e.g., `research/YYYY-MM-DD_TYK2_htvs`).
- **Objective**: Define the target protein, the disease context, known actives/inactives (if available), and the desired hit profile (potency, selectivity, drug-likeness, route of administration).
- **Target class check**: Confirm the target is amenable to noncovalent small-molecule docking. Flag covalent mechanisms, metal-dependent active sites, or highly flexible/disordered binding regions for specialized treatment.

## 2. Target Retrieval and Preparation

Retrieve the protein structure and prepare it for docking and simulation.

- **Retrieve target PDB**: Download the target structure with a co-crystal ligand when available. Prefer high-resolution holo structures. If only apo or AlphaFold-predicted structures are available, mark the campaign as lower-confidence and require stricter validation at the benchmark gate.
  - *Skill Reference*: `drug-db-pdb`

- **Prepare the receptor**: Add hydrogens, resolve missing residues, and clean up the structure. Remove bulk solvent, but **retain conserved or bridging waters, metals, cofactors, and biologically relevant ions that participate in binding**. Pay particular attention to binding-site residue protonation states (especially histidine tautomers and catalytic residues) and rotamer states, as these directly affect docking accuracy.
  - *Skill Reference*: `drug-protein-prep`
  - **Protonation tooling**: Use PROPKA3 or PDB2PQR for pKa prediction and protonation state assignment at the screening pH (typically 7.4). Record the pH and the tool version in `params.json`.
  - **Identifying conserved/bridging waters**: Apply concrete criteria rather than relying on visual inspection. A water should be retained if it satisfies all of: (1) within 3.5 A of at least one protein heavy atom AND at least one co-crystal ligand heavy atom (bridging geometry), (2) B-factor below the mean protein B-factor in the binding site (well-ordered), and optionally (3) present in the same position across multiple independent holo structures when available (conserved). Log the retained water residue IDs in `params.json` along with which criteria each satisfied.

- **Define the binding site**: Derive the docking box from the co-crystal ligand or from known active-site residues.
  - *Skill Reference*: `drug-binding-site-definition`

- **Decide rigid vs. ensemble receptor**: If multiple relevant holo structures exist, or the binding site is known to be flexible (loop motions, side-chain rotamer switching, induced fit), plan to use an ensemble of receptor conformations rather than a single rigid structure. Prepare each conformation independently (hydrogen addition, protonation, waters) and carry them forward to Stage 5. See Stage 5 for how ensemble docking is executed and how scores are combined.

## 3. Protocol Validation Gate

Before committing compute to the full library, validate the docking protocol on known data. Do not proceed to production screening until this gate passes (however, if there is no known data to operate on, then you can skip this stage).

- **Self-docking control**: If a co-crystal ligand is available, redock it and confirm symmetry-corrected heavy-atom RMSD < 2 A for the top pose. Run with 3-5 independent seeds and report the mean.
  - *Skill Reference*: `drug-redocking-rmsd`

- **Retrospective enrichment** (when actives/inactives are available): Dock a small set of known actives alongside property-matched decoys. Compute enrichment metrics (ROC AUC, early enrichment factors at 1%/5%/10%). If enrichment is near-random, revisit receptor prep, protonation, box placement, or receptor conformation before proceeding.
  - *Skill Reference*: `drug-docking-analysis`
  - **Rough pass criteria** (target-dependent, not universal): ROC AUC above ~0.7 and EF1% at least 5x over random are reasonable minimum bars for a well-prepared docking setup. Targets with poorly defined or highly flexible binding sites may legitimately score below these; treat them as indicators rather than hard cutoffs, and interpret in context with the self-docking RMSD.
  - **Decoy sources**: In rough order of preference: (1) known inactives from the same assay as the actives (cleanest baseline, since they share assay conditions and target state), (2) property-matched decoys generated on-the-fly from a large database like ChEMBL or PubChem by matching MW, logP, HBD/HBA, rotatable bonds, and charge state to each active, or (3) pre-built benchmark decoy sets (e.g., DUD-E, DEKOIS). Pre-built sets are convenient but can carry property or topological biases that inflate enrichment metrics, so interpret absolute enrichment numbers cautiously and focus on relative comparisons between protocol variants. Whatever source you use, log the selection criteria in `params.json`.

- **Cross-docking** (when multiple holo structures exist): Dock known ligands into non-cognate receptor conformations to assess protocol robustness across receptor states.
  - *Skill Reference*: `drug-redocking-rmsd` (for per-pose RMSD against each reference)

This gate catches bad receptor prep, incorrect protonation, poor box placement, or unsuitable receptor conformation before wasting compute on the production screen.

## 4. Compound Library Assembly and Pre-filtering

Build the set of compounds to screen, applying cheap filters early to reduce the docking set. 

Note: If the user has manually provided a library to screen (e.g., a subset of Enamine REAL that they have downloaded), then you may the querying part and only do the pre-filtering in this stage.

- **Query compound databases**: Search for analogs of known actives, or retrieve focused libraries by target/activity.
  - *Skill Reference*: `drug-db-chembl` (bioactivity-annotated compounds)
  - *Skill Reference*: `drug-db-pubchem` (broad chemical space)

- **Curate bioactivity data**: For ChEMBL pulls, filter by assay-to-target confidence score (>=7 recommended), exact target type (single protein), standard relation (=), and consistent units. Do not mix IC50 and Ki data without explicit justification. For PubChem, prefer confirmatory assay results over primary screening actives. Log the curation criteria in `params.json`.

- **Apply campaign-specific physicochemical and nuisance-compound filters**: Use Ro5/Veber rules as hard gates only when they match the desired hit profile (e.g., oral small molecule). For other modalities (PROTACs, macrocycles, CNS-penetrant), adjust or relax these thresholds. Treat PAINS as a severity-graded flag by default, not an automatic rejection. Add aggregation-risk and chemical-reactivity flags alongside PAINS. This step typically eliminates 20-40% of a raw database pull.
  - *Skill Reference*: `drug-admet-prediction` (Lipinski, Veber, PAINS filters)

- **Cluster and diversify** (optional): Compute fingerprints and cluster the library to remove redundancy and ensure chemical diversity.
  - *Skill Reference*: `drug-molecular-fingerprints`

- **Prepare ligands**: Generate 3D conformers, assign protonation states, and convert to docking-ready format. For a pH 7.4 screen, enumerate reasonable protonation states and tautomers for each compound (especially those with ionizable groups) and dock each form as a separate entry, since the dominant microspecies may not be the bioactive one.
  - *Skill Reference*: `drug-ligand-prep`
  - **Tooling**: Dimorphite-DL is a reasonable open-source choice for enumerating ionization states at a target pH. Record the pH, the enumeration tool, and the tool version in `params.json`. Assign a `microstate_id` to each generated form so that microstates can be aggregated back to `parent_compound_id` at ranking time (Stage 5).

**Library size guidance**: For a focused analog series around a known active, 200-500 compounds is typical. For a broad diversity screen from ChEMBL or PubChem, start with 5,000-50,000 and let the pre-filters reduce the set. The docking stage below assumes 500-10,000 compounds after pre-filtering.

## 5. Docking (Coarse Ranking)

Dock all prepared ligands into the binding site. This is the primary filter stage.

- **Run batch docking**: Score and rank all compounds.
  - *Skill Reference*: `drug-docking-vina`
  - Use Vina's default `exhaustiveness=8` for most screens. Systematic benchmarks show docking power converges around exhaustiveness ~25, so increase to 16-32 only if the validation gate (step 3) shows pose reproducibility issues or if you have the compute budget for higher-confidence poses on a smaller library. Lock whichever value you choose for the production screen and record it in `params.json`.
  - **Docking is stochastic**: Vina results vary with random seed. During the validation gate, run self-docking with 3-5 independent seeds and report mean top-pose RMSD. For the production screen, a single seed is acceptable but log it in `params.json`.
  - **Retained waters**: If Stage 2 identified conserved/bridging waters, include them as rigid receptor atoms in the PDBQT (i.e., merged into the receptor file, not docked as flexible). Do **not** use Vina's hydrated docking protocol (ligand decoration with "W" dummy atoms via `mapwater.py`/`dry.py`, scored with `--scoring ad4`) for virtual screening: the Vina documentation explicitly warns that hydrated docking is not suitable for VS because energy normalization is needed when comparing diverse ligands, and the protocol is validated only with the AutoDock4 force field (not with Vina or Vinardo scoring). If the target's binding mode genuinely depends on water placement and rigid-water treatment is insufficient, flag the campaign for manual review rather than proceeding with an unreliable protocol.
  - **Selection criteria**: Do not rank by raw docking score alone, as Vina scores are biased toward larger, more lipophilic molecules. Select by a combination of score, pose validity (key interaction recovery), and scaffold diversity. Since protomers/tautomers were enumerated, **aggregate microstates back to parent compounds** before final ranking so that compounds with more enumerated states do not get extra chances to rank high.
  - **Post-docking analysis**: Compute score distributions, ligand efficiency metrics (LE, BEI, SEI), and (when labels are available) enrichment statistics against the production results. The score-vs-molecular-weight plot is especially useful for diagnosing whether Vina's size bias is dominating the ranking.
    - *Skill Reference*: `drug-docking-analysis`
  - **Ensemble docking** (if Stage 2 prepared multiple receptor conformations): Dock each compound independently into every receptor conformation in the ensemble. Each compound ends up with one score per conformation, which must then be combined into a single ranking score. There is no consensus "correct" combination rule in the literature, and different fusion rules can win on different targets, so the validation gate (Stage 3) is the place to decide which rule to use for the production screen. Reasonable options to compare:
    - **Best-score-per-compound (MIN)**: Take the minimum (most favorable) Vina score across all conformations. Simple and by far the most commonly used rule in practice. Corresponds to asking "does this compound bind *any* accessible receptor state?"
    - **Geometric or harmonic mean**: Some benchmarking studies report that geometric/harmonic means can be more consistent than MIN across targets. Worth comparing against MIN in the validation gate if you have retrospective data.
    - **Arithmetic mean**: Tends to dilute compounds that bind one state well but not others, which is often the case ensemble docking is meant to capture. Some studies still find it useful in combination with other rules, so it is not obviously wrong, just less commonly chosen as the primary metric.
    - **Boltzmann-weighted average**: Weight each conformation's score by `exp(-E_conf / kT)` where `E_conf` is a relative conformational energy estimate. More faithful to the thermodynamic picture but rarely used in practice because reliable conformational energies are hard to obtain from crystal structures alone. Reserve for small ensembles (2-5 conformations) where you have a defensible energy ordering.
    - Pick one rule via the validation gate and then lock it. Record the ensemble members and the chosen combination rule in `params.json`. Cross-docking validation (Stage 3) should use the same combination rule that the production screen will use.
  - Select top N compounds (e.g., top 100-200) for the next stage.

## 6. Pose Validation (Physical Plausibility Filter)

Filter docked poses for chemical and physical plausibility before committing to MD.

- **Validate poses**: Run PoseBusters on the top-ranked docked poses.
  - *Skill Reference*: `drug-pose-validation`
  - Discard poses failing bond geometry, planarity, or protein-ligand clash checks.
  - This stage typically removes 10-30% of docked poses.

- **Target-specific interaction filter** (optional but recommended): When the target class has a well-characterized binding motif (e.g., kinase hinge contact, protease catalytic triad interaction, GPCR key-residue contacts), add an interaction-based filter requiring recovery of that motif in the docked pose. This catches poses that are geometrically valid but pharmacologically implausible.

## 7. Soft ADMET Ranking (Optional)

Before committing to expensive MD, apply predictive ADMET models as a soft ranking signal to prioritize compounds for simulation. This is not a hard filter; it helps allocate MD budget to compounds with better predicted profiles.

- **Soft-rank by predicted ADMET**: Score surviving compounds on CYP inhibition, hERG liability, metabolic clearance, and solubility predictions. Use these as tiebreakers when selecting which compounds to advance to MD.
  - *Skill Reference*: `drug-admet-prediction`
  - ADMET models should report applicability domain or prediction uncertainty. Flag out-of-domain predictions rather than silently treating them as failures.

## 8. MD Refinement (Optional but Recommended)

For the validated top hits, run short MD to assess pose stability. This is the most expensive stage and should only be applied to the surviving compounds (typically 20-50).

- **Build solvated complexes**: Parameterize each protein-ligand complex for simulation.
  - *Skill Reference*: `drug-complex-system-builder`
  - Use OpenFF Sage for the ligand and Amber ff14SB for the protein with TIP3P water. Specify salt concentration (typically 0.15 M NaCl for physiological conditions).

- **Run short MD**: 1-5 ns production per compound is typically sufficient for pose stability assessment (not ranking). The purpose at this stage is strictly a binary go/no-go for pose stability, not binding affinity estimation.
  - *Skill Reference*: `drug-protein-ligand-md`
  - Specify the full protocol explicitly: equilibration schedule (NVT heating, NPT density equilibration), production ensemble (NPT), integration timestep (typically 2 fs with HMT or 4 fs with hydrogen mass repartitioning), save interval (e.g., every 10 ps), and random seeds for replicates.
  - Use 3 independent replicates with different seeds for statistical confidence on the top 5-10 hits.

- **Analyze trajectories**: Compute ligand RMSD, pocket contacts, H-bond persistence, and interaction fingerprints.
  - *Skill Reference*: `drug-trajectory-analysis`
  - Key stability criteria (assess all of these, not just RMSD):
    - **Ligand RMSD** < 2-3 A, plateauing rather than drifting
    - **COM drift**: no monotonic increase (indicates unbinding)
    - **H-bond and contact persistence**: define target-specific critical interactions based on the binding hypothesis (from docking or co-crystal structure), not a universal expectation that every hit must have persistent H-bonds. Loss of >50% of the defined critical interactions across replicates is a red flag even if RMSD looks acceptable.
    - **Contact occupancy**: key hydrophobic contacts and salt bridges should be consistent. A ligand can slide within the pocket while maintaining low RMSD, so contact stability is a more informative metric than RMSD alone.
    - **IFP consistency**: stable binding modes show consistent interaction fingerprint patterns. Sudden fingerprint changes indicate pose transitions.
  - Use `--snapshots` to generate PyMOL binding pocket visualizations for manual inspection of top hits.

- **Rescore with MM-GBSA**: For compounds that pass the stability criteria, compute single-trajectory MM-GBSA binding free energies as a re-ranking signal before hard ADMET filtering. **If you ran the MD, run this.** The trajectories already exist, so the marginal cost is small relative to the MD itself, and it provides an orthogonal signal to docking scores and geometric stability metrics.
  - *Skill Reference*: `drug-mmpbsa-gbsa`
  - Single-trajectory MM-GBSA strips explicit solvent and evaluates complex/receptor/ligand energies in GBn2 implicit solvent; ensemble-average rescoring has been shown to improve rank-ordering correlation with experimental affinities over docking scores alone.
  - **How to use the signal**: Treat MM-GBSA as a **relative ranking tool**, not an absolute binding affinity predictor. The entropy term is omitted, so absolute dG values are not physically meaningful, but rank-ordering across a congeneric or chemically similar series is informative. Skip the first ~0.5-1 ns of each trajectory as equilibration and stride through frames (e.g., every 5th) to reduce correlation.
  - **Caveats**: If the MD replicates disagree strongly on pose stability, MM-GBSA will be noisy and should not be used as a tiebreaker. Resolve the stability question first. For chemically diverse ligand sets (very different scaffolds, charge states, or sizes), MM-GBSA rank-ordering is less reliable than within a congeneric series.

## 9. Hard ADMET Filtering

Apply predictive ADMET models as hard filters to the MD-validated hits.

- **Compute predictive ADMET properties**: Evaluate CYP inhibition, hERG liability, metabolic clearance, and other pharmacokinetic predictions.
  - *Skill Reference*: `drug-admet-prediction`
  - Use consensus predictions from multiple models where available. Report applicability domain or prediction uncertainty alongside point estimates.
  - Remove compounds with high-confidence toxicity flags or poor pharmacokinetic profiles. Out-of-domain predictions should be flagged for human review rather than treated as automatic failures.

## 10. Commercial Availability and Retrosynthesis (Optional)

For the final shortlist, check whether compounds can be purchased before investing in synthesis planning.

- **Check commercial availability**: Query ZINC, Enamine REAL, or MolPort for the hit compounds. Purchasable compounds can skip retrosynthesis entirely and go directly to experimental validation.

- **Predict retrosynthetic routes**: For non-purchasable hits, identify whether the compounds can be made in a reasonable number of steps.
  - *Skill Reference*: `drug-retrosynthesis`

## 11. Results Compilation

- Compile a ranked hit list with: compound ID (both parent and microstate), docking score, pose validation pass/fail, target-interaction recovery, MD stability metrics (RMSD, critical-contact persistence, IFP stability), ADMET predictions with confidence, availability/retrosynthesis score.
- Maintain a tracking CSV in the research directory (`hit_tracking.csv`) with `reason_code` for every elimination at every stage.
- Generate a summary figure showing the screening funnel (compounds surviving each stage).

## Decision Points and Escalation

| Stage | Typical input | Typical output | Go/no-go criterion |
|---|---|---|---|
| Validation gate | Co-crystal + decoys | Pass/fail | Self-dock RMSD < 2 A; rough bars ROC AUC > 0.7, EF1% > 5x (target-dependent) |
| Pre-filter (physicochemical) | 1,000-50,000 compounds | 500-10,000 | Campaign-specific rules |
| Docking | 500-10,000 | Top 100-200 | Score + pose validity + diversity |
| Pose validation | 100-200 | 70-150 | PoseBusters pass, target interaction recovery |
| Soft ADMET ranking | 70-150 | 20-50 (prioritized) | Soft rank, not hard cutoff |
| MD refinement | 20-50 | 10-30 | RMSD < 3 A, critical contacts maintained |
| MM-GBSA rescoring | 10-30 | 10-30 (re-ranked) | Relative ranking signal, not a hard cutoff |
| Hard ADMET | 10-30 | 5-15 | No high-confidence CYP/hERG/clearance flags |
| Availability/retrosynthesis | 5-15 | 3-10 | Purchasable or SA score < 5 |

The workflow is designed so that each stage is independently useful. You can stop after docking for a quick screen, or continue through MD refinement for a higher-confidence hit list.

## Expectations at the End of the Funnel

Setting expectations helps the agent and the user judge whether a campaign is succeeding or whether the protocol needs revisiting. Rough rules of thumb for a reasonably well-validated SBVS campaign (these vary by target, library, and assay):

- **Experimental hit rate on the final shortlist**: typically 1-10% of compounds that survive the full funnel confirm activity in the primary assay. A hit rate above ~5% indicates a well-validated protocol on a tractable target. A hit rate below ~1% suggests the protocol or the target is harder than the funnel detected, and retrospective failure analysis is warranted.
- **Scaffold novelty**: expect most confirmed hits to be analogs of known chemotypes if the library was seeded from ChEMBL. True novel scaffolds are rarer and should be prioritized for follow-up.
- **False negatives**: this workflow is tuned to minimize false positives at each gate. Compounds eliminated at the pose validation or MD stages are not necessarily inactive, just unranked. If the confirmed hit rate is low and the target is important, consider re-running with relaxed gates on the next-tier compounds.

If the campaign's hit rate falls well outside these ranges, treat it as a signal to audit the validation gate results, the receptor prep, and the decoy/active balance rather than to assume the target is intractable.