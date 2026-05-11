---
name: drug-docking-analysis
description: Post-docking analysis of virtual screening results including score distributions, enrichment metrics (ROC AUC, enrichment factors), and ligand efficiency calculations.
category: [drug-discovery]
---

# drug-docking-analysis

## Goal

To analyze virtual screening docking results by computing score distributions, ligand efficiency metrics, and (when labeled actives/inactives are available) enrichment statistics. This skill sits between [drug-docking-vina](../drug-docking-vina/SKILL.md) and downstream refinement stages, providing quantitative assessment of docking campaign quality.

**Important**: this skill does **not** assess pose quality. A compound can receive an excellent Vina score with a physically implausible pose (internal clashes, strained torsions, mis-assigned bond orders). Always pair this analysis with [drug-pose-validation](../drug-pose-validation/SKILL.md) (PoseBusters) before acting on the top-ranked compounds.

Outputs:
- Score distribution KDE plot
- Score vs. molecular weight scatter (visualizes Vina's size/lipophilicity bias)
- Ligand efficiency (LE, BEI, SEI) distributions
- ROC curve with AUC (when labels available)
- Enrichment factor bar chart at 1%, 2%, 5%, 10%, 20% (when labels available)
- Enriched results CSV with per-compound efficiency metrics

## Instructions

### 0. Prerequisites: produce a docking_ranked.csv

This skill expects a ranked CSV produced by [drug-docking-vina](../drug-docking-vina/SKILL.md)'s `collect_results.py`. If you are starting from raw `drug-docking-vina` JSON output, run the collect step first:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-vina/scripts/collect_results.py \
  --results docking/results/docking_results.json \
  --library_csv library/library_master.csv \
  --output_dir docking/analysis/
```

The collect step joins the docking scores with the library CSV to pull SMILES, labels, and (when present) `parent_compound_id` / `microstate_id` columns. See [drug-docking-vina SKILL.md step 5](../drug-docking-vina/SKILL.md) for details.

### 1. Basic analysis (no labels)

When you have docking results but no active/inactive labels:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-analysis/scripts/analyze_docking.py \
  --docking_csv docking/docking_ranked.csv \
  --output_dir docking/analysis/
```

This produces score KDE, score vs. MW, and ligand efficiency plots.

### 2. With enrichment analysis (labeled library)

When your library has known actives and inactives:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-analysis/scripts/analyze_docking.py \
  --docking_csv docking/docking_ranked.csv \
  --library_csv library/library_master.csv \
  --active_label active \
  --inactive_label inactive \
  --output_dir docking/analysis/
```

The `--library_csv` must have `compound_id` and `label` columns. If labels are already in the docking CSV, the library CSV is not needed.

### 3. Aggregate microstates before ranking

If the library contained enumerated protomers/tautomers (each parent compound appearing multiple times under different `compound_id` values), you must collapse microstates back to best-score-per-parent before computing any ranking metric. Without aggregation, compounds with more enumerated forms get extra chances to rank high and inflate the apparent library size, biasing enrichment.

Pass `--parent_id_col parent_compound_id` to opt in:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-analysis/scripts/analyze_docking.py \
  --docking_csv docking/docking_ranked.csv \
  --parent_id_col parent_compound_id \
  --output_dir docking/analysis/
```

`collect_results.py` propagates `parent_compound_id` and `microstate_id` from the library CSV automatically when those columns exist, so if you prepared ligands with [drug-ligand-prep](../drug-ligand-prep/SKILL.md) in its enumeration mode you should use this flag.

See [examples/README.md](examples/README.md) for a side-by-side comparison of aggregated vs. unaggregated analysis on a small synthetic library.

### 4. Interpret results

**Score distribution**: A healthy screen typically shows a unimodal distribution with the bulk of scores in the -6 to -8 kcal/mol range and a tail extending toward -9 or beyond; the tail is where you look for hits. A bimodal distribution often means the library contains structurally distinct subsets (e.g. actives + fillers with very different MW profiles) and should be investigated before ranking.

**Score vs. MW**: Vina scores are biased toward larger, more lipophilic molecules. This plot reveals the bias. If actives cluster in a different MW range than inactives, the enrichment may be driven by size rather than binding complementarity, and you should re-rank by a size-normalized metric (LE or BEI) or apply an MW cutoff.

**Ligand efficiency (LE)**: `LE = -score / heavy_atom_count`. Normalizes for molecular size. LE > 0.3 kcal/mol/HA is a common rule-of-thumb threshold for drug-like efficiency, **but note that this threshold was derived from calibrated experimental binding free energies (Hopkins et al., 2004), not from Vina scores**. Vina scores correlate with binding affinity but are not on the same kcal/mol scale as true free energies, so applying the 0.3 threshold directly to Vina-derived LE is common practice but not rigorously justified. Treat the dashed line on the plot as a visual reference, not a hard cutoff. BEI (`-score*1000/MW`) and SEI (`-score*1000/TPSA`) provide alternative normalizations; TPSA here is RDKit's Ertl 2D method via `Descriptors.TPSA`.

**Enrichment**: ROC AUC > 0.7 indicates decent discrimination. EF1% > 5x indicates meaningful early enrichment. Interpret in context: AUC and EF depend heavily on the decoy set composition, so report the decoy source alongside the metrics and prefer relative comparisons between protocol variants over absolute enrichment claims.

**Pose quality**: This skill reports score-based metrics only. None of these plots tell you whether the docked poses are physically reasonable. Always run [drug-pose-validation](../drug-pose-validation/SKILL.md) (PoseBusters) on the top-ranked compounds before committing them to MD or experimental validation; a great score with a clashing or strained pose is a false positive waiting to happen.

## Outputs

- **`docking_analysis.csv`**: per-compound enriched CSV with columns `compound_id, label, docking_score, mw, clogp, tpsa, heavy_atoms, le, bei, sei, smiles`. Rows come from the input docking CSV (after microstate aggregation if `--parent_id_col` is set) and are ordered in the same order as the input.
- **`analysis_summary.json`**: summary metrics (`n_compounds`, `microstate_aggregation`, `score_*`, `le_*`, and, when labels are available, an `enrichment` sub-dict with AUC and EF at 1/2/5/10/20%).
- **`plots/score_kde.*`**, **`plots/score_hist_kde.*`**: score distribution KDEs (PNG and PDF).
- **`plots/score_vs_mw.*`**: score vs. molecular weight scatter with active/inactive coloring when labels are available.
- **`plots/le_distribution.*`**: ligand efficiency distribution with the 0.3 kcal/mol/HA reference line.
- **`plots/roc_curve.*`** and **`plots/enrichment_factors.*`**: only written when labels are available.

## Constraints

- **Environment**: Requires `drugdisc-agent`.
- **Dependencies**: rdkit, numpy, scipy, matplotlib.
- **Input format**: CSV with at minimum `compound_id`, `best_affinity`, and `smiles` columns. Optional passthrough columns: `label`, `parent_compound_id`, `microstate_id`. Use `collect_results.py` in [drug-docking-vina](../drug-docking-vina/SKILL.md) to produce a CSV in the expected shape.
- **Join key**: join between the docking CSV and the optional `--library_csv` is on `compound_id`, **not** on SMILES. The SMILES string in a docked row may reflect a specific protonation or tautomer microstate and will not necessarily match the canonical SMILES in the parent library. Always use `compound_id` as the key.
- **Score convention**: Assumes Vina-style scores where more negative = better binding.
- **Enrichment caveats**: ROC AUC and EF depend on the decoy set. ChEMBL-confirmed inactives (structurally similar to actives) give lower AUC than property-matched decoys (DUD-E). Always report the decoy source.
- **No pose-quality signal**: score-based metrics only. Run [drug-pose-validation](../drug-pose-validation/SKILL.md) alongside this skill to catch physically implausible poses that happen to score well.

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
