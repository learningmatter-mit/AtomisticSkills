---
name: mat-xrd-digitizer
description: Digitize an image of an XRD plot into a numeric .xy data file by extracting visual peaks.
category: [materials]
---

# XRD Digitizer

## Goal

To convert an image or screenshot of an X-Ray Diffraction (XRD) pattern into a digitized, numeric `.xy` data file, which can then be used by downstream analysis tools like `mat-xrd-phase-analysis`. 

This skill leverages the AI Agent's built-in Vision/Language Model (VLM) capabilities. The Agent will visually parse the provided image to extract key peak positions (2-theta) and approximate relative intensities, and then use a provided script to mathematically generate a representative pseudo-Voigt profile.

## Instructions

### 1. Extract Peaks Visually

Provide the agent with an image (e.g., screenshot) of the XRD plot. The agent will visually inspect the plot and identify the coordinates of the major peaks.

**Handling Multiple Curves/Colors:**
If the image contains multiple XRD patterns, the user should specify which curve to digitize by its color, label, or position (e.g., *"digitize the red curve"* or *"digitize the curve labeled 'sample A'"*). The agent will then selectively extract peaks from only that specific curve.

**Agent Action:** The agent should:
1. Create a JSON file (e.g., `peaks.json`) containing the extracted peaks as an array of objects for the target curve. **CRITICAL: You must ensure every single visible peak, including the tiny minor peaks, is reported and digitized to ensure accurate full-profile refinement downstream.**
2. Save a copy of the original image (e.g., `original_plot.png`) in the same directory as the JSON file for future reference.

Example `peaks.json` format:
```json
[
  {"2theta": 8.8, "intensity": 0.05, "fwhm": 0.3},
  {"2theta": 15.8, "intensity": 0.08, "fwhm": 0.3},
  {"2theta": 33.1, "intensity": 1.00, "fwhm": 0.3}
]
```
*Note: `intensity` should be normalized between 0 and 1.0 (where the highest peak is 1.0). `fwhm` defaults to 0.3.*

### 2. Generate the Digitized `.xy` File

Use the provided script to generate the experimental `.xy` file based on the extracted peaks.

```bash
# Env: base-agent
python .agents/skills/mat-xrd-digitizer/scripts/digitize_plot.py peaks.json --output digitized_plot.xy --min-x 5.0 --max-x 80.0
```

**Parameters:**
- `input`: The JSON file containing the extracted peak parameters.
- `--output`: Path to save the resulting `.xy` file.
- `--min-x`: Minimum 2-theta value to generate (default: 5.0).
- `--max-x`: Maximum 2-theta value to generate (default: 90.0).
- `--points`: Number of data points in the `.xy` file (default: 4000).
- `--noise`: Amplitude of experimental noise to add (default: 0.01).
- `--background`: Amplitude of exponential background baseline (default: 0.05).

## Examples

For a full working example of extracting and digitizing a YBCO plot:
See [`examples/digitize-ybco/README.md`](examples/digitize-ybco/README.md).

```bash
# Env: base-agent
python .agents/skills/mat-xrd-digitizer/scripts/digitize_plot.py .agents/skills/mat-xrd-digitizer/examples/digitize-ybco/peaks.json --output test_ybco.xy
```

## Constraints

- **Approximation:** The digitized plot is a mathematical approximation using pseudo-Voigt profiles. It does not perfectly recreate the exact pixel-by-pixel raw data of the original scan, but it is highly effective for downstream phase matching tools.
- **Vision Accuracy:** The accuracy of the 2-theta positions entirely depends on the clarity of the provided image axes.
- **Environments:** Scripts require the `base-agent` Conda environment. **Each code block MUST specify the environment.**

## References

- Pseudo-Voigt profile generation is standard practice in XRD peak fitting (e.g., Rietveld refinement tools).

## Related Skills

- [mat-xrd-phase-analysis](../mat-xrd-phase-analysis/SKILL.md): Use the generated `.xy` file to identify the material phases.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
