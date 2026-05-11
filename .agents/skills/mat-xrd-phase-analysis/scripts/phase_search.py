"""
Phase search using DARA's tree search (search_phases + CODDatabase).

Follows the DARA tutorial: https://cedergrouphub.github.io/dara/notebooks/phase_search.html
- Step 1: Get reference CIFs by chemical system (CODDatabase) or from --cif_dir.
- Step 2: Run search_phases(pattern_path, phases=all_cifs, wavelength, instrument_profile).
- Step 3: Save results and refinement plots under phase_analysis_results/.

Usage:
    # Download CIFs and perform phase analysis
    python phase_search.py --xrd_data pattern.xrdml --chemical_system "Ge-O-Zn"

    # Alternative: reuse pre-downloaded CIFs (no COD download)
    python phase_search.py --xrd_data pattern.xrdml --cif_dir path/to/cifs

Output (default: same directory as the pattern, under phase_analysis_results/):
    - results_summary.json
    - solution_0_refinement.html, solution_0_refinement.png (best solution)
    - solution_1_... if multiple
    - cifs/ (if CIFs were downloaded by chemical system)

Requirements:
    - Conda environment with dara-xrd (e.g. xrd-agent)
    - BGMN installed; DARA may download it on first run
"""
import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional

try:
    from dara.structure_db import CODDatabase, ICSDDatabase
except ImportError:
    raise ImportError(
        "DARA is not installed. Install with: pip install dara-xrd\n"
        "See https://cedergrouphub.github.io/dara/ for details."
    )

import warnings
warnings.simplefilter("ignore", DeprecationWarning)

def phase_search(
    xrd_data_path: str,
    chemical_system: Optional[str] = None,
    cif_dir: Optional[str] = None,
    database: str = "cod",
    output_dir: Optional[str] = None,
    wavelength: str = "Cu",
    instrument_profile: str = "Aeris-fds-Pixcel1d-Medipix3",
    verbose: bool = True,
    save_html: bool = False,
) -> List:
    """
    Run DARA phase search on an XRD pattern.

    Args:
        xrd_data_path: Path to pattern file (.xy, .xrdml, or .raw).
        chemical_system: Chemical system for COD/ICSD lookup (e.g. "Ge-O-Zn"). Required if cif_dir not given.
        cif_dir: Directory of CIF files to search. If given, chemical_system and COD/ICSD lookup are skipped.
        database: Source of database ("cod" or "icsd").
        output_dir: Where to write results. Default: same directory as pattern, under phase_analysis_results/.
        wavelength: "Cu", "Co", "Cr", "Fe", "Mo" or wavelength in nm.
        instrument_profile: BGMN instrument profile name.
        verbose: Print progress.

    Returns:
        List of DARA SearchResult objects.
    """
    xrd_path = Path(xrd_data_path).resolve()
    if not xrd_path.exists():
        raise FileNotFoundError(f"XRD file not found: {xrd_path}")

    if output_dir is None:
        output_dir = xrd_path.parent / "phase_analysis_results"
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Get CIFs
    if cif_dir:
        cif_dir_path = Path(cif_dir).resolve()
        if not cif_dir_path.is_dir():
            raise FileNotFoundError(f"CIF directory not found: {cif_dir_path}")
        all_cifs = sorted(cif_dir_path.glob("*.cif"))
        if not all_cifs:
            raise FileNotFoundError(f"No *.cif files in {cif_dir_path}")
        if verbose:
            print(f"Using {len(all_cifs)} CIFs from {cif_dir_path}")
    else:
        # Default CIF location tied to this pattern's results
        cifs_dest = output_path / "cifs"
        existing = sorted(cifs_dest.glob("*.cif"))
        if existing:
            all_cifs = existing
            if verbose:
                print(f"Using {len(all_cifs)} existing CIFs from {cifs_dest}")
        else:
            if not chemical_system:
                raise ValueError("Provide either --chemical_system or --cif_dir")
            cifs_dest.mkdir(parents=True, exist_ok=True)
            if verbose:
                print(f"Fetching CIFs for chemical system {chemical_system} from {database.upper()} to {cifs_dest} ...")
            try:
                if database.lower() == "icsd":
                    db = ICSDDatabase()
                else:
                    db = CODDatabase()
                db.get_cifs_by_chemsys(chemical_system, dest_dir=str(cifs_dest))
            except Exception as e:  # friendly exit when database lookup fails
                if verbose:
                    print(
                        "----------------------------------------\n"
                        f"Error fetching CIFs for {chemical_system} via {database.upper()}: {e}\n"
                        "This can happen if the node has no internet access, the service is unavailable, or local database is missing.\n"
                        "Hint: Ensure the node running this script has internet access, or provide an existing\n"
                        "      CIF directory via --cif_dir so no database lookup is needed."
                    )
                # Exit phase_search gracefully
                return []
            all_cifs = sorted(cifs_dest.glob("*.cif"))
            if not all_cifs:
                raise RuntimeError(f"No CIFs found for {chemical_system} in COD (check system string).")
            if verbose:
                print(f"Using {len(all_cifs)} CIFs from {cifs_dest}")

    # Step 2: Search
    import ray
    from dara import search_phases

    # Init Ray before search_phases.
    ray.init(
        address="local",
        num_cpus=min(8, os.cpu_count() or 1),
        include_dashboard=False,
        ignore_reinit_error=True,
    )
    if verbose:
        print("Running phase search (this may take a few minutes) ...")
    search_results = search_phases(
        pattern_path=str(xrd_path),
        phases=all_cifs,
        wavelength=wavelength,
        instrument_profile=instrument_profile,
    )

    if not search_results:
        if verbose:
            print("No solutions found.")
        summary = {
            "pattern": str(xrd_path),
            "chemical_system": chemical_system,
            "cif_dir": str(cif_dir) if cif_dir else None,
            "num_solutions": 0,
            "solutions": [],
        }
        summary_path = output_path / "results_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        return []

    # Step 3: Save results and plots
    solutions = []
    for i, sr in enumerate(search_results):
        rwp = sr.refinement_result.lst_data.rwp
        phase_names = []
        for group in sr.phases:
            for phase in group:
                phase_names.append(phase.path.name)
        solutions.append({"rank": i + 1, "rwp": rwp, "phase_files": phase_names})

        # Save refinement plot (SearchResult has .visualize())
        try:
            fig = sr.visualize()
            base = output_path / f"solution_{i}_refinement"
            if save_html:
                fig.write_html(str(base) + ".html")
            try:
                fig.write_image(str(base) + ".png")
            except Exception:
                pass  # kaleido optional
        except Exception as e:
            if verbose:
                print(f"Warning: could not save plot for solution {i}: {e}")

    summary = {
        "pattern": str(xrd_path),
        "chemical_system": chemical_system,
        "cif_dir": str(cif_dir) if cif_dir else str(output_path / "cifs") if not cif_dir and chemical_system else None,
        "num_solutions": len(search_results),
        "best_rwp": search_results[0].refinement_result.lst_data.rwp,
        "solutions": solutions,
    }
    summary_path = output_path / "results_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    if verbose:
        print(f"\nPhase search completed. {len(search_results)} solution(s) found.")
        print(f"Best R_wp: {summary['best_rwp']:.2f}%")
        for s in solutions[:5]:
            print(f"  {s['rank']}. R_wp = {s['rwp']:.2f}% | {', '.join(s['phase_files'][:3])}{'...' if len(s['phase_files']) > 3 else ''}")
        print(f"Results saved to: {output_path}")
        print(f"Summary: {summary_path}")

    return search_results


def main():
    parser = argparse.ArgumentParser(
        description="DARA phase search: identify phases in an XRD pattern (tutorial: https://cedergrouphub.github.io/dara/notebooks/phase_search.html)"
    )
    parser.add_argument(
        "--xrd_data",
        required=True,
        help="Path to XRD pattern file (.xy, .xrdml, or .raw)",
    )
    parser.add_argument(
        "--chemical_system",
        help='Chemical system for COD (e.g. "Ge-O-Zn"). Required unless --cif_dir is set.',
    )
    parser.add_argument(
        "--cif_dir",
        help="Directory containing CIF files to search (skips COD/ICSD download/lookup)",
    )
    parser.add_argument(
        "--database",
        default="cod",
        choices=["cod", "icsd"],
        help='Database source to fetch CIFs from when given a chemical system. Default: "cod".',
    )
    parser.add_argument(
        "--output_dir",
        help='Output directory. Default: same directory as pattern, under "phase_analysis_results/"',
    )
    parser.add_argument(
        "--wavelength",
        default="Cu",
        help="Wavelength: Cu, Co, Cr, Fe, Mo or value in nm (default: Cu)",
    )
    parser.add_argument(
        "--instrument_profile",
        default="Aeris-fds-Pixcel1d-Medipix3",
        help="BGMN instrument profile (default: Aeris-fds-Pixcel1d-Medipix3)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--save_html",
        action="store_true",
        help="Save interactive HTML plots of the phase solutions (can be large)",
    )
    args = parser.parse_args()

    if not args.chemical_system and not args.cif_dir:
        parser.error("Provide either --chemical_system (to fetch CIFs from COD/ICSD) or --cif_dir (existing CIFs)")

    # Full phase search
    phase_search(
        xrd_data_path=args.xrd_data,
        chemical_system=args.chemical_system,
        cif_dir=args.cif_dir,
        database=args.database,
        output_dir=args.output_dir,
        wavelength=args.wavelength,
        instrument_profile=args.instrument_profile,
        verbose=not args.quiet,
        save_html=args.save_html,
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
