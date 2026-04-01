# Amorphorization Skill — Presentation Example

Demonstrates using `slide_utils.py` to generate a 12-slide presentation
summarizing the **mat-amorphorization** skill with LiCl as the example material.

## Files

| File | Description |
|------|-------------|
| `amorphorization_slides.py` | Script that builds the presentation |
| `amorphorization_skill_demo.pptx` | Generated output (12 slides) |
| `LiCl_crystalline.png` | Structure visualization (crystalline rocksalt) |
| `LiCl_amorphous.png` | Structure visualization (amorphous after melt-quench) |

## Usage

```bash
# Env: base-agent
conda run -n base-agent python .agents/skills/general-presentation/examples/amorphorization/amorphorization_slides.py
```

## Slide Contents

1. Title slide
2. What is Amorphorization? (bullets)
3. Section: Melt-Quench Protocol
4. 3-Stage protocol table
5. Key parameters (bullets)
6. Section: LiCl Example
7. LiCl setup table
8. Crystalline structure image
9. Amorphous structure image
10. RDF analysis plot
11. Crystalline vs. Amorphous comparison table
12. Summary & Takeaways (bullets)

## Dependencies

- `python-pptx`, `Pillow` (installed in `base-agent`)
- Structure images generated via `mcp_base_visualize_structure`
- RDF plot from `mat-amorphorization/examples/LiCl/rdf_plot.png`
