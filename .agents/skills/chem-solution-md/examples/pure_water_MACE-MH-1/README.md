# Pure Water MD Example — MACE-MH-1 (omol)

## Setup

- **System**: 64 H₂O molecules (192 atoms)
- **Box size**: 12.43 Å (cubic, auto-calculated from water density 0.997 g/cm³)
- **MLIP**: MACE-MH-1, `omol` head
- **Ensemble**: NVT at 300 K
- **Timestep**: 0.5 fs
- **Production**: 10,000 steps (5 ps), log every 10 steps
- **Analysis stride**: every 20th frame, starting at frame 200 (skip initial equilibration)

## Commands

### 1. Build box
```bash
# Env: base-agent
python .agents/skills/chem-solution-md/scripts/build_solvation_box.py \
    --solvent water --num_solvent 64 \
    --output_dir <research_dir>/solvation_box
```

### 2. Run NVT production
```python
mcp_mace_load_model(model_name="MACE-MH-1", task_name="omol")
mcp_mace_run_md(
    structure_data="<research_dir>/solvation_box/solvated_box.cif",
    temperature=300, ensemble="nvt", steps=10000, timestep=0.5,
    log_interval=10, monitor=True, monitor_type=["explosion"],
    output_dir="<research_dir>/nvt_production"
)
```

### 3. Analyze
```bash
# Env: base-agent
python .agents/skills/chem-solution-md/scripts/analyze_solution_md.py \
    --trajectory <research_dir>/nvt_production/H128O64_300.0K_nvt.traj \
    --rdf_pairs O-O,O-H --log_interval_fs 5.0 --stride 20 --start_frame 200 \
    --output_dir <research_dir>/analysis
```

## Results vs Literature

| Property | This Work | Experiment | Reference |
|:---|:---|:---|:---|
| O-O first peak position | 2.78 Å | 2.76 Å | Soper (2000), *Chem. Phys.* |
| O-O first peak height g(r) | 2.64 | 2.6–3.1 | Skinner et al. (2013), *JCP* |
| O-H intramolecular peak | 0.98 Å | 0.97 Å | Soper & Benmore (2008), *PRL* |
| Density (NVT, fixed box) | 0.997 g/cm³ | 0.997 g/cm³ | NIST |

> [!NOTE]
> - Density is fixed at the experimental value in NVT (box size set from target density).
> - The O-O first peak position (2.78 Å) agrees with experiment (2.76 Å) to within 0.02 Å.
> - The O-O peak height (2.64) falls within the experimental range (2.6–3.1) reported by different scattering experiments.
> - NPT equilibration was not used because the MACE-MH-1 `omol` head does not currently predict stress tensors. For systems requiring density equilibration, use a model that supports stress (e.g., `omat_pbe` head).

## Output Files

- `rdf_plots.png` — O-O and O-H radial distribution functions
- `density_convergence.png` — Density vs. time
- `solution_analysis.json` — Full numerical results
- `box_metadata.json` — Box construction metadata

## References

- Soper, A.K., "The radial distribution functions of water and ice from 220 to 673 K and at pressures up to 400 MPa", *Chem. Phys.*, **258**(2–3), 121–137, 2000. [DOI](https://doi.org/10.1016/S0301-0104(00)00179-8)
- Skinner, L.B. et al., "Benchmark oxygen-oxygen pair-distribution function of ambient water from x-ray diffraction measurements", *J. Chem. Phys.*, **138**, 074506, 2013. [DOI](https://doi.org/10.1063/1.4790861)
- Soper, A.K. & Benmore, C.J., "Quantum Differences between Heavy and Light Water", *Phys. Rev. Lett.*, **101**, 065502, 2008. [DOI](https://doi.org/10.1103/PhysRevLett.101.065502)

