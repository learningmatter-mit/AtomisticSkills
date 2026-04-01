# MgO Charged O Vacancy (F-center) Example

Charged defect formation energy diagram for the oxygen vacancy (F-center) in MgO,
with actual PBE DFT results from atomate2 local execution.

## System
- **Material**: MgO (rocksalt, mp-1265)
- **Defect**: Oxygen vacancy (V_O), also known as the F-center
- **Charge states**: 0 (F⁰), +1 (F⁺), +2 (F²⁺)
- **Supercell**: 3×3×3 (54 atoms pristine, 53 atoms with vacancy)
- **DFT method**: PBE static (MatPES preset via atomate2)

## Run

```bash
# Step 1: Get structure
mcp_base_search_materials_project_by_formula(formula="MgO")

# Step 2: Generate charged vacancy structures
# Env: base-agent
python .agents/skills/mat-defect-energy-dft/scripts/generate_defect_structures.py \
    --bulk MgO.cif \
    --supercell_size 3 3 3 \
    --defect_type vacancy \
    --charge_range -2 2 \
    --output dft_defects/

# Step 3: Run DFT (pristine + each charge state separately for NELECT control)
# For charged states, pass NELECT via config:
#   q=0:  no NELECT needed (neutral)
#   q=+1: config={"NELECT": 371}  (neutral=372, remove 1 electron)
#   q=+2: config={"NELECT": 370}  (neutral=372, remove 2 electrons)
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="dft_defects/pristine_supercell.cif",
    output_dir="./dft_pristine/",
    calculation_type="static",
    preset_type="matpes-pbe",
    execution_mode="local",
    config={"LREAL": "Auto", "NCORE": 4}
)

mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="dft_defects/vac_O_1_q0.cif",
    output_dir="./dft_vac_q0/",
    calculation_type="static",
    preset_type="matpes-pbe",
    execution_mode="local",
    config={"LREAL": "Auto", "NCORE": 4}
)

mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="dft_defects/vac_O_1_q+1.cif",
    output_dir="./dft_vac_q+1/",
    calculation_type="static",
    preset_type="matpes-pbe",
    execution_mode="local",
    config={"LREAL": "Auto", "NCORE": 4, "NELECT": 371}
)

mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="dft_defects/vac_O_1_q+2.cif",
    output_dir="./dft_vac_q+2/",
    calculation_type="static",
    preset_type="matpes-pbe",
    execution_mode="local",
    config={"LREAL": "Auto", "NCORE": 4, "NELECT": 370}
)

# Step 4: Parse results and build formation energy diagram
# See build_diagram.py for the analysis script
```

## Results (PBE, MatPES preset, no finite-size corrections)

### Raw DFT Energies

| Calculation | Energy (eV) | Atoms | Converged |
|---|:---:|:---:|:---:|
| Pristine (Mg₂₇O₂₇) | -320.668 | 54 | ✅ |
| V_O q=0 (F⁰)        | -309.061 | 53 | ✅ |
| V_O q=+1 (F⁺)       | -313.712 | 53 | ✅ |
| V_O q=+2 (F²⁺)      | -316.803 | 53 | ✅ |

### Formation Energies (O-rich, at E_F = 0)

| Charge State | E_f (eV) |
|:---:|:---:|
| V_O⁰  | 6.66 |
| V_O⁺¹ | 2.01 |
| V_O⁺² | -1.08 |

### Charge Transition Levels

Transition levels are **Fermi level positions** (above VBM) where two charge states
have equal formation energy. They indicate which charge state is most stable:

| Transition | Energy above VBM (eV) | Meaning |
|:---:|:---:|---|
| ε(+2/+1) | 3.09 | Below: V_O⁺² preferred; Above: V_O⁺¹ preferred |
| ε(+1/0)  | 4.65 | Below: V_O⁺¹ preferred; Above: V_O⁰ (F⁰) preferred |
| ε(+2/0)  | 3.87 | Thermodynamic transition (if +1 is metastable) |

### Comparison with Literature

| Property | This work (PBE) | HSE06 (literature) | Experiment |
|---|:---:|:---:|:---:|
| Band gap | 4.7 eV | 6.1–6.5 eV | 7.7 eV |
| V_O⁰ E_f (O-rich) | 6.66 eV | 7.05 eV | 9.29 eV |
| V_O⁺² E_f at VBM | -1.08 eV | 2.75 eV | — |
| ε(+2/+1) | 3.09 eV | ~1.6 eV | — |
| ε(+1/0) | 4.65 eV | ~3.4 eV | — |
| MACE-MH-1 V_O⁰ | 7.13 eV | — | — |

**Key observations:**
- PBE underestimates formation energies vs HSE06/experiment due to self-interaction error
- Transition levels are shifted upward in PBE due to band gap underestimation (4.7 vs 7.7 eV)
- MACE-MH-1 neutral vacancy (7.13 eV) is closer to HSE06 (7.05 eV) than our PBE result (6.66 eV)
- Freysoldt finite-size corrections (not applied here) would further modify charged state energies

## Output Files

- `formation_energy_diagram_PBE.png` — Formation energy vs Fermi energy (O-rich & O-poor)
- `full_results.json` — Complete results with formation energies, transition levels, and chemical potentials
- `dft_energies.json` — Raw DFT energies from each calculation
- `build_diagram.py` — Script to regenerate the diagram from parsed energies
- `charged_formation_energy_diagram.png` — HSE06 reference diagram (from literature)
- `charged_formation_energies.json` — HSE06 reference formation energies
- `defect_index.json` — Defect structure index from generation step

## References

1. P. Rinke, A. Schleife, E. Kioupakis, A. Janotti, C. Rödl, F. Bechstedt, M. Scheffler, C. G. Van de Walle, "First-Principles Optical Spectra for F Centers in MgO," *Phys. Rev. Lett.* **108**, 126404 (2012). [DOI: 10.1103/PhysRevLett.108.126404](https://doi.org/10.1103/PhysRevLett.108.126404)
2. W. Chen, A. Pasquarello, "Accuracy of GW for calculating defect energy levels in solids," *Phys. Rev. B* **96**, 020101(R) (2017). [DOI: 10.1103/PhysRevB.96.020101](https://doi.org/10.1103/PhysRevB.96.020101)
3. C. Freysoldt, B. Grabowski, T. Hickel, J. Neugebauer, G. Kresse, A. Janotti, C. G. Van de Walle, "First-principles calculations for point defects in solids," *Rev. Mod. Phys.* **86**, 253 (2014). [DOI: 10.1103/RevModPhys.86.253](https://doi.org/10.1103/RevModPhys.86.253)
