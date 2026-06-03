# Si Doping & Point-Defect Test Project

Atomistic test project: **bulk Si → substitutional P/B → vacancy & self-interstitial → formation energies → short interpretation.**

Uses AtomisticSkills skills `mat-db-mp`, `mat-defect-energy`, `ml-foundation-potentials` with **MACE-MH-1** (`matpes_r2scan`).

## Quick start

```bash
cd projects/si-doping-defects
bash run_pipeline.sh
```

Requires `base-agent` and `mace-agent` conda envs and `MP_API_KEY` in `~/.atomistic_skills.yaml`.

## Pipeline steps

| Step | What it does | Output |
|------|----------------|--------|
| `fetch` | Download Si from Materials Project | `structures/Si_mp.cif` |
| `relax_bulk` | Relax primitive Si cell | `results/bulk_relaxation/` |
| `generate_defects` | 3×3×3 supercell + P, B, V, Si_i | `structures/defect_structures/` |
| `relax_defects` | Fixed-cell relax pristine + defects | `results/pristine_relaxation/`, `results/defect_relaxations/` |
| `energies` | Formation energies | `results/defect_energies.json` |
| `summary` | Markdown report | `results/ANALYSIS.md` |

Run one step:

```bash
conda run -n mace-agent python run_pipeline.py --step relax_bulk
```

## Directory layout (after run)

```
projects/si-doping-defects/
├── README.md                 ← you are here
├── run_pipeline.sh
├── run_pipeline.py
├── structures/
│   ├── Si_mp.cif
│   └── defect_structures/
│       ├── pristine_supercell.cif
│       ├── sub_P_0.cif
│       ├── sub_B_0.cif
│       ├── vac_Si_0.cif
│       └── int_Si_0.cif
└── results/
    ├── bulk_relaxation/
    ├── pristine_relaxation/
    ├── defect_relaxations/
    ├── defect_energies.json
    └── ANALYSIS.md
```

## Workflow document

See [`.agents/workflows/si-doping-point-defects.md`](../../.agents/workflows/si-doping-point-defects.md) for the full agent-facing workflow.

## MCP alternative (interactive in Cursor)

After MCP restart, you can run the same logic via tools:

1. `mcp_base_search_materials_project_by_formula(formula="Si", save_to_file="structures/Si_mp.cif")`
2. `mcp_mace_load_model(model_name="MACE-MH-1", task_name="matpes_r2scan")`
3. `mcp_mace_relax_structure(...)` — follow steps in `mat-defect-energy` SKILL.md

## Expected runtime

- **CPU (Mac):** ~10–30 min depending on network (first MACE model download) and supercell size.
- Use `3×3×3` supercell by default; increase to `4×4×4` only if you need lower finite-size error.
