# drug-docking-analysis examples

Two worked examples live here:

- **`cdk2-htvs/`**: Realistic VS analysis on 286 CDK2 compounds (40 actives, 150 inactives, 96 fillers) from a ChEMBL-seeded library. Full flow with enrichment metrics on real-scale data.
- **`microstates-demo/`**: Small synthetic example showing how `--parent_id_col` collapses enumerated protomers/tautomers to best-score-per-parent.

## Upstream: generating a docking_ranked.csv

Both examples start from a `docking_ranked.csv` that has already been produced upstream. If you are starting from `drug-docking-vina` output, run `collect_results.py` first:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-vina/scripts/collect_results.py \
  --results docking/results/docking_results.json \
  --library_csv library/library_master.csv \
  --output_dir docking/analysis/
```

See [drug-docking-vina SKILL.md step 5](../../drug-docking-vina/SKILL.md) for details.

## Example 1: CDK2 virtual screening (cdk2-htvs/)

Input: `cdk2-htvs/inputs/docking_ranked.csv` (real CDK2 docking results from a 286-compound ChEMBL-seeded library, with `label` and `pchembl` columns).

Run the analysis:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-analysis/scripts/analyze_docking.py \
  --docking_csv .agents/skills/drug-docking-analysis/examples/cdk2-htvs/inputs/docking_ranked.csv \
  --output_dir .agents/skills/drug-docking-analysis/examples/cdk2-htvs/output/
```

Because the CSV already has a `label` column, no separate `--library_csv` is needed. Outputs land in `cdk2-htvs/output/` (`docking_analysis.csv`, `analysis_summary.json`, `plots/*`).

Key results from `analysis_summary.json`:

| Metric | Value |
|---|---|
| n_compounds | 286 |
| Mean Vina score | -8.8 kcal/mol |
| Mean LE | 0.37 |
| ROC AUC | 0.58 |
| EF1% | 2.5x |
| EF5% | 1.0x |
| EF10% | 1.5x |

**Interpretation**: This is a marginal docking campaign. AUC of 0.58 is only slightly above random (0.5), and EF5% of 1.0 means the top 5% of the ranked list contains the same fraction of actives as the full library. EF1% of 2.5x is the only real signal and it only applies to the very top of the list. The `plots/score_vs_mw.png` scatter shows Vina's classic size bias (scores track molecular weight) and reveals that actives cluster in the mid-MW range rather than at the top-scoring (large) end, which is why raw score ranking doesn't discriminate well here. A realistic outcome worth seeing before interpreting your own results.

## Example 2: Microstate aggregation (microstates-demo/)

Input: `microstates-demo/inputs/docking_ranked_microstates.csv`. Ten rows covering four synthetic parent compounds (`DEMO001-004`), each with 2-3 enumerated microstates. The file has `parent_compound_id` and `microstate_id` columns populated by `collect_results.py` in a realistic pipeline.

**Run unaggregated (wrong)**:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-analysis/scripts/analyze_docking.py \
  --docking_csv .agents/skills/drug-docking-analysis/examples/microstates-demo/inputs/docking_ranked_microstates.csv \
  --output_dir .agents/skills/drug-docking-analysis/examples/microstates-demo/output_unaggregated/
```

Reports `n_compounds: 10, n_actives: 6, n_inactives: 4`. These counts are wrong because each parent is double-counted once per microstate.

**Run with aggregation (correct)**:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-analysis/scripts/analyze_docking.py \
  --docking_csv .agents/skills/drug-docking-analysis/examples/microstates-demo/inputs/docking_ranked_microstates.csv \
  --parent_id_col parent_compound_id \
  --output_dir .agents/skills/drug-docking-analysis/examples/microstates-demo/output/
```

Reports `n_compounds: 4, n_actives: 2, n_inactives: 2`. Correct counts, and the `best_affinity` for each parent is the minimum (most favorable) score across its microstates.

Side-by-side comparison:

| Metric | Unaggregated | With --parent_id_col |
|---|---|---|
| n_compounds | 10 | 4 |
| n_actives | 6 | 2 |
| n_inactives | 4 | 2 |
| Mean score | -9.09 | -9.73 |
| ROC AUC | 0.71 | 1.00 |
| EF1% | 16.7x | 50.0x |

The aggregated numbers are the ones to report. The unaggregated version inflates the apparent library size and double-counts compounds that had more enumerated forms during ligand prep, which biases enrichment toward chemistries with many ionizable groups. **Always pass `--parent_id_col` when the docking CSV contains enumerated microstates.**

See [drug-hit-finding-htvs workflow Stage 5](../../../workflows/drug-hit-finding-htvs.md) for the broader microstate aggregation rule this enforces.
