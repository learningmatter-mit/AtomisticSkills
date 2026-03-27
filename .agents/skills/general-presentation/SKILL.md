---
name: general-presentation
description: Generate and iteratively refine PowerPoint presentations from simulation results using python-pptx.
category: [general]
---

# Presentation Generation

## Goal

Create professional PowerPoint presentations from simulation results (plots, tables, parameters) using `python-pptx`. The agent writes standalone Python scripts using a helper library, enabling direct iteration with the user on the script to refine slides.

## Instructions

### 1. Import the Helper Library

All scripts should import `slide_utils` from this skill:

```python
# Env: base-agent
import sys
sys.path.insert(0, ".agents/skills/general-presentation/scripts")
from slide_utils import *
```

### 2. Build Slides Using Helper Functions

Available functions:

| Function | Purpose |
|---|---|
| `create_presentation(title, subtitle, author)` | Create a new presentation with a styled title slide |
| `add_title_slide(prs, title, subtitle)` | Additional title/divider slides |
| `add_section_slide(prs, title)` | Section divider (colored background) |
| `add_image_slide(prs, title, image_path, caption, notes)` | Single image/plot slide |
| `add_two_image_slide(prs, title, left_img, right_img, ...)` | Side-by-side images |
| `add_image_and_text_slide(prs, title, image_path, text, ...)` | Image + text layout |
| `add_table_slide(prs, title, headers, rows)` | Data table slide |
| `add_bullets_slide(prs, title, bullets)` | Bullet point slide |
| `add_autofit_box(slide, left, top, height, text, bg_color)` | Add a colored box that auto-scales width to text |
| `save_presentation(prs, path)` | Save to `.pptx` file |

Every builder function returns the `Slide` (or Shape) object, allowing further customization with raw `python-pptx` calls if needed.

### 3. Customize the Theme (Optional)

Override the `THEME` dictionary before building slides:

```python
from slide_utils import *
THEME["primary"] = RGBColor(0x00, 0x50, 0x80)
THEME["font_family"] = "Arial"
```

### 4. Save and Iterate Visually

```python
save_presentation(prs, "output.pptx")
```

The agent edits the Python script and re-runs to reflect changes. 
**CRITICAL ITERATION LOOP**: The agent **MUST** visually inspect the generated slides using their VLM capabilities to ensure elements do not overlap, text fits perfectly within boxes, and the slide space is used efficiently with a universal, professional design style.

To preview a slide as an image for visual inspection:
```bash
# Render PPTX to PDF using LibreOffice, then to PNG
libreoffice --headless --convert-to pdf output.pptx --outdir .
pdftocairo -png output.pdf output
# This generates output-1.png, which you can visually inspect.
```

## Examples

Generating a simulation report:

```python
# Env: base-agent
import sys
sys.path.insert(0, ".agents/skills/general-presentation/scripts")
from slide_utils import *

prs = create_presentation("LiFePO4 Stability", "MACE-MP Results", "Research Agent")
add_image_slide(prs, "Phonon DOS", "phonon_dos.png", caption="No imaginary modes observed")
add_table_slide(prs, "Parameters", ["Param", "Value"], [["Model", "MACE-MP"], ["fmax", "0.02 eV/A"]])
add_bullets_slide(prs, "Conclusions", ["Dynamically stable", "E_hull = 0 meV/atom"])
save_presentation(prs, "LiFePO4_report.pptx")
```

See [amorphorization example](examples/amorphorization/) for a complete runnable example with structure images, tables, and RDF plots.

## Constraints

- **Environment**: Scripts require `base-agent` with `python-pptx` installed.
- **Image formats**: PNG, JPG, BMP, GIF, TIFF supported.
- **Slide dimensions**: Default 16:9 (13.333 × 7.5 inches). Override via `THEME["width"]` / `THEME["height"]`.
- **Tables**: Large tables (>15 rows) may overflow the slide — split across multiple slides.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
