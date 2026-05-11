# MM-PBSA / MM-GBSA via AmberTools (CDK2 + CHEMBL388978)

Real outputs from `compute_mmpbsa.py` (rep1 only) on a CDK2 / CHEMBL388978 trajectory. The same compound and replicate were rescored with the OpenMM GBn2 path in the [sibling example](../README.md). This example covers the **AmberTools MMPBSA.py path** so you can compare what each backend reports on identical input data.

> **This is one replicate.** Numbers below are an illustrative single-run rescore; production rankings need at least three independent MD replicates (see the OpenMM example for a worked case where one compound's dG swings 35 kcal/mol across replicates).

## Inputs

| Input | Source |
|---|---|
| Solvated topology | `examples/drug-discovery/cdk2-htvs/07_md_refinement/complexes/CHEMBL388978/complex_solvated.pdb` |
| Production trajectory | `examples/drug-discovery/cdk2-htvs/07_md_refinement/results/CHEMBL388978/rep1/production.dcd` (~12 MB DCD; not shipped here) |
| Ligand SDF | `examples/drug-discovery/cdk2-htvs/05_pose_validation/poses_sdf/CHEMBL388978.sdf` |

## Command

```bash
# Env: drugmd-agent
python .agents/skills/drug-mmpbsa-gbsa/scripts/compute_mmpbsa.py \
  --topology .../CHEMBL388978/complex_solvated.pdb \
  --trajectory .../CHEMBL388978/rep1/production.dcd \
  --ligand_sdf .../CHEMBL388978.sdf \
  --ligand_sel "resname UNK" \
  --skip_ns 0.5 \
  --stride 10 \
  --method both \
  --output_dir .agents/skills/drug-mmpbsa-gbsa/examples/cdk2-mmpbsa/run/
```

Settings: 49 frames skipped as equilibration (~0.5 ns; the script's `int(skip_ns * 1000 / dt_ps)` converts using the trajectory's actual dt, which need not be a round number), then every 10th frame analyzed. 16 evaluated frames total. GB model = igb=5 (OBC2, mbondi2 radii); PB at indi=1.0, exdi=80.0, salt=0 M. `--method both` runs PB and GB on the same prepared trajectory in one MMPBSA.py invocation.

## Shipped artifacts (`outputs/`)

| File | What it is |
|---|---|
| `mmpbsa.in` | The auto-generated MMPBSA.py input file (kept for provenance) |
| `mmpbsa_summary.json` | Parsed dG mean / std / SEM per method, plus all the run parameters |
| `FINAL_RESULTS_MMPBSA.dat` | The verbatim MMPBSA.py output, with the per-method energy decomposition (BOND, ANGLE, DIHED, VDWAALS, EEL, EGB / EPB, ESURF / ENPOLAR + EDISPER, DELTA G gas, DELTA G solv, DELTA TOTAL) |

The intermediate prmtops, NetCDF trajectory, and per-frame `_MMPBSA_*` files that MMPBSA.py writes (~44 MB for this example) are kept locally under `run/` for re-analysis but excluded from git.

## Headline results

| Method | dG mean (kcal/mol) | std | SEM | n_frames |
|---|---:|---:|---:|---:|
| MM-GBSA (igb=5, OBC2) | **-52.91** | 4.74 | 1.19 | 16 |
| MM-PBSA (indi=1, exdi=80) | **-2.02** | 6.27 | 1.57 | 16 |

For comparison, the OpenMM GBn2 path (`compute_mmgbsa.py`) on the same
trajectory / replicate reports **dG = -45.9 +/- 5.2 kcal/mol** (see
[../README.md](../README.md)). All three numbers disagree, and that is
the expected and instructive part.

## Why three different numbers from the same trajectory?

The frames are identical. Everything below the FF14SB protein backbone + OpenFF ligand parameters is approximation, and three different approximations give three different answers:

| Run | GB / PB model | Radius set | Surface-area term | dG (kcal/mol) |
|---|---|---|---|---:|
| OpenMM GBn2 (`compute_mmgbsa.py`) | GBn2 (Amber-equivalent igb=8) | mbondi3 (via OpenMM's `GBSAGBn2Force.getStandardParameters`) | ACE method (Schaefer-Karplus), included by default in OpenMM's `implicit/gbn2.xml` | -45.9 |
| AmberTools GB (this example) | OBC2 (igb=5) | mbondi2 | LCPO (gamma * SASA) | -52.9 |
| AmberTools PB (this example) | PBSA solver | mbondi2 | INP=2 (cavity + dispersion split: ENPOLAR + EDISPER) | -2.0 |

All three runs include a nonpolar surface-area term, but they use different methods and surface tensions to compute it: ACE (OpenMM GBn2), LCPO (AmberTools GB), and the cavity+dispersion split (AmberTools PB with `inp=2`). The polar solvation models also differ in magnitude (`EGB = +39.7 kcal/mol` from OBC2 vs `EPB = +53.5 kcal/mol` from PBSA for the desolvation cost), and the PB nonpolar split (ENPOLAR ~-39 kcal/mol attractive, EDISPER ~+70 kcal/mol repulsive) nets out very differently from GB's ESURF (~-6.7 kcal/mol). The ~7 kcal/mol gap between the OpenMM GBn2 result and AmberTools-GB is fully attributable to GB-model + radius + SA-method differences, not to one path missing a term.

**The usable signal across these three runs is the *sign* and the *relative ordering of compounds*, not the absolute dG.** Both GB methods give large negative dG values consistent with binding; the PB result of -2.02 +/- 1.57 kcal/mol is essentially zero within the within-trajectory SEM and is itself a useful illustration of the cross-method disagreement discussed below. You cannot quote any of these numbers as a "predicted affinity". For ranking a series of congeneric compounds with this protein, pick one method, run replicates (see the OpenMM GBn2 example for why three replicates is the floor), and compare consistently.

## When PB and GB disagree on rankings

The PB and GB results above are wildly different in magnitude (~50 kcal/mol gap). On a single compound this just tells you the implicit solvent model matters a lot for this system. **Where it becomes diagnostic is when you run the same protocol on a series of compounds and the PB ranking does not track the GB ranking.** That is a sign your system is near the edge of where end-point methods work, often because:

- The pocket has many charged side chains where GB / PB disagree on local
  electrostatics.
- The ligand has high formal charge or strongly polar groups.
- The trajectory is sampling multiple binding modes, which the
  single-trajectory approximation handles poorly regardless of the
  solvent model.

When PB and GB rank-orders diverge, neither is reliable. The honest answer is to fall back to a more rigorous method (FEP / ABFE) for the compounds you care about, not to pick whichever ranking flatters your favourite candidates. See the Roux & Chipot 2024 editorial cited in the SKILL.md references for a clear statement of this.

## Reproducing this example locally

The trajectory is ~12 MB and the prmtops add another ~3 MB; the full intermediate set is ~44 MB. Reproduce with:

```bash
# Env: drugmd-agent
python .agents/skills/drug-mmpbsa-gbsa/scripts/compute_mmpbsa.py \
  --topology examples/drug-discovery/cdk2-htvs/07_md_refinement/complexes/CHEMBL388978/complex_solvated.pdb \
  --trajectory examples/drug-discovery/cdk2-htvs/07_md_refinement/results/CHEMBL388978/rep1/production.dcd \
  --ligand_sdf examples/drug-discovery/cdk2-htvs/05_pose_validation/poses_sdf/CHEMBL388978.sdf \
  --ligand_sel "resname UNK" \
  --skip_ns 0.5 --stride 10 --method both \
  --output_dir /tmp/cdk2_mmpbsa/
```

Wall time on macOS arm64 (M-series): ~5 minutes (GB ~1 minute, PB ~4 minutes for this 297-residue receptor + 61-atom ligand at 16 frames).
