# Methanol BDE — Homolytic vs Heterolytic (MACE-OMOL)

**Molecule:** Methanol (CH₄O, SMILES: `CO`)  
**Model:** `MACE-OMOL-extra-large`  
**Cleavage mode:** `both` (homolytic + heterolytic)  
**Includes H bonds:** Yes  

## How to Reproduce

```bash
# Env: mace-agent
python .agents/skills/chem-bond-dissociation/scripts/calculate_bde.py \
    --smiles CO \
    --all_bonds \
    --include_h_bonds \
    --cleavage both \
    --model_type mace \
    --model_name MACE-OMOL-extra-large \
    --output_dir .agents/skills/chem-bond-dissociation/examples/methanol_mace_omol_both
```

## Key Result: C–O Bond

| Cleavage | Fragments | BDE (kcal/mol) |
|:---|:---|:---:|
| Homolytic | CH₃· + OH· | **143.0** |
| Heterolytic (best) | CH₃⁺ + OH⁻ | **90.0** |
| Heterolytic variant B | CH₃⁻ + OH⁺ | 125.9 |

The heterolytic C–O BDE is **53 kcal/mol lower** than homolytic — reflecting the difference between radical and ionic cleavage.

> [!NOTE]
> C–H and O–H bonds produce a single H atom as one fragment.
> Heterolytic BDE is automatically skipped for these bonds because MACE-OMOL
> has no neutral single-atom reference for H⁺ or H⁻ in gas phase.

## Bug Note (Historical)

Earlier runs of this example showed homo = hetero for all bonds. This was caused by
a **key name bug**: the script was writing `atoms.info["total_charge"]` instead of the
correct `atoms.info["charge"]` that MACE reads. After the fix, MACE-OMOL correctly
produces different energies for neutral, cationic, and anionic fragments.
