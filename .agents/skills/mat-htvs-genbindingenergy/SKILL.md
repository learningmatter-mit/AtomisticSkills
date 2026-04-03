---
name: mat-htvs-genbindingenergy
description: Calculate and store surface adsorption binding energies for OER intermediates (O, OH, OOH) using DFT total energies from the HTVS database.
category: materials
---
# Generate Surface Binding Energies (HTVS)

## Goal
Compute the binding energy $\Delta E$ for OER adsorbates (O, OH, OOH) on relaxed surface slabs relative to H₂O and H₂ gas-phase references, and store the results as `BindingEnergy` records in the HTVS database.

$$
\Delta E_{ads} = E_{slab+ads} - E_{slab} - n_{H_2O} E_{H_2O} - \frac{n_H}{2} E_{H_2}
$$

## Instructions

### 1. Prerequisites
- Clean surfaces with `clean_surface_cut` config must be relaxed and their energies stored in HTVS.
- Adsorbate surfaces with `add_adsorbate` config must be relaxed and energies stored.
- Gas-phase reference crystals (H₂O, H₂) must exist in the reference group.

### 2. Run the Script
```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-genbindingenergy/scripts/run.py \
    --group my_project \
    --config_name pbe_u_paw_spinpol_opt_vasp \
    --ref_group surface_binding_energy_references \
    --ref_config pbe_u_paw_spinpol_opt_vasp \
    --method dft_d3_paw_gga_pbe \
    --metric surface_binding_dE \
    --settings djangochem.settings.orgel
```

#### Parameters
| Flag | Required | Default | Description |
|---|---|---|---|
| `--group` | ✅ | — | HTVS project group name |
| `--config_name` | ✅ | — | JobConfig name for adsorbate-surface DFT calcs |
| `--settings` | ✅ | — | Django settings module |
| `--ref_group` | ❌ | `surface_binding_energy_references` | Group name of gas reference crystals |
| `--ref_config` | ❌ | `pbe_u_paw_spinpol_opt_vasp` | Config name of gas reference calcs |
| `--method` | ❌ | `dft_d3_paw_gga_pbe` | Method name for energy lookups |
| `--metric` | ❌ | `surface_binding_dE` | AffinityType name for stored binding energies |
| `--limit` | ❌ | 10000 | Max number of surfaces to process |
| `--dry_run` | ❌ | — | Simulate without writing to DB |
| `--djangochem` | ❌ | — | Path to the djangochem project root if needed |

### 3. Verify Results
After the run, verify binding energies were saved:
```python
mcp_htvs_query_results(
    settings_module="orgel",
    group_name="my_project",
    config_name="pbe_u_paw_spinpol_opt_vasp",
)
```

## Constraints
- Supported adsorbates: `O`, `HO` (OH), `HOO` (OOH).
- The script skips surfaces that already have a `BindingEnergy` record for the given metric.
- The `--ref_group` and `--ref_config` flags make gas-phase references fully configurable with no hardcoded names.
- **Environment**: `htvs-agent`

## References
- Nørskov et al., *J. Electrochem. Soc.*, 2004. [DOI](https://doi.org/10.1149/1.1612015)
- Man et al., *ChemCatChem*, 2011. [DOI](https://doi.org/10.1002/cctc.201000397)

---

**Author:** Hoje Chun  
**Contact:** [GitHub @hojechun](https://github.com/hojechun)
