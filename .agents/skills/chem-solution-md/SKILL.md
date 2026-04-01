---
name: chem-solution-md
description: Set up and run molecular dynamics simulations of molecules in explicit solvent boxes using Packmol for box construction and MLIPs for dynamics.
category: [chemistry]
---

# Solution-Phase Molecular Dynamics

## Goal

Set up and run molecular dynamics (MD) simulations of molecules in explicit solvent. This skill covers three stages: (1) building a solvation box with Packmol, (2) running NPT/NVT MD using MLIPs, and (3) analyzing the trajectory for radial distribution functions (RDFs), coordination numbers, density convergence, and mean-square displacement (MSD).

> [!IMPORTANT]
> This skill bridges gas-phase `chem-*` skills and condensed-phase `mat-*` skills by providing workflows for solvation dynamics, liquid structure characterization, and dissolution studies.

## 1. Prerequisites

- **Packmol binary** must be installed and on `PATH` in the `base-agent` environment.
- **RDKit** must be available in the `base-agent` environment (for SMILES → 3D geometry).
- An MLIP backend must be available via MCP tools (MACE, MatGL, or FairChem).

## 2. MLIP Selection

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for model selection.

> [!NOTE]
> - **Organic solvents**: Use `MACE-MH-1` with `omol` head, or `UMA` with `omol` task.
> - **Aqueous inorganic systems**: Use `MACE-MH-1` with `omat_pbe` head, or MatGL/CHGNet.
> - **Mixed organic-inorganic**: Use `UMA` which handles both.

## 3. Workflow

### Step 1: Build Solvation Box

Use the box-building script to create a solvated system with Packmol:

```bash
# Env: base-agent
# Pure solvent box (64 water molecules)
python .agents/skills/chem-solution-md/scripts/build_solvation_box.py \
    --solvent water \
    --num_solvent 64 \
    --output_dir research/my_folder/solvation_box

# Solute in solvent (NaCl in 64 water molecules)
python .agents/skills/chem-solution-md/scripts/build_solvation_box.py \
    --solute_smiles "[Na+].[Cl-]" \
    --solvent water \
    --num_solvent 64 \
    --output_dir research/my_folder/solvation_box
```

**Key Parameters:**

| Argument | Description |
|:---|:---|
| `--solvent` | Pre-defined solvent name (see available solvents below) |
| `--solvent_smiles` | SMILES string for custom solvent |
| `--solvent_file` | Path to solvent structure file |
| `--solute_smiles` | SMILES string for solute (optional) |
| `--solute_file` | Path to solute structure file (optional) |
| `--num_solvent` | Number of solvent molecules (default: 64) |
| `--box_size` | Cubic box side in Å (auto-calculated from density if omitted) |
| `--tolerance` | Minimum inter-molecular distance in Å (default: 2.0) |
| `--output_dir` | Output directory |

**Available pre-defined solvents:** water, methanol, ethanol, acetonitrile, dmso, dmf, thf, toluene, acetone, dichloromethane, chloroform, hexane

**Output files:**
- `solvated_box.cif` — Periodic structure for MD
- `solvated_box.xyz` — Non-periodic XYZ for visualization
- `box_metadata.json` — Box size, atom counts, solute indices

### Step 2: Run MD with MLIP

Use MCP `run_md` tools for NPT equilibration followed by NVT production.

**NPT Equilibration** (stabilize density):
```bash
mcp_mace_load_model(
    model_name="MACE-MH-1",
    task_name="omol"
)
mcp_mace_run_md(
    structure_data="research/my_folder/solvation_box/solvated_box.cif",
    temperature=300,
    ensemble="npt",
    pressure=1.01325,        # 1 atm in bar
    steps=5000,              # 2.5 ps at 0.5 fs timestep
    timestep=0.5,            # 0.5 fs for systems with water (fast O-H vibrations)
    log_interval=10,
    monitor=True,
    monitor_type=["explosion", "volume"],
    output_dir="research/my_folder/npt_equilibration"
)
```

**NVT Production** (use the equilibrated structure):
```bash
mcp_mace_run_md(
    structure_data="research/my_folder/npt_equilibration/final_structure.cif",
    temperature=300,
    ensemble="nvt",
    steps=20000,             # 10 ps at 0.5 fs timestep
    timestep=0.5,
    log_interval=10,
    monitor=True,
    monitor_type="explosion",
    output_dir="research/my_folder/nvt_production"
)
```

### Step 3: Analyze Trajectory

Run the analysis script on the production trajectory:

```bash
# Env: base-agent
python .agents/skills/chem-solution-md/scripts/analyze_solution_md.py \
    --trajectory research/my_folder/nvt_production/trajectory.traj \
    --rdf_pairs "Na-O,Cl-O,O-O" \
    --msd_elements "Na,Cl" \
    --log_interval_fs 5.0 \
    --output_dir research/my_folder/analysis
```

**Key Parameters:**

| Argument | Description |
|:---|:---|
| `--trajectory` | Path to ASE .traj trajectory file |
| `--rdf_pairs` | Comma-separated element pairs for RDF, e.g. `"Na-O,Cl-O"` |
| `--rmax` | Maximum RDF distance in Å (default: 8.0) |
| `--start_frame` | First frame to include in analysis (default: 0) |
| `--stride` | Frame stride (default: 1) |
| `--log_interval_fs` | Time between frames in fs (default: 10.0) |
| `--msd_elements` | Comma-separated elements for MSD (optional) |

**Output files:**
- `solution_analysis.json` — Full results (RDF data, coordination numbers, density, MSD)
- `rdf_plots.png` — RDF plots for each element pair
- `density_convergence.png` — Density vs. time
- `msd_plot.png` — MSD for specified elements (if requested)

## 4. Examples

### Pure Water Box

```bash
# Env: base-agent
python .agents/skills/chem-solution-md/scripts/build_solvation_box.py \
    --solvent water --num_solvent 64 \
    --output_dir .agents/skills/chem-solution-md/examples/pure_water
```
Expected: 192 atoms (64 × 3), box ~12.4 Å

### NaCl in Water

```bash
# Env: base-agent
python .agents/skills/chem-solution-md/scripts/build_solvation_box.py \
    --solute_smiles "[Na+].[Cl-]" --solvent water --num_solvent 64 \
    --output_dir .agents/skills/chem-solution-md/examples/NaCl_in_water
```

After MD + analysis, expected RDF peak positions:
- Na–O first peak: ~2.4 Å
- Cl–O first peak: ~3.2 Å
- Na coordination number: ~5–6

## 5. Constraints

- **Timestep**: Use **0.5 fs** for water and systems with O–H/N–H bonds (fast vibrations). Can use 1.0 fs for heavier solvents without H.
- **Equilibration**: NPT equilibration is critical. Verify density stabilization before production run.
- **System size**: A minimum of **64 solvent molecules** is recommended for reliable RDFs. Larger boxes (128–256) reduce finite-size effects.
- **PBC interactions**: Ensure the box is large enough that periodic images do not interact (box side > 2 × rmax for RDF).
- **Environments**:
  - `base-agent` for box building and analysis scripts
  - MCP tools for MD (any MLIP backend)

## References

- Martínez et al., "PACKMOL: A package for building initial configurations for molecular dynamics simulations", *J. Comput. Chem.*, 2009. [DOI](https://doi.org/10.1002/jcc.21224)
- pymatgen PackmolBoxGen: [pymatgen.io.packmol](https://pymatgen.org/pymatgen.io.packmol.html)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
