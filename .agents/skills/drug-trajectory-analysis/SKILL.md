---
name: drug-trajectory-analysis
description: Analyze a protein-ligand MD trajectory to compute ligand RMSD, pocket RMSF, hydrogen bonds, contact occupancy, and protein-ligand interaction fingerprints over time.
category: [drug-discovery]
---

# drug-trajectory-analysis

## Goal
To extract quantitative binding-mode descriptors from a protein-ligand MD trajectory, producing:
- Ligand heavy-atom RMSD (pose stability)
- Ligand center-of-mass drift
- Binding-pocket residue RMSF (pocket flexibility)
- Hydrogen bond persistence
- Key contact occupancy
- Protein-ligand interaction fingerprints (IFPs) over time

These outputs feed directly into go/no-go decisions about pose validity and can be used to compare refinement trajectories across compounds.

## Instructions

### 1. Prepare inputs

Required:
- **Trajectory**: DCD file from [drug-protein-ligand-md](../drug-protein-ligand-md/SKILL.md)
- **Topology**: the solvated complex PDB used as the MD input

### 2. Run trajectory analysis

```bash
# Env: drugmd-agent
python .agents/skills/drug-trajectory-analysis/scripts/analyze_trajectory.py \
  --topology md/system/complex_solvated.pdb \
  --trajectory md/run/production.dcd \
  --ligand_resname UNL \
  --pocket_cutoff 5.0 \
  --output_dir md/analysis/
```

Key parameters:
- `--ligand_resname`: residue name of the ligand in the topology (default: `UNL`). Check the solvated PDB if unsure.
- `--pocket_cutoff`: distance cutoff in Angstroms for defining pocket residues around the ligand in the first frame (default: 5.0).
- `--skip_frames`: skip the first N frames as equilibration (default: 0).
- `--snapshots`: render PyMOL binding pocket snapshots at 4 timepoints (requires `pymol-open-source`).

### 3. Output files

The script produces:
- `md/analysis/ligand_rmsd.csv`: per-frame ligand heavy-atom RMSD (Angstroms)
- `md/analysis/ligand_com.csv`: per-frame ligand COM relative to protein backbone COM
- `md/analysis/pocket_rmsf.csv`: per-residue RMSF of pocket residues (Angstroms)
- `md/analysis/hbonds.csv`: hydrogen bond donor-acceptor pairs and occupancy fractions
- `md/analysis/contacts.csv`: residue-level contact occupancy fractions
- `md/analysis/interaction_fingerprints.csv`: per-frame binary IFP matrix (requires ProLIF)
- `md/analysis/analysis_summary.json`: summary statistics
- `md/analysis/plots/`: directory with PNG plots (RMSD time series, COM drift, RMSF bar chart, contact occupancy, PyMOL binding pocket snapshots)

### 4. Interpret results

Key indicators of a stable binding pose:
- **Ligand RMSD**: should plateau below 2-3 A for a stable pose. Persistent drift above 3 A suggests the ligand is leaving the pocket or adopting an alternative binding mode.
- **COM drift**: large monotonic drift indicates ligand unbinding.
- **Pocket RMSF**: identifies flexible vs. rigid pocket regions. High RMSF (>2 A) at key contact residues may indicate induced fit.
- **H-bond persistence**: critical hydrogen bonds should have >50% occupancy for a well-resolved interaction.
- **IFP consistency**: stable binding modes show consistent fingerprint patterns across the trajectory.

### 5. Quick single-metric check

For a fast assessment, check only ligand RMSD:

```bash
# Env: drugmd-agent
python .agents/skills/drug-trajectory-analysis/scripts/analyze_trajectory.py \
  --topology md/system/complex_solvated.pdb \
  --trajectory md/run/production.dcd \
  --ligand_resname UNL \
  --rmsd_only \
  --output_dir md/analysis/
```

## Examples

### Example: full analysis of TYK2 inhibitor trajectory

```bash
# Env: drugmd-agent
python .agents/skills/drug-trajectory-analysis/scripts/analyze_trajectory.py \
  --topology tyk2/md/system/complex_solvated.pdb \
  --trajectory tyk2/md/run/production.dcd \
  --ligand_resname UNL \
  --pocket_cutoff 5.0 \
  --skip_frames 10 \
  --output_dir tyk2/md/analysis/
```

## Constraints

- **Environment**: Requires `drugmd-agent` with MDAnalysis and ProLIF.
- **Trajectory format**: DCD is the default from the MD skill. PDB trajectories and XTC are also supported by MDAnalysis.
- **Ligand residue name**: must match the name used in the topology PDB. OpenMM often assigns `UNL` to non-standard residues.
- **ProLIF requirement**: interaction fingerprints require ProLIF. If ProLIF is not installed, the script skips IFP computation and logs a warning.
- **Memory**: large trajectories (>10k frames) may require significant memory for IFP computation. Use `--skip_frames` or `--stride` to downsample.

## References

- Michaud-Agrawal, N.; Denning, E. J.; Woolf, T. B.; Beckstein, O. MDAnalysis: A Toolkit for the Analysis of Molecular Dynamics Simulations. *J. Comput. Chem.* **2011**, *32*, 2319-2327. https://doi.org/10.1002/jcc.21787
- Bouysset, C.; Fiorucci, S. ProLIF: a Library to Encode Molecular Interactions as Fingerprints. *J. Cheminform.* **2021**, *13*, 72. https://doi.org/10.1186/s13321-021-00548-6

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
