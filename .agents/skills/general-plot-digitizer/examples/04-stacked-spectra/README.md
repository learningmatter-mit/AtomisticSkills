# Example 04: Stacked Spectra (Per-Curve Normalized)

## Scenario

Three Raman spectra (Polyethylene, Polystyrene, Nylon 6,6) plotted with vertical offsets in a stacked arrangement. The Y axis has no numeric tick labels -- just "Intensity (a.u.)". Each curve must be independently normalized to 0--1. This demonstrates `y_calibration: "per_curve_normalized"` with per-curve `region` bounds and the `--all-curves` workflow.

## Command

```bash
# Env: base-agent
python .agents/skills/general-plot-digitizer/scripts/digitize_pipeline.py \
  .agents/skills/general-plot-digitizer/examples/04-stacked-spectra/source.png \
  --full \
  --metadata .agents/skills/general-plot-digitizer/examples/04-stacked-spectra/metadata.json \
  --all-curves \
  --output-dir ./output \
  --overlay
```

## Metadata Notes

- **`y_calibration: "per_curve_normalized"`**: Each curve is mapped to 0 (baseline) -- 1 (peak) independently, rather than using shared Y-axis tick values.
- **`y_tick_min: 0, y_tick_max: 1`**: Placeholder values since Y ticks are absent; actual normalization uses per-curve pixel range.
- **`curves[]`** with three entries, each specifying `color_hint` and a `region` with `y_min`/`y_max` to isolate each trace vertically. Regions may overlap slightly at the boundary between adjacent curves.
- Source image was generated synthetically with known Gaussian peaks for validation.

## Expected Output

- **Polyethylene:** ~1105 points, strongest peaks near 2850 and 2880 cm⁻¹.
- **Polystyrene:** ~1098 points, strongest peak near 1000 cm⁻¹.
- **Nylon 6,6:** ~1089 points, prominent peaks near 1635 and 2930 cm⁻¹.
- **Y range:** 0.0 -- 1.0 for all curves (per-curve normalized).
- **Files per curve:** `source_{label}_digitized.csv`, `.md`, `.overlay.png`

## Common Pitfalls

- Without `y_calibration: "per_curve_normalized"`, the pipeline maps Y to the (meaningless) tick range, producing wrong intensity values.
- Without `region` bounds per curve, each extraction captures pixels from adjacent offset curves.
- Text labels matching the curve color (e.g., "Polyethylene" in blue) may need `text_regions` if they overlap the trace. In this example, labels are far enough from the curve baseline to avoid contamination.
