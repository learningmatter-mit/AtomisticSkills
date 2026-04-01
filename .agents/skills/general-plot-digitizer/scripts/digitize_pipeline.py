"""
Orchestrate the full plot digitization pipeline: metadata -> curve extraction -> calibration -> output.

Runs Phases 2-4 (CV + transform + export). Phase 1 (metadata) can be provided
by the agent or by extract_metadata.py when API keys are set.

Usage:
    # Full pipeline (requires metadata.json; or run extract_metadata.py first with API key)
    python digitize_pipeline.py plot.png --full --curve-color "#1f77b4" --output-dir ./output

    # Curves only (Phases 2-4, requires --metadata)
    python digitize_pipeline.py plot.png --curves-only --metadata metadata.json --output-dir ./output

    # Metadata only (Phase 1 via VLM API, requires GOOGLE_API_KEY or OPENAI_API_KEY)
    python digitize_pipeline.py plot.png --metadata-only --output-dir ./output

Requirements:
    - Conda environment: base-agent
    - Required packages: opencv, scikit-image, numpy, pandas
    - Optional for --metadata-only: google-generativeai or openai
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

# Load repo-root .env so GOOGLE_API_KEY / OPENAI_API_KEY work without manual export
# (matches extract_metadata.py behavior).
try:
    from dotenv import load_dotenv

    for _d in Path(__file__).resolve().parents:
        _env = _d / ".env"
        if _env.exists():
            load_dotenv(_env)
            break
except ImportError:
    pass

from plot_utils import scale_metadata_bbox


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def run_upscale_image(image_path: Path, output_path: Path, factor: float = 2.0) -> Path:
    """Upscale image and save. Returns path to upscaled image."""
    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"Could not load image: {image_path}")
    upscaled = cv2.resize(
        img,
        None,
        fx=factor,
        fy=factor,
        interpolation=cv2.INTER_CUBIC,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), upscaled):
        raise RuntimeError(f"Could not save upscaled image to: {output_path}")
    return output_path


def run_metadata_extraction(
    image_path: str,
    output_dir: Path,
    provider: str = "gemini",
    gemini_model: str | None = None,
) -> Path:
    """Run extract_metadata.py via subprocess. Returns path to metadata.json."""
    meta_path = output_dir / "metadata.json"
    cmd = [
        sys.executable,
        str(get_script_dir() / "extract_metadata.py"),
        image_path,
        "--output",
        str(meta_path),
        "--provider",
        provider,
    ]
    if provider == "gemini" and gemini_model:
        cmd.extend(["--gemini-model", gemini_model])
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            "Metadata extraction failed. Ensure GOOGLE_API_KEY or OPENAI_API_KEY is set."
        )
    return meta_path


def _sanitize_label(label: str) -> str:
    """Sanitize curve label for use in filenames."""
    import re
    s = re.sub(r"[^\w\-]", "_", label.strip().lower())
    return re.sub(r"_+", "_", s).strip("_") or "curve"


def run_isolate_curves(
    image_path: str,
    metadata_path: Path,
    output_dir: Path,
    curve_color: str | None,
    curve_tolerance: int,
    skeletonize: bool,
    morph_open: bool = False,
    allow_black: bool = False,
    spatial_filter: bool = False,
    upscale: float = 1.0,
    curve_index: int | None = None,
    output_name: str = "pixels.csv",
    debug: bool = False,
    extraction_method: str = "color",
    text_mask: str | None = None,
    cluster_centroid: bool = False,
    smooth: bool = False,
    smooth_window: int = 5,
    smooth_deviation: float = 15.0,
) -> Path:
    """Run isolate_curves.py. Returns path to pixels file."""
    pixels_path = output_dir / output_name
    cmd = [
        sys.executable,
        str(get_script_dir() / "isolate_curves.py"),
        image_path,
        str(metadata_path),
        "--output",
        str(pixels_path),
        "--tolerance",
        str(curve_tolerance),
    ]
    if curve_color:
        cmd.extend(["--color", curve_color])
    if curve_index is not None:
        cmd.extend(["--curve-index", str(curve_index)])
    if skeletonize:
        cmd.append("--skeletonize")
    if morph_open:
        cmd.append("--morph-open")
    if allow_black:
        cmd.append("--allow-black")
    if spatial_filter:
        cmd.append("--spatial-filter")
    if upscale > 1.0:
        cmd.extend(["--upscale", str(upscale)])
    if debug:
        cmd.extend(["--debug", "--debug-dir", str(output_dir)])
    if extraction_method != "color":
        cmd.extend(["--extraction-method", extraction_method])
    if text_mask:
        cmd.extend(["--text-mask", text_mask])
    if cluster_centroid:
        cmd.append("--cluster-centroid")
    if smooth:
        cmd.append("--smooth")
        cmd.extend(["--smooth-window", str(smooth_window)])
        cmd.extend(["--smooth-deviation", str(smooth_deviation)])
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError("Curve isolation failed")
    return pixels_path


def run_pixel_to_data(
    pixels_path: Path,
    metadata_path: Path,
    output_path: Path,
    y_calibration: str = "axis",
) -> None:
    """Run pixel_to_data.py."""
    cmd = [
        sys.executable,
        str(get_script_dir() / "pixel_to_data.py"),
        str(pixels_path),
        str(metadata_path),
        "--output",
        str(output_path),
    ]
    if y_calibration == "per_curve_normalized":
        cmd.extend(["--y-calibration", "per_curve_normalized"])
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError("Pixel-to-data transformation failed")


def write_xy_output(csv_path: Path) -> Path:
    """Convert a digitized CSV (x,y header + data) to space-separated .xy format."""
    data = np.loadtxt(csv_path, delimiter=",", skiprows=1)
    xy_path = csv_path.with_suffix(".xy")
    np.savetxt(xy_path, data, fmt="%.6f", delimiter=" ")
    print(f"Saved {len(data)} data points to {xy_path}")
    return xy_path


def prepend_header_metadata(
    csv_path: Path,
    meta: dict,
    image_path: str,
    curve_label: str | None = None,
) -> None:
    """Prepend commented metadata lines to a CSV file for traceability."""
    from datetime import date

    x_range = f"{meta.get('x_tick_min')}-{meta.get('x_tick_max')}" if "x_tick_min" in meta else "calibrated"
    y_range = f"{meta.get('y_tick_min')}-{meta.get('y_tick_max')}" if "y_tick_min" in meta else "calibrated"

    header_lines = [
        f"# source: {Path(image_path).name}",
        f"# x_axis: {meta.get('x_axis_label', '')}, range: {x_range}",
        f"# y_axis: {meta.get('y_axis_label', '')}, range: {y_range}",
    ]
    if curve_label:
        header_lines.append(f"# curve: {curve_label}")
    if meta.get("spectrum_type"):
        header_lines.append(f"# spectrum_type: {meta['spectrum_type']}")
    header_lines.append(f"# extracted: {date.today().isoformat()}")
    header_lines.append("")

    original = csv_path.read_text(encoding="utf-8")
    csv_path.write_text("\n".join(header_lines) + original, encoding="utf-8")


def write_markdown_summary(
    output_path: Path,
    meta: dict,
    csv_path: Path,
    image_path: str,
) -> None:
    """Write markdown summary for Obsidian/Zotero."""
    md_path = output_path.with_suffix(".md")
    x_range = f"{meta.get('x_tick_min')} - {meta.get('x_tick_max')}" if "x_tick_min" in meta else "custom calibrated points"
    y_range = f"{meta.get('y_tick_min')} - {meta.get('y_tick_max')}" if "y_tick_min" in meta else "custom calibrated points"
    
    lines = [
        f"# Digitized: {meta.get('plot_title', 'Plot')}",
        "",
        f"- **X axis:** {meta.get('x_axis_label', '')} ({x_range})",
        f"- **Y axis:** {meta.get('y_axis_label', '')} ({y_range})",
        f"- **Source image:** {image_path}",
        f"- **Data file:** {csv_path.name}",
        "",
    ]
    if meta.get("spectrum_type"):
        lines.append(f"- **Spectrum type:** {meta['spectrum_type']}")
        lines.append("")
    if meta.get("notes"):
        lines.append(f"- **Notes:** {meta['notes']}")
        lines.append("")
    if meta.get("annotations"):
        lines.append("## Annotations")
        lines.append("")
        for ann in meta["annotations"]:
            desc = ", ".join(f"{k}: {v}" for k, v in ann.items() if v is not None)
            lines.append(f"- {desc}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved markdown summary to {md_path}")


def create_overlay_image(
    image_path: str,
    pixels_path: Path,
    metadata_path: Path,
    output_path: Path,
) -> None:
    """Create overlay of extracted curve on original image."""
    try:
        import cv2
    except ImportError:
        return

    img = cv2.imread(image_path)
    if img is None:
        return

    pixels = np.loadtxt(pixels_path, delimiter=",", skiprows=1)
    if len(pixels) < 2:
        return

    pts = pixels[:, :2].astype(np.int32)
    pts = pts.reshape((-1, 1, 2))
    cv2.polylines(img, [pts], False, (0, 255, 0), 2)

    overlay_path = output_path.with_suffix(".overlay.png")
    cv2.imwrite(str(overlay_path), img)
    print(f"Saved overlay image to {overlay_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Digitize experimental spectrum plots: extract continuous X-Y data"
    )
    parser.add_argument("image", help="Path to plot image (PNG, JPG)")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline (Phases 2-4). Requires metadata.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Run Phase 1 only: extract metadata via VLM API (requires API key)",
    )
    parser.add_argument(
        "--curves-only",
        action="store_true",
        help="Run Phases 2-4 only. Requires --metadata.",
    )
    parser.add_argument(
        "--metadata",
        "-m",
        help="Path to metadata.json (required for --full or --curves-only)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--curve-color",
        help="Hex color of target curve (e.g. #1f77b4)",
    )
    parser.add_argument(
        "--curve-tolerance",
        type=int,
        default=40,
        help="HSV hue/saturation/value tolerance for color mask. Increase (55-85) for JPEG artifacts "
        "or anti-aliased edges; decrease (20-30) if mask bleeds into nearby colors. (default: 40)",
    )
    parser.add_argument(
        "--skeletonize",
        action="store_true",
        help="Reduce thick curves to 1px skeleton. Use when trace is very thick (>5px) and you need "
        "a clean centerline. Rarely needed.",
    )
    parser.add_argument(
        "--morph-open",
        action="store_true",
        help="Erode-then-dilate to remove small same-color text blobs touching the curve. "
        "Use when in-plot labels share the curve color and contaminate the mask. "
        "CAUTION: destroys thin (<3px) curves — only safe on thick traces.",
    )
    parser.add_argument(
        "--allow-black",
        action="store_true",
        help="Include near-black pixels in color mask. Use when the data curve is black "
        "(same color as axes/frame). Auto-enables --spatial-filter and --cluster-centroid for single-curve.",
    )
    parser.add_argument(
        "--spatial-filter",
        action="store_true",
        help="Keep only the largest connected line-like component, discard everything else. "
        "Use when curve color matches the axis frame — removes axes/ticks that pass the color mask. "
        "Auto-enabled by --allow-black for single-curve extraction.",
    )
    parser.add_argument(
        "--crop-upscale",
        type=float,
        default=1.0,
        metavar="FACTOR",
        dest="crop_upscale",
        help="Upscale the cropped plot region before extraction. Use for thin needle-like peaks "
        "(XRD, FTIR) that are <2px wide — try 2.0-4.0. Does NOT affect metadata coordinates. (default: 1.0)",
    )
    parser.add_argument(
        "--all-curves",
        action="store_true",
        help="Extract all curves from metadata.curves[] (requires curves in metadata)",
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Save overlay image with extracted curve",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save intermediate artifacts (crop, masks) for inspection",
    )
    parser.add_argument(
        "--upscale-strategy",
        choices=["none", "auto", "force"],
        default="auto",
        dest="upscale_strategy",
        help="Pre-upscale the entire source image before extraction. "
        "'none': never upscale. "
        "'auto' (default): upscale if metadata low_resolution flag is set or heuristic detects small bbox. "
        "'force': always upscale by --upscale-factor. Use when the whole image is low resolution. "
        "Different from --crop-upscale which only upscales the cropped region.",
    )
    parser.add_argument(
        "--upscale-factor",
        type=float,
        default=2.0,
        metavar="FACTOR",
        dest="upscale_factor",
        help="Multiplier for --upscale-strategy auto|force pre-upscale (default: 2.0). "
        "Only used when pre-upscaling is triggered.",
    )
    parser.add_argument(
        "--vlm-metadata-on-upscale",
        action="store_true",
        default=False,
        help="After pre-upscale, re-run VLM metadata extraction on the upscaled image (requires API key). "
        "Default is off: only scale bounding boxes/calibration proportionally. "
        "Use only when hand-tuned metadata is not critical and you want a fresh extraction.",
    )
    parser.add_argument(
        "--extraction-method",
        choices=["color", "edge", "edge+color"],
        default="color",
        help="Extraction method. 'color' (default): HSV color mask — best for most plots. "
        "'edge+color': Canny edges intersected with color mask — use for thin anti-aliased lines "
        "where pure color misses pixels. 'edge': Canny only — rarely useful alone.",
    )
    parser.add_argument(
        "--preset",
        choices=["lowres", "thin-red"],
        help="Preset for common cases: lowres (upscale 2, tolerance 55, edge+color), thin-red (tolerance 50, no morph-open)",
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai"],
        default="gemini",
        help="VLM provider for --metadata-only (default: gemini)",
    )
    parser.add_argument(
        "--gemini-model",
        default=None,
        metavar="MODEL",
        help=(
            "Gemini model id for Phase 1 metadata (default: gemini-1.5-flash or GEMINI_MODEL env)"
        ),
    )
    # Deprecated aliases (hidden) — mapped to --upscale-strategy after parse
    parser.add_argument("--low-res", action="store_true", dest="low_res", help=argparse.SUPPRESS)
    parser.add_argument("--no-low-res", action="store_true", dest="no_low_res", help=argparse.SUPPRESS)
    parser.add_argument("--upscale", type=float, default=1.0, dest="_legacy_upscale", help=argparse.SUPPRESS)
    parser.add_argument("--auto-lowres", action="store_true", dest="_legacy_auto_lowres", help=argparse.SUPPRESS)
    parser.add_argument(
        "--text-mask",
        default=None,
        metavar="JSON",
        help="Separate JSON file with text bounding boxes to mask out. Overrides text_regions "
        "in metadata.json. Usually not needed — prefer adding text_regions to metadata directly.",
    )
    parser.add_argument(
        "--cluster-centroid",
        action="store_true",
        help="Per X-column, use centroid of the largest connected cluster instead of full-column median. "
        "Use when text labels or axis fragments pass the color mask and create spurious blobs. "
        "Auto-enabled with --allow-black or when text_regions/mask_regions are present.",
    )
    parser.add_argument(
        "--smooth",
        action="store_true",
        help="Post-process the extracted trace: median filter + outlier rejection + gap interpolation. "
        "Use for noisy, jagged, or thick traces with scatter. "
        "AVOID on thin needle-like peaks (XRD, FTIR) — it flattens sharp features.",
    )
    parser.add_argument(
        "--smooth-window",
        type=int,
        default=5,
        metavar="N",
        help="Median filter window size for --smooth. Larger = more aggressive smoothing. (default: 5)",
    )
    parser.add_argument(
        "--smooth-deviation",
        type=float,
        default=15.0,
        metavar="PX",
        help="Max pixel distance from local median before a point is rejected as an outlier "
        "during --smooth. Increase if valid peaks are being removed. (default: 15.0 pixels)",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "xy", "both"],
        default="csv",
        dest="output_format",
        help="Output format: csv (default), xy (space-separated, no header), both",
    )
    parser.add_argument(
        "--header-metadata",
        action="store_true",
        default=False,
        help="Embed source/axis metadata as # comments at the top of CSV output",
    )
    parser.add_argument(
        "--json-summary",
        action="store_true",
        default=False,
        dest="json_summary",
        help="Emit a machine-readable JSON summary to stdout after completion",
    )
    args = parser.parse_args()

    # Handle deprecated aliases
    if args.low_res:
        print("Warning: --low-res is deprecated; use --upscale-strategy force", file=sys.stderr)
        args.upscale_strategy = "force"
    if args.no_low_res:
        print("Warning: --no-low-res is deprecated; use --upscale-strategy none", file=sys.stderr)
        args.upscale_strategy = "none"
    if args._legacy_upscale > 1.0 and args.crop_upscale == 1.0:
        print("Warning: --upscale is deprecated; use --crop-upscale", file=sys.stderr)
        args.crop_upscale = args._legacy_upscale
    if args._legacy_auto_lowres:
        print("Warning: --auto-lowres is deprecated; use --upscale-strategy auto (the default)", file=sys.stderr)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Metadata
    if args.metadata_only:
        try:
            meta_path = run_metadata_extraction(
                str(image_path),
                output_dir,
                provider=args.provider,
                gemini_model=args.gemini_model,
            )
            print(f"Metadata saved to {meta_path}")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Resolve metadata path for Phases 2-4
    if args.metadata:
        metadata_path = Path(args.metadata)
    else:
        metadata_path = output_dir / "metadata.json"

    if not metadata_path.exists() and args.full:
        # Try to extract via API
        import os

        if os.environ.get("GOOGLE_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            try:
                provider = "openai" if os.environ.get("OPENAI_API_KEY") else "gemini"
                metadata_path = run_metadata_extraction(
                    str(image_path),
                    output_dir,
                    provider=provider,
                    gemini_model=args.gemini_model,
                )
            except RuntimeError as e:
                print(
                    f"Metadata not found and extraction failed: {e}",
                    file=sys.stderr,
                )
                print(
                    "Provide metadata.json (e.g. from agent visual extraction) or set GOOGLE_API_KEY/OPENAI_API_KEY.",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            print(
                "Error: metadata.json not found. Create it via agent visual extraction or run with --metadata-only (requires API key).",
                file=sys.stderr,
            )
            sys.exit(1)

    if not metadata_path.exists():
        print(f"Error: Metadata file not found: {metadata_path}", file=sys.stderr)
        sys.exit(1)

    if not (args.full or args.curves_only):
        parser.error("Specify --full, --metadata-only, or --curves-only")

    meta = json.loads(metadata_path.read_text())

    # Apply cli_hints from VLM metadata (mechanical mapping with conflict resolution)
    hints = meta.get("cli_hints") or {}
    is_thin = hints.get("thin_lines", False)
    uses_edge = hints.get("extraction_method", "") in ("edge", "edge+color")
    has_text_overlap = hints.get("text_overlaps_curve", False)
    curves_list = meta.get("curves") or []
    is_multi = len(curves_list) > 1

    if hints.get("curve_is_black"):
        args.allow_black = True
        if not is_multi:
            args.spatial_filter = True
            args.cluster_centroid = True
    if has_text_overlap and not is_thin and not uses_edge:
        args.morph_open = True
    # Auto-apply extraction_method from cli_hints when user didn't override.
    # Skip for multi-curve stacked plots where edge+color is unreliable.
    hint_method = hints.get("extraction_method")
    if hint_method and args.extraction_method == "color":
        if not (is_multi and hint_method == "edge+color"):
            args.extraction_method = hint_method
    if hints.get("smooth"):
        args.smooth = True

    if is_multi and not args.all_curves:
        args.all_curves = True

    # Apply preset overrides
    if args.preset == "lowres":
        args.upscale_strategy = "force"
        args.curve_tolerance = 55
        args.extraction_method = "edge+color"
    elif args.preset == "thin-red":
        args.curve_tolerance = 50
        args.morph_open = False

    # Pre-upscale decision (single clean path)
    do_upscale = False
    if args.upscale_strategy == "force":
        do_upscale = True
    elif args.upscale_strategy == "auto":
        if meta.get("low_resolution") is True:
            do_upscale = True
        else:
            bb = meta.get("bounding_box", {})
            bw = bb.get("x_max", 0) - bb.get("x_min", 0)
            bh = bb.get("y_max", 0) - bb.get("y_min", 0)
            plot_px = bw * bh if (bw > 0 and bh > 0) else 0
            min_dim = min(bw, bh) if (bw > 0 and bh > 0) else 0
            if plot_px < 50_000 or min_dim < 200:
                do_upscale = True

    working_image = image_path
    working_metadata = metadata_path

    if do_upscale:
        upscaled_path = output_dir / f"{image_path.stem}_upscaled.png"
        try:
            run_upscale_image(image_path, upscaled_path, factor=args.upscale_factor)
            print(f"Pre-upscaled image ({args.upscale_factor}x) saved to {upscaled_path}")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        working_image = upscaled_path

        # Default: scale metadata coordinates to match the upscaled image (preserves hand-tuned JSON).
        # Opt-in: --vlm-metadata-on-upscale + API key re-runs extract_metadata.py on the upscaled PNG.
        import os

        use_vlm_upscale = bool(
            getattr(args, "vlm_metadata_on_upscale", False)
            and (
                os.environ.get("GOOGLE_API_KEY") or os.environ.get("OPENAI_API_KEY")
            )
        )
        if use_vlm_upscale:
            try:
                provider = "openai" if os.environ.get("OPENAI_API_KEY") else "gemini"
                working_metadata = run_metadata_extraction(
                    str(upscaled_path),
                    output_dir,
                    provider=provider,
                    gemini_model=args.gemini_model,
                )
                meta = json.loads(working_metadata.read_text())
                print("Re-extracted metadata on upscaled image via VLM (--vlm-metadata-on-upscale)")
            except RuntimeError as e:
                print(
                    f"VLM re-extraction failed ({e}); falling back to scaled metadata.",
                    file=sys.stderr,
                )
                scaled_meta = scale_metadata_bbox(meta, args.upscale_factor)
                meta_upscaled_path = output_dir / "metadata_upscaled.json"
                with open(meta_upscaled_path, "w") as f:
                    json.dump(scaled_meta, f, indent=2)
                working_metadata = meta_upscaled_path
                meta = scaled_meta
        else:
            if getattr(args, "vlm_metadata_on_upscale", False) and not (
                os.environ.get("GOOGLE_API_KEY") or os.environ.get("OPENAI_API_KEY")
            ):
                print(
                    "Note: --vlm-metadata-on-upscale ignored (no GOOGLE_API_KEY / OPENAI_API_KEY); "
                    "using proportional metadata scaling.",
                    file=sys.stderr,
                )
            scaled_meta = scale_metadata_bbox(meta, args.upscale_factor)
            meta_upscaled_path = output_dir / "metadata_upscaled.json"
            with open(meta_upscaled_path, "w") as f:
                json.dump(scaled_meta, f, indent=2)
            working_metadata = meta_upscaled_path
            meta = scaled_meta

    pipeline_upscale = args.crop_upscale
    y_cal = meta.get("y_calibration", "axis")
    curves = meta.get("curves") or []

    # Structured summary for --json-summary
    summary = {"status": "success", "curves": [], "warnings": [], "files": {}}

    if args.all_curves and curves:
        # Multi-curve extraction
        csv_paths = []
        for i, c in enumerate(curves):
            label = _sanitize_label(c.get("label", f"curve_{i}"))
            pixels_name = f"pixels_{label}.csv"
            csv_name = f"{image_path.stem}_{label}_digitized.csv"
            try:
                px_path = run_isolate_curves(
                    str(working_image),
                    working_metadata,
                    output_dir,
                    curve_color=c.get("color_hint") or args.curve_color,
                    curve_tolerance=args.curve_tolerance,
                    skeletonize=args.skeletonize,
                    morph_open=args.morph_open,
                    allow_black=args.allow_black,
                    spatial_filter=args.spatial_filter,
                    upscale=pipeline_upscale,
                    curve_index=i,
                    output_name=pixels_name,
                    debug=args.debug,
                    extraction_method=args.extraction_method,
                    text_mask=args.text_mask,
                    cluster_centroid=args.cluster_centroid,
                    smooth=args.smooth,
                    smooth_window=args.smooth_window,
                    smooth_deviation=args.smooth_deviation,
                )
            except RuntimeError as e:
                msg = f"Extraction failed for curve {i} ({label}): {e}"
                print(msg, file=sys.stderr)
                summary["warnings"].append(msg)
                continue
            csv_path = output_dir / csv_name
            try:
                run_pixel_to_data(px_path, working_metadata, csv_path, y_calibration=y_cal)
            except RuntimeError as e:
                msg = f"Calibration failed for curve {i} ({label}): {e}"
                print(msg, file=sys.stderr)
                summary["warnings"].append(msg)
                continue
            if args.output_format in ("xy", "both"):
                write_xy_output(csv_path)
            if args.header_metadata and args.output_format != "xy":
                prepend_header_metadata(csv_path, meta, str(image_path), curve_label=c.get("label"))
            if args.output_format == "xy":
                csv_path.unlink()
            write_markdown_summary(csv_path, meta, csv_path, str(working_image))
            if args.overlay:
                create_overlay_image(str(working_image), px_path, working_metadata, csv_path)
            # Count data points for summary
            n_pts = len(np.loadtxt(csv_path, delimiter=",", skiprows=1)) if csv_path.exists() else 0
            summary["curves"].append({
                "label": c.get("label", f"curve_{i}"),
                "n_points": n_pts,
                "csv_path": str(csv_path),
            })
            csv_paths.append(csv_path)
        print(f"\nDone. Digitized {len(csv_paths)} curves: {[str(p) for p in csv_paths]}")
    else:
        # Single-curve extraction
        try:
            pixels_path = run_isolate_curves(
                str(working_image),
                working_metadata,
                output_dir,
                curve_color=args.curve_color or (curves[0].get("color_hint") if curves else None),
                curve_tolerance=args.curve_tolerance,
                skeletonize=args.skeletonize,
                morph_open=args.morph_open,
                allow_black=args.allow_black,
                spatial_filter=args.spatial_filter,
                upscale=pipeline_upscale,
                debug=args.debug,
                extraction_method=args.extraction_method,
                text_mask=args.text_mask,
                cluster_centroid=args.cluster_centroid,
                smooth=args.smooth,
                smooth_window=args.smooth_window,
                smooth_deviation=args.smooth_deviation,
            )
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        csv_name = f"{image_path.stem}_digitized.csv"
        csv_path = output_dir / csv_name

        try:
            run_pixel_to_data(pixels_path, working_metadata, csv_path, y_calibration=y_cal)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if args.output_format in ("xy", "both"):
            write_xy_output(csv_path)
        if args.header_metadata and args.output_format != "xy":
            prepend_header_metadata(csv_path, meta, str(image_path))
        if args.output_format == "xy":
            csv_path.unlink()

        write_markdown_summary(csv_path, meta, csv_path, str(working_image))

        if args.overlay:
            create_overlay_image(str(working_image), pixels_path, working_metadata, csv_path)

        n_pts = len(np.loadtxt(csv_path, delimiter=",", skiprows=1)) if csv_path.exists() else 0
        summary["curves"].append({
            "label": curves[0].get("label", "curve") if curves else "curve",
            "n_points": n_pts,
            "csv_path": str(csv_path),
        })
        print(f"\nDone. Digitized data: {csv_path}")

    # Emit machine-readable summary for coding agents
    if args.json_summary:
        summary["files"]["metadata"] = str(working_metadata)
        summary["files"]["output_dir"] = str(output_dir)
        summary["files"]["source_image"] = str(working_image)
        print("---JSON_SUMMARY_START---")
        print(json.dumps(summary, indent=2))
        print("---JSON_SUMMARY_END---")


if __name__ == "__main__":
    main()
