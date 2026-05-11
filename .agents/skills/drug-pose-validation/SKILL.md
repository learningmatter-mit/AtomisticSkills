---
name: drug-pose-validation
description: Validate docked or generated ligand poses for physical plausibility using PoseBusters, filtering out chemically invalid or clashing poses before downstream refinement.
category: [drug-discovery]
---

# drug-pose-validation

## Goal
To filter docked or generated ligand poses through **physical plausibility checks** (bond lengths, angles, planarity, internal clashes, protein-ligand clashes, stereochemistry) using [PoseBusters](https://github.com/maabuu/posebusters), producing a validated subset of poses plus a machine-readable report.

This skill sits between docking ([drug-docking-vina](../drug-docking-vina/SKILL.md)) and downstream refinement ([drug-complex-system-builder](../drug-complex-system-builder/SKILL.md), [drug-protein-ligand-md](../drug-protein-ligand-md/SKILL.md)), ensuring that only physically reasonable poses enter expensive simulation stages.

## Instructions

### 1. Prepare inputs

You need:
- **Docked poses**: an SDF file containing one or more ligand poses (e.g., output from Vina converted to SDF, or from any pose-generation tool).
- **Receptor structure** (optional but recommended): PDB file of the protein. When provided, PoseBusters also checks for protein-ligand steric clashes.

If your docked poses are in PDBQT format, convert them to SDF first:

```bash
# Env: drugdisc-agent
obabel docking/results/ligand_docked.pdbqt -O docking/results/ligand_docked.sdf -m
```

### 2. Run pose validation

```bash
# Env: drugdisc-agent
python .agents/skills/drug-pose-validation/scripts/validate_poses.py \
  --poses docking/results/ligand_docked.sdf \
  --receptor docking/inputs/protein_prepared.pdb \
  --output_dir docking/validation/
```

This produces:
- `docking/validation/validation_report.json`: per-pose pass/fail results for each check
- `docking/validation/valid_poses.sdf`: SDF containing only poses that pass all checks
- `docking/validation/summary.txt`: human-readable summary

### 3. Run without receptor (ligand-only checks)

When no receptor is available, run ligand-only validation (checks bond geometry, planarity, stereochemistry, internal clashes):

```bash
# Env: drugdisc-agent
python .agents/skills/drug-pose-validation/scripts/validate_poses.py \
  --poses generated/conformers.sdf \
  --output_dir generated/validation/
```

### 4. Interpret results

The validation report JSON contains per-pose results:

```json
{
  "n_poses_input": 10,
  "n_poses_valid": 7,
  "pass_rate": 0.7,
  "per_pose": [
    {
      "pose_index": 0,
      "valid": true,
      "tests": {
        "mol_pred_loaded": true,
        "sanitization": true,
        "bond_lengths": true,
        "bond_angles": true,
        "internal_steric_clash": true,
        "aromatic_ring_flatness": true,
        "internal_energy": true,
        "minimum_distance_to_protein": true,
        "volume_overlap_with_protein": true
      },
      "diagnostics": { "...": "..." }
    }
  ]
}
```

The `tests` dict contains the PoseBusters pass/fail columns that determine validity. The `diagnostics` dict includes all boolean columns from the full report (loading status, extra sanitization checks, etc.) for debugging. Column names come directly from PoseBusters and vary by mode.

Key tests (ligand-only, `mol` mode):
- **bond_lengths / bond_angles**: flags chemically unreasonable geometry
- **aromatic_ring_flatness**: aromatic rings should be planar
- **internal_steric_clash**: atoms within the ligand should not overlap
- **internal_energy**: conformer energy should be reasonable relative to an ensemble average

Additional tests with receptor (`dock` mode):
- **minimum_distance_to_protein**: ligand atoms should not penetrate protein atoms
- **volume_overlap_with_protein**: ligand should not occupy protein-filled space

Poses failing any test are excluded from `valid_poses.sdf`. If all poses fail, revisit docking parameters or ligand preparation.

## Examples

### Example: validate Vina docking output for HIV-1 protease

```bash
# Env: drugdisc-agent
obabel hiv_docking/results/indinavir_docked.pdbqt -O hiv_docking/results/indinavir_docked.sdf -m

# Env: drugdisc-agent
python .agents/skills/drug-pose-validation/scripts/validate_poses.py \
  --poses hiv_docking/results/indinavir_docked.sdf \
  --receptor hiv_docking/inputs/1HSG_prepared.pdb \
  --output_dir hiv_docking/validation/
```

## Constraints

- **Environment**: Requires `drugdisc-agent` with `posebusters` installed.
- **Input format**: Poses must be SDF. Convert PDBQT to SDF with Open Babel before running.
- **Receptor**: Optional but strongly recommended. Without it, protein-ligand clash checks are skipped.
- **Hydrogen handling**: PoseBusters expects explicit hydrogens on the ligand. Ensure hydrogens are present in the input SDF (they should be if you used [drug-ligand-prep](../drug-ligand-prep/SKILL.md)).

## References

- Buttenschoen, M.; Morris, G. M.; Deane, C. M. PoseBusters: AI-Based Docking Methods Fail to Generate Physically Valid Poses or Generalise to Novel Sequences. *Chem. Sci.* **2024**, *15*, 3130-3139. https://doi.org/10.1039/D3SC04185A

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
