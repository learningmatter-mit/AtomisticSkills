"""
Generate a presentation about the mat-amorphorization skill example (LiCl).

Usage:
    # Env: base-agent
    python .agents/skills/general-presentation/examples/amorphorization/amorphorization_slides.py

Requirements:
    - Conda environment: base-agent
    - Required packages: python-pptx, Pillow
"""

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, ".agents", "skills", "general-presentation", "scripts"))
from slide_utils import (
    create_presentation,
    add_image_slide,
    add_table_slide,
    add_bullets_slide,
    add_section_slide,
    add_image_and_text_slide,
    save_presentation,
    THEME,
    RGBColor,
)


# Paths
EXAMPLE_DIR = os.path.join(
    PROJECT_ROOT, ".agents", "skills",
    "mat-amorphorization", "examples", "LiCl",
)
RDF_PLOT = os.path.join(EXAMPLE_DIR, "rdf_plot.png")
CRYST_IMG = os.path.join(os.path.dirname(__file__), "LiCl_crystalline.png")
AMORPH_IMG = os.path.join(os.path.dirname(__file__), "LiCl_amorphous.png")

OUTPUT = os.path.join(os.path.dirname(__file__), "amorphorization_skill_demo.pptx")


def main() -> None:
    """Build a presentation describing the amorphorization skill with LiCl example."""

    prs = create_presentation(
        title="Amorphorization Skill",
        subtitle="Generating amorphous structures via melt-quench MD",
        author="AtomisticSkills",
    )

    # --- Slide: Overview ---
    add_bullets_slide(
        prs,
        title="What is Amorphorization?",
        bullets=[
            "Goal: Generate disordered, amorphous structures from crystalline inputs",
            "Method: Melt-quench molecular dynamics protocol using MLIPs",
            "Use case: Study properties of glasses, amorphous electrolytes, coatings",
            "Tools: MACE / CHGNet foundation potentials + MCP run_md tool",
        ],
    )

    # --- Slide: Protocol ---
    add_section_slide(prs, "Melt-Quench Protocol")

    add_table_slide(
        prs,
        title="3-Stage Melt-Quench Protocol",
        headers=["Stage", "Temperature", "Duration", "Thermostat", "Purpose"],
        rows=[
            ["1. Melting", "3000 K", "10 ps (5000 steps)", "NVT Langevin", "Destroy crystalline order"],
            ["2. Quenching", "3000 K -> 300 K", "10 ps (5000 steps)", "NVT Langevin", "Freeze disordered state"],
            ["3. Equilibration", "300 K", "5 ps (2500 steps)", "NVT Bussi", "Relax to equilibrium"],
        ],
    )

    add_bullets_slide(
        prs,
        title="Key Parameters",
        bullets=[
            "Supercell: >100 atoms to avoid periodicity artifacts",
            "Melt temperature: ~1000 K above experimental melting point",
            "Cooling rate: 1-10 K/ps (typical MD quench rate)",
            "Final step: Static relaxation (0 K) to find local energy minimum",
            "Timestep: 2 fs throughout all stages",
        ],
    )

    # --- Slide: LiCl Example ---
    add_section_slide(prs, "Example: LiCl Amorphorization")

    add_table_slide(
        prs,
        title="LiCl Example — Setup",
        headers=["Parameter", "Value"],
        rows=[
            ["Material", "LiCl (Lithium Chloride)"],
            ["Starting structure", "Crystalline rocksalt (Fm-3m)"],
            ["Supercell", "3 x 3 x 2 expansion (~108 atoms)"],
            ["MLIP Model", "MACE-OMAT-0-small"],
            ["Crystalline density", "2.07 g/cm3"],
        ],
    )

    # --- Slide: Structure Visualizations ---
    if os.path.isfile(CRYST_IMG):
        add_image_slide(
            prs,
            title="Crystalline LiCl — Rocksalt Structure",
            image_path=CRYST_IMG,
            caption="3x3x2 supercell (~108 atoms), Fm-3m space group",
        )

    if os.path.isfile(AMORPH_IMG):
        add_image_slide(
            prs,
            title="Amorphous LiCl — After Melt-Quench",
            image_path=AMORPH_IMG,
            caption="Disordered structure after 3-stage melt-quench protocol",
        )

    # --- Slide: RDF Analysis ---
    add_image_slide(
        prs,
        title="Radial Distribution Function (RDF) — Confirms Amorphous State",
        image_path=RDF_PLOT,
        caption="Sharp first peak (Li-Cl at ~2.4 A) with no long-range periodicity",
        notes="The RDF confirms amorphous nature: first peak preserves local bonding, but peaks decay to 1.0 beyond second neighbor shell.",
    )

    # --- Slide: Results Summary ---
    add_table_slide(
        prs,
        title="LiCl Results — Crystalline vs. Amorphous",
        headers=["Property", "Crystalline", "Amorphous"],
        rows=[
            ["Density", "2.07 g/cm3", "1.66 g/cm3"],
            ["Coordination Number", "6 (rocksalt)", "~4 (open network)"],
            ["Long-range order", "Yes (sharp RDF peaks)", "No (peaks decay to 1)"],
            ["Structure type", "Periodic lattice", "Disordered network"],
        ],
    )

    # --- Slide: Takeaways ---
    add_bullets_slide(
        prs,
        title="Summary & Takeaways",
        bullets=[
            "Melt-quench protocol successfully generates amorphous LiCl",
            "20% density reduction from crystalline to amorphous state",
            "Coordination number drops from 6 to ~4, reflecting open network",
            "RDF analysis confirms complete loss of long-range order",
            "Protocol generalizes to other materials (oxides, sulfides, etc.)",
            "Analysis tools: RDF + coordination number via analyze_amorphous.py",
        ],
    )

    save_presentation(prs, OUTPUT)
    print(f"Slides: {len(prs.slides)}")


if __name__ == "__main__":
    main()
