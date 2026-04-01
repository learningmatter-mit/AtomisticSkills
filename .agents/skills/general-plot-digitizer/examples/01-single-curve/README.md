# Example 01: Single Colored Curve

## Scenario

A single blue Raman spectrum (PMMA) on a white background with clearly labeled axes. This is the simplest digitization case -- one curve, distinct color, no overlapping text.

## Command

```bash
# Env: base-agent
python .agents/skills/general-plot-digitizer/scripts/digitize_pipeline.py \
  .agents/skills/general-plot-digitizer/examples/01-single-curve/source.png \
  --full \
  --metadata .agents/skills/general-plot-digitizer/examples/01-single-curve/metadata.json \
  --curve-color "#1f77b4" \
  --output-dir ./output \
  --overlay
```

## Metadata Notes

- Standard linear axes with tick ranges read directly from the plot.
- `y_calibration: "axis"` -- Y values mapped from axis tick labels (0.0--1.0 normalized intensity).
- Single curve, no `curves[]` array needed.
- No `text_regions` needed -- the "PMMA" label is black, not the same color as the blue curve.

## Expected Output

- **Points:** ~499 data points covering 250--3500 cm⁻¹.
- **Overlay:** Green trace tightly follows the blue curve with all peaks captured.
- **Files:** `source_digitized.csv`, `source_digitized.md`, `source_digitized.overlay.png`

## Common Pitfalls

- Omitting `--curve-color` causes auto-detection, which may pick the wrong color on plots with axis lines or annotations.
- If the blue is faint or anti-aliased, increase `--curve-tolerance` (default 40) to 50--60.
