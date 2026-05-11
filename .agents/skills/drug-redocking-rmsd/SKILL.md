---
name: drug-redocking-rmsd
description: Compute symmetry-corrected heavy-atom RMSD between docked poses and a reference crystal ligand to validate docking protocols.
category: [drug-discovery]
---

# drug-redocking-rmsd

## Goal

To quantitatively validate a docking protocol by computing the symmetry-corrected **in-place** heavy-atom RMSD between docked poses and the crystallographic reference ligand. A top-scored pose (pose 1) RMSD below 2.0 A is the standard threshold for a successful self-docking control.

**Self-docking is a necessary, not sufficient, check.** It verifies that your receptor preparation, box definition, and scoring function can recover a known pose in its own binding site. It does not verify that the protocol will work on new compounds. For a production virtual screen, complement self-docking with cross-docking into different receptor conformations when available (see the [HTVS workflow](../../workflows/drug-hit-finding-htvs.md) Stage 3), and pair this RMSD check with [drug-pose-validation](../drug-pose-validation/SKILL.md) to catch poses that are geometrically near-native but physically implausible (internal clashes, strained torsions).

## Instructions

### 1. Compute RMSD from a crystal PDB reference

When the reference ligand is extracted from a PDB (HETATM records, no bond orders), provide the SMILES so the script can assign bond orders via template matching:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-redocking-rmsd/scripts/compute_rmsd.py \
  --docked docking/ligand_docked.pdbqt \
  --reference crystal_ligand.pdb \
  --smiles "NS(=O)(=O)c1ccc(Nc2nc3[nH]cnc3c(OCC3CCCCC3)n2)cc1" \
  --output_dir validation/
```

### 2. Compute RMSD from an SDF reference

When the reference ligand is an SDF with proper bond orders (e.g., from a database or ligand-prep), no SMILES is needed:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-redocking-rmsd/scripts/compute_rmsd.py \
  --docked docking/ligand_docked.pdbqt \
  --reference crystal_ligand.sdf \
  --output_dir validation/
```

### 3. Tune the pass/fail threshold

The default threshold is 2.0 A, which is the classical success criterion from the original docking validation literature. Modern docking programs often do substantially better, and the threshold should scale with ligand size and flexibility:

| Ligand character | Suggested `--threshold` |
|---|---|
| Small, rigid (fragments, few rotatable bonds) | 1.0-1.5 |
| Drug-like, moderate flexibility | 2.0 (default) |
| Large or highly flexible (>10 rotatable bonds, macrocycles) | 2.5-3.0 |

Below about 1.5 A is typically considered "good" and below 1.0 A is "very good" for modern docking of small rigid compounds. Above roughly 3 A, numeric ordering loses meaning (a 4 A pose is not usefully "better" than a 6 A pose; both are wrong).

```bash
# Env: drugdisc-agent
python .agents/skills/drug-redocking-rmsd/scripts/compute_rmsd.py \
  --docked docking/ligand_docked.pdbqt \
  --reference crystal_ligand.sdf \
  --threshold 1.5 \
  --output_dir validation/
```

### 4. Interpret the output

The script writes `rmsd_results.json`:

```json
{
    "reference": "crystal_ligand.sdf",
    "docked": "ligand_docked.pdbqt",
    "n_poses": 5,
    "threshold": 2.0,
    "top_pose_rmsd": 0.823,
    "gate_pass": true,
    "gate_criterion": "Top-scored docked pose (pose 1) heavy-atom RMSD below threshold. ...",
    "best_rmsd": 0.823,
    "best_pose": 1,
    "best_rmsd_note": "best_rmsd is the minimum RMSD across all poses. Use as a diagnostic only: ...",
    "poses": [
        {"pose": 1, "rmsd_heavy_atom": 0.823, "pass": true},
        {"pose": 2, "rmsd_heavy_atom": 1.451, "pass": true},
        {"pose": 3, "rmsd_heavy_atom": 4.102, "pass": false}
    ]
}
```

- **`gate_pass`** is the protocol-validation verdict: true iff **pose 1** (the top-scored pose) is within `threshold`. A near-native pose further down the list is not enough; if the scoring function cannot rank it first, the protocol is not working.
- **`top_pose_rmsd`** is the pose-1 RMSD, the value `gate_pass` keys off.
- **`best_rmsd`** / **`best_pose`** are diagnostics only. If `best_pose > 1` but `best_rmsd < threshold`, the sampling is finding near-native conformations but the scoring function is failing to prioritize them. This is a scoring problem, not a sampling problem, and warrants rescoring or re-ranking rather than redoing the search.
- **`rmsd_heavy_atom`** is the symmetry-corrected in-place RMSD over all heavy atoms in Angstroms. The script uses RDKit's `CalcRMS` which enumerates molecular automorphisms and (by default) symmetrizes conjugated terminal groups like carboxylates and nitros.

### 5. Use in the HTVS validation gate

This skill is designed to be called during the protocol validation gate of the [HTVS workflow](../../workflows/drug-hit-finding-htvs.md) (Stage 3). If `gate_pass` is false, revisit receptor preparation, protonation states, or box placement before proceeding to the production screen. If `best_pose > 1` while `top_pose_rmsd > threshold`, the scoring function rather than the search is the bottleneck; consider alternative scoring functions or rescoring with a more expensive method.

See [examples/README.md](examples/README.md) for a worked case using real NU6102 / CDK2 self-docking data from the cdk2-htvs HTVS campaign. That example also documents a real correctness discrepancy between this version of the skill and an earlier (buggy) version, and is worth reading if you have cached validation results from a previous run.

## Constraints

- **Environment**: Requires `drugdisc-agent`.
- **Docked format**: Multi-model PDBQT (as output by [drug-docking-vina](../drug-docking-vina/SKILL.md)). Poses must be in Vina order (pose 1 = top-scored) or the top-1 gate will key off the wrong pose.
- **Reference format**: PDB (requires `--smiles`) or SDF (self-contained bond orders).
- **In-place RMSD, no alignment**: The script uses `rdMolAlign.CalcRMS` (not `GetBestRMS`) to compute RMSD *without* rigid-body alignment between probe and reference. For self-docking validation this is mandatory: the docked pose and the crystal reference are expected to share the receptor's coordinate frame, so any alignment would artificially deflate the RMSD and silently pass a failing protocol.
- **Symmetry handling**: Uses RDKit's `CalcRMS` to enumerate molecular automorphisms and return the minimum RMSD over all valid atom mappings. `symmetrizeConjugatedTerminalGroups=True` is passed explicitly (default since RDKit 2022.09) so that carboxylates, nitro groups, and amidinium groups are treated symmetrically. This can change the reported RMSD by up to ~0.8 A for compounds carrying such groups.
- **Molecule identity check**: Before computing RMSD, the script compares the InChIKey connectivity block between the reference and the docked pose. A mismatch raises an error rather than producing a meaningless number. This catches the silent-failure mode where the reference and docked files correspond to different compounds (easy mistake in batch workflows). Protonation/tautomer differences do **not** trigger a false mismatch because only the connectivity-only block of the InChIKey is compared.
- **Receptor coordinate frame**: The receptor used for docking must share the coordinate frame of the crystal structure the reference ligand was extracted from. If the receptor was energy-minimized, realigned, or had waters rearranged between the crystal and the docking run, self-docking RMSD will be inflated for reasons unrelated to docking accuracy. Do not minimize the receptor before a self-docking validation.
- **Crystal structure quality matters**: The reference is treated as ground truth, but the crystal model is itself uncertain. Prefer references from structures with resolution better than 2.5 A and ligand B-factors comparable to or below the local protein mean. For poorly resolved ligands, consider the real-space R-factor (RSR) as a complementary sanity check, or treat the RMSD with larger uncertainty.
- **Alternate conformations / multi-molecule references**: For PDB references, the script does not explicitly resolve ALT-LOC records; RDKit will take the first conformation it encounters. For SDF references, only the **first** molecule in the file is used. If your reference has multiple conformations or alternate ligands, split them into separate files and run the script per conformation.
- **Threshold**: The 2.0 A default is widely used but not universal. See section 3 above for size- and flexibility-based guidance. The threshold is exposed as `--threshold`.

## References

- Trott, O.; Olson, A. J. AutoDock Vina: Improving the Speed and Accuracy of Docking. *J. Comput. Chem.* **2010**, *31*, 455-461. [doi:10.1002/jcc.21334](https://doi.org/10.1002/jcc.21334)
- Bento, A. P.; et al. An open source chemical structure curation pipeline using RDKit. *J. Cheminform.* **2020**, *12*, 51. [doi:10.1186/s13321-020-00456-1](https://doi.org/10.1186/s13321-020-00456-1)

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
