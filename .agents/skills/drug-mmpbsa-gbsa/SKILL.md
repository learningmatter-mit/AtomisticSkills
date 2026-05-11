---
name: drug-mmpbsa-gbsa
description: >
  Compute single-trajectory MM-GBSA and / or MM-PBSA binding free energy
  estimates from a protein-ligand MD trajectory. Two backends: a fast
  OpenMM GBn2 path (no extra dependencies) and an AmberTools MMPBSA.py
  path that supports both GB (multiple igb models) and Poisson-Boltzmann
  PB on the same trajectory.
category: [drug-discovery]
---

# drug-mmpbsa-gbsa (MM-GBSA / MM-PBSA)

## Goal

To estimate relative binding free energies from MD trajectories using the single-trajectory MM-GBSA / MM-PBSA approach. For each trajectory frame, the method strips explicit solvent, evaluates potential energies of the complex, receptor, and ligand subsystems in implicit solvent, and computes:

    dG = E_complex - E_receptor - E_ligand

The entropy term (-TdS) is omitted, which is standard practice when the goal is relative ranking rather than absolute binding affinity. MM-GBSA / MM-PBSA is most useful for re-ranking docked poses after MD refinement, providing an orthogonal signal to docking scores and geometric stability metrics.

## Choosing a backend

| Path | Script | When to use | Extras |
|---|---|---|---|
| **OpenMM GBn2 (fast)** | `compute_mmgbsa.py` | Throughput rescoring of HTVS hits; everything stays inside OpenMM with the same force field as the MD | No extra dependencies; ~1-5 minutes per compound on CPU |
| **AmberTools MMPBSA.py** | `compute_mmpbsa.py` | When you need PB (not just GB), per-method decomposition (ELE, VDW, EGB / EPB, ESURF), or a setup that matches what reviewers expect from the MM-PBSA literature | Adds `MMPBSA.py`, `cpptraj`, and `parmed` to the dependency surface (already in `drugmd-agent`); ~1-3 minutes for GB, ~5-30 minutes for PB depending on system size and frame count |

Both paths give comparable GB rankings for typical drug-protein systems, but the absolute dG numbers will differ across backends because they use different GB models, radius sets, and surface-area treatments. **Don't compare numbers across the two scripts.**

## Instructions

### 1. Basic usage (protein + ligand, short HTVS-style MD)

For the 1-5 ns production runs typical in the [HTVS workflow](../../workflows/drug-hit-finding-htvs.md):

```bash
# Env: drugmd-agent
python .agents/skills/drug-mmpbsa-gbsa/scripts/compute_mmgbsa.py \
  --topology md/system/complex_solvated.pdb \
  --trajectory md/run/production.dcd \
  --ligand_sdf md/ligand.sdf \
  --ligand_resname UNL \
  --skip_ns 0.5 \
  --stride 5 \
  --output_dir md/mmgbsa/
```

Key parameters:
- `--topology`: solvated complex PDB from [drug-complex-system-builder](../drug-complex-system-builder/SKILL.md)
- `--trajectory`: production DCD from [drug-protein-ligand-md](../drug-protein-ligand-md/SKILL.md)
- `--ligand_sdf`: ligand SDF with correct bond orders (for OpenFF parameterization and AM1-BCC charges)
- `--ligand_resname`: residue name of the ligand in the PDB topology (default: UNL)
- `--skip_ns`: skip the first N nanoseconds of trajectory as equilibration (default: 0.5). For longer production runs, increase proportionally: roughly 10% of production length is a reasonable rule of thumb, capped at ~5 ns for 50+ ns runs.
- `--stride`: evaluate every Nth frame after skipping (default: 5)
- `--solute_dielectric`: interior dielectric of the solute (default: 1.0). See section 3 below on when to raise this.

### 2. With a cofactor (e.g., NADPH) and longer MD

When the receptor has a bound cofactor that should be part of the receptor subsystem, and the MD production was long enough (>=10 ns) to justify a longer equilibration skip:

```bash
# Env: drugmd-agent
python .agents/skills/drug-mmpbsa-gbsa/scripts/compute_mmgbsa.py \
  --topology md/system/complex_solvated.pdb \
  --trajectory md/run/production.dcd \
  --ligand_sdf md/ligand.sdf \
  --cofactor_sdf md/nadph.sdf \
  --ligand_resname UNL \
  --cofactor_resname NDP \
  --skip_ns 2.0 \
  --output_dir md/mmgbsa/
```

### 3. Tuning the solute dielectric

The interior dielectric of the solute (`--solute_dielectric`, OpenMM's `soluteDielectric` parameter) is a major knob for MM-GBSA rankings and is often the difference between sensible and nonsense results. The default of 1.0 treats the solute interior as electronically non-polarizable; the explicit partial charges and atom geometries are still there, but no implicit electronic polarization is added on top. This is the most physically pure choice and works well for **nonpolar binding sites with few charged residues**. For **polar or highly charged pockets**, raise it:

| Binding site character | Suggested `--solute_dielectric` |
|---|---|
| Mostly hydrophobic, few ionizable residues | 1.0 (default) |
| Mixed polar/nonpolar | 2.0 |
| Many charged residues (Asp/Glu/Lys/Arg clusters, salt bridges) | 4.0 |

Higher dielectrics damp electrostatic contributions and generally improve ranking agreement with experiment for charged systems, at the cost of losing sensitivity to directional electrostatic interactions. If you are unsure, run the rescoring at 1.0 and 2.0 on a small subset with known rank-order and pick the value that tracks better. The chosen value is recorded in `mmgbsa_summary.json` for provenance.

```bash
# Env: drugmd-agent
python .agents/skills/drug-mmpbsa-gbsa/scripts/compute_mmgbsa.py \
  --topology md/system/complex_solvated.pdb \
  --trajectory md/run/production.dcd \
  --ligand_sdf md/ligand.sdf \
  --ligand_resname UNL \
  --solute_dielectric 2.0 \
  --output_dir md/mmgbsa/
```

### 4. Custom selections

For non-standard residue naming or multi-chain receptors:

```bash
# Env: drugmd-agent
python .agents/skills/drug-mmpbsa-gbsa/scripts/compute_mmgbsa.py \
  --topology md/system/complex_solvated.pdb \
  --trajectory md/run/production.dcd \
  --ligand_sdf md/ligand.sdf \
  --ligand_sel "resname UNK and not name H*" \
  --output_dir md/mmgbsa/
```

### 5. Interpret results

The script outputs:

- `mmgbsa_frames.csv`: per-frame energies (E_complex, E_receptor, E_ligand, dG)
- `mmgbsa_summary.json`: mean, std, SEM of dG, and the dielectric/frame parameters used

```json
{
    "dG_mean_kcal_mol": -42.5,
    "dG_std_kcal_mol": 8.3,
    "dG_sem_kcal_mol": 1.2,
    "n_frames_evaluated": 50,
    "solute_dielectric": 1.0,
    "solvent_dielectric": 78.5
}
```

More negative dG indicates stronger predicted binding. **Only relative ranking within a congeneric series is interpretable.** Absolute dG values from single-trajectory MM-GBSA without entropy corrections are not binding free energies in any physical sense, and specific numbers should not be reported as "predicted affinities" or compared across chemically distinct scaffolds. When ranking compounds:

- Group comparisons by formal charge state (see Constraints below).
- Compare mean dG values, but also inspect the per-frame trace in `mmgbsa_frames.csv` for stability. A compound with a noisy or drifting dG signal is less trustworthy than one with a tight distribution, even if the mean looks favorable.
- Use MM-GBSA as an additional signal alongside geometric stability (RMSD, contact persistence) from `drug-trajectory-analysis`, not as a standalone ranking.
- **Compare replicate means, not within-trajectory SEMs.** The honest uncertainty for a compound is the spread across independent MD replicates, not the SEM from any single one. See [examples/README.md](examples/README.md) for a real CDK2 case study that demonstrates this: one compound in the example shows a 35 kcal/mol swing across three MD replicates while each individual replicate reports a tight single-run SEM. Trusting any single replicate on that compound would be deeply misleading.

### 6. AmberTools path: MM-PBSA / MM-GBSA via MMPBSA.py

When you need Poisson-Boltzmann (not just GB), or when you want a method that matches what reviewers expect from the MM-PBSA literature, use `compute_mmpbsa.py`. It builds the same dry-complex / receptor / ligand subsystems as the OpenMM path, then converts the systems to Amber prmtops via ParmEd, converts the trajectory to NetCDF via cpptraj, and hands everything to AmberTools `MMPBSA.py`.

```bash
# Env: drugmd-agent
python .agents/skills/drug-mmpbsa-gbsa/scripts/compute_mmpbsa.py \
  --topology md/system/complex_solvated.pdb \
  --trajectory md/run/production.dcd \
  --ligand_sdf md/ligand.sdf \
  --ligand_resname UNL \
  --skip_ns 0.5 \
  --stride 5 \
  --method both \
  --output_dir md/mmpbsa/
```

Key parameters:

- `--method`: `gb` (only Generalized Born), `pb` (only Poisson-Boltzmann), or `both` (default). PB is much slower than GB (~5-10x for typical systems); use `gb` for HTVS-style throughput and `both` only when you need the cross-check.
- `--gb_model`: `igb` value passed to MMPBSA.py. The script sets the prmtop's GB radius set to match the chosen model via ParmEd.

  | igb | Model | Paired radius set | Notes |
  |---:|---|---|---|
  | 1 | HCT (Hawkins / Cramer / Truhlar) | mbondi | |
  | 2 | OBC1 (Onufriev / Bashford / Case) | mbondi2 | |
  | **5** | **OBC2** | **mbondi2** | **Default; most widely used for protein-ligand MM-GBSA** |
  | 7 | GBn / GB-Neck | mbondi | Mongan et al. 2007 (note: the Amber manual recommends mbondi here; some downstream tools and PB-focused docs recommend bondi instead - we follow the Mongan 2007 parameterization) |
  | 8 | GBn2 / GB-Neck2 | mbondi3 | Nguyen et al. 2013 |

  Note that **the OpenMM `compute_mmgbsa.py` path uses GBn2 (Amber-equivalent igb=8 with mbondi3-like radii), while this AmberTools path defaults to OBC2 (igb=5 with mbondi2)**. They are different GB models. Even on a GB-only comparison, you should expect the absolute dG to differ across the two scripts; this is the main reason for the gap, alongside the LCPO / no-SA difference noted in the comparison table.

- `--pb_int_diel` (default 1.0), `--pb_ext_diel` (default 80.0): PB dielectric constants. Same dielectric-tuning logic applies as for GB (raise `--pb_int_diel` to 2-4 for polar / charged pockets, see section 3). For PB specifically, raising the interior dielectric above ~2 is **an empirical fitting choice rather than a physical correction**: ε_int ~ 2 is the upper end of what is physically defensible (modeling electronic polarization only); larger values are commonly used in the literature but they are tuning parameters, not first-principles. Note also that the OpenMM path defaults to a solvent dielectric of 78.5 (the standard 25 °C value), while the AmberTools path defaults to AmberTools' own 80.0 - one more reason absolute numbers are not comparable across backends.
- `--salt_conc` (default 0.0 M): salt concentration used by both GB (`saltcon`) and PB (`istrng`). Set to 0.15 to match physiological ionic strength.

The script writes:

- `mmpbsa.in`: the auto-generated MMPBSA.py input file (kept for provenance).
- `complex.prmtop`, `receptor.prmtop`, `ligand.prmtop`, `*.inpcrd`: ParmEd-built Amber topologies and coords. Atom ordering is preserved against the source PDB so the trajectory aligns without any tleap-side reordering.
- `trajectory_dry.nc`: the stripped, NetCDF-format trajectory MMPBSA.py consumed.
- `FINAL_RESULTS_MMPBSA.dat`: the verbatim MMPBSA.py results file (per-method breakdown of ELE, VDW, EGB/EPB, ESURF/ECAVITY, etc.).
- `mmpbsa_summary.json`: parsed dG mean / std / SEM per method, plus all provenance.

```json
{
    "method": "both",
    "results": {
        "GB": {"dG_mean_kcal_mol": -51.13, "dG_std_kcal_mol": 2.36, "dG_sem_kcal_mol": 1.36},
        "PB": {"dG_mean_kcal_mol":  -0.39, "dG_std_kcal_mol": 2.85, "dG_sem_kcal_mol": 1.64}
    },
    "gb_model": 5,
    "pb_int_diel": 1.0,
    "pb_ext_diel": 80.0,
    ...
}
```

**PB and GB will often disagree by 30+ kcal/mol** in absolute dG. This is normal: PB and GB make different approximations for the polar solvation free energy, and the nonpolar / cavity terms also differ. Within a single method, ranking is what matters; across methods, large absolute differences are diagnostic of how sensitive your system is to the implicit-solvent approximation, not a sign that one method is "wrong". When PB and GB give wildly different rank orders on the same set of compounds, neither is reliable, and you are probably out of the regime where end-point free-energy methods work, and you should consider FEP / ABFE instead.

The same caveats from sections 3 and 5 (replicates beat single-run SEM, charge state matters, electrostatic environment mismatch) apply equally to the AmberTools path.

### 7. Integration with the HTVS workflow

In the [HTVS workflow](../../workflows/drug-hit-finding-htvs.md), MM-GBSA is run after MD refinement (Stage 8) as an additional ranking signal. Combined with trajectory stability metrics (RMSD, H-bonds, contacts from [drug-trajectory-analysis](../drug-trajectory-analysis/SKILL.md)), it provides a more complete picture of binding quality than docking scores alone.

## Constraints

- **Environment**: Requires `drugmd-agent`.
- **Dependencies**:
  - OpenMM path (`compute_mmgbsa.py`): openmm, openmmforcefields, openff-toolkit (for SMIRNOFF parameterization), rdkit, MDAnalysis.
  - AmberTools path (`compute_mmpbsa.py`): the OpenMM deps above plus parmed, AmberTools (`MMPBSA.py`, `mmpbsa_py_energy`, `cpptraj`). All present in `drugmd-agent`.
- **Implicit solvent**:
  - OpenMM path: GBn2 (Generalized Born with neck correction, model 2). NoCutoff nonbonded method.
  - AmberTools path: igb=5 (OBC2) by default, with mbondi2 GB radii. Other igb models supported with their canonical paired radii: 1 (HCT / mbondi), 2 (OBC1 / mbondi2), 7 (GBn / mbondi), 8 (GBn2 / mbondi3). Radii are set automatically via ParmEd `changeRadii`.
- **Force fields**: Protein: Amber ff14SB. Ligand: OpenFF 2.2.0 (Sage) with AM1-BCC charges. These must match the explicit-solvent MD force fields. Both scripts re-use the same ff14SB + OpenFF parameters for the rescoring pass; the AmberTools path then exports those parameters to Amber prmtop format via ParmEd, so atom ordering is preserved against the trajectory and no tleap-side reordering occurs.
- **Single-trajectory approximation**: Receptor and ligand conformations are extracted from the complex trajectory rather than from independently simulated apo / unbound trajectories. This neglects the **conformational reorganization energy** (an enthalpic strain difference between the bound and free states), not the configurational entropy specifically. Standard practice for ranking; separate from the entropy issue covered next.
- **No entropy correction**: The -TdS term is omitted. This is acceptable for relative ranking but means absolute dG values are not comparable to experimental binding affinities.
- **Reported SEM is optimistic**: `dG_sem_kcal_mol` is computed as `std / sqrt(n_frames)`, which assumes independent samples. Frames from a single trajectory are correlated, so the true statistical error is larger (often by 2-5x for typical HTVS MD lengths). For honest uncertainties, run multiple independent replicates (different seeds) and compare across them rather than trusting the single-run SEM. See Genheden & Ryde (2010) for a detailed treatment of block averaging and replicate-based error estimation.
- **Charged ligands are a known weakness**: MM-GBSA / MM-PBSA's treatment of charge desolvation penalties is approximate. For monovalent ligands (formal charge ±1) the issue is usually manageable; ranking accuracy degrades noticeably for ±2 and beyond. Compare compounds within their own charge state rather than across charge states; a dG comparison between a neutral and a dication is not meaningful even within a congeneric series.
- **Electrostatic environment mismatch**: The explicit-solvent MD samples conformations under PME long-range electrostatics with a specific ionic strength. The rescoring pass re-evaluates those conformations under `NoCutoff` electrostatics in continuum solvent (with explicit ions absent in the OpenMM path; with `saltcon` / `istrng` only in the AmberTools path). This is standard practice, but it is a real source of systematic error, especially for highly charged systems or binding sites near the protein surface where ionic screening matters.
- **Temperature handling**: MMPBSA.py does not expose a temperature variable; sander / PBSA use a hard-coded thermal context. The temperature MD ran at is implicit in the sampled trajectory frames.
- **Computation**: Both scripts run on CPU (no GPU needed). OpenMM GBn2 ~1-5 minutes per compound; AmberTools GB ~1-3 minutes; AmberTools PB ~5-30 minutes depending on system size.

## References

- Genheden, S.; Ryde, U. The MM/PBSA and MM/GBSA Methods to Estimate Ligand-Binding Affinities. *Expert Opin. Drug Discov.* **2015**, *10*, 449-461. [doi:10.1517/17460441.2015.1032936](https://doi.org/10.1517/17460441.2015.1032936)
- Genheden, S.; Ryde, U. How to Obtain Statistically Converged MM/GBSA Results. *J. Comput. Chem.* **2010**, *31*, 837-846. [doi:10.1002/jcc.21366](https://doi.org/10.1002/jcc.21366) (on block averaging and the need for replicate trajectories for honest error bars)
- Onufriev, A.; Case, D. A. Generalized Born Implicit Solvent Models for Biomolecules. *Annu. Rev. Biophys.* **2019**, *48*, 275-296. [doi:10.1146/annurev-biophys-052118-115325](https://doi.org/10.1146/annurev-biophys-052118-115325)
- Wang, E.; et al. End-Point Binding Free Energy Calculation with MM/PBSA and MM/GBSA: Strategies and Applications in Drug Design. *Chem. Rev.* **2019**, *119*, 9478-9508. [doi:10.1021/acs.chemrev.9b00055](https://doi.org/10.1021/acs.chemrev.9b00055)
- Roux, B.; Chipot, C. Editorial: Guidelines for Computational Studies of Ligand Binding Using MM/PBSA and MM/GBSA Approximations Wisely. *J. Phys. Chem. B* **2024**, *128*, 12027-12029. [doi:10.1021/acs.jpcb.4c06614](https://doi.org/10.1021/acs.jpcb.4c06614) (cautionary framing: end-point approximations like MM/GBSA are not a substitute for rigorous FEP/ABFE and should not be compared to experiment via a pre-established standard protocol)
- Miller III, B. R.; McGee Jr., T. D.; Swails, J. M.; Homeyer, N.; Gohlke, H.; Roitberg, A. E. MMPBSA.py: An Efficient Program for End-State Free Energy Calculations. *J. Chem. Theory Comput.* **2012**, *8*, 3314-3321. [doi:10.1021/ct300418h](https://doi.org/10.1021/ct300418h) (the AmberTools MMPBSA.py reference; used by `compute_mmpbsa.py`)

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
