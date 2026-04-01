
from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Any, Callable, Literal, Sequence

import numpy as np
import plotly.graph_objects as go
from pymatgen.analysis.local_env import CrystalNN, NearNeighbors
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.core import PeriodicSite, Structure

from pymatviz.enums import ElemColorScheme, SiteCoords
from pymatviz.colors import ELEM_COLORS_VESTA
from pymatviz.structure.helpers import (
    NO_SYM_MSG,
    draw_bonds,
    draw_cell,
    draw_vector,
    get_atomic_radii,
    get_elem_colors,
    get_first_matching_site_prop,
    get_image_sites,
    generate_site_label,
    get_subplot_title,
)
from pymatviz.typing import ColorType
from plotly.subplots import make_subplots

# MatterViz Vesta colors (extracted from vesta-colors.json)
ELEM_COLORS_MATTERVIZ = {
    "Ac": "rgb(112, 171, 250)",
    "Ag": "rgb(192, 192, 192)",
    "Al": "rgb(129, 178, 214)",
    "Am": "rgb(84, 92, 242)",
    "Ar": "rgb(207, 254, 196)",
    "As": "rgb(116, 208, 87)",
    "At": "rgb(117, 79, 69)",
    "Au": "rgb(255, 209, 35)",
    "B": "rgb(31, 162, 15)",
    "Ba": "rgb(0, 201, 0)",
    "Be": "rgb(94, 215, 123)",
    "Bh": "rgb(224, 0, 56)",
    "Bi": "rgb(158, 79, 181)",
    "Bk": "rgb(138, 79, 227)",
    "Br": "rgb(126, 49, 2)",
    "C": "rgb(76, 76, 76)",
    "Ca": "rgb(90, 150, 189)",
    "Cd": "rgb(255, 217, 143)",
    "Ce": "rgb(255, 255, 199)",
    "Cf": "rgb(161, 54, 212)",
    "Cl": "rgb(49, 252, 2)",
    "Cm": "rgb(120, 92, 227)",
    "Co": "rgb(0, 0, 175)",
    "Cr": "rgb(0, 0, 158)",
    "Cs": "rgb(87, 23, 143)",
    "Cu": "rgb(34, 71, 220)",
    "Db": "rgb(209, 0, 79)",
    "Dy": "rgb(31, 255, 199)",
    "Er": "rgb(0, 230, 117)",
    "Es": "rgb(179, 31, 212)",
    "Eu": "rgb(97, 255, 199)",
    "F": "rgb(176, 185, 230)",
    "Fe": "rgb(181, 113, 0)",
    "Fm": "rgb(179, 31, 186)",
    "Fr": "rgb(66, 0, 102)",
    "Ga": "rgb(158, 227, 115)",
    "Gd": "rgb(69, 255, 199)",
    "Ge": "rgb(126, 110, 166)",
    "H": "rgb(255, 204, 204)",
    "He": "rgb(252, 232, 206)",
    "Hf": "rgb(77, 194, 255)",
    "Hg": "rgb(184, 184, 208)",
    "Ho": "rgb(0, 255, 156)",
    "Hs": "rgb(230, 0, 46)",
    "I": "rgb(148, 0, 148)",
    "In": "rgb(166, 117, 115)",
    "Ir": "rgb(23, 84, 135)",
    "K": "rgb(161, 33, 246)",
    "Kr": "rgb(250, 193, 243)",
    "La": "rgb(90, 196, 73)",
    "Li": "rgb(134, 223, 115)",
    "Lr": "rgb(199, 0, 102)",
    "Lu": "rgb(0, 171, 36)",
    "Md": "rgb(179, 13, 166)",
    "Mg": "rgb(251, 123, 21)",
    "Mn": "rgb(167, 8, 157)",
    "Mo": "rgb(84, 181, 181)",
    "Mt": "rgb(235, 0, 38)",
    "N": "rgb(176, 185, 230)",
    "Na": "rgb(249, 220, 60)",
    "Nb": "rgb(115, 194, 201)",
    "Nd": "rgb(199, 255, 199)",
    "Ne": "rgb(254, 55, 181)",
    "Ni": "rgb(183, 187, 189)",
    "No": "rgb(189, 13, 135)",
    "Np": "rgb(0, 128, 255)",
    "O": "rgb(254, 3, 0)",
    "Os": "rgb(38, 102, 150)",
    "P": "rgb(192, 156, 194)",
    "Pa": "rgb(0, 161, 255)",
    "Pb": "rgb(87, 89, 97)",
    "Pd": "rgb(0, 105, 133)",
    "Pm": "rgb(163, 255, 199)",
    "Po": "rgb(171, 92, 0)",
    "Pr": "rgb(217, 255, 199)",
    "Pt": "rgb(208, 208, 224)",
    "Pu": "rgb(0, 107, 255)",
    "Ra": "rgb(0, 125, 0)",
    "Rb": "rgb(112, 46, 176)",
    "Re": "rgb(38, 125, 171)",
    "Rf": "rgb(204, 0, 89)",
    "Rh": "rgb(10, 125, 140)",
    "Rn": "rgb(66, 130, 150)",
    "Ru": "rgb(36, 143, 143)",
    "S": "rgb(255, 250, 0)",
    "Sb": "rgb(158, 99, 181)",
    "Sc": "rgb(181, 99, 171)",
    "Se": "rgb(154, 239, 15)",
    "Sg": "rgb(217, 0, 69)",
    "Si": "rgb(27, 59, 250)",
    "Sm": "rgb(143, 255, 199)",
    "Sn": "rgb(154, 142, 185)",
    "Sr": "rgb(0, 255, 0)",
    "Ta": "rgb(77, 166, 255)",
    "Tb": "rgb(48, 255, 199)",
    "Tc": "rgb(59, 158, 158)",
    "Te": "rgb(212, 122, 0)",
    "Th": "rgb(0, 186, 255)",
    "Ti": "rgb(120, 202, 255)",
    "Tl": "rgb(166, 84, 77)",
    "Tm": "rgb(0, 212, 82)",
    "U": "rgb(0, 143, 255)",
    "V": "rgb(229, 25, 0)",
    "W": "rgb(33, 148, 214)",
    "Xe": "rgb(66, 158, 176)",
    "Y": "rgb(148, 255, 255)",
    "Yb": "rgb(0, 191, 56)",
    "Zn": "rgb(143, 143, 129)",
    "Zr": "rgb(0, 255, 0)",
}


def draw_site_custom(
    fig: go.Figure,
    site: PeriodicSite,
    coords: np.ndarray,
    site_idx: int,
    site_labels: Any,
    _elem_colors: dict[str, ColorType],
    _atomic_radii: dict[str, float],
    atom_size: float,
    scale: float,
    site_kwargs: dict[str, Any],
    *,
    is_image: bool = False,
    is_3d: bool = False,
    row: int | None = None,
    col: int | None = None,
    scene: str | None = None,
    hover_text: SiteCoords | Callable[[PeriodicSite], str] = SiteCoords.cartesian_fractional,
    **kwargs: Any,
) -> None:
    """Add a site (regular or image) to the plot with custom 3D lighting."""
    species = getattr(site, "specie", site.species)
    # Handle Composition objects (disordered structures)
    # Use symbol of majority species for radius lookup
    symbol = species.elements[0].symbol if hasattr(species, "elements") else species.symbol
    
    site_radius = _atomic_radii.get(symbol, 1.0) * scale
    color = _elem_colors.get(symbol, "gray")

    # Build hover text manually to avoid pymatviz species_string incompatibility
    coords_cart = site.coords
    coords_frac = site.frac_coords if hasattr(site, "frac_coords") else None
    hover_parts = [f"<b>{symbol}</b>"]
    hover_parts.append(f"Cart: ({coords_cart[0]:.3f}, {coords_cart[1]:.3f}, {coords_cart[2]:.3f})")
    if coords_frac is not None:
        hover_parts.append(f"Frac: ({coords_frac[0]:.3f}, {coords_frac[1]:.3f}, {coords_frac[2]:.3f})")
    site_hover_text = "<br>".join(hover_parts)

    # Re-derive majority species for label generation if needed, or just pass species
    # Helpers.generate_site_label expects majority_species (Species object)
    # Let's simplify and use species directly if it's a Species, else majority.
    if hasattr(species, "elements"): # Composition
         majority_species = max(species, key=species.get)
    else:
         majority_species = species

    txt = generate_site_label(site_labels, site_idx, site)

    # Custom marker settings for 3D sphere look
    marker = dict(
        size=site_radius * atom_size,
        color=color,
        opacity=1.0 if not is_image else 0.6, # Make images more transparent
        line=dict(width=0), # Remove outline for 3D effect
    )
    marker.update(site_kwargs)

    # Calculate text color based on background color (pymatviz helper uses picking function, we skip for now or import)
    # from pymatviz.utils.plotting import pick_max_contrast_color
    # text_color = pick_max_contrast_color(color)
    text_color = "black" # Default or compute if really needed

    scatter_kwargs = dict(
        x=[coords[0]],
        y=[coords[1]],
        mode="markers+text" if txt else "markers",
        marker=marker,
        text=txt,
        textposition="middle center",
        # textfont=dict(color=text_color, size=...),
        hoverinfo="text" if hover_text else None,
        hovertext=site_hover_text,
        hoverlabel=dict(namelength=-1),
        name=f"Image of {majority_species!s}" if is_image else str(majority_species),
        showlegend=False,
    )
    scatter_kwargs.update(kwargs)

    if is_3d:
        scatter_kwargs["z"] = [coords[2]]
        # Scatter3d markers don't accept custom lighting dict, but line=0 helps 3D look
        fig.add_scatter3d(**scatter_kwargs, scene=scene)
    else:
        fig.add_scatter(**scatter_kwargs, row=row, col=col)


def structure_3d_custom(
    struct: Structure | Sequence[Structure],
    *,
    atomic_radii: float | dict[str, float] | None = None,
    atom_size: float = 5, # Reduced for multi-view layout
    elem_colors: ElemColorScheme | dict[str, ColorType] = ELEM_COLORS_MATTERVIZ,
    scale: float = 1,
    show_unit_cell: bool | dict[str, Any] = True,
    show_sites: bool | dict[str, Any] = True,
    show_image_sites: bool | dict[str, Any] = False, # Disabled for cleaner multi-view
    show_bonds: bool | NearNeighbors = True, # Enable bonds by default
    site_labels: Literal["symbol", "species", False] | dict[str, str] | Sequence[str] = "symbol",
    standardize_struct: bool | None = None,
    n_cols: int = 3, # Only used if struct is a sequence
    subplot_title: Callable[[Structure, str | int], str | dict[str, Any]] | None | Literal[False] = None,
    show_site_vectors: str | Sequence[str] = ("force", "magmom"),
    vector_kwargs: dict[str, dict[str, Any]] | None = None,
    hover_text: SiteCoords | Callable[[PeriodicSite], str] = SiteCoords.cartesian_fractional,
    bond_kwargs: dict[str, Any] | None = None,
) -> go.Figure:
    """Plot pymatgen structures in 3D with Plotly using custom styling."""
    
    # If single structure, use 2x2 multi-view layout
    if isinstance(struct, Structure):
        # We will create 4 copies of the struct for the 4 views
        # But we can just iterate 4 times
        n_rows, n_cols = 2, 2
        structs = [struct] * 4
        specs = [[{"type": "scene"}] * n_cols] * n_rows
        # No subplot titles - save space and use main title + axes labels instead
        fig = make_subplots(
            rows=n_rows,
            cols=n_cols,
            specs=specs,
            horizontal_spacing=0.0,  # Zero spacing
            vertical_spacing=0.0,    # Zero spacing
        )
    else:
        # Sequence of structures (legacy/batch mode)
        structs = list(struct) if not isinstance(struct, Structure) else [struct]
        if standardize_struct:
            structs = [s.get_primitive_structure() if standardize_struct is True else s for s in structs]
        n_rows = (len(structs) - 1) // n_cols + 1
        specs = [[{"type": "scene"}] * n_cols] * n_rows
        fig = make_subplots(
            rows=n_rows,
            cols=n_cols,
            specs=specs,
            subplot_titles=[f"{i+1}. {s.formula}" for i, s in enumerate(structs)],
        )

    # Default bond kwargs to look better
    default_bond_kwargs = dict(width=5, color=True) # Thicker bonds (relative to smaller atoms)
    if bond_kwargs:
        default_bond_kwargs.update(bond_kwargs)
    bond_kwargs = default_bond_kwargs

    _elem_colors = get_elem_colors(elem_colors)
    _atomic_radii = get_atomic_radii(atomic_radii)

    if isinstance(show_site_vectors, str):
        show_site_vectors = [show_site_vectors]

    # Determine vector_prop once for all structures if it's a sequence, or for the single structure
    vector_prop = get_first_matching_site_prop(
        list(structs) if not isinstance(struct, Structure) else [struct],
        show_site_vectors,
        warn_if_none=show_site_vectors != ("force", "magmom"),
        filter_callback=lambda _prop, value: (np.array(value).shape or [None])[-1] == 3,
    )


    for idx, struct_i in enumerate(structs):
        row = (idx // n_cols) + 1
        col = (idx % n_cols) + 1
        
        # We need to call drawing functions with row/col or scene name.
        scene_name = f"scene{idx+1}" if idx > 0 else "scene"

        plotted_sites_coords: set[tuple[float, float, float]] = set()

        if show_image_sites and show_sites:
            for site_idx, site in enumerate(struct_i):
                image_atoms = get_image_sites(site, struct_i.lattice)
                if len(image_atoms) > 0:
                    for image_coords in image_atoms:
                        plotted_sites_coords.add(tuple(image_coords))
                        draw_site_custom(
                            fig,
                            site,
                            image_coords,
                            site_idx,
                            site_labels,
                            _elem_colors,
                            _atomic_radii,
                            atom_size,
                            scale,
                            {} if show_image_sites is True else show_image_sites,
                            is_image=True,
                            is_3d=True,
                            scene=scene_name,
                        )

        if show_bonds:
            draw_bonds(
                fig=fig,
                structure=struct_i,
                nn=CrystalNN() if show_bonds is True else show_bonds,
                is_3d=True,
                bond_kwargs=bond_kwargs,
                scene=scene_name,
                plotted_sites_coords=plotted_sites_coords,
                elem_colors=_elem_colors,
            )

        # Plot atoms and vectors
        if show_sites:
            for site_idx, site in enumerate(struct_i):
                draw_site_custom(
                    fig,
                    site,
                    site.coords,
                    site_idx,
                    site_labels,
                    _elem_colors,
                    _atomic_radii,
                    atom_size,
                    scale,
                    {} if show_sites is True else show_sites,
                    is_3d=True,
                    scene=scene_name,
                    name=f"site{site_idx}",
                    hover_text=hover_text,
                )

                if vector_prop:
                    vector = None
                    if vector_prop in site.properties:
                        vector = np.array(site.properties[vector_prop])
                    elif vector_prop in struct_i.properties:
                        vector = struct_i.properties[vector_prop][site_idx]

                    if vector is not None and np.any(vector):
                        draw_vector(
                            fig,
                            site.coords,
                            vector,
                            is_3d=True,
                            arrow_kwargs=(vector_kwargs or {}).get(vector_prop, {}),
                            scene=scene_name,
                            name=f"vector{site_idx}",
                        )

        if show_unit_cell:
            # MatterViz defaults: color specific gray, width 1.5 (scaled)
            # We use gray and width 3 for visibility
            uc_kwargs = dict(color="gray", width=3)
            if isinstance(show_unit_cell, dict):
                uc_kwargs.update(show_unit_cell)
            
            draw_cell(
                fig,
                struct_i,
                cell_kwargs=uc_kwargs,
                is_3d=True,
                scene=scene_name,
            )

    # Update 3D scene properties - hide axes for clean visualization
    axes_kwargs = dict(
        showticklabels=False, showgrid=False, zeroline=False, visible=False
    )
    
    # Common scene layout
    scene_base = dict(
        xaxis=axes_kwargs,
        yaxis=axes_kwargs,
        zaxis=axes_kwargs,
        aspectmode="data",
        bgcolor="rgba(0,0,0,0)",
        camera=dict(projection=dict(type="orthographic")),
    )

    # Update all scenes first
    fig.update_scenes(patch=scene_base)

    # Now apply specific camera angles if we are in single-structure multi-view mode
    if isinstance(struct, Structure):
        # View 1 (Top-Left): Along a-axis (looking from x)
        # In Plotly, eye=(x,y,z). If a is x-axis, we want large x.
        camera_a = dict(eye=dict(x=2, y=0, z=0), up=dict(x=0, y=0, z=1))
        
        # View 2 (Top-Right): Along b-axis (looking from y)
        camera_b = dict(eye=dict(x=0, y=2, z=0), up=dict(x=0, y=0, z=1))
        
        # View 3 (Bottom-Left): Along c-axis (looking from z)
        camera_c = dict(eye=dict(x=0, y=0, z=2), up=dict(x=0, y=1, z=0))
        
        # View 4 (Bottom-Right): Default perspective (angular)
        camera_d = dict(eye=dict(x=1.25, y=1.25, z=1.25))

        # Update specific scenes
        # scene1 (1,1), scene2 (1,2), scene3 (2,1), scene4 (2,2)
        fig.update_layout(scene_camera=camera_a) # scene 1
        # For other scenes, property is sceneN_camera
        fig.update_layout(scene2=dict(camera=camera_b))
        fig.update_layout(scene3=dict(camera=camera_c))
        fig.update_layout(scene4=dict(camera=camera_d))
        # Note: fig.update_layout(scene2_camera=...) might not work directly for some versions
        # Standard way is scene2=dict(...)

    # Layout updates
    # Larger dimensions for 2x2 grid to maximize subplot sizes
    fig.layout.height = 1400 if isinstance(struct, Structure) else 400 * n_rows
    fig.layout.width = 1400 if isinstance(struct, Structure) else 400 * n_cols
    fig.layout.showlegend = False
    fig.layout.paper_bgcolor = "rgba(0,0,0,0)"
    fig.layout.plot_bgcolor = "rgba(0,0,0,0)"
    # Minimal margins to maximize subplot area (no bottom margin needed without subplot titles)
    fig.layout.margin = dict(l=5, r=5, t=60, b=5)
    
    # Add structure metadata and axis labels for single-structure multi-view
    if isinstance(struct, Structure):
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            sga = SpacegroupAnalyzer(struct)
            spacegroup = sga.get_space_group_symbol()
        except Exception:
            spacegroup = "Unknown"
        
        formula = struct.composition.reduced_formula
        title_text = f"{formula} | Space Group: {spacegroup} | Views: a-axis, b-axis, c-axis, Default"
        fig.layout.title = dict(
            text=title_text,
            x=0.5,
            xanchor='center',
            font=dict(size=16)
        )

    return fig
