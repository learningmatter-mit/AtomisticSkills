"""
Perform Rietveld refinement with known phases using DARA.

This script wraps DARA's RefinementMaker to perform Rietveld refinement
Based on the DARA tutorial: https://cedergrouphub.github.io/dara/notebooks/automated_refinement.html
on observed XRD patterns with provided candidate phases.

Usage:
    python refine.py --xrd_data pattern.xy --cifs phase1.cif phase2.cif --output_dir results/

Requirements:
    - Conda environment: xrd-agent
    - Required packages: dara-xrd, pymatgen
"""

import argparse
import json
from pathlib import Path
from typing import List, Optional

try:
    from dara.refine import do_refinement_no_saving
except ImportError:
    raise ImportError(
        "DARA is not installed. Install with: pip install dara-xrd\n"
        "See https://idocx.github.io/dara/install.html for details."
    )
import warnings
warnings.simplefilter("ignore", DeprecationWarning)

def refine(
    xrd_data_path: str,
    cif_paths: Optional[List[str]] = None,
    instrument_profile: str = "Aeris-fds-Pixcel1d-Medipix3",
    phase_params: Optional[dict] = None,
    refinement_params: Optional[dict] = None,
    show_progress: bool = True,
    save_html: bool = False,
):
    """
    Perform Rietveld refinement with known phases.
    
    Args:
        xrd_data_path: Path to experimental XRD pattern (.xy .xrdml or .raw format)
        cif_paths: List of CIF file paths, or None to auto-discover from cifs/ or XRD directory
        instrument_profile: Instrument profile name
        phase_params: Phase-specific refinement parameters
        refinement_params: General refinement parameters
        show_progress: Print progress information
        
    Returns:
        RefinementDocument with refinement results
    """
    xrd_path = Path(xrd_data_path)
    if not xrd_path.exists():
        raise FileNotFoundError(f"XRD data file not found: {xrd_path}")
    
    output_path = Path(xrd_path.parent / "refinement_results")
    output_path.mkdir(parents=True, exist_ok=True)

    # Resolve CIF paths: use provided list, or discover from cifs/ subdir or XRD directory
    if cif_paths:
        resolved_cif_paths = [str(Path(p).resolve()) for p in cif_paths]
    else:
        parent = xrd_path.parent
        cifs_dir = parent / "cifs"
        if cifs_dir.is_dir():
            discovered = sorted(cifs_dir.glob("*.cif"))
        else:
            discovered = sorted(parent.glob("*.cif"))
        if not discovered:
            raise FileNotFoundError(
                "No CIF files found in the XRD directory or in a 'cifs/' subfolder."
            )
        resolved_cif_paths = [str(p) for p in discovered]
    for p in resolved_cif_paths:
        if not Path(p).exists():
            raise FileNotFoundError(f"CIF file not found: {p}")

    # Run refinement via DARA
    result = do_refinement_no_saving(
        pattern_path=xrd_path,
        phases=resolved_cif_paths,
        instrument_profile=instrument_profile,
        phase_params=phase_params,
        refinement_params=refinement_params,
        show_progress=show_progress,
    )

    # Generate visualization using DARA's Plotly backend
    stem = "refinement"
    if getattr(result, "lst_data", None) is not None:
        pattern_name = getattr(result.lst_data, "pattern_name", "")
        if pattern_name:
            stem = Path(pattern_name).stem.replace("_xrd", "")
    stem_dir = output_path / stem
    stem_dir.mkdir(parents=True, exist_ok=True)
    html_path = stem_dir / f"{stem}_refinement.html"
    png_path = stem_dir / f"{stem}_refinement.png"
    png_saved: Optional[Path] = None
    try:
        fig = result.visualize()
        
        # Apply standard plotly formatting based on plot-standards.md
        fig.update_layout(
            width=600,
            height=400,
            font=dict(size=14, color="black"),
            legend=dict(
                x=0.99,
                y=0.99,
                xanchor="right",
                yanchor="top",
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="black",
                borderwidth=1
            ),
            margin=dict(l=60, r=20, t=20, b=60),
        )
        
        # Make axes titles bold
        fig.update_xaxes(title_text="<b>" + str(fig.layout.xaxis.title.text) + "</b>", title_font=dict(size=14, color="black"))
        fig.update_yaxes(title_text="<b>" + str(fig.layout.yaxis.title.text) + "</b>", title_font=dict(size=14, color="black"))

        if save_html:
            fig.write_html(str(html_path))
        try:
            fig.write_image(str(png_path), scale=2)
            png_saved = png_path
        except Exception as e:
            print(f"Warning: could not save PNG (install kaleido for PNG: pip install kaleido): {e}")
        try:
            svg_path = png_path.with_suffix('.svg')
            fig.write_image(str(svg_path))
        except Exception as e:
            print(f"Warning: could not save SVG: {e}")
    except Exception as e:
        print(f"Warning: failed to create refinement plot: {e}")

    # Export peak_data (simulated peaks in the calculated pattern) as CSV.
    peak_data_path = stem_dir / f"{stem}_peak_data.csv"
    if getattr(result, "peak_data", None) is not None:
        result.peak_data.to_csv(peak_data_path, index=False)
    else:
        peak_data_path = None
        
    # Export curve_data (x, y_obs, y_calc, background, individual phases) as CSV.
    curve_data_path = stem_dir / f"{stem}_curve_data.csv"
    if getattr(result, "plot_data", None) is not None:
        import pandas as pd
        curve_dict = {
            "x": result.plot_data.x,
            "y_obs": result.plot_data.y_obs,
            "y_calc": result.plot_data.y_calc,
            "y_bkg": result.plot_data.y_bkg,
        }
        for phase_name, phase_y in result.plot_data.structs.items():
            curve_dict[f"struct_{phase_name}"] = phase_y
        pd.DataFrame(curve_dict).to_csv(curve_data_path, index=False)
    else:
        curve_data_path = None

    # Extract lattice parameters and related phase info from lst_data.
    phases_summary = []
    lst = getattr(result, "lst_data", None)

    def _to_list_or_value(v):
        if v is None:
            return None
        try:
            return list(v)
        except TypeError:
            return v

    if lst is not None:
        phases_results = getattr(lst, "phases_results", {}) or {}
        for phase_name, pr in phases_results.items():
            phases_summary.append(
                {
                    "name": phase_name,
                    "gewicht": _to_list_or_value(getattr(pr, "gewicht", None)),
                    "lattice": {
                        "a": _to_list_or_value(getattr(pr, "a", None)),
                        "b": _to_list_or_value(getattr(pr, "b", None)),
                        "c": _to_list_or_value(getattr(pr, "c", None)),
                        "alpha": _to_list_or_value(getattr(pr, "alpha", None)),
                        "beta": _to_list_or_value(getattr(pr, "beta", None)),
                        "gamma": _to_list_or_value(getattr(pr, "gamma", None)),
                    },
                }
            )

    # Save results summary (Rwp, lattice parameters, and plot locations)
    results_summary = {
        "rwp": lst.rwp if lst is not None else None,
        "refined_cif": str(result.cif) if getattr(result, "cif", None) is not None else None,
        "instrument_profile": instrument_profile,
        "phase_params": phase_params,
        "refinement_params": refinement_params,
        "phases": phases_summary,
        "plots": {
            "html": str(html_path) if save_html else None,
            "png": str(png_saved) if png_saved is not None else None,
        },
        "peak_data": str(peak_data_path) if peak_data_path is not None else None,
    }
    summary_path = stem_dir / "refinement_result.json"
    with open(summary_path, "w") as f:
        json.dump(results_summary, f, indent=2)
    
    print(f"\nRefinement completed!")
    if lst is not None and lst.rwp is not None:
        print(f"R_wp: {lst.rwp:.2f}%")
    else:
        print("R_wp: unavailable (no lst_data.rwp in result)")
    print(f"\nResults saved to: {stem_dir}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Perform Rietveld refinement with known phases using DARA"
    )
    parser.add_argument(
        "--xrd_data",
        required=True,
        help="Path to experimental XRD pattern file (.xy .xrdml or .raw format)"
    )
    parser.add_argument(
        "--cifs",
        nargs="*",
        default=None,
        help="Paths to CIF files. If not provided, CIFs are auto-discovered from the XRD directory or from a 'cifs/' subfolder (e.g. examples/LiFePO4/cifs/)."
    )
    parser.add_argument(
        "--instrument_profile",
        default="Aeris-fds-Pixcel1d-Medipix3",
        help="Instrument profile name (default: Aeris-fds-Pixcel1d-Medipix3)"
    )
    parser.add_argument(
        "--phase_params",
        help="Path to JSON file with phase-specific refinement parameters"
    )
    parser.add_argument(
        "--refinement_params",
        help="Path to JSON file with general refinement parameters"
    )
    parser.add_argument(
        "--bgmn_dir",
        help="Path to local BGMNwin directory (avoids network download on HPC/login nodes). "
             "Alternatively set DARA_BGMN_DIR."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )
    parser.add_argument(
        "--save_html",
        action="store_true",
        help="Save interactive HTML plot of the refinement (can be large)"
    )
    
    args = parser.parse_args()
    
    # Load parameters if provided (no defaults: let DARA/BGMN use its own)
    phase_params = None
    if args.phase_params:
        with open(args.phase_params) as f:
            phase_params = json.load(f)

    refinement_params = None
    if args.refinement_params:
        with open(args.refinement_params) as f:
            refinement_params = json.load(f)
    
    refine(
        xrd_data_path=args.xrd_data,
        cif_paths=args.cifs,
        instrument_profile=args.instrument_profile,
        phase_params=phase_params,
        refinement_params=refinement_params,
        show_progress=not args.quiet,
        save_html=args.save_html,
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
