---
name: general-plot-digitizer
description: Extract continuous X-Y data from experimental spectrum images (Raman, XRD, UV-Vis, IR, etc.) via hybrid VLM + CV pipeline and agent-in-the-loop workflow.
category: [general]
---

# General Plot Digitizer

## Goal

Extract calibrated numeric X-Y data from images of experimental spectra (Raman, XRD, UV-Vis, IR, NMR, etc.) using a deterministic "Agent-in-the-Loop" workflow.

The labor is divided between two models:
1. **Vision-Language Model (Visual Sensor)**: Reads the image and returns a rich, unstructured narrative description of axes, colors, and visual obstacles. It does **not** produce JSON.
2. **Coding Agent (Translator & Executor)**: Translates the VLM narrative into a precise `metadata.json`, runs the CV pipeline, inspects the overlay, and iterates until the curve is correctly isolated.

## Instructions

### Phase 1: Visual Inspection (VLM)

Do **not** attempt to generate JSON with the VLM. It acts only as a visual sensor.

1. **Generate grid overlay**:
```bash
# Env: base-agent
python .agents/skills/general-plot-digitizer/scripts/plot_utils.py plot.png --draw-grid
```
This produces `plot_grid.png` with a labeled pixel grid for precise coordinate reading.

2. **Prompt the VLM** to analyze `plot_grid.png` (not the raw image). Use the built-in vision capabilities or the `notify_user` VLM inspection tool. Provide the prompt guidelines from [scripts/vlm_prompt_template.txt](scripts/vlm_prompt_template.txt).

3. **Expected VLM output** — a natural-language report covering:
   - Axis labels, numeric ranges, and directions (is X reversed?).
   - Bounding box of the data region in pixels (read from the grid).
   - Color and style of each target curve (hex guess from the pixels on the line itself).
   - Pixel bounding boxes of **all visual obstacles** (legends, text annotations, gridlines, tick marks) that overlap the data curves.
   - Trace quality hints: thin/needle-like, thick/noisy, anti-aliased, JPEG artifacts.

### Phase 2: Metadata Construction (Coding Agent)

Read the VLM narrative and construct `metadata.json`. Schema: [resources/metadata_schema.json](resources/metadata_schema.json).

**Required fields:**
```json
{
  "plot_title": "",
  "x_axis_label": "Wavelength (nm)",
  "y_axis_label": "Absorbance",
  "x_tick_min": 400, "x_tick_max": 800,
  "y_tick_min": 0, "y_tick_max": 1,
  "x_calibration_points": [
    { "pixel": 70, "value": 400 },
    { "pixel": 450, "value": 800 }
  ],
  "x_scale": "linear", "y_scale": "linear",
  "bounding_box": {"x_min": 72, "y_min": 28, "x_max": 452, "y_max": 318},
  "x_reversed": false, "y_reversed": false,
  "spectrum_type": "UV-Vis",
  "curves": [{"label": "sample", "color_hint": "#1f77b4"}],
  "text_regions": [{"x_min": 300, "y_min": 50, "x_max": 400, "y_max": 80, "label": "legend"}]
}
```

**`x_calibration_points`** (strongly recommended): anchor the X-axis transform to exact pixel→value pairs read from the grid, rather than assuming axis ticks align perfectly with bbox edges. Pick two well-separated ticks visible on the grid. If provided, these override `x_tick_min/max` for pixel-to-data mapping.

**Translation rules** (VLM narrative → metadata fields):
- Obstacles → `text_regions[]` and/or `mask_regions[]` with pixel bounding boxes.
- Curve colors → `curves[].color_hint` (from **pixels on the plotted line**, not from legend swatches).
- "Curve is black / same as axes" → `"cli_hints": {"curve_is_black": true}`.
- "Noisy / jagged trace" → `"cli_hints": {"smooth": true}`.
- "Thin, needle-like peaks" → **do not** set smooth; set upscale in Phase 3 instead.

**If the VLM color guess is uncertain**, run:
```bash
# Env: base-agent
python .agents/skills/general-plot-digitizer/scripts/suggest_colors.py plot.png \
  --bounding-box x_min,y_min,x_max,y_max
```
This reports dominant non-background colors in the cropped region. Use the top result as `color_hint`.

### Phase 3: Pipeline Execution

**Select CLI flags based on VLM visual cues:**

| VLM describes... | Required CLI flags | Avoid |
|---|---|---|
| Thin, needle-like peaks (XRD, FTIR) | `--crop-upscale 4.0` | `--smooth`, `--cluster-centroid` |
| Fuzzy / anti-aliased / JPEG artifacts | `--curve-tolerance 75` (up to 85) | — |
| Thick, noisy trace / scatter points | `--smooth --smooth-window 5 --smooth-deviation 15.0` | — |
| Black curve on black axes | `--allow-black` (auto-enables `--spatial-filter --cluster-centroid`) | — |
| Thin anti-aliased colored line | `--extraction-method edge+color` | `--morph-open` |

**Run the pipeline:**
```bash
# Env: base-agent
python .agents/skills/general-plot-digitizer/scripts/digitize_pipeline.py \
  plot.png \
  --full \
  --metadata metadata.json \
  --output-dir ./output \
  --overlay \
  --format both
```
Append the VLM-dictated flags from the table above. The pipeline also reads `cli_hints` from metadata and auto-applies safe flags (`--allow-black`, `--smooth`, `--all-curves`).

### Phase 4: Overlay Inspection & Iteration

1. **Inspect** `*_digitized.overlay.png` visually.
2. **If extraction is wrong**, diagnose using this table and re-run Phase 3:

| Symptom | Fix (metadata or CLI) |
|---------|----------------------|
| Wrong curve extracted (e.g. legend ink) | Set `curves[].color_hint` from actual line pixels; or run `suggest_colors.py` on a tight crop |
| Text / labels contaminating trace | Add bounding boxes to `text_regions[]` in metadata; add `--smooth` |
| Black curve picks up axis lines | `--allow-black` + add axis regions to `mask_regions[]` |
| Trace too sparse / broken gaps | `--curve-tolerance 55` or `--preset lowres` |
| Thin line lost entirely | `--extraction-method edge+color`; or `--crop-upscale 4.0` for needle peaks |
| Same-color text blobs on thick curve | `--morph-open` (caution: destroys thin <3px curves) |
| Low-res image, everything pixelated | `--upscale-strategy force` (pre-upscales image, scales metadata bbox) |
| X/Y values shifted or inverted | Fix `x_tick_min/max`, `x_reversed`, `y_reversed`, or `x_calibration_points` in metadata |

3. **Prefer metadata edits** (adjusting `color_hint`, `text_regions`, `mask_regions`, `bounding_box`) over adding CLI flags. Re-run the same pipeline command after editing `metadata.json`.

**Outputs:**
- `*_digitized.csv` — comma-separated with `x,y` header
- `*_digitized.xy` — space-separated, no header (if `--format xy` or `both`)
- `*_digitized.overlay.png` — visual QC
- `*_digitized.md` — summary

## Agent Rules

- **Do not** write ad-hoc NumPy/OpenCV pixel-scanning code. The pipeline already handles HSV masking, spatial filtering, and smoothing internally.
- **Do not** skip the grid overlay step. The VLM is significantly more accurate on `plot_grid.png` than on raw images.
- **Do not** guess CLI flags without VLM visual evidence. The flag table above is the complete decision tree.
- **Always** inspect the overlay image after each run before declaring success.

## Key Parameters

| Flag | Use when... | Default |
|------|-------------|---------|
| `--curve-color HEX` | VLM identified a specific curve color | auto-detect |
| `--curve-tolerance N` | Trace is sparse or image has JPEG artifacts (increase); or mask bleeds into nearby colors (decrease) | 40 |
| `--overlay` | Always recommended for QC | off |
| `--format {csv,xy,both}` | Downstream tool needs specific format | csv |
| `--all-curves` | Multiple curves in metadata `curves[]` (auto-enabled when >1 curve) | off |
| `--allow-black` | Data curve is black (same color as axes/frame) | off |
| `--smooth` | Noisy, jagged, or thick trace with outlier points | off |
| `--smooth-window N` | Tune smoothing aggressiveness (larger = more smoothing) | 5 |
| `--smooth-deviation PX` | Pixel distance from local median beyond which a point is rejected as outlier | 15.0 |
| `--crop-upscale FACTOR` | Thin peaks (XRD, FTIR) need more pixel width to register; or generally low-res crop | 1.0 |
| `--upscale-strategy {none,auto,force}` | `auto` (default) pre-upscales when metadata or heuristic says low-res; `force` always pre-upscales; `none` skips | auto |
| `--upscale-factor FACTOR` | Controls the multiplier used by `--upscale-strategy auto\|force` | 2.0 |
| `--vlm-metadata-on-upscale` | After pre-upscale, re-run VLM metadata on upscaled image instead of just scaling coordinates. Only if API keys are set | off |
| `--extraction-method {color,edge,edge+color}` | `color` (default) fails on thin anti-aliased lines; try `edge+color` | color |
| `--morph-open` | Same-color text blobs touching a **thick** curve; erodes then dilates to remove small blobs. **Destroys thin (<3px) curves** | off |
| `--spatial-filter` | Curve matches frame/axis color — keeps only the largest connected line-like component | off |
| `--cluster-centroid` | Text or axes bleed into mask — uses largest-cluster centroid instead of full-column median. Auto-enabled with `--allow-black` | off |
| `--preset {lowres,thin-red}` | Quick combos: `lowres` = upscale 2 + tolerance 55 + edge+color; `thin-red` = tolerance 50, no morph-open | none |
| `--debug` | Save intermediate crops/masks for diagnosing failures | off |
| `--json-summary` | Emit machine-readable JSON summary to stdout after completion | off |

Full flag list: `python .agents/skills/general-plot-digitizer/scripts/digitize_pipeline.py --help`

## Examples

| Scenario | Directory | Key Flags |
|----------|-----------|-----------|
| Single colored curve | [01-single-curve/](examples/01-single-curve/) | `--curve-color` |
| Multiple curves by color | [02-multi-curve-color/](examples/02-multi-curve-color/) | `--all-curves` |
| Black curve + text masking | [03-black-curve-text-mask/](examples/03-black-curve-text-mask/) | `--allow-black --smooth`, `text_regions` |
| Stacked spectra | [04-stacked-spectra/](examples/04-stacked-spectra/) | `--all-curves`, `per_curve_normalized` |

## Constraints

- **Bounding box** must enclose only the inner data region (inside axis lines, excluding labels/legend/title). VLMs often get this wrong — verify against the grid overlay.
- **Multi-curve:** Each curve in `curves[]` must have a `color_hint`. Auto-detect is unreliable with multiple traces.
- **Per-curve regions:** For stacked/offset plots, `curves[].region.y_min/y_max` must include generous padding (10-20px) above tallest peaks and below baseline.
- **Environments:** All scripts require `base-agent` conda env.

## Resources

- [resources/metadata_schema.json](resources/metadata_schema.json) — full metadata schema
- [scripts/vlm_prompt_template.txt](scripts/vlm_prompt_template.txt) — VLM prompt guidelines
- [scripts/suggest_colors.py](scripts/suggest_colors.py) — dominant color detection for unknown curve colors

## Related Skills

- [mat-xrd-digitizer](../mat-xrd-digitizer/SKILL.md): Peak-based XRD digitization for phase matching.

## References

- Gonzalez & Woods, *Digital Image Processing*, Pearson, 4th ed., 2018. Standard reference for HSV color-space segmentation, morphological operations, and connected-component analysis used in the extraction pipeline.
- Bradski, G., "The OpenCV Library", *Dr. Dobb's Journal of Software Tools*, 2000. Core CV library underlying all image manipulation in this skill.

---

**Author:** Jesus Diaz Sanchez
**Contact:** [GitHub @jdsanc](https://github.com/jdsanc)
