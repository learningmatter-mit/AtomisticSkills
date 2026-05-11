---
name: drug-complex-system-builder
description: >
  Build a solvated, charge-neutralized protein-ligand complex for OpenMM molecular dynamics
  simulation. Combines a prepared receptor PDB and ligand SDF, parameterizes the ligand with
  OpenFF Sage or GAFF (AM1-BCC charges), applies Amber ff14SB to the protein, solvates with
  explicit water, and adds counterions. Use this skill when the user wants to solvate a complex,
  set up a system for MD, prepare for simulation, add water and ions, or build a simulation box
  from a protein-ligand structure.
category: [drug-discovery]
---

# drug-complex-system-builder

## Goal
To take a prepared protein (PDB) and a validated ligand pose (SDF) and produce a fully parameterized, solvated, ion-neutralized OpenMM simulation bundle ready for [drug-protein-ligand-md](../drug-protein-ligand-md/SKILL.md).

The output bundle includes:
- Serialized OpenMM System XML (force field parameters, constraints)
- Full-precision initial state XML (positions + box vectors for exact restart)
- Solvated PDB with protein + ligand + water + ions (for visualization)
- Provenance JSON recording all build parameters

## Instructions

### 1. Prepare inputs

Required inputs:
- **Receptor PDB**: from [drug-protein-prep](../drug-protein-prep/SKILL.md) (protonated, missing residues resolved).
- **Ligand SDF**: from [drug-pose-validation](../drug-pose-validation/SKILL.md) or [drug-docking-vina](../drug-docking-vina/SKILL.md). Must have 3D coordinates in the receptor frame and explicit hydrogens.

### 2. Build the solvated complex

```bash
# Env: drugmd-agent
python .agents/skills/drug-complex-system-builder/scripts/build_complex.py \
  --receptor docking/inputs/protein_prepared.pdb \
  --ligand docking/validation/valid_poses.sdf \
  --ligand_ff openff-2.2.0 \
  --protein_ff amber/ff14SB \
  --water_model tip3p \
  --box_padding 12.0 \
  --ionic_strength 0.15 \
  --output_dir md/system/
```

Key parameters:
- `--ligand_ff`: Force field for the ligand. Options: `openff-2.2.0` (Sage, recommended), `gaff-2.11`. OpenFF Sage is generally preferred for drug-like molecules.
- `--protein_ff`: Protein force field. Default: `amber/ff14SB`.
- `--water_model`: Water model. Default: `tip3p`. Options: `tip3p`, `tip3pfb`, `tip4pew`, `opc`, `spce`. Use `tip3pfb` or `opc` for better accuracy at higher cost.
- `--box_padding`: Minimum distance from solute to box edge in Angstroms (default: 12.0). Use 10-12 A for production; smaller values risk periodic image artifacts.
- `--ionic_strength`: Target NaCl concentration in mol/L (default: 0.15, physiological). The system is always charge-neutralized first; additional ion pairs are added to reach the target ionic strength. The ionic strength calculation does not count the neutralization ions (they are treated as bound to the solute).
- `--pose_index`: Which pose from the SDF to use (default: 0, the top-ranked pose).
- `--box_shape`: Simulation box geometry (default: `cube`). Options: `cube`, `dodecahedron`, `octahedron`. Dodecahedron and octahedron use ~30% less water for the same minimum solute-edge distance.
- `--hydrogen_mass`: Hydrogen mass in amu for hydrogen mass repartitioning (default: 4.0). With HMR (3-4 amu), the script uses `AllBonds` constraints, enabling 4-5 fs timesteps (OpenMM recommends 5 fs with `LangevinMiddleIntegrator`). Set to 1.008 to disable HMR (uses `HBonds` constraints, requires 2 fs timestep). Note: at 4 amu, methyl carbons become lighter than their bonded hydrogens, which can affect dynamics in some systems (particularly membranes). Use 3 amu if this is a concern. The downstream MD skill **must** use a matching timestep (check `hmr_enabled` and `constraints` in the provenance JSON).

### 3. Inspect outputs

The script produces:
- `md/system/complex_solvated.pdb`: solvated system for visualization (PDB precision: 0.001 A)
- `md/system/system.xml`: serialized OpenMM System (force field parameters, constraints)
- `md/system/state_initial.xml`: full-precision positions and box vectors for simulation restart
- `md/system/build_provenance.json`: records all build parameters, atom counts, box dimensions, HMR status, constraint type

Visually inspect `complex_solvated.pdb` to verify:
- The ligand is in the expected binding pocket
- No steric clashes between protein and ligand
- Water fills the box uniformly
- Ions are distributed (not clustered)

### 4. Troubleshooting

Common issues:
- **Ligand parameterization fails**: ensure the ligand SDF has explicit hydrogens and correct bond orders. Re-run [drug-ligand-prep](../drug-ligand-prep/SKILL.md) if needed. The script assigns AM1-BCC partial charges automatically; any pre-existing charges in the SDF are overwritten to ensure deterministic behavior.
- **Steric clash warning**: the script checks minimum protein-ligand interatomic distances before solvation. If you see a clash warning, the docking pose may need refinement. Mild clashes (1.0-1.5 A) can often be resolved by energy minimization, but severe clashes (<1.0 A) usually indicate a bad pose.
- **Missing residues in protein**: the builder does not fix gaps. Use [drug-protein-prep](../drug-protein-prep/SKILL.md) first.
- **Box too small**: increase `--box_padding` if you see solute atoms near box edges.
- **Simulation blowup after building**: check the provenance JSON for `hmr_enabled`. If HMR is on (default), the downstream MD should use a 4-5 fs timestep (OpenMM recommends 5 fs with `LangevinMiddleIntegrator`). If HMR is off, use 2 fs. Mismatched timestep/HMR settings are a common cause of NaN energies at startup.

## Examples

### Example: build TYK2 inhibitor complex

```bash
# Env: drugmd-agent
python .agents/skills/drug-complex-system-builder/scripts/build_complex.py \
  --receptor tyk2/inputs/4GIH_prepared.pdb \
  --ligand tyk2/validation/valid_poses.sdf \
  --ligand_ff openff-2.2.0 \
  --box_padding 12.0 \
  --ionic_strength 0.15 \
  --output_dir tyk2/md/system/
```

## Constraints

- **Environment**: Requires `drugmd-agent`.
- **Ligand size**: OpenFF Sage handles typical drug-like molecules well. For very large ligands (>100 heavy atoms) or metal-containing compounds, parameterization may require manual intervention.
- **Protein force field**: Only Amber-family force fields (ff14SB, ff19SB) are supported through openmmforcefields. CHARMM support would require a different builder.
- **Box shape**: Defaults to cubic. Dodecahedron and truncated octahedron are supported via `--box_shape` (requires OpenMM 8.0+).

## References

- Maier, J. A.; Martinez, C.; Kasavajhala, K.; Wickstrom, L.; Hauser, K. E.; Simmerling, C. ff14SB: Improving the Accuracy of Protein Side Chain and Backbone Parameters from ff99SB. *J. Chem. Theory Comput.* **2015**, *11*, 3696-3713. https://doi.org/10.1021/acs.jctc.5b00255
- Boothroyd, S.; Behara, P. K.; Madin, O. C.; et al. Development and Benchmarking of Open Force Field 2.0.0: The Sage Small Molecule Force Field. *J. Chem. Theory Comput.* **2023**, *19*, 3251-3275. https://doi.org/10.1021/acs.jctc.3c00039
- Eastman, P.; Swails, J.; Chodera, J. D.; et al. OpenMM 7: Rapid Development of High Performance Algorithms for Molecular Dynamics. *PLoS Comput. Biol.* **2017**, *13*, e1005659. https://doi.org/10.1371/journal.pcbi.1005659

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
