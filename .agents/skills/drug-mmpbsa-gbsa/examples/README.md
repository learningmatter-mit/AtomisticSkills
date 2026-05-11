# drug-mmpbsa-gbsa example: CDK2 HTVS MD refinement

Real MM-GBSA outputs from the [HTVS workflow](../../../workflows/drug-hit-finding-htvs.md) applied to CDK2, showing what a healthy rescoring campaign looks like and, more importantly, what a broken one looks like. The three compounds here were chosen to span the full convergence spectrum that an agent will encounter on real data.

## What's in the folder

```
cdk2-htvs/results/
  CHEMBL1087650/{rep1,rep2,rep3}/   # tight convergence: replicate spread < 1 kcal/mol
  CHEMBL388978/{rep1,rep2,rep3}/    # moderate convergence: spread ~3 kcal/mol
  CHEMBL3943841/{rep1,rep2,rep3}/   # catastrophic: spread > 34 kcal/mol
```

Each `rep*` directory contains the two files `compute_mmgbsa.py` produces:
- `mmgbsa_frames.csv`: per-frame energies (`frame, time_ns, E_complex_kcal, E_receptor_kcal, E_ligand_kcal, dG_kcal`)
- `mmgbsa_summary.json`: means, std, SEM, and all provenance (force field, dielectrics, selections, skip/stride settings)

The underlying trajectories are not shipped (each DCD is ~100 MB). If you want to regenerate these outputs, the trajectories are under `examples/drug-discovery/cdk2-htvs/07_md_refinement/results/<compound>/<rep>/production.dcd` in the repo.

## Inspecting a single replicate

Start with a "normal" case. `CHEMBL388978/rep1/mmgbsa_summary.json` looks like:

```json
{
    "dG_mean_kcal_mol": -45.9,
    "dG_std_kcal_mol": 5.17,
    "dG_sem_kcal_mol": 0.93,
    "sem_note": "SEM assumes frames are independent samples...",
    "n_frames_evaluated": 31,
    "skip_ns": 0.5,
    "stride": 5,
    "solute_dielectric": 1.0,
    "solvent_dielectric": 78.5,
    ...
}
```

A single-run SEM of ~0.9 kcal/mol *looks* reassuring, but remember it treats 31 stride-correlated frames as independent. The SEM reported here is a **within-trajectory** estimate, not a true statistical error. Always interpret alongside the other replicates.

## Replicate comparison across the three compounds

All three compounds were run with identical settings (`skip_ns=0.5`, `stride=5`, `n_frames=31` per replicate). The table below shows each replicate's reported mean and single-run SEM, then what a replicate-pooled analysis reveals:

| Compound | rep1 dG | rep2 dG | rep3 dG | Spread | Replicate-pooled dG | Honest SEM |
|---|---:|---:|---:|---:|---:|---:|
| CHEMBL1087650 | -43.65 | -44.46 | -43.58 | **0.88** | -43.90 | 0.23 |
| CHEMBL388978  | -45.90 | -44.42 | -47.38 | **2.96** | -45.90 | 0.70 |
| CHEMBL3943841 |  -2.26 |  -9.68 | -36.94 | **34.68** | -16.29 | 8.61 |

The "replicate-pooled dG" column is the mean of the three rep means, and "Honest SEM" is the standard deviation of those three means divided by sqrt(3). This is much closer to the true statistical error than any single-run SEM.

**What this tells you about ranking:**
- CHEMBL1087650 and CHEMBL388978 are trustworthy: the replicate-pooled means are self-consistent and their confidence intervals do not overlap, so CHEMBL388978 can reasonably be ranked above CHEMBL1087650 on MM-GBSA.
- CHEMBL3943841 is not rankable. Its replicate-pooled value of -16.29 ± 8.61 overlaps both of the other compounds' intervals, and the raw spread (34 kcal/mol across replicates of the same compound) dwarfs any chemically meaningful difference between hits. Do not include this compound in a ranked shortlist.

## The CHEMBL3943841 cautionary tale

Open `CHEMBL3943841/rep3/mmgbsa_summary.json` in isolation:

```json
{
    "dG_mean_kcal_mol": -36.94,
    "dG_std_kcal_mol": 3.01,
    "dG_sem_kcal_mol": 0.54,
    "n_frames_evaluated": 31
}
```

Seen alone, this looks like a **high-confidence strong binder**. The tightest single-run SEM in the entire dataset. If you trusted rep3 by itself, you would prioritize this compound for experimental follow-up.

Now look at rep1 of the same compound: `dG_mean_kcal_mol = -2.26`. That is the same compound, same pocket, same force field, same protocol, same ligand coordinates from the same docking campaign, just a different random seed on the MD. A 35 kcal/mol swing from re-running the trajectory.

The single-run SEM completely hides this. `rep3` looks converged because the 31 stride-5 frames within that one trajectory are consistent with each other: the ligand found a stable local minimum and stayed there. But the ligand found a *different* stable local minimum in rep1, and a third one in rep2, and the within-trajectory SEM has no way to know that the energy landscape has more than one basin.

This is what the Genheden & Ryde (2010) and Roux & Chipot (2024) papers in the SKILL.md references are warning about. Single-trajectory SEM is not a trustworthy uncertainty estimate for compounds where MD sampling is incomplete, and you cannot detect the problem from a single run.

## How to use MM-GBSA safely given this

1. **Always run replicates.** The HTVS workflow recommends three independent MD replicates for the top hits. This example shows why: one replicate gives you no signal about whether your result is converged.
2. **Compare replicate means, not within-trajectory SEMs.** The honest confidence interval for a compound is the spread across its replicates, not the SEM within any single one.
3. **Discard compounds whose replicate spread is comparable to or larger than the differences you are trying to resolve.** If you are trying to pick the top 5 of 20 hits and the compounds' means differ by ~5 kcal/mol, any compound with a replicate spread >5 kcal/mol is untrusted and should be held back.
4. **Inspect per-frame traces on divergent replicates.** For CHEMBL3943841, plotting `dG_kcal` vs `time_ns` from the `mmgbsa_frames.csv` of each replicate will show that the ligand is visiting qualitatively different conformations. That is a red flag for the MD refinement, not just the rescoring.

## Regenerating from scratch

If you have a trajectory, produce an equivalent result with:

```bash
# Env: drugmd-agent
python .agents/skills/drug-mmpbsa-gbsa/scripts/compute_mmgbsa.py \
  --topology examples/drug-discovery/cdk2-htvs/07_md_refinement/complexes/CHEMBL388978/complex_solvated.pdb \
  --trajectory examples/drug-discovery/cdk2-htvs/07_md_refinement/results/CHEMBL388978/rep1/production.dcd \
  --ligand_sdf examples/drug-discovery/cdk2-htvs/05_pose_validation/poses_sdf/CHEMBL388978.sdf \
  --ligand_sel "resname UNK" \
  --skip_ns 0.5 \
  --stride 5 \
  --output_dir /tmp/mmgbsa_test/
```

The output should match `CHEMBL388978/rep1/` in this folder to within numerical noise.
