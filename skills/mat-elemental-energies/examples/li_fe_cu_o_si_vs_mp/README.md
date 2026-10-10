# Elemental Reference Energies vs Materials Project (Li, Fe, Cu, O, Si)

## Goal

Retrieve elemental reference energies (eV/atom) for Li, Fe, Cu, O and Si from four library checkpoints:

- **GGA/GGA+U (MPtrj-trained):** `MACE-MP-medium`, `CHGNet-MPtrj-2023.12.1-2.7M-PES`
- **r2SCAN (MatPES-trained):** `TensorNet-MatPES-r2SCAN-v2025.1-PES`, `MACE-MATPES-R2SCAN-0`

The example then:

1. compares them with Materials Project (MP) DFT energies of the same ground-state materials, GGA for
   the MPtrj models and r2SCAN for the MatPES models;
2. recomputes the library values on CPU to check that they are reproducible;
3. uses the references to compute Li2O and Fe2O3 formation energies and compares them with MP.

An MLIP's absolute energy matches DFT only up to its training error, so the deviations are read against
the published energy MAEs of each model family.

## Inputs

**Library structures** are the CIFs in [`../../resources/structures/`](../../resources/structures/).
They carry no MP ID, so each was matched to MP's E<sub>hull</sub> = 0 entries with pymatgen's
`StructureMatcher`:

| Element | Library CIF | MP ID | Space group | Atoms in CIF |
| :--- | :--- | :--- | :--- | :---: |
| Li | `Li.cif` | mp-1018134 | R-3m | 3 |
| Fe | `Fe.cif` | mp-13 | Im-3m (bcc) | 2 |
| Cu | `Cu.cif` | mp-30 | Fm-3m (fcc) | 1 |
| O | `O.cif` | mp-12957 | C2/m (O2 molecular crystal) | 8 |
| Si | `Si.cif` | mp-149 | Fd-3m (diamond) | 2 |

**MP reference energies** are in [`mp_reference_energies.json`](mp_reference_energies.json). They come
from the MP API `materials/thermo` endpoint (database version 2026.04.13, retrieved 2026-10-10):

```python
from mp_api.client import MPRester

with MPRester() as mpr:  # reads MP_API_KEY from the environment
    docs = mpr.materials.thermo.search(
        material_ids=["mp-1018134", "mp-13", "mp-30", "mp-12957", "mp-149",
                      "mp-1524462", "mp-1960", "mp-19770"],
        thermo_types=["GGA_GGA+U", "R2SCAN"],
        fields=["material_id", "thermo_type", "uncorrected_energy_per_atom",
                "energy_per_atom", "formation_energy_per_atom"],
    )
```

- **GGA:** `uncorrected_energy_per_atom` of thermo type `GGA_GGA+U`. For elements the MP2020 correction
  is zero, so corrected and uncorrected values are identical.
- **r2SCAN:** thermo type `R2SCAN`. mp-12957 has no r2SCAN calculation. The O r2SCAN reference is
  therefore mp-1524462, a different C2/m O2 molecular-crystal polymorph that MP computed only with
  r2SCAN. It is the ground state of MP's r2SCAN hull and ties with mp-12957 at E<sub>hull</sub> = 0 in
  the default mixed hull. Because it is not the library's polymorph, the O r2SCAN comparison carries
  an extra small polymorph uncertainty.
- Do **not** use the default (`GGA_GGA+U_R2SCAN`) summary energies. For Li, Cu and Si that mixed scheme
  reports the r2SCAN energy (for example, Cu -10.847 eV/atom instead of the GGA value -4.099).

## Commands

All commands run from the repository root.

### 1. Retrieve the library energies

```bash
for ck in MACE-MP-medium CHGNet-MPtrj-2023.12.1-2.7M-PES TensorNet-MatPES-r2SCAN-v2025.1-PES MACE-MATPES-R2SCAN-0; do
  venv/run cpu python skills/mat-elemental-energies/scripts/get_elemental_energies.py \
      --elements Li Fe Cu O Si --checkpoint $ck \
      --output skills/mat-elemental-energies/examples/li_fe_cu_o_si_vs_mp/$ck/elemental_energies.json
done
```

Each `<checkpoint>/` folder holds the retrieved `elemental_energies.json` and the run's
`input_configs.yaml`.

### 2. Recompute library values on CPU (verification)

The library entries come from full cell + position relaxations (`relax_cell=True`), except
MACE-MP-medium O, which is a single point on MP's structure (see below). They were recomputed with
the MCP CLI fallback on CPU. The relaxations write trajectories, so the output
directories are in the gitignored scratch area. Only the relaxed CIFs and the energies are kept here,
in [`cpu_verification.json`](cpu_verification.json).

```bash
S=skills/mat-elemental-energies/resources/structures
O=.agents/test/skill_examples
# MACE-MP-medium (GGA); predict_structure = single point on the MP structure
CUDA_VISIBLE_DEVICES="" venv/run mlip python -m src.mcp_server.cli mace load_model model_name=MACE-MP-medium device=cpu \
    predict_structure structure_data=$S/O.cif \
    relax_structure structure_data=$S/Li.cif output_dir=$O/mace_cpu/Li \
    relax_structure structure_data=$S/Fe.cif output_dir=$O/mace_cpu/Fe \
    relax_structure structure_data=$S/Cu.cif output_dir=$O/mace_cpu/Cu \
    relax_structure structure_data=$S/Si.cif output_dir=$O/mace_cpu/Si \
    relax_structure structure_data=$S/O.cif  output_dir=$O/mace_cpu/O
# MACE-MATPES-R2SCAN-0 (r2SCAN)
CUDA_VISIBLE_DEVICES="" venv/run mlip python -m src.mcp_server.cli mace load_model model_name=MACE-MATPES-R2SCAN-0 device=cpu \
    predict_structure structure_data=$S/O.cif \
    relax_structure structure_data=$S/Li.cif output_dir=$O/mace_r2scan_cpu/Li \
    relax_structure structure_data=$S/Fe.cif output_dir=$O/mace_r2scan_cpu/Fe \
    relax_structure structure_data=$S/Cu.cif output_dir=$O/mace_r2scan_cpu/Cu \
    relax_structure structure_data=$S/Si.cif output_dir=$O/mace_r2scan_cpu/Si \
    relax_structure structure_data=$S/O.cif  output_dir=$O/mace_r2scan_cpu/O
# TensorNet-MatPES-r2SCAN-v2025.1-PES (r2SCAN)
CUDA_VISIBLE_DEVICES="" venv/run mlip python -m src.mcp_server.cli matgl load_model model_name=TensorNet-MatPES-r2SCAN-v2025.1-PES device=cpu \
    predict_structure structure_data=$S/Si.cif predict_structure structure_data=$S/O.cif \
    relax_structure structure_data=$S/Li.cif output_dir=$O/tensornet_cpu/Li \
    relax_structure structure_data=$S/Fe.cif output_dir=$O/tensornet_cpu/Fe \
    relax_structure structure_data=$S/Cu.cif output_dir=$O/tensornet_cpu/Cu \
    relax_structure structure_data=$S/Si.cif output_dir=$O/tensornet_cpu/Si \
    relax_structure structure_data=$S/O.cif  output_dir=$O/tensornet_cpu/O
```

The tool defaults are `fmax=0.02`, `steps=500`, `optimizer=FIRE` and `relax_cell=True`. The tool calls
were split over several CLI invocations, but the parameters are the same as above. Each run takes
seconds to a few minutes on CPU. `CHGNet-MPtrj-2023.12.1-2.7M-PES` is not recomputed: the current
matgl 4.x wrapper (`src/utils/mlips/matgl/matgl_wrapper.py`) cannot load it.

### 3. Formation energies of Li2O and Fe2O3 (MACE-MP-medium)

1. Relax the MP structures of Li2O (mp-1960) and Fe2O3 (mp-19770, the GGA+U entry structure) with the
   same `mace relax_structure` call.
2. Apply the MP2020 correction with
   [mat-dft-mixing-functionals](../../../mat-dft-mixing-functionals/SKILL.md). `check_compatibility.py`
   reports that MACE-MP-medium requires it.

```bash
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/apply_correction.py \
    skills/mat-elemental-energies/examples/li_fe_cu_o_si_vs_mp/Li2O_MACE-MP-medium_relaxed.cif --energy -14.235254287719727
# -> correction -0.687 eV (oxide); corrected -14.9223 eV
venv/run cpu python skills/mat-dft-mixing-functionals/scripts/apply_correction.py \
    skills/mat-elemental-energies/examples/li_fe_cu_o_si_vs_mp/Fe2O3_MACE-MP-medium_relaxed.cif --energy -66.2035903930664
# -> correction -13.146 eV (oxide -4.122, Fe GGA/GGA+U mixing -9.024); corrected -79.3496 eV
```

$$\Delta H_f = \frac{E^{\mathrm{MLIP}}_{\mathrm{compound}} + E^{\mathrm{MP2020}}_{\mathrm{corr}} - \sum_i n_i\,\mu_i^{\mathrm{MLIP}}}{\sum_i n_i}$$

Here μ<sub>i</sub> are the library energies from step 1. The results are in
[`formation_energies.csv`](formation_energies.csv).

## Results

### GGA: MPtrj checkpoints vs MP GGA (thermo type `GGA_GGA+U`)

Δ = library − MP, in meV/atom ([`comparison_vs_mp.csv`](comparison_vs_mp.csv)).

| Element | MP ID | MP GGA (eV/atom) | MACE-MP-medium (eV/atom) | Δ | CHGNet-MPtrj-2023.12.1 (eV/atom) | Δ |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| Li | mp-1018134 | -1.90892 | -1.90653 | +2.4 | -1.86350 | +45.4 |
| Fe | mp-13 | -8.47002 | -8.39086 | +79.2 | -8.35561 | +114.4 |
| Cu | mp-30 | -4.09921 | -4.08482 | +14.4 | -4.07275 | +26.5 |
| Si | mp-149 | -5.42532 | -5.34204 | +83.3 | -5.39151 | +33.8 |
| O | mp-12957 | -4.94796 | -4.92510 | +22.9 (single point, see below) | -4.86834 | +79.6 |
| **MAE** | | | | **40.4** | | **59.9** |
| **Published energy MAE** | | | | 18 (MACE-MP-0 medium, MPtrj) | | 30 (CHGNet, MPtrj test set) |

The deviations are 2–114 meV/atom, and they are positive for every element. In other words, both
models slightly underbind these elements relative to DFT. The mean deviation is about 2.2×
MACE-MP-0's and 2.0× CHGNet's published MPtrj energy MAE.

That is within expected scatter, for two reasons:

- An MAE is an average over many structures. Individual structures, such as Fe (+79 and +114 meV/atom)
  and Si (+83 meV/atom for MACE), can sit several MAEs away.
- The MP energies here are from the 2026.04.13 database, while MPtrj was parsed from the September 2022
  MP database (Deng et al., 2023). MP's current task for a material need not be the one the models
  were trained on.

The published CHGNet number is for the original CHGNet. `CHGNet-MPtrj-2023.12.1-2.7M-PES` is MatGL's
re-implementation trained on MPtrj; the MatPES paper reports 30 meV/atom validation MAE for a
MatGL CHGNet trained on MPtrj (Kaplan et al., 2025, Table 1).

**MACE-MP-medium O is stored as a single point on MP's O2 structure.** MACE-MP-medium has no
molecular minimum for this crystal. The library protocol (cell relaxation, 500 FIRE steps) does not
converge and ends in an unphysical structure at -5.789 eV/atom
([O2_MACE-MP-medium_relaxed.cif](O2_MACE-MP-medium_relaxed.cif)):

- the volume doubles from 13.46 to 26.2 Å<sup>3</sup>/atom;
- the O–O bond contracts from 1.231 to 1.13–1.14 Å;
- the shortest intermolecular contact drops from 2.14 to 1.92 Å.

Even a positions-only relaxation in MP's cell collapses the same way (1.92 Å contacts). The library
therefore stores the single point, **-4.9251 eV/atom, +22.9 meV/atom from MP**. Before this
correction it held the collapsed -5.789 eV/atom, an O reference 0.86 eV/atom too low that made
every oxide formation energy too positive by 0.86 eV per O atom. The other MPtrj library entries for O are consistent with MP:

| Checkpoint | Δ vs MP (meV/atom) |
| :--- | ---: |
| MACE-MP-small | -2.4 |
| MACE-MP-large | -38.6 |
| M3GNet-MP-2021.2.8-PES | +7.5 |
| CHGNet-MPtrj-2024.2.13-11M-PES | +87.0 |

### r2SCAN: MatPES checkpoints vs MP r2SCAN (thermo type `R2SCAN`)

Δ in meV/atom.

| Element | MP ID | MP r2SCAN (eV/atom) | TensorNet-MatPES-r2SCAN (eV/atom) | Δ | MACE-MATPES-R2SCAN-0 (eV/atom) | Δ |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| Li | mp-1018134 | -2.38671 | -2.37420 | +12.5 | -2.36335 | +23.4 |
| Fe | mp-13 | -14.41339 | -14.41332 | +0.1 | -14.44184 | -28.5 |
| Cu | mp-30 | -10.84680 | -10.82150 | +25.3 | -10.83915 | +7.6 |
| Si | mp-149 | -8.77376 | -8.65597 | +117.8 | -8.79134 | -17.6 |
| O | mp-1524462 | -5.97253 | -5.88344 | +89.1 | -5.89470 | +77.8 |
| **MAE** | | | | 49.0 | | **31.0** |
| **Published energy MAE** (MatPES r2SCAN test set) | | | | 34 (TensorNet) | | — |

- **MACE-MATPES-R2SCAN-0** agrees with MP r2SCAN to 31 meV/atom MAE (8–78 meV/atom per element). That
  is in line with the 30–44 meV/atom test MAEs that Kaplan et al. (2025, Table 1) report for MatPES
  r2SCAN models (CHGNet 30, TensorNet 34, M3GNet 44). The MatPES paper reports no number for the MACE
  model itself.
- Exact agreement is not expected. MatPES uses the PBE 64 pseudopotential set and its own
  `MatPESStaticSet` parameters (Kaplan et al., 2025), which differ from MP's r2SCAN workflow. Even so,
  the MACE-MATPES-R2SCAN-0 deviations stay below 80 meV/atom for these elements.
- **TensorNet-MatPES-r2SCAN** deviates from MP r2SCAN by 49.0 meV/atom MAE, close to its published
  34 meV/atom. Its library file was regenerated (2026-10) with the weights the matgl wrapper loads
  under this name (`TensorNet-PES-MatPES-r2SCAN-2025.2`). The previous file held the energies of the
  older weights: Fe, Si and O were off by 11, 79 and 493 meV/atom, and the MAE vs MP was 164.5 meV/atom.

**Do not mix functionals.** The MatPES-PBE checkpoints are on yet another absolute scale. For Cu the
library holds -3.746 (CHGNet-MatPES-PBE), -3.735 (TensorNet-MatPES-PBE) and -3.745 eV/atom
(MACE-MATPES-PBE-0), 353–365 meV/atom above MP's GGA value. Always take references and compound
energies from the same checkpoint.

### Library reproducibility (CPU recomputation, [`cpu_verification.json`](cpu_verification.json))

Recomputed minus library, in meV/atom.

| Checkpoint | Li | Fe | Cu | Si | O |
| :--- | ---: | ---: | ---: | ---: | ---: |
| MACE-MP-medium | 0.0 | 0.0 | 0.0 | 0.0 | -864.3 (collapsed relaxation; library stores the single point) |
| MACE-MATPES-R2SCAN-0 | 0.0 | 0.0 | 0.0 | 0.0 | -0.2 (not converged, stays molecular) |
| TensorNet-MatPES-r2SCAN-v2025.1-PES | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 (regenerated library) |

All three libraries are reproduced to within 0.05 meV/atom by the protocol stated in `SKILL.md`, except
the deliberate single-point O entry of MACE-MP-medium.
The MACE-MATPES-R2SCAN-0 O2 relaxation also hits the 500-step limit, but it ends at a final fmax of
0.09 eV/Å with the molecules intact (O–O 1.21–1.22 Å). Its stored value is therefore a reasonable
reference even though the relaxation is formally unconverged.

### Formation energies with MACE-MP-medium ([`formation_energies.csv`](formation_energies.csv))

MP values are GGA_GGA+U `formation_energy_per_atom`. Δ = MLIP − MP.

| Compound | MP ID | Variant | μ<sub>O</sub> (eV/atom) | ΔH<sub>f</sub> MLIP (eV/atom) | ΔH<sub>f</sub> MP (eV/atom) | Δ (meV/atom) |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| Li2O | mp-1960 | raw MLIP energy, no MP2020 | -4.9251 (library) | -1.8324 | -2.0616 | +229.2 |
| Li2O | mp-1960 | **MP2020-corrected** | -4.9251 (library) | **-2.0614** | -2.0616 | **+0.2** |
| Fe2O3 | mp-19770 | raw MLIP energy, no MP2020 | -4.9251 (library) | -0.3090 | -1.7071 | +1398.1 |
| Fe2O3 | mp-19770 | **MP2020-corrected** | -4.9251 (library) | **-1.6236** | -1.7071 | **+83.5** |

- **The MP2020 correction is essential for MACE-MP-medium.** Without it, Li2O is off by 0.23 eV/atom
  and Fe2O3 by 1.40 eV/atom. Fe2O3 is worse because the Fe GGA+U/GGA mixing correction is missing.
- **With the correction and a sound O reference:**
  - Li2O matches MP to 0.2 meV/atom. The per-structure errors largely cancel: Li2O +9.5, Li +2.4 and
    O +22.9 meV/atom.
  - Fe2O3 is within 84 meV/atom. This error comes from the compound itself: MACE-MP-medium's Fe2O3
    energy is 129 meV/atom above MP's uncorrected GGA+U value, and only partly cancelled by the Fe
    (+79) and O (+23) reference errors.
- **The O reference matters.** The former library value (-5.789 eV/atom, a collapsed relaxation) was
  0.86 eV per O atom too low. It raised the errors vs MP to +288 meV/atom for Li2O and +602 meV/atom
  for Fe2O3.

## References

- A. Jain et al., "Commentary: The Materials Project: A materials genome approach to accelerating materials
  innovation", *APL Mater.* **1**, 011002 (2013). [DOI: 10.1063/1.4812323](https://doi.org/10.1063/1.4812323)
- I. Batatia, P. Benner, Y. Chiang et al., "A foundation model for atomistic materials chemistry",
  arXiv:2401.00096 (v3, 2025). The Methods section reports an energy MAE of 18 meV/atom and a force MAE
  of 39 meV/Å for the medium model. [DOI: 10.48550/arXiv.2401.00096](https://doi.org/10.48550/arXiv.2401.00096)
- B. Deng, P. Zhong, K. Jun, J. Riebesell, K. Han, C. J. Bartel, G. Ceder, "CHGNet as a pretrained universal
  neural network potential for charge-informed atomistic modelling", *Nat. Mach. Intell.* **5**, 1031–1041
  (2023). Table I: energy MAE 30 meV/atom on the MPtrj test set.
  [DOI: 10.1038/s42256-023-00716-3](https://doi.org/10.1038/s42256-023-00716-3)
- A. D. Kaplan, R. Liu, J. Qi et al., "A Foundational Potential Energy Surface Dataset for Materials",
  arXiv:2503.04070 (2025). Table 1: MatPES r2SCAN test energy MAEs of 30 (CHGNet), 34 (TensorNet) and
  44 (M3GNet) meV/atom. [DOI: 10.48550/arXiv.2503.04070](https://doi.org/10.48550/arXiv.2503.04070)
- A. Wang et al., "A framework for quantifying uncertainty in DFT energy corrections", *Sci. Rep.* **11**,
  15496 (2021). [DOI: 10.1038/s41598-021-94550-5](https://doi.org/10.1038/s41598-021-94550-5)
- R. S. Kingsbury et al., "A flexible and scalable scheme for mixing computed formation energies from
  different levels of theory", *npj Comput. Mater.* **8**, 195 (2022).
  [DOI: 10.1038/s41524-022-00881-w](https://doi.org/10.1038/s41524-022-00881-w)

## 3D Structures

- [O2_MACE-MP-medium_relaxed.cif](O2_MACE-MP-medium_relaxed.cif): unphysical, unconverged MACE-MP-medium
  O2 relaxation that produced the former library O value
- [Li2O_MACE-MP-medium_relaxed.cif](Li2O_MACE-MP-medium_relaxed.cif)
- [Fe2O3_MACE-MP-medium_relaxed.cif](Fe2O3_MACE-MP-medium_relaxed.cif)
- [O.cif](../../resources/structures/O.cif): MP O2 ground state mp-12957 (library input)
