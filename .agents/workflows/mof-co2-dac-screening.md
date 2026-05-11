---
description: End-to-end high-throughput screening of MOF databases for CO2 direct air capture (DAC), from database query through Widom insertion ranking to GCMC isotherm validation of top candidates.
---

# MOF CO2 Direct Air Capture (DAC) Screening Workflow

This workflow guides you through a two-stage computational screening pipeline to identify the most promising Metal-Organic Frameworks (MOFs) for CO2 direct air capture from a large structural database.

**Scientific Problem:** Direct air capture of CO2 requires adsorbents with high CO2 uptake at dilute conditions (~0.04% CO2 in air, ~0.4 mbar), a favorable heat of adsorption (ideally 20–40 kJ/mol for physisorbents), and good capacity at 1 bar. Screening thousands of MOFs exhaustively with GCMC is prohibitively expensive. This workflow uses Widom insertion as a fast infinite-dilution filter (Stage 1), then validates the top candidates with a full GCMC pressure isotherm (Stage 2). The MLIP-driven approach (no empirical force fields) ensures transferability to novel hypothetical MOFs absent from classical parameterization databases.

---

## Stage 1: High-Throughput Widom Screening

### Step 1. Query MOF Database and Download Structures

Use the `chem-db-mof` skill to download a candidate set from ARC-MOF or QMOF.

```bash
# Env: base-agent
# Example: download all MOFs from ARC-MOF DB7 (Majumdar et al.)
python .agents/skills/chem-db-mof/scripts/query_mof_db.py \
    --database arc-mof \
    --output-dir research/<date>_MOF_CO2_DAC_screening/structures/
```

**Decision point:** Filter the raw set by pore-limiting diameter (PLD > 3.3 Å for CO2) to immediately exclude geometrically inaccessible frameworks. This can dramatically reduce the candidate count.

### Step 2. Structure Preparation and Supercell Generation

For every framework, check the minimum interplanar distance and build a supercell if needed (≥12 Å threshold to prevent periodic self-interaction of CO2).

- See: [`chem-sorption-relax`](../skills/chem-sorption-relax/SKILL.md)

```bash
# Env: fairchem-agent
python .agents/skills/chem-sorption-relax/scripts/relax_structure.py \
    --structure path/to/framework.cif \
    --calculator fairchem \
    --model-name uma-s-1p2 \
    --task-name omol \
    --min-interplanar-distance 12.0 \
    --device cuda \
    --output-dir research/<date>_MOF_CO2_DAC_screening/supercells/
```

> **Note:** Do NOT relax the host geometry before Widom insertion for large databases — this is expensive and unnecessary for relative ranking. Use the as-deposited (or energy-minimized with a fast force field) geometry for screening.

### Step 3. Widom Insertion for Henry Coefficient and Heat of Adsorption

Run Widom insertion on every prepared supercell to estimate the Henry coefficient $K_H$ (mol/kg/Pa) and isosteric heat of adsorption $Q_{st}$ (kJ/mol) at infinite dilution.

- See: [`chem-sorption-widom`](../skills/chem-sorption-widom/SKILL.md)

```bash
# Env: fairchem-agent
python .agents/skills/chem-sorption-widom/scripts/run_widom.py \
    --structure path/to/supercell.cif \
    --name FRAMEWORK_NAME \
    --calculator fairchem \
    --model-name uma-s-1p2 \
    --task-name omol \
    --gas CO2 \
    --temperature 298 \
    --num-insertions 5000 \
    --device cuda \
    --output-dir research/<date>_MOF_CO2_DAC_screening/widom/FRAMEWORK_NAME/
```

**Key Widom parameters:**
| Parameter | Value | Rationale |
|---|---|---|
| `--num-insertions` | 5 000 (screening) / 20 000 (validation) | Balance speed vs. statistical noise |
| `--temperature` | 298 K | Standard DAC operating temperature |
| `--gas` | CO2 | Primary target sorbate |
| `--task-name` | `omol` | Correct UMA head for gas–framework non-covalent interactions |
| `--cutoff-distance` | 1.0 Å | Reject insertions clashing with framework atoms |

**Henry coefficient computation:** Uses logsumexp (numerically stable) + 100-sample bootstrap for $K_H$ uncertainty. This avoids overflow at large negative energies (important at cryogenic or high-binding conditions).

### Step 4. Rank and Filter Candidates

Collect all `widom_results.json` files and rank by $K_H$ and $Q_{st}$.

```python
import json, pathlib
import pandas as pd

rows = []
for f in pathlib.Path("research/.../widom").rglob("widom_results.json"):
    d = json.load(f.open())
    rows.append({
        "name": d["cof_name"],
        "K_H_mol_kg_Pa": d["henry_mol_kg_Pa"],
        "Qst_kJ_mol": d["heat_of_adsorption_kJ_mol"],
    })
df = pd.DataFrame(rows).sort_values("K_H_mol_kg_Pa", ascending=False)
df.to_csv("widom_ranking.csv", index=False)
```

**Decision thresholds for DAC physisorbents:**
- $K_H > 10^{-7}$ mol/kg/Pa → reasonable CO2 affinity at dilute partial pressure
- $Q_{st}$ in 15–60 kJ/mol → not too weak (poor uptake), not too strong (hard regeneration)
- Select the top-N candidates (e.g., N = 5–10) for Stage 2

**Visualization:** Plot $K_H$ vs. $Q_{st}$ scatter for all candidates, highlighting the top-N.

---

## Stage 2: Deep-Dive GCMC Isotherm for Top Candidates

### Step 5. Full Pressure Isotherm via GCMC

For each top candidate, run Grand Canonical Monte Carlo across a pressure grid spanning DAC-relevant conditions to obtain the full adsorption isotherm.

- See: [`chem-sorption-gcmc`](../skills/chem-sorption-gcmc/SKILL.md)

Run pressures **sequentially** (not in parallel) to prevent GPU OOM:

```bash
#!/bin/bash
# Env: fairchem-agent
PRESSURES=(0.01 0.05 0.1 0.2 0.5 1.0)
CIF_PATH="research/.../supercells/FRAMEWORK_supercell.cif"
BASE_OUT="research/.../gcmc/FRAMEWORK_isotherm"

for p in "${PRESSURES[@]}"; do
    conda run --no-capture-output -n fairchem-agent \
        python .agents/skills/chem-sorption-gcmc/scripts/run_gcmc.py \
            --cif "$CIF_PATH" \
            --output-dir "${BASE_OUT}/${p}_bar" \
            --calculator fairchem \
            --model-name uma-s-1p2 \
            --task-name omol \
            --steps 50000 \
            --temperature-K 298 \
            --pressure-bar "$p" \
            --device cuda \
            --keep-intermediates
done
```

**Key GCMC parameters:**
| Parameter | Value | Rationale |
|---|---|---|
| `--steps` | 50 000 (screening) / 200 000 (publication) | More steps for statistically reliable low-P points |
| `--task-name` | `omol` | Must match Widom — the same UMA head for host–guest interactions |
| `--keep-intermediates` | `true` | Preserves `.npy` trajectories for post-hoc re-analysis |
| Sequential execution | One pressure at a time | Avoids GPU OOM from multiple calculator instances |

> **Critical:** Always use `--task-name omol` with `uma-s-1p2` for sorption calculations. The `odac` task head was trained exclusively on dense MOF and adsorbate complexes and lacks training on isolated gas-phase molecules. When asked to evaluate the isolated gas reference energy required by GCMC math, `odac` yields wildly unphysical repulsions, resulting in a strict 0% Monte Carlo insertion acceptance rate. The `omol` (OpenMolecules) dataset explicitly contains isolated gases, ensuring accurate absolute gas baseline energies.

### Step 6. Parse and Plot the Isotherm

Collect `gcmc_results.json` files across pressure points and plot loading (mmol/g) vs. pressure (bar):

```python
import json, pathlib
import numpy as np
import matplotlib.pyplot as plt

base = pathlib.Path("research/.../gcmc/FRAMEWORK_isotherm")
pressures, loadings = [], []
for p_dir in sorted(base.iterdir(), key=lambda d: float(d.name.replace("_bar", ""))):
    result = json.load((p_dir / "gcmc_results.json").open())
    pressures.append(result["pressure_bar"])
    loadings.append(result["q_total"])  # mmol/g

fig, ax = plt.subplots(figsize=(5, 4))
ax.plot(pressures, loadings, "o-", lw=2)
ax.set_xlabel("Pressure (bar)")
ax.set_ylabel("CO₂ Loading (mmol/g)")
ax.set_xscale("log")
ax.set_title("CO₂ Isotherm — FRAMEWORK")
fig.savefig("isotherm.png", dpi=150, bbox_inches="tight")
```

**Units note:** The GCMC skill reports in **mmol/g** (numerically equal to mol/kg). No unit conversion factor should be applied post-hoc.

### Step 7. Compute Working Capacity and Selectivity

For DAC evaluation, the relevant metric is the **working capacity**: loading at absorption pressure (e.g., 1 bar) minus loading at desorption pressure (e.g., 0.01 bar):

```
ΔN = N(1.0 bar) - N(0.01 bar)   [mmol/g]
```

For multi-component selectivity (CO2/N2), use `run_gcmc_multi.py` with a realistic DAC gas composition (0.04% CO2 / 99.96% N2 or 15% CO2 / 85% N2 for post-combustion):

```bash
# Env: fairchem-agent
python .agents/skills/chem-sorption-gcmc/scripts/run_gcmc_multi.py \
    --cif path/to/supercell.cif \
    --output-dir research/.../gcmc/FRAMEWORK_mixture \
    --calculator fairchem \
    --model-name uma-s-1p2 \
    --task-name omol \
    --steps 100000 \
    --temperature-K 298 \
    --total-pressure-bar 1.0 \
    --mole-fractions CO2=0.04 N2=0.96 \
    --device cuda
```

---

## MLIP Selection Guide

| Condition | Recommended Model | Task Name |
|---|---|---|
| General MOF screening (physisorption) | `uma-s-1p2` (FairChem) | `omol` |
| Chemisorption / reactive systems | `MACE-MH-1` | `matpes_r2scan` |
| Speed-critical large supercells | `uma-s-1` (smaller) | `omol` |

> **Note:** Always use the same MLIP and the same `task-name` for both Widom and GCMC to ensure internal consistency between the infinite-dilution and finite-pressure results.

---

## Summary Checklist

```
Stage 1 — High-Throughput Screening
[ ] 1. Query MOF database (`chem-db-mof`)
[ ] 2. Filter by geometric criteria (PLD, void fraction)
[ ] 3. Build supercells with min interplanar distance ≥ 12 Å (`chem-sorption-relax`)
[ ] 4. Run Widom insertion for K_H and Q_st on all candidates (`chem-sorption-widom`)
[ ] 5. Rank by K_H; filter top-N by Q_st threshold

Stage 2 — Isotherm Validation
[ ] 6. Run sequential GCMC pressure isotherm for top-N (`chem-sorption-gcmc`)
[ ] 7. Compute working capacity ΔN and selectivity
[ ] 8. Plot isotherm; compare K_H from Widom vs. GCMC low-P limit for consistency
```

---

## Known Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Wrong `--task-name` for UMA | Zero GCMC insertions; all-zero nmols.npy | Use `--task-name omol` for `uma-s-1p2` |
| Parallel GCMC pressures | CUDA OOM crash | Run pressures **sequentially** in a loop |
| Too few GCMC steps at low P | NaN or 0 loading at 0.01 bar | Increase `--steps` to 200k for P < 0.05 bar |
| GCMC stochastic variance | Two identical runs give different loadings | Run ≥ 3 random seeds; report mean ± std |

---

## References

- Majumdar, S. et al., "A Database of Porous Rigid Metal-Organic Frameworks", *AIP Advances*, 2021. 
- Widom, B., "Some Topics in the Theory of Fluids", *J. Chem. Phys.*, 1963. [DOI](https://doi.org/10.1063/1.1734110)
- Perdew, J. P. et al., "PBE + Dispersion for MOF Screening", *J. Phys. Chem. Lett.*, 2022.
- Tong, L. et al., "FAIRChem Universal Models (UMA)", *arXiv*, 2025.
