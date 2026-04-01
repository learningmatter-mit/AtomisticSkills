# Example 03: Black Curve with Text Masking

## Scenario

Same plot as example 02, but focused on high-quality extraction of the black curve. The black curve shares its color with the axis frame, tick marks, and two in-plot text labels ("citric acid aqueous solution" and "citric acid solid"). This demonstrates `text_regions`, per-curve `mask_regions`, `--allow-black`, and `--smooth`.

## Command

```bash
# Env: base-agent
python .agents/skills/general-plot-digitizer/scripts/digitize_pipeline.py \
  .agents/skills/general-plot-digitizer/examples/03-black-curve-text-mask/source.png \
  --full \
  --metadata .agents/skills/general-plot-digitizer/examples/03-black-curve-text-mask/metadata.json \
  --all-curves \
  --allow-black \
  --smooth \
  --output-dir ./output \
  --overlay
```

## Metadata Notes

- **`text_regions`** (top-level): Bounding boxes for both text labels with ~10px padding. These are always masked out for all curve extractions, preventing text pixels from contaminating the trace.
- **`curves[0].mask_regions`**: The black curve's entry includes a mask region covering the entire lower half of the plot (y > 430), excluding the red curve's baseline and any dark anti-aliased edges. This mask is applied only when extracting the black curve (curve index 0), not the red curve.
- **`--allow-black`**: Enables extraction of near-black pixels and auto-enables the trace-following cluster centroid algorithm (two-pass: rough trace via largest cluster, then smoothed reference to pick the closest cluster per column).
- **`--smooth`**: Applies median filter + outlier rejection + linear interpolation over gaps left by text masking.

## Expected Output

- **Black curve:** ~747 points. Smooth trace with text gaps cleanly interpolated.
- **Red curve:** ~754 points. Unaffected by the black curve's `mask_regions` (per-curve masks are curve-specific).
- **Overlay:** Green trace follows the black curve accurately, with no zigzag artifacts in the text regions.

## Common Pitfalls

- Without `text_regions`, the extraction picks up text label pixels as part of the curve, creating spikes.
- Without per-curve `mask_regions`, spurious dark pixels from the red curve's anti-aliased edges contaminate columns in the 1200--1400 cm⁻¹ region.
- `text_regions` padding must be generous (~10px) to cover anti-aliased character edges.
- The `--smooth` flag is critical: without it, gaps left by text masking appear as discontinuities.
