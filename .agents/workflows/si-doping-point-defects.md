---
description: MLIP study of substitutional (P, B) and native (vacancy, interstitial) point defects in silicon for doping and implant-damage thermodynamics.
---

# Si Doping & Point-Defect Workflow

This workflow guides you through a **test-scale** atomistic study of silicon doping and implantation-relevant point defects using Materials Project structures and MACE MLIPs.

**Scientific problem:** After ion implantation, the crystal contains substitutional dopants plus native defects (vacancies, self-interstitials). At finite temperature, the defect population evolves toward lower-formation-energy configurations. Neutral formation energies from a consistent MLIP reference rank which defect types are thermodynamically favored in the **metal-rich / elemental-reservoir** limit (see skill constraints).

## Prerequisites

- Conda envs: `base-agent`, `mace-agent`
- `MP_API_KEY` in `~/.atomistic_skills.yaml` or environment
- MCP servers `base` and `mace` configured (optional; project script runs without MCP)

## Runnable project

All commands and outputs live in:

`projects/si-doping-defects/`

```bash
cd projects/si-doping-defects
bash run_pipeline.sh          # full pipeline
# or step-by-step:
conda run -n mace-agent python run_pipeline.py --step fetch
conda run -n mace-agent python run_pipeline.py --step relax_bulk
# ...
```

## Step-by-step methodology

### 1. Bulk silicon from Materials Project

**Skill:** `mat-db-mp` (or project `fetch` step)

- Retrieve the lowest-energy Si structure (diamond cubic, e.g. MP `mp-149`).
- Save as `structures/Si_mp.cif`.

### 2. Relax bulk with MACE

**Skill:** `mat-defect-energy`, `ml-foundation-potentials`

- Model: `MACE-MH-1`, head `matpes_r2scan` (r2SCAN-level, recommended for inorganic defects).
- `relax_cell=True`, `fmax=0.01` → `results/bulk_relaxation/`.

### 3. Generate defect supercells

**Skill:** `mat-defect-energy` — `generate_defects.py`

- Supercell: **3×3×3** (54 atoms for conventional Si cell).
- Defects on the **same** reference supercell:
  - **P@Si** (n-type substitutional)
  - **B@Si** (p-type substitutional)
  - **Si vacancy**
  - **Si self-interstitial**
- Output: `structures/defect_structures/*.cif` + `pristine_supercell.cif`.

### 4. Relax pristine supercell and each defect

**MCP:** `mcp_mace_relax_structure` with `relax_cell=False` (fixed supercell volume).

- Pristine → `results/pristine_relaxation/`
- Each defect → `results/defect_relaxations/<name>/`

### 5. Formation energies

**Skill:** `mat-defect-energy` — `calculate_defect_energy.py`

- Chemical potentials: `mat-elemental-energies` → `MACE-MH-1_matpes_r2scan_energies.json`
- Output: `results/defect_energies.json`

### 6. Interpretation (short write-up)

**Skill:** `general-peer-review` (optional)

Compare $E_f$ values:

| Defect | Physical role |
|--------|----------------|
| P@Si, B@Si | Equilibrium substitutional doping |
| V_Si | Implant damage / vacancy-mediated diffusion |
| Si_i | Implant damage / interstitial-mediated diffusion |

**Annealing narrative (qualitative):** Lower $E_f$ defects are more stable at the MLIP level; Frenkel pairs (V + Si_i) tend to recombine if barriers allow; substitutional dopants remain after damage anneals if incorporation energy is favorable vs native defects.

## Limitations

- **Neutral defects only** — no charged dopant levels (use `mat-defect-energy-dft` + VASP for that).
- **Not a cascade simulation** — no implant energy, dose, or depth profile.
- **MLIP accuracy** — formation energies are trends; validate key values with DFT if publishing.

## References

- C. Freysoldt et al., *Rev. Mod. Phys.* **86**, 253 (2014) — defect formation energy formalism.
- T. Lenosky et al., *Phys. Rev. B* **55**, 12529 (1997) — Si point-defect energetics (DFT benchmarks).
