---
name: mat-defect-energy-dft
description: Calculate charged defect formation energies and transition level diagrams using pymatgen-analysis-defects and atomate2 VASP workflows.
category: [materials]
---

# Point-Defect Formation Energy (DFT)

## Goal
To calculate the formation energy of point defects (vacancies, substitutions, interstitials) including **charged defect states** and **finite-size corrections** using DFT (VASP) via atomate2 workflows. This produces formation energy diagrams showing defect charge transition levels as a function of Fermi energy.

$$E_f[D^q] = E[D^q] - E[\text{bulk}] + \sum_i \Delta n_i \mu_i + q(E_\text{VBM} + \Delta E_F) + E_\text{corr}$$

where $q$ is the charge state, $E_\text{VBM}$ is the valence band maximum, $\Delta E_F$ is the Fermi energy relative to VBM, and $E_\text{corr}$ is the finite-size correction (Freysoldt/FNV).

## Instructions

### 1. Obtain Bulk Structure
Start with a relaxed primitive cell:
```bash
mcp_base_search_materials_project_by_formula(formula="MgO", save_to_file="MgO.cif")
```

### 2. Generate Defect Structures
Use `pymatgen-analysis-defects` to generate all symmetry-unique defect supercells with charge states:
```bash
# Env: base-agent
python .agents/skills/mat-defect-energy-dft/scripts/generate_defect_structures.py \
    --bulk MgO.cif \
    --supercell_size 3 3 3 \
    --defect_type vacancy \
    --charge_range -2 2 \
    --output dft_defects/
```

This generates:
- POSCAR files for each defect × charge state
- A `defect_index.json` mapping defect names to charge states and structures
- Pristine supercell for the bulk reference

### 3. Run DFT Calculations (atomate2)
Submit calculations via the atomate2 MCP tool:
```python
# Bulk supercell reference
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="dft_defects/pristine_supercell.cif",
    output_dir="./dft_bulk/",
    calculation_type="static",
    preset_type="matpes-pbe",
    execution_mode="remote"
)

# All defect structures
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="dft_defects/",
    output_dir="./dft_defect_calcs/",
    calculation_type="relaxation",
    preset_type="matpes-pbe",
    execution_mode="remote"
)
```

### Alternative: atomate2 `FormationEnergyMaker`
For fully automated defect workflows with built-in corrections:
```python
# Env: atomate2-agent (Python API)
from atomate2.vasp.flows.defect import FormationEnergyMaker
from pymatgen.analysis.defects.generators import VacancyGenerator
from pymatgen.core import Structure

bulk = Structure.from_file("MgO.cif")
vac_gen = VacancyGenerator()
defects = vac_gen.generate(bulk)

maker = FormationEnergyMaker()
# Submit via jobflow-remote for each defect
```

### 4. Parse Results and Compute Formation Energies
After DFT calculations complete:
```bash
# Env: base-agent
python .agents/skills/mat-defect-energy-dft/scripts/parse_defect_results.py \
    --bulk_dir dft_bulk/ \
    --defect_dir dft_defect_calcs/ \
    --defect_index dft_defects/defect_index.json \
    --dielectric 9.8 \
    --output formation_energies.json \
    --plot formation_energy_diagram.png
```

The script:
- Parses VASP outputs for total energies
- Applies Freysoldt (FNV) finite-size corrections for charged defects
- Determines VBM and band gap from bulk calculation
- Constructs the formation energy diagram

### 5. Interpret Results
The formation energy diagram shows:
- **Slopes**: Each line segment has slope = charge state $q$
- **Transition levels**: Intersections where the stable charge state changes ($\epsilon(q/q')$)
- **Low formation energy → high concentration**: Defects with low $E_f$ at the Fermi level are most abundant

## Examples

### Oxygen Vacancy in MgO
```bash
# 1. Get MgO
mcp_base_search_materials_project_by_formula(formula="MgO")

# 2. Generate defects with charges -2 to +2
python .agents/skills/mat-defect-energy-dft/scripts/generate_defect_structures.py \
    --bulk MgO.cif --supercell_size 3 3 3 --defect_type vacancy --charge_range -2 2 --output mgo_defects/

# 3. Run DFT (remote)
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="mgo_defects/", output_dir="./mgo_dft/",
    calculation_type="relaxation", preset_type="matpes-pbe", execution_mode="remote"
)

# 4. Parse and plot (after DFT completes)
python .agents/skills/mat-defect-energy-dft/scripts/parse_defect_results.py \
    --bulk_dir mgo_dft/pristine_supercell/ --defect_dir mgo_dft/ \
    --defect_index mgo_defects/defect_index.json --dielectric 9.8 --output mgo_fe.json
```

## Constraints
- **VASP required**: Actual DFT calculations require a valid VASP setup (`PMG_VASP_PSP_DIR`, atomate2/jobflow-remote configured).
- **Supercell size**: Use at least 3×3×3 for cubic systems. Charged defect corrections are less reliable for small cells.
- **Dielectric constant**: The Freysoldt correction requires the static dielectric constant of the host material. Use experimental or computed values.
- **Functional**: PBE underestimates band gaps → transition levels may be shifted. For accurate results, use HSE06 hybrid functional (requires custom INCAR settings).
- **Environments**:
  - Structure generation: `base-agent` (pymatgen-analysis-defects)
  - DFT submission: `atomate2-agent` (via MCP tool)
  - Post-processing: `base-agent`
- **For neutral defects only (no DFT)**: See [mat-defect-energy](../mat-defect-energy/SKILL.md) for MLIP-based approach.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
