# HIV-1 Protease Complex System Builder Example (PDB 1HSG)

## Goal
Demonstrate building a solvated protein-ligand complex for OpenMM simulation using the HIV-1 protease (PDB 1HSG) with a small ligand (phenylacetic acid).

## Input Files
- `1HSG_prepared.pdb`: protein prepared via PDBFixer (hydrogens added, heterogens removed)
- `ligand.sdf`: phenylacetic acid positioned at the binding site (~14, 24, 6 A)

## Steps

```bash
# Env: drugmd-agent
python .agents/skills/drug-complex-system-builder/scripts/build_complex.py \
  --receptor .agents/skills/drug-complex-system-builder/examples/hiv1-protease/1HSG_prepared.pdb \
  --ligand .agents/skills/drug-complex-system-builder/examples/hiv1-protease/ligand.sdf \
  --ligand_ff openff-2.2.0 \
  --protein_ff amber/ff14SB \
  --water_model tip3p \
  --box_padding 10.0 \
  --ionic_strength 0.15 \
  --output_dir system/
```

## Expected Output
- `system/complex_solvated.pdb`: ~55,000 atoms (3,509 protein + 18 ligand + ~52,000 solvent/ions)
- `system/system.xml`: serialized OpenMM System with PME, HBonds constraints, HMR (1.5 amu)
- `system/build_provenance.json`: full build parameters and atom counts

## Notes
- The ligand was crudely placed (not docked), so this example is for testing the build pipeline, not for scientific analysis.
- Box dimensions are ~84 A cubic with 10 A padding.
