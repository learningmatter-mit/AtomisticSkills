# drug-redocking-rmsd example: CDK2 self-docking (NU6102 / 4SP)

Real self-docking validation data from the CDK2 HTVS campaign in this repo. NU6102 (a CDK2 inhibitor, PDB ligand ID 4SP in the 1H1S crystal structure) was docked back into its own receptor with AutoDock Vina as the protocol validation gate. This example shows what the output looks like for a failing example.

## What's in the folder

```
cdk2-nu6102/
  inputs/
    cocrystal_ligand_4SP.pdb       # crystal reference (HETATM records from 1H1S)
    cocrystal_NU6102_docked.pdbqt  # 10-pose docked output from drug-docking-vina
  output/
    rmsd_results.json              # canonical output from the current script
```

Total input size is ~40 KB. The receptor itself is not needed: RMSD is computed on the ligand coordinates alone.

## How to run it

```bash
# Env: drugdisc-agent
python .agents/skills/drug-redocking-rmsd/scripts/compute_rmsd.py \
  --docked .agents/skills/drug-redocking-rmsd/examples/cdk2-nu6102/inputs/cocrystal_NU6102_docked.pdbqt \
  --reference .agents/skills/drug-redocking-rmsd/examples/cdk2-nu6102/inputs/cocrystal_ligand_4SP.pdb \
  --smiles "NS(=O)(=O)c1ccc(Nc2nc3[nH]cnc3c(OCC3CCCCC3)n2)cc1" \
  --output_dir /tmp/cdk2_validation/
```

The reference is a PDB extracted from the 1H1S crystal structure (HETATM records only, no bond orders), so `--smiles` is required to assign bond orders via template matching.

The output should match `cdk2-nu6102/output/rmsd_results.json` bit-for-bit.

## What the output tells you

```
top_pose_rmsd: 5.16 A
gate_pass: False
best_rmsd: 4.829 A (pose 2)
  pose 1: 5.160 A  pass=False
  pose 2: 4.829 A  pass=False
  pose 3: 5.217 A  pass=False
  pose 4: 6.786 A  pass=False
  pose 5: 8.810 A  pass=False
  pose 6: 8.895 A  pass=False
  pose 7: 5.213 A  pass=False
  pose 8: 5.715 A  pass=False
  pose 9: 6.842 A  pass=False
  pose 10: 8.750 A  pass=False
```

**This is a failing self-docking gate.** Every pose is above the default 2.0 A threshold, and the best pose (pose 2 at 4.83 A) is nowhere near passing even a relaxed 3.0 A criterion. The docked ligand is in the right pocket (centroid offset from the crystal is only ~0.6 A), but its internal orientation and conformation differ enough from the crystal pose that the heavy-atom RMSD is large.

For the HTVS workflow, this means the CDK2 / NU6102 protocol as configured **should not be trusted for a production screen** without revisiting receptor prep, protonation states, box placement, or scoring function. The workflow's Stage 3 protocol validation gate exists precisely to catch cases like this before compute is burned on a broken setup.

## Control: verifying the script works

As a positive-control smoke test, you can run the script against pose 1 used as its own reference. The result should be `pose 1 = 0.0 A`, `gate_pass = True`, with the other poses at their real in-place distances from pose 1:

```bash
# Env: drugdisc-agent
python - <<'PY'
from meeko import PDBQTMolecule, RDKitMolCreate
from rdkit import Chem
pdbqt = PDBQTMolecule.from_file(".agents/skills/drug-redocking-rmsd/examples/cdk2-nu6102/inputs/cocrystal_NU6102_docked.pdbqt", skip_typing=True)
mol = Chem.RemoveHs(RDKitMolCreate.from_pdbqt_mol(pdbqt, only_cluster_leads=False)[0])
p1 = Chem.RWMol(mol); p1.RemoveAllConformers()
p1.AddConformer(Chem.Conformer(mol.GetConformer(0)), assignId=True)
w = Chem.SDWriter("/tmp/pose1_self.sdf"); w.write(p1.GetMol()); w.close()
PY

python .agents/skills/drug-redocking-rmsd/scripts/compute_rmsd.py \
  --docked .agents/skills/drug-redocking-rmsd/examples/cdk2-nu6102/inputs/cocrystal_NU6102_docked.pdbqt \
  --reference /tmp/pose1_self.sdf \
  --output_dir /tmp/pose1_control/
```

Expected: `top_pose_rmsd = 0.0`, `gate_pass = True`, and the other nine poses report their real distances from pose 1 (not the crystal).

## Negative test: identity check

As another sanity check, point the script at a reference that is a different molecule than the docked compound:

```bash
# Env: drugdisc-agent
python -c "
from rdkit import Chem
from rdkit.Chem import AllChem
m = Chem.MolFromSmiles('CC(=O)Oc1ccccc1C(=O)O')  # aspirin
m = Chem.AddHs(m); AllChem.EmbedMolecule(m, randomSeed=1); m = Chem.RemoveHs(m)
w = Chem.SDWriter('/tmp/wrong_ref.sdf'); w.write(m); w.close()
"

python .agents/skills/drug-redocking-rmsd/scripts/compute_rmsd.py \
  --docked .agents/skills/drug-redocking-rmsd/examples/cdk2-nu6102/inputs/cocrystal_NU6102_docked.pdbqt \
  --reference /tmp/wrong_ref.sdf \
  --output_dir /tmp/wrong_test/
```

Expected: the script fails loudly with `ValueError: Reference and docked pose appear to be different molecules. Reference InChIKey: BSYNRYMUTXBXSQ-..., docked pose InChIKey: ... Check that --reference and --docked correspond to the same compound.`
