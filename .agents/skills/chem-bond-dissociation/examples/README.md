# Ethanol BDE Examples

Bond dissociation energies (BDEs) for ethanol (CH₃CH₂OH) computed with two MLIPs.

## Quick Comparison

| Bond | MACE-OFF23-small | UMA-s-1p1 omol | Exp. (kcal/mol) | Exp. ref. |
|:---|:---|:---|:---|:---|
| C–H methylene (CH₃C**H₂**OH) | 104.5 | 106.7–107.4 | 95.5 ± 1 | [1] |
| C–O (CH₃CH₂–OH) | 83.9 | 122.5 | 92.1 ± 1 | [2] |
| C–H methyl (**CH₃**CH₂OH) | 116.9–117.6 | 122.8–123.5 | 101.1 ± 0.4 | [1] |
| C–C (CH₃–CH₂OH) | 104.0 | 131.4 | 85.4 ± 1 | [2] |
| O–H (CH₃CH₂O–**H**) | 107.9 | 139.8 | 104.7 ± 0.8 | [1] |

## Key Observations

- **MACE-OFF23-small** gives closer absolute BDE values (~10–20 kcal/mol error).
- **UMA-s-1p1 omol** systematically overestimates BDEs by ~12–36 kcal/mol, likely because radical fragments default to spin=1 (singlet) instead of the correct doublet state.
- Both models correctly rank methylene C–H as weaker than methyl C–H.
- BDE **ranking** is generally more reliable than absolute values with general-purpose MLIPs.

## References

1. Blanksby, S. J.; Ellison, G. B. "Bond Dissociation Energies of Organic Molecules." *Acc. Chem. Res.* **2003**, *36*, 255–263. [doi:10.1021/ar020230d](https://doi.org/10.1021/ar020230d)
2. Luo, Y.-R. *Comprehensive Handbook of Chemical Bond Energies*; CRC Press: Boca Raton, FL, **2007**. [doi:10.1201/9781420007282](https://doi.org/10.1201/9781420007282)

## Subdirectories

- `ethanol_mace_off23_small/` — MACE-OFF23-small results
- `ethanol_uma_s_1p1_omol/` — FairChem UMA-s-1p1 (omol head) results
