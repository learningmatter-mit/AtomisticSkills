# HKUST-1 (Cu-BTC) from QMOF: DFT-Relaxed Cell and PBE Band Gap

## Goal

Retrieve the PBE-D3(BJ)-relaxed crystal structure and the tabulated PBE band gap of
HKUST-1, Cu<sub>3</sub>(BTC)<sub>2</sub> (BTC = benzene-1,3,5-tricarboxylate), from the
QMOF database by CSD refcode. Then validate:

1. the relaxed cubic lattice parameter against the experimental single-crystal value from
   the original synthesis paper (Chui et al., *Science* 1999), and
2. the band gap returned through MPContribs against the official QMOF dataset release
   on figshare.

## Locating HKUST-1 in QMOF

QMOF does not index MOF common names, and `--identifier FIQCEN` returns no entry.
HKUST-1 is in QMOF as **`qmof-8b5bb88`** (CSD refcode **DOTSOV01**). It was found by listing
the 80 entries in the C-Cu-H-O chemical system and keeping the Fm-3m one whose formula,
Cu<sub>12</sub>C<sub>72</sub>H<sub>24</sub>O<sub>48</sub>, is 4 &times; Cu<sub>3</sub>(C<sub>9</sub>H<sub>3</sub>O<sub>6</sub>)<sub>2</sub>.
The official QMOF release confirms the assignment. Its MOFid is
`[Cu][Cu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-] MOFid-v1.tbo.cat0`, i.e. a Cu<sub>2</sub>
paddlewheel and the BTC linker on the **tbo** net. Its source structure is
Wu et al., *Angew. Chem. Int. Ed.* 2008 (DOI 10.1002/anie.200803925). The dataset's own README
also uses `qmof-8b5bb88` as its worked example.

## Inputs

| Input | Value |
|---|---|
| `--identifier` | `DOTSOV01` (a CSD refcode, matched against the QMOF `data.filename` field) |
| `--max-results` | `1` |
| Credentials | `MP_API_KEY` exported in the environment |
| Compute | CPU only, ~10 s (network-bound) |

## Command

Run from the repository root:

```bash
venv/run cpu python skills/chem-db-qmof/scripts/query_qmof.py \
    --identifier DOTSOV01 \
    --max-results 1 \
    --output-dir skills/chem-db-qmof/examples/hkust1_dotsov01
```

Console output:

```text
Querying QMOF with parameters: {'data__filename__contains': 'DOTSOV01'}
Found 1 matching MOFs. Downloading CIFs to skills/chem-db-qmof/examples/hkust1_dotsov01...
Downloading qmof-8b5bb88 (Formula: Cu12C72H24O48)...
  Saved to skills/chem-db-qmof/examples/hkust1_dotsov01/qmof-8b5bb88.cif
Saved tabulated properties to skills/chem-db-qmof/examples/hkust1_dotsov01/qmof_properties.json
Done.
```

### Validation step

This step derives the conventional cubic cell, the density and the shortest Cu-Cu distance
from the retrieved CIF with pymatgen, then writes [validation.json](validation.json):

```bash
venv/run cpu python - <<'PY'
import json
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

ex = "skills/chem-db-qmof/examples/hkust1_dotsov01"
s = Structure.from_file(f"{ex}/qmof-8b5bb88.cif")
entry = json.load(open(f"{ex}/qmof_properties.json"))["entries"][0]

sga = SpacegroupAnalyzer(s, symprec=0.01)
conv = sga.get_conventional_standard_structure()
cu = [i for i, site in enumerate(s) if site.specie.symbol == "Cu"]
d_cucu = min(s.get_distance(i, j) for i in cu for j in cu if i < j)

ours = {
    "reduced_formula": s.composition.reduced_formula,
    "n_atoms_primitive": len(s),
    "spacegroup": sga.get_space_group_symbol(),
    "a_conventional_A": round(conv.lattice.a, 4),
    "volume_primitive_A3": round(s.volume, 3),
    "volume_conventional_A3": round(conv.volume, 3),
    "density_g_cm3": round(float(s.density), 6),
    "d_CuCu_A": round(d_cucu, 4),
    "EgPBE_eV": entry["EgPBE"],
}
ref = {"a_exp_A": 26.343, "d_CuCu_exp_A": 2.63,
       "EgPBE_official_eV": 0.886534, "density_official_g_cm3": 0.866108,
       "volume_official_A3": 4638.737256}
dev = {
    "a_rel_dev_pct": round(100 * (ours["a_conventional_A"] / ref["a_exp_A"] - 1), 2),
    "volume_rel_dev_vs_exp_pct": round(100 * (ours["a_conventional_A"] ** 3 / ref["a_exp_A"] ** 3 - 1), 2),
    "d_CuCu_dev_A": round(ours["d_CuCu_A"] - ref["d_CuCu_exp_A"], 3),
    "EgPBE_abs_dev_eV": round(abs(ours["EgPBE_eV"] - ref["EgPBE_official_eV"]), 6),
    "density_abs_dev_g_cm3": round(abs(ours["density_g_cm3"] - ref["density_official_g_cm3"]), 6),
}
out = {"retrieved": ours, "reference": ref, "deviation": dev}
json.dump(out, open(f"{ex}/validation.json", "w"), indent=2)
print(json.dumps(out, indent=2))
PY
```

## Outputs

| File | Content |
|---|---|
| [qmof-8b5bb88.cif](qmof-8b5bb88.cif) | PBE-D3(BJ)-relaxed primitive cell (156 atoms, written in P1) |
| [qmof_properties.json](qmof_properties.json) | Tabulated QMOF properties for the hit (refcode, source DOI, density, pore sizes, `EgPBE`, ...) plus a `units` block |
| [input_configs.yaml](input_configs.yaml) | Arguments of the run |
| [validation.json](validation.json) | Output of the validation step |

## Results and Validation

### (a) Structure vs. experiment, (b) band gap vs. official release

| Quantity | This run (skill output) | Reference | Deviation | Reference source |
|---|---|---|---|---|
| Space group | Fm-3m (symprec 0.01 Å) | Fm-3m | — | Chui et al. 1999, as tabulated in Bristow et al. 2014, Table 1 |
| Conventional cubic *a* (Å) | **26.474** | **26.343** (experiment) | **+0.50 %** (+1.5 % in volume) | Chui et al. 1999, as tabulated in Bristow et al. 2014, Table 1 |
| Shortest Cu–Cu, paddlewheel (Å) | 2.457 | 2.63 (room-temperature experimental structure) | −0.17 Å (indicative only, see notes) | Bristow et al. 2014, Section 2 |
| PBE band gap `EgPBE` (eV) | **0.886534** | **0.886534** | 0 | QMOF figshare release v18, `qmof.csv`, `outputs.pbe.bandgap` |
| Density (g cm<sup>−3</sup>), computed by pymatgen from the CIF | 0.866108 | 0.866108 | 0 | QMOF `qmof.csv`, `info.density` |
| Primitive-cell volume (Å<sup>3</sup>) | 4638.737 | 4638.737256 | < 0.001 Å<sup>3</sup> | QMOF `qmof.csv`, `info.volume` |
| Formula per cell | Cu<sub>12</sub>C<sub>72</sub>H<sub>24</sub>O<sub>48</sub> | Cu<sub>12</sub>C<sub>72</sub>H<sub>24</sub>O<sub>48</sub> | — | QMOF `qmof.csv`, `info.formula` |
| Net magnetic moment (PBE) | 0.0 | 0.0 | — | QMOF `qmof.csv`, `outputs.pbe.net_magmom` |

The official values come from `qmof_database/qmof.csv` inside `qmof_database.zip` of the
QMOF figshare record (version 18, published 2025-11-15). For this entry the release also
records a spin-polarised PBE-D3(BJ) calculation (`inputs.pbe.spin = True`, ENCUT 520 eV,
Γ-only k-points), a direct gap, and spin-resolved gaps of 0.8865 / 0.8869 eV.
There are no HLE17, HSE06\* or HSE06 band gaps for this entry: those columns are empty in
`qmof.csv` and absent from the MPContribs record.

### Discussion

- **Lattice parameter.** The QMOF PBE-D3(BJ) cell is 0.50 % longer than the experimental
  *a* = 26.343 Å, which reproduces the Fm-3m framework closely. The comparison is not exactly
  like-for-like, for two reasons:
  - Chui et al. characterised the hydrated framework [Cu<sub>3</sub>(TMA)<sub>2</sub>(H<sub>2</sub>O)<sub>3</sub>]<sub>n</sub>,
    whereas QMOF relaxed the solvent-free framework derived from DOTSOV01.
  - The DFT cell is static (0 K, no zero-point or thermal motion). HKUST-1 shows negative
    thermal expansion (Wu et al. 2008), so a low-temperature cell is expected to be slightly
    larger than a room-temperature one.
- **Band gap.** The MPContribs value matches the official release to all reported digits.
  This confirms that the skill reads the right record and the right column (`EgPBE` = PBE-D3(BJ) gap).
  PBE underestimates band gaps (Rosen et al. 2022). Use the HLE17/HSE06 columns in
  `qmof_properties.json` when an entry has them.
- **Cu–Cu distance.** The paddlewheel Cu–Cu separation is 2.457 Å in the relaxed solvent-free
  framework. Bristow et al. quote 2.63 Å for "the room temperature experimental crystal
  structure" without giving its hydration state. Their Section 2 also notes axial water on Cu in
  hydrated crystals, which the QMOF structure does not have. Because the two are not
  like-for-like, this row is shown for information only and is not a pass/fail criterion.

## Notes

- `--identifier` takes either a QMOF ID with the `qmof-` prefix (e.g. `qmof-8b5bb88`) or a CSD
  refcode or source-name substring. Matching is case-sensitive against `data.filename`: for
  example, `DOTSOV` would also match any other `DOTSOV*` entry.
- QMOF stores the primitive cell (156 atoms for HKUST-1). Use
  `SpacegroupAnalyzer.get_conventional_standard_structure()` to recover the 624-atom cubic
  cell when comparing with crystallographic data.

## References

- S. S.-Y. Chui, S. M.-F. Lo, J. P. H. Charmant, A. G. Orpen, I. D. Williams, "A Chemically Functionalizable Nanoporous Material [Cu<sub>3</sub>(TMA)<sub>2</sub>(H<sub>2</sub>O)<sub>3</sub>]<sub>n</sub>", *Science* **283**, 1148–1150 (1999). [DOI: 10.1126/science.283.5405.1148](https://doi.org/10.1126/science.283.5405.1148)
- J. K. Bristow, D. Tiana, A. Walsh, "Transferable Force Field for Metal–Organic Frameworks from First-Principles: BTW-FF", *J. Chem. Theory Comput.* **10**, 4644–4652 (2014), Table 1 (experimental *a* of HKUST-1, citing Chui et al.) and Section 2 (Cu–Cu separation). [DOI: 10.1021/ct500515h](https://doi.org/10.1021/ct500515h); open access: [PMC4284133](https://pmc.ncbi.nlm.nih.gov/articles/PMC4284133/)
- Y. Wu, A. Kobayashi, G. J. Halder, V. K. Peterson, K. W. Chapman, N. Lock, P. D. Southon, C. J. Kepert, "Negative Thermal Expansion in the Metal–Organic Framework Material Cu<sub>3</sub>(1,3,5-benzenetricarboxylate)<sub>2</sub>", *Angew. Chem. Int. Ed.* **47**, 8929–8932 (2008), the source of CSD entry DOTSOV01. [DOI: 10.1002/anie.200803925](https://doi.org/10.1002/anie.200803925)
- A. S. Rosen, S. M. Iyer, D. Ray, Z. Yao, A. Aspuru-Guzik, L. Gagliardi, J. M. Notestein, R. Q. Snurr, "Machine learning the quantum-chemical properties of metal–organic frameworks for accelerated materials discovery", *Matter* **4**, 1578–1597 (2021). [DOI: 10.1016/j.matt.2021.02.015](https://doi.org/10.1016/j.matt.2021.02.015)
- A. S. Rosen, V. Fung, P. Huck, C. T. O'Donnell, M. K. Horton, D. G. Truhlar, K. A. Persson, J. M. Notestein, R. Q. Snurr, "High-throughput predictions of metal–organic framework electronic properties: theoretical challenges, graph neural networks, and data exploration", *npj Comput. Mater.* **8**, 112 (2022). [DOI: 10.1038/s41524-022-00796-6](https://doi.org/10.1038/s41524-022-00796-6)
- A. S. Rosen, "QMOF Database", figshare, version 18 (2025). [DOI: 10.6084/m9.figshare.13147324](https://doi.org/10.6084/m9.figshare.13147324)
- MPContribs QMOF project (data source queried by the skill): [contribs.materialsproject.org/projects/qmof](https://contribs.materialsproject.org/projects/qmof)

## 3D Structures

- [qmof-8b5bb88.cif](qmof-8b5bb88.cif): HKUST-1 (DOTSOV01), PBE-D3(BJ)-relaxed primitive cell
