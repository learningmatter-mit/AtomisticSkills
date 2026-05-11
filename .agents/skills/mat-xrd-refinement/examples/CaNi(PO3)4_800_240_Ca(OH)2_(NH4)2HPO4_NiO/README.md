# Multiphase Rietveld Refinement of CaNi(PO3)4 System

This example explores a complex multiphase experimental XRD scan, consisting of a synthesis reaction product containing `CaNi(PO3)4` and other intermediate reagents like `NiO` or byproduct phases at 800°C.

### Files Provided:
- `CaNi(PO3)4_800_240_Ca(OH)2_(NH4)2HPO4_NiO.xy`: The multi-component experimental XRD scan data.
- `cifs/`: Reference structural constraints. Includes target product and remaining precursors.
- `refinement_results/`: Outcome metrics, goodness of fit, and phase ratios resulting from DARA.

### Workflow

This example runs a simultaneous multi-phase Rietveld refinement to quantitatively ascertain the sample's purity and presence of defect pathways.

```bash
python ../../scripts/run_refinement.py \
    --data "CaNi(PO3)4_800_240_Ca(OH)2_(NH4)2HPO4_NiO.xy" \
    --cif_dir cifs \
    --output_dir refinement_results
```

The resulting fraction estimates for each structure are written out, and the full experimental overlay is modeled in `_refinement.png`.

### Visual Validation
![XRD Refinement Fit](refinement_results/CaNi(PO3)4_800_240_Ca(OH)2_(NH4)2HPO4_NiO/CaNi(PO3)4_800_240_Ca(OH)2_(NH4)2HPO4_NiO_refinement.png)
