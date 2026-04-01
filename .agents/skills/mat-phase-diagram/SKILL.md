---
name: mat-phase-diagram
description: Retrieve and visualize pre-computed phase diagrams from Materials Project for thermodynamic stability analysis.
category: [thermodynamics]
---

# Phase Diagram Retrieval

## Goal

Retrieve pre-computed phase diagrams from Materials Project to analyze thermodynamic stability, competing phases, and convex hull relationships. Phase diagrams are essential for understanding:
- Which compounds are stable at 0 K
- Energy above hull (formation energy distance to the convex hull)
- Competing phases that may form during synthesis
- Thermodynamic driving forces for phase transformations

## Instructions

### 1. Basic Phase Diagram Retrieval

Retrieve a phase diagram for a chemical system:

```bash
# Env: base-agent
python .agents/skills/mat-phase-diagram/scripts/get_phase_diagram.py \
  --chemsys "Li-O" \
  --output li_o_phase_diagram.json
```

**Output**: JSON file containing the phase diagram data (entries, energies, hull)

### 2. Generate Phase Diagram Plot

Add `--plot` flag to create a visualization:

```bash
# Env: base-agent
python .agents/skills/mat-phase-diagram/scripts/get_phase_diagram.py \
  --chemsys "Li-O" \
  --output li_o_pd.json \
  --plot li_o_pd.png
```

**Output**: PNG plot showing the convex hull and stable/unstable phases

### 3. Use Different DFT Functional

By default, retrieves GGA+U phase diagrams. For R2SCAN data:

```bash
# Env: base-agent
python .agents/skills/mat-phase-diagram/scripts/get_phase_diagram.py \
  --chemsys "Li-Fe-P-O" \
  --thermo_type "R2SCAN" \
  --output lifepo4_r2scan_pd.json \
  --plot lifepo4_r2scan_pd.png
```

**Thermo types**:
- `GGA_GGA+U` (default): Standard PBE with U corrections
- `R2SCAN`: Meta-GGA functional (more accurate)
- `GGA`: Pure PBE without U corrections

## Integration with Other Skills

### With `material-stability` Skill

Use phase diagrams to visualize competing phases:

```bash
# 1. Get phase diagram
python .agents/skills/mat-phase-diagram/scripts/get_phase_diagram.py \
  --chemsys "Li-O" \
  --output li_o_pd.json \
  --plot li_o_pd.png

# 2. Check specific material's position on hull
python .agents/skills/mat-db-mp/scripts/query_mp.py \
  --formula "Li2O" \
  --properties energy_above_hull formation_energy_per_atom \
  --output li2o_stability.json
```

### With MatterGen Fine-Tuning

Query stable structures from a chemical system for training data:

```bash
# 1. Visualize phase diagram to understand stable phases
python .agents/skills/mat-phase-diagram/scripts/get_phase_diagram.py \
  --chemsys "Li-S" \
  --output li_s_pd.json \
  --plot li_s_pd.png

# 2. Query all stable structures
python .agents/skills/mat-db-mp/scripts/query_mp.py \
  --chemsys "Li-S" \
  --e_above_hull_max 0.0 \
  --properties energy_above_hull formation_energy_per_atom \
  --output li_s_stable.json
```

## Constraints

- **API Key Required**: Set `MP_API_KEY` environment variable
- **Pre-Computed Only**: Returns Materials Project's pre-computed phase diagrams. Cannot compute custom phase diagrams with user-provided energies.
- **Chemical System Format**: Use hyphen-separated elements (e.g., "Li-O", not "LiO" or "Li O")
- **Availability**: Not all chemical systems have pre-computed phase diagrams. Common systems (binary oxides, battery materials) are well-covered.
- **Thermo Type Availability**: R2SCAN phase diagrams are available for a subset of systems
- **Environment**: Requires `base-agent` conda environment
- **Dependencies**: `mp-api`, `pymatgen`, `matplotlib` (all installed in base-agent)

## When to Use This vs. Calculate

**Use MP Phase Diagrams (this skill) when**:
- You need quick exploratory analysis
- You want DFT-quality phase diagrams without running calculations
- You're analyzing common chemical systems
- You need GGA+U or R2SCAN accuracy

**Calculate Custom Phase Diagrams when**:
- You have MLIP-relaxed structures not in MP
- You need to compare MLIP formation energies
- Your chemical system is not in MP
- You want to use specific MLIP models or DFT settings

For custom phase diagram construction, see `material-stability` skill which can build phase diagrams from user-provided energies.

## Examples

See `examples/` directory for:
- Li-O binary phase diagram retrieval and visualization
- Li-Fe-P-O quaternary phase diagram (LiFePO4 system)
- Integration with stability analysis workflow

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
