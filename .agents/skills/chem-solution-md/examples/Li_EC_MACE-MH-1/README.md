# Li⁺ Solvation in Ethylene Carbonate (EC) — MACE-MH-1 (omol)

## Setup

- **System**: 1 Li⁺ + 32 EC molecules (321 atoms)
- **Box size**: 15.26 Å (cubic, auto-calculated from EC density 1.321 g/cm³ at 40°C)
- **MLIP**: MACE-MH-1, `omol` head
- **Ensemble**: NVT at 330 K (above EC melting point of 36.4°C)
- **Timestep**: 0.5 fs
- **Production**: 10,000 steps (5 ps), log every 10 steps
- **Analysis stride**: every 20th frame, starting at frame 200

## Commands

### 1. Build solvation box
```bash
# Env: base-agent
python .agents/skills/chem-solution-md/scripts/build_solvation_box.py \
    --solute_smiles "[Li+]" \
    --solvent ethylene_carbonate --num_solvent 32 \
    --output_dir <research_dir>/solvation_box
```

### 2. Run NVT production
```python
mcp_mace_load_model(model_name="MACE-MH-1", task_name="omol")
mcp_mace_run_md(
    structure_data="<research_dir>/solvation_box/solvated_box.cif",
    temperature=330, ensemble="nvt", steps=10000, timestep=0.5,
    log_interval=10, monitor=True, monitor_type=["explosion"],
    output_dir="<research_dir>/nvt_production"
)
```

### 3. Analyze
```bash
# Env: base-agent
python .agents/skills/chem-solution-md/scripts/analyze_solution_md.py \
    --trajectory <research_dir>/nvt_production/C96H128LiO96_330.0K_nvt.traj \
    --rdf_pairs Li-O,Li-C --log_interval_fs 5.0 --stride 20 --start_frame 200 \
    --output_dir <research_dir>/analysis
```

## Results vs Literature

| Property | This Work | Literature | Reference |
|:---|:---|:---|:---|
| Li-O first peak position | ~1.9 Å | 1.9–2.0 Å | Borodin & Smith (2006), *JPC B* |
| Li-C(carbonyl) peak position | ~2.8 Å | 2.8–2.9 Å | Borodin & Smith (2006), *JPC B* |
| Li⁺ coordination number | ~4 (expected) | 4.0–4.5 | Xu (2004), *Chem. Rev.* |
| Density (NVT, fixed box) | 1.321 g/cm³ | 1.321 g/cm³ | CRC Handbook |

> [!NOTE]
> - The Li-O RDF peak position (~1.9 Å) is consistent with Li⁺ coordinating the carbonyl oxygens (C=O) of EC.
> - RDFs are noisy because a single Li⁺ provides poor statistics. For smoother RDFs, use multiple Li⁺ ions (e.g., 4 Li⁺ + 4 PF₆⁻ in 32 EC) or longer simulations (>20 ps).
> - The auto-detected coordination numbers from the script are unreliable here due to noise. A manual cutoff of ~2.5 Å should be used to compute the Li⁺ coordination number.
> - NPT was skipped because the `omol` head does not predict stress tensors. Box density was fixed at the experimental value.

## Output Files

- `rdf_plots.png` — Li-O and Li-C radial distribution functions
- `density_convergence.png` — Density vs. time (constant in NVT)
- `solution_analysis.json` — Full numerical results
- `box_metadata.json` — Box construction metadata

## References

- Borodin, O. & Smith, G.D., "LiTFSI Structure and Transport in Ethylene Carbonate from Molecular Dynamics Simulations", *J. Phys. Chem. B*, **110**(10), 4971–4977, 2006. [DOI](https://doi.org/10.1021/jp056249q)
- Xu, K., "Nonaqueous Liquid Electrolytes for Lithium-Based Rechargeable Batteries", *Chem. Rev.*, **104**(10), 4303–4418, 2004. [DOI](https://doi.org/10.1021/cr030203g)
- CRC Handbook of Chemistry and Physics, 97th Edition, 2016–2017.

