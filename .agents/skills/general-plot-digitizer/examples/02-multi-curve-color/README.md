# Example 02: Multiple Curves by Color

## Scenario

Two Raman spectra plotted on the same axes: a black curve (citric acid aqueous solution, upper) and a red curve (citric acid solid, lower). Curves are distinguished by color. This demonstrates `--all-curves` extraction using the `curves[]` metadata array.

## Command

```bash
# Env: base-agent
python .agents/skills/general-plot-digitizer/scripts/digitize_pipeline.py \
  .agents/skills/general-plot-digitizer/examples/02-multi-curve-color/source.png \
  --full \
  --metadata .agents/skills/general-plot-digitizer/examples/02-multi-curve-color/metadata.json \
  --all-curves \
  --output-dir ./output \
  --overlay
```

## Metadata Notes

- `curves[]` array with two entries, each specifying `label`, `color_hint`, and `region` (vertical pixel bounds).
- `color_hint` per curve tells the pipeline which color to isolate: `"#000000"` for black, `"#cd4440"` for red.
- `region.y_min` / `region.y_max` restricts extraction to the vertical band containing each curve, preventing cross-contamination.
- No `text_regions` or `mask_regions` -- the red curve extracts cleanly by color, and the black curve uses region restriction. For higher-quality black curve extraction, see [example 03](../03-black-curve-text-mask/).

## Expected Output

- **Black curve:** ~639 points (400--1800 cm⁻¹). Some noise near text labels is expected without text masking.
- **Red curve:** ~681 points (400--1800 cm⁻¹). Clean extraction since red is distinct from background.
- **Files per curve:** `source_{label}_digitized.csv`, `.md`, `.overlay.png`

## Common Pitfalls

- Without `--all-curves`, only a single curve is extracted. Always pair with a `curves[]` array in metadata.
- Without `region` bounds, the black curve extraction may pick up the x-axis line or the red curve's dark edges.
- The `--curve-color` CLI flag is overridden by `color_hint` in `curves[]` when using `--all-curves`.
