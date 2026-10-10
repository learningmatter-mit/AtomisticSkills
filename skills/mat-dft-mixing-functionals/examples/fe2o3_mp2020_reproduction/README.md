# Reproducing Materials Project MP2020 Corrections (Fe2O3, Al2O3, FeS2)

## Goal

Validate `apply_correction.py` against the Materials Project (MP) database. MP stores both the raw
(uncorrected) DFT total energy of each calculation and the energy after the MP2020 compatibility scheme.
Starting from MP's raw energy, the skill should give MP's corrected energy and the same per-species
adjustments. Three compounds cover the three branches of the scheme:

| Compound | MP ID | MP run type | What it tests |
| :--- | :--- | :--- | :--- |
| Fe2O3 (hematite) | mp-19770 | GGA+U (U<sub>Fe</sub> = 5.3 eV) | oxide anion correction **and** the Fe GGA/GGA+U mixing correction |
| Al2O3 (corundum) | mp-1143 | GGA | oxide anion correction only (Al has no U) |
| FeS2 (pyrite) | mp-226 | GGA | sulfide anion correction only; Fe gets no U correction in a sulfide |

The example also checks the correction constants against the published values (Wang et al., 2021, Table 1)
and pymatgen's `MP2020Compatibility.yaml`. It also runs `check_compatibility.py` on models that need
the correction and on models that don't.

## Inputs

| File | Sites | MP uncorrected total energy (eV) | MP corrected total energy (eV) |
| :--- | :---: | ---: | ---: |
| [Fe2O3_mp-19770.cif](Fe2O3_mp-19770.cif) | 10 (Fe4O6) | -67.4927644 | -80.6387644 |
| [Al2O3_mp-1143.cif](Al2O3_mp-1143.cif) | 10 (Al4O6) | -74.81357943 | -78.93557943 |
| [FeS2_mp-226.cif](FeS2_mp-226.cif) | 12 (Fe4S8) | -73.03390479 | -77.05790479 |

The structures, energies and MP's own correction breakdown are stored in
[`mp_reference_entries.json`](mp_reference_entries.json). They came from the MP API `materials/thermo`
endpoint with `thermo_types=["GGA_GGA+U"]` (MP database version 2026.04.13, retrieved 2026-10-10).
Each structure is the `ComputedStructureEntry.structure` of the entry, so it matches the energy:

```python
from mp_api.client import MPRester

with MPRester() as mpr:  # reads MP_API_KEY from the environment
    doc = mpr.materials.thermo.search(
        material_ids=["mp-19770"], thermo_types=["GGA_GGA+U"], fields=["entries"]
    )[0]
entry = next(iter(doc.entries.values()))  # pymatgen ComputedStructureEntry
print(entry.uncorrected_energy, entry.energy)  # -67.4927644 -80.6387644
for adj in entry.energy_adjustments:
    print(adj.name, adj.value, adj.uncertainty)
entry.structure.to(filename="Fe2O3_mp-19770.cif")
```

> [!IMPORTANT]
> Request `thermo_types=["GGA_GGA+U"]`. The default MP summary and thermo values use the
> GGA/GGA+U/r2SCAN mixing scheme (Kingsbury et al., 2022). For many materials that scheme reports an
> r2SCAN energy. For Fe2O3 the default `uncorrected_energy_per_atom` is -10.894 eV/atom (r2SCAN), while
> the GGA+U value is -6.749 eV/atom. MP2020 corrections only apply to the GGA/GGA+U energy.

## Commands

All commands run from the repository root.

### 1. Apply the MP2020 correction to MP's raw energies

```bash
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/apply_correction.py \
    skills/mat-dft-mixing-functionals/examples/fe2o3_mp2020_reproduction/Fe2O3_mp-19770.cif --energy -67.4927644
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/apply_correction.py \
    skills/mat-dft-mixing-functionals/examples/fe2o3_mp2020_reproduction/Al2O3_mp-1143.cif --energy -74.81357943
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/apply_correction.py \
    skills/mat-dft-mixing-functionals/examples/fe2o3_mp2020_reproduction/FeS2_mp-226.cif --energy -73.03390479
```

The full output is in [`apply_correction_output.txt`](apply_correction_output.txt).

### 2. Check which models need the correction

```bash
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/check_compatibility.py --name MACE-MP-medium
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/check_compatibility.py --name MACE-MH-1 --head omat_pbe
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/check_compatibility.py --name CHGNet-MPtrj-2023.12.1-2.7M-PES
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/check_compatibility.py --name MACE-MATPES-R2SCAN-0
```

The full output is in [`check_compatibility_output.txt`](check_compatibility_output.txt).

## Results

### Corrected energies: skill vs Materials Project

| Compound | Uncorrected (eV) | MP corrected (eV) | Skill corrected (eV) | Difference (meV) | MP adjustments (eV) | Skill adjustments (eV) |
| :--- | ---: | ---: | ---: | ---: | :--- | :--- |
| Fe2O3 | -67.4928 | -80.6388 | -80.6388 | 0.0 | oxide -4.122; Fe mixing -9.024 | oxide -4.122; Fe mixing -9.024 |
| Al2O3 | -74.8136 | -78.9356 | -78.9356 | 0.0 | oxide -4.122 | oxide -4.122 |
| FeS2 | -73.0339 | -77.0579 | -77.0579 | 0.0 | S -4.024 | S -4.024 |

The skill reproduces MP's corrected total energies and every per-species adjustment exactly. Per atom,
the Fe2O3 result is -80.6388 / 10 = -8.06388 eV/atom, which equals MP's GGA_GGA+U `energy_per_atom`
(-8.06387644 eV/atom).

The script builds the GGA+U parameters itself (`hubbards = {"Fe": 5.3}` from the MP2020 `u_settings`).
These match the parameters stored on MP's entry (`{"Fe": 5.3, "O": 0.0}`). For FeS2 it sets no U
because MP2020 applies U, and therefore the mixing correction, only in oxides and fluorides. MP's own
FeS2 entry is likewise a plain GGA calculation with only the sulfide correction.

### Correction constants vs literature

Each adjustment divided by the number of atoms of that species in the cell gives the per-atom constant.
The MP uncertainty divided the same way gives the per-atom uncertainty.

| Species (compound) | Atoms in cell | Adjustment (eV) | Per atom (eV/atom) | Wang et al. 2021, Table 1 (eV/atom) | `MP2020Compatibility.yaml` (eV/atom) | Uncertainty per atom: MP / Table 1 (eV/atom) |
| :--- | :---: | ---: | ---: | ---: | ---: | :---: |
| oxide (Fe2O3, Al2O3) | 6 O | -4.122 | -0.687 | -0.687 | -0.687 | 0.0020 / 0.0020 |
| Fe, GGA+U oxide (Fe2O3) | 4 Fe | -9.024 | -2.256 | -2.256 | -2.256 | 0.0101 / 0.0101 |
| S (FeS2) | 8 S | -4.024 | -0.503 | -0.503 | -0.503 | 0.0093 / 0.0093 |

All three constants and their uncertainties agree with Table 1 of Wang et al. (2021), read from the
published article for this example. pymatgen 2026.9.24 is the version installed in the `cpu`
environment. Its `MP2020Compatibility.yaml` (`pymatgen/analysis/compatibility/`) is byte-identical to
the current upstream file on GitHub. MP computed its adjustments with pymatgen 2026.5.18
(`builder_meta` in `mp_reference_entries.json`), and they are identical to the ones the skill
computes with 2026.9.24.

### Which models need the correction

| Model | Head | Training data | Requires MP2020? | Exit code |
| :--- | :--- | :--- | :---: | :---: |
| MACE-MP-medium | — | MPtrj (GGA/GGA+U) | True | 0 |
| MACE-MH-1 | `omat_pbe` | OMat-PBE head | True | 0 |
| CHGNet-MPtrj-2023.12.1-2.7M-PES | — | MPtrj with the MP2020 mixing correction already applied | False | 1 |
| MACE-MATPES-R2SCAN-0 | — | MatPES r2SCAN | False | 1 |

CHGNet and MACE-MP are both trained on MPtrj, but they need different treatment. The CHGNet paper
states that the GGA/GGA+U mixing compatibility correction of Wang et al. was applied to the MPtrj
energies (Deng et al., 2023), so CHGNet predictions already include the correction. Correcting them
again would count it twice. MACE-MP-medium predicts uncorrected energies, as measured in the companion
example
[mat-elemental-energies/examples/li_fe_cu_o_si_vs_mp](../../../mat-elemental-energies/examples/li_fe_cu_o_si_vs_mp/README.md).
There, its raw Li2O energy is 9.5 meV/atom from MP's uncorrected value and 238 meV/atom from the
corrected one. Applying this script, with an O2 reference from a single point on MP's O2 structure,
brings its Li2O formation energy to within 0.2 meV/atom of MP's.

## References

- A. Wang, R. Kingsbury, M. McDermott, M. Horton, A. Jain, S. P. Ong, S. Dwaraknath, K. A. Persson,
  "A framework for quantifying uncertainty in DFT energy corrections", *Sci. Rep.* **11**, 15496 (2021).
  [DOI: 10.1038/s41598-021-94550-5](https://doi.org/10.1038/s41598-021-94550-5)
- pymatgen `MP2020Compatibility.yaml`:
  [github.com/materialsproject/pymatgen/.../MP2020Compatibility.yaml](https://github.com/materialsproject/pymatgen/blob/main/src/pymatgen/analysis/compatibility/MP2020Compatibility.yaml)
- R. S. Kingsbury, A. S. Rosen, A. S. Gupta, J. M. Munro, S. P. Ong, A. Jain, S. Dwaraknath, M. K. Horton,
  K. A. Persson, "A flexible and scalable scheme for mixing computed formation energies from different
  levels of theory", *npj Comput. Mater.* **8**, 195 (2022).
  [DOI: 10.1038/s41524-022-00881-w](https://doi.org/10.1038/s41524-022-00881-w)
- B. Deng, P. Zhong, K. Jun, J. Riebesell, K. Han, C. J. Bartel, G. Ceder, "CHGNet as a pretrained universal
  neural network potential for charge-informed atomistic modelling", *Nat. Mach. Intell.* **5**, 1031–1041
  (2023). [DOI: 10.1038/s42256-023-00716-3](https://doi.org/10.1038/s42256-023-00716-3)
- A. Jain et al., "Commentary: The Materials Project: A materials genome approach to accelerating materials
  innovation", *APL Mater.* **1**, 011002 (2013). [DOI: 10.1063/1.4812323](https://doi.org/10.1063/1.4812323)

## 3D Structures

- [Fe2O3_mp-19770.cif](Fe2O3_mp-19770.cif)
- [Al2O3_mp-1143.cif](Al2O3_mp-1143.cif)
- [FeS2_mp-226.cif](FeS2_mp-226.cif)
