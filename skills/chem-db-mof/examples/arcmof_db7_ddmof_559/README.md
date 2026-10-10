# ARC-MOF DB7 (Majumdar et al.): Top Post-Combustion CO<sub>2</sub> MOF `ddmof_559`

## Goal

Retrieve one specific hypothetical MOF by identifier from the Majumdar et al. (2021) database,
which ARC-MOF includes as **DB7**. Then validate the downloaded CIF and its metadata row against:

1. the structure description in the original paper. Figure 7 of Majumdar et al. shows `ddmof_559`
   as "a top performing MOF for post-combustion carbon capture": metal node **mn1** + organic edge
   **oe31** + topology **snk**. The text defines mn1 as the six-connected
   **Ni<sub>4</sub>(μ<sub>3</sub>-OH)<sub>2</sub>(COO)<sub>6</sub>** cluster;
2. the geometric descriptors published with ARC-MOF (`geometric_properties.csv`, Zenodo); and
3. the paper's CO<sub>2</sub> screening benchmark (Zeolite-13X, ~5 mmol g<sup>−1</sup> at 1 bar and 298 K).

## Inputs

| Input | Value |
|---|---|
| `--database` | `arcmof-majumdar` |
| `--identifier` | `ddmof_559` (a full MOF name, so it is matched exactly) |
| `--max-results` | `1` |
| Data source | Materials Cloud Archive 2021.126, `mof_data.tar.gz` (156,255,289 bytes, md5 `a424d0a320baaad4a97378a78d8022dd`), cached at `~/.cache/arcmof/` |
| Compute | CPU only. About 5 s with a warm cache. The first run downloads the 149 MB archive once. |

MOF names in this database are `ddmof_<N>` with N = 1 to 23891, without zero padding.

## Command

Run from the repository root:

```bash
venv/run cpu python skills/chem-db-mof/scripts/query_mof_db.py \
    --database arcmof-majumdar \
    --identifier ddmof_559 \
    --max-results 1 \
    --output-dir skills/chem-db-mof/examples/arcmof_db7_ddmof_559
```

Console output:

```text
Using cached Majumdar tarball: ~/.cache/arcmof/majumdar_mof_data.tar.gz
Loading mof_data.csv metadata ...
Extracting CIFs from nested mof_structures.tar ...
  Identifier filter (exact name): 'ddmof_559'
  [1] ddmof_559.cif
Done. Checked 1 CIFs, saved 1 to skills/chem-db-mof/examples/arcmof_db7_ddmof_559.
Metadata (incl. CO2 uptake, selectivity) saved: skills/chem-db-mof/examples/arcmof_db7_ddmof_559/majumdar_metadata.csv
```

### Reference row from ARC-MOF

This takes the `DB7-ddmof_559` row from ARC-MOF's `geometric_properties.csv` (110,395,714 bytes,
md5 `345ecb861674a3a25e7be580cd1ab716`, Zenodo record 16802743). The streaming `grep` avoids
loading the 521,316-row table into memory:

```bash
curl -L -o ~/.cache/arcmof/geometric_properties.csv \
    "https://zenodo.org/records/16802743/files/geometric_properties.csv?download=1"
{ head -1 ~/.cache/arcmof/geometric_properties.csv; \
  grep -F ',DB7-ddmof_559.cif,' ~/.cache/arcmof/geometric_properties.csv; } \
    > skills/chem-db-mof/examples/arcmof_db7_ddmof_559/arcmof_geometric_properties_ddmof_559.csv
```

### Validation step

This step derives the composition, the node motif counts, the net charge, the volume and the
density from the CIF with pymatgen, then compares them with both metadata rows and writes
[validation.json](validation.json):

```bash
venv/run cpu python - <<'PY'
import json, tarfile
from pathlib import Path
import numpy as np
import pandas as pd
from pymatgen.core import Structure

ex = "skills/chem-db-mof/examples/arcmof_db7_ddmof_559"
s = Structure.from_file(f"{ex}/ddmof_559.cif")
mj = pd.read_csv(f"{ex}/majumdar_metadata.csv").iloc[0]                       # skill output
arc = pd.read_csv(f"{ex}/arcmof_geometric_properties_ddmof_559.csv").iloc[0]  # ARC-MOF reference row

# Partial charges: 6-column rows of the atom-site loop (label, type, x, y, z, charge)
rows = [l.split() for l in open(f"{ex}/ddmof_559.cif")]
charges = [float(r[5]) for r in rows if len(r) == 6 and r[1].isalpha()]

# Bond-based motif counts: mu3-OH hydrogens (H-O < 1.1 A), carboxylate carbons (two O < 1.4 A)
dm, sym = s.distance_matrix, np.array([site.specie.symbol for site in s])
n_oh = int(sum((dm[i, sym == "O"] < 1.1).any() for i in np.where(sym == "H")[0]))
n_coo = int(sum((dm[i, sym == "O"] < 1.4).sum() == 2 for i in np.where(sym == "C")[0]))
el = s.composition.get_el_amt_dict()

# Dataset-level check against the paper: count of MOFs above the Zeolite-13X benchmark (~5 mmol/g)
tar = Path("~/.cache/arcmof/majumdar_mof_data.tar.gz").expanduser()
with tarfile.open(tar, "r:gz") as t:
    co2 = pd.read_csv(t.extractfile("mof_data/mof_data.csv"), usecols=["CO2_uptake_1bar_298K (mmol/g)"]).iloc[:, 0]

out = {
    "retrieved": {
        "formula": s.composition.formula.replace(" ", ""),
        "n_atoms": len(s),
        "elements": sorted(el),
        "n_Ni": int(el["Ni"]), "n_mu3_OH": n_oh, "n_carboxylate": n_coo, "n_F": int(el["F"]),
        "net_charge_e": round(sum(charges), 4),
        "volume_A3": round(s.volume, 2),
        "density_g_cm3": round(float(s.density), 5),
        "metal_node": mj["metal_node"], "organic_edge": mj["organic_edge"], "topology": mj["topology"],
        "CO2_uptake_1bar_298K_mmol_g": round(float(mj["CO2_uptake_1bar_298K (mmol/g)"]), 3),
    },
    "reference": {
        "paper_fig7": {"metal_node": "mn1", "organic_edge": "oe31", "topology": "snk",
                       "mn1_cluster": "Ni4(mu3-OH)2(COO)6", "zeolite_13X_CO2_mmol_g": 5.0,
                       "n_above_13X": "around 800"},
        "majumdar_mof_data": {"volume_A3": float(mj["CellV (A^3)"]), "density_g_cm3": float(mj["Density (g/cm^3)"]),
                              "Di_A": float(mj["Di"]), "Df_A": float(mj["Df"])},
        "arcmof_geometric_properties": {"filename": arc["filename"], "volume_A3": float(arc["UC_volume"]),
                                        "density_g_cm3": float(arc["Density"]), "Di_A": float(arc["Di"]),
                                        "Df_A": float(arc["Df"]), "in_ARC-MOF": bool(arc["ARC-MOF"])},
    },
    "derived": {
        "Ni_per_OH": el["Ni"] / n_oh, "COO_per_Ni4": 4 * n_coo / el["Ni"], "linkers_C8F4O4": int(el["F"] // 4),
        "n_above_13X_in_dataset": int((co2 > 5.0).sum()), "n_with_CO2_data": int(co2.notna().sum()),
        "volume_rel_dev_vs_arcmof_pct": round(100 * (s.volume / arc["UC_volume"] - 1), 4),
        "density_rel_dev_vs_arcmof_pct": round(100 * (float(s.density) / arc["Density"] - 1), 4),
    },
}
json.dump(out, open(f"{ex}/validation.json", "w"), indent=2)
print(json.dumps(out, indent=2))
PY
```

## Outputs

| File | Content |
|---|---|
| [ddmof_559.cif](ddmof_559.cif) | UFF-optimised hypothetical MOF, 896 atoms in P1, with `_atom_site_charge` partial charges |
| [majumdar_metadata.csv](majumdar_metadata.csv) | The `mof_data.csv` row for `ddmof_559` (building blocks, topology, GCMC CO<sub>2</sub>/N<sub>2</sub>/H<sub>2</sub> uptakes, Zeo++ descriptors, linker SMILES) |
| [input_configs.yaml](input_configs.yaml) | Arguments of the run |
| [arcmof_geometric_properties_ddmof_559.csv](arcmof_geometric_properties_ddmof_559.csv) | Reference row extracted from ARC-MOF `geometric_properties.csv` |
| [validation.json](validation.json) | Output of the validation step |

## Results and Validation

| Quantity | This run (skill output) | Reference | Agreement | Reference source |
|---|---|---|---|---|
| Building blocks | mn1 + `['oe31']`, topology `snk` | mn1 + oe31 + snk | exact | Majumdar et al. 2021, Figure 7 caption |
| Metal | Ni (elements C, F, H, Ni, O) | mn1 is "a Ni-based metal node" | yes | Majumdar et al. 2021, Section 3.2 |
| Node stoichiometry, Ni : μ<sub>3</sub>-OH : COO | 64 : 32 : 96 = **4 : 2 : 6** | Ni<sub>4</sub>(μ<sub>3</sub>-OH)<sub>2</sub>(COO)<sub>6</sub> | exact (16 nodes) | Majumdar et al. 2021, Section 3.2 |
| Formula per cell | Ni<sub>64</sub>H<sub>32</sub>C<sub>384</sub>O<sub>224</sub>F<sub>192</sub> = 16 Ni<sub>4</sub>(OH)<sub>2</sub> + 48 C<sub>8</sub>F<sub>4</sub>O<sub>4</sub> | linker SMILES `C(=O)([O])c1c(c(F)c(c(c1F)F)C(=O)[O])F` (tetrafluoroterephthalate) | consistent | `mof_data.csv` (`linker-SMILES`) |
| Cell volume (Å<sup>3</sup>), pymatgen | **32395.98** | 32396.0 (Majumdar) / 32396.0 (ARC-MOF `UC_volume`) | −0.0001 % | Materials Cloud 2021.126; ARC-MOF Zenodo |
| Density (g cm<sup>−3</sup>), pymatgen | **0.80127** | 0.80127 (Majumdar) / 0.80127 (ARC-MOF `Density`) | +0.0005 % | Materials Cloud 2021.126; ARC-MOF Zenodo |
| Largest included / free sphere D<sub>i</sub> / D<sub>f</sub> (Å) | 11.022 / 7.259 (metadata) | 11.02193 / 7.25913 (ARC-MOF) | exact | ARC-MOF `geometric_properties.csv` |
| Net framework charge (e) | 0.0000 (sum over 896 sites) | 0 (charge-neutral framework) | yes | — |
| Pure CO<sub>2</sub> uptake, 1 bar, 298 K (mmol g<sup>−1</sup>) | **7.660** | > Zeolite-13X benchmark of ~5 | yes (rank 60 of 23,651) | Majumdar et al. 2021, Section 3.2 |
| Number of MOFs above ~5 mmol g<sup>−1</sup> in the whole dataset | 807 | "around 800" | yes | Majumdar et al. 2021, Section 3.2 |

### Discussion

- The CIF the skill returns is the structure the paper describes. The building-block labels and
  the snk net match the Figure 7 caption. The bond-perceived composition gives exactly
  16 Ni<sub>4</sub>(μ<sub>3</sub>-OH)<sub>2</sub>(COO)<sub>6</sub> clusters linked by 48 tetrafluoroterephthalates.
- The volume and density pymatgen computes from the CIF agree with both published metadata
  tables to the five significant digits they report. ARC-MOF's `UC_volume`, `Density`, `Di` and
  `Df` for `DB7-ddmof_559` equal Majumdar's values digit for digit. The two tables are therefore
  consistent with each other, but they may not be independent calculations.
- **ARC-MOF membership.** ARC-MOF's `geometric_properties.csv` lists 12,316 `DB7-` entries,
  6,955 of which are flagged `ARC-MOF = True`. `ddmof_559` is in the DB7 design space but
  is flagged `ARC-MOF = False`, so it is not among the ARC-MOF structures with REPEAT charges.
  The `arcmof-majumdar` option downloads from the original Materials Cloud archive, which
  holds all 23,891 `ddmof_*` structures. Its charges were generated with EQeq on the
  UFF-optimised frameworks (Majumdar et al., Section 2.2), not with REPEAT.
- The structure is UFF-optimised and stored in P1. Relax it with an MLIP before any
  property calculation (see [chem-sorption-relax](../../../chem-sorption-relax/SKILL.md)).

## References

- S. Majumdar, S. M. Moosavi, K. M. Jablonka, D. Ongari, B. Smit, "Diversifying Databases of Metal Organic Frameworks for High-Throughput Computational Screening", *ACS Appl. Mater. Interfaces* **13**, 61004–61014 (2021). [DOI: 10.1021/acsami.1c16220](https://doi.org/10.1021/acsami.1c16220); open access: [PMC8719320](https://pmc.ncbi.nlm.nih.gov/articles/PMC8719320/)
- S. Majumdar, S. M. Moosavi, K. M. Jablonka, D. Ongari, B. Smit, "Diversifying databases of metal organic frameworks for high-throughput computational screening", *Materials Cloud Archive* 2021.126 (2021), CC BY 4.0. [DOI: 10.24435/materialscloud:yn-de](https://doi.org/10.24435/materialscloud:yn-de)
- J. Burner, J. Luo, A. White, A. Mirmiran, O. Kwon, P. G. Boyd, S. Maley, M. Gibaldi, S. Simrod, V. Ogden, T. K. Woo, "ARC–MOF: A Diverse Database of Metal-Organic Frameworks with DFT-Derived Partial Atomic Charges and Descriptors for Machine Learning", *Chem. Mater.* **35**, 900–916 (2023). [DOI: 10.1021/acs.chemmater.2c02485](https://doi.org/10.1021/acs.chemmater.2c02485)
- ARC-MOF dataset, "ab initio REPEAT Charge MOF Database (ARC-MOF)", Zenodo record 16802743 (concept DOI 10.5281/zenodo.6908727). [DOI: 10.5281/zenodo.16802743](https://doi.org/10.5281/zenodo.16802743)

## 3D Structures

- [ddmof_559.cif](ddmof_559.cif): `ddmof_559`, Ni<sub>4</sub>(μ<sub>3</sub>-OH)<sub>2</sub> nodes and tetrafluoroterephthalate linkers on the snk net
