"""
Isolate data curves from a plot image using color masking and centroid extraction.

Crops to the plot bounding box, applies color masking (HSV), and extracts
a 1D trace by computing median/center-of-mass of masked pixels per X-column.

Usage:
    python isolate_curves.py plot.png metadata.json --output pixels.csv
    python isolate_curves.py plot.png metadata.json --color "#1f77b4" --output pixels.csv

Requirements:
    - Conda environment: base-agent
    - Required packages: opencv, scikit-image, numpy
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from plot_utils import load_metadata


HSVRange = tuple[tuple[int, int, int], tuple[int, int, int]]


def _hsv_ranges(
    h: int, s: int, v: int, tolerance: int = 30
) -> list[HSVRange]:
    """Build HSV range(s) from center (H,S,V) and tolerance.

    Returns 1 range normally, or 2 ranges when the hue wraps around
    the 0/179 boundary (reds).
    """
    tolerance = max(0, min(tolerance, 127))
    s_lo, s_hi = max(0, s - tolerance), min(255, s + tolerance)
    v_lo, v_hi = max(0, v - tolerance), min(255, v + tolerance)
    h_lo = h - tolerance
    h_hi = h + tolerance

    if h_lo < 0:
        # Wraps below 0: two ranges [0, h_hi] and [180+h_lo, 179]
        return [
            ((0, s_lo, v_lo), (h_hi, s_hi, v_hi)),
            ((180 + h_lo, s_lo, v_lo), (179, s_hi, v_hi)),
        ]
    elif h_hi > 179:
        # Wraps above 179: two ranges [h_lo, 179] and [0, h_hi-180]
        return [
            ((h_lo, s_lo, v_lo), (179, s_hi, v_hi)),
            ((0, s_lo, v_lo), (h_hi - 180, s_hi, v_hi)),
        ]
    else:
        return [((h_lo, s_lo, v_lo), (h_hi, s_hi, v_hi))]


def _hsv_mask(
    hsv_img: np.ndarray, hsv_ranges: list[HSVRange]
) -> np.ndarray:
    """Create combined binary mask from one or more HSV ranges (handles red wraparound)."""
    mask = np.zeros(hsv_img.shape[:2], dtype=np.uint8)
    for lower, upper in hsv_ranges:
        mask = cv2.bitwise_or(
            mask, cv2.inRange(hsv_img, np.array(lower), np.array(upper))
        )
    return mask


def hex_to_hsv_ranges(
    hex_color: str, tolerance: int = 30
) -> list[HSVRange]:
    """
    Convert hex color to HSV range(s) for masking.

    Args:
        hex_color: Hex string like "#1f77b4" or "1f77b4"
        tolerance: Hue/saturation/value tolerance for mask (default 30)

    Returns:
        List of (lower, upper) HSV bounds. Usually 1 element, but 2
        when the hue wraps around the 0/179 boundary (reds).
        OpenCV H range is 0-179; S and V are 0-255.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color '{hex_color}': expected 6 hex digits")
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError as e:
        raise ValueError(f"Invalid hex color '{hex_color}': {e}") from e
    # OpenCV uses BGR order
    pixel = np.uint8([[[b, g, r]]])
    hsv_pixel = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)
    h = int(hsv_pixel[0, 0, 0])
    s = int(hsv_pixel[0, 0, 1])
    v = int(hsv_pixel[0, 0, 2])
    return _hsv_ranges(h, s, v, tolerance)


def detect_dominant_curve_color(
    cropped_bgr: np.ndarray,
    exclude_white: bool = True,
    allow_black: bool = False,
) -> tuple[int, int, int]:
    """
    Detect dominant non-background color in cropped plot (for auto color detection).

    Excludes near-white; optionally excludes near-black unless allow_black=True.
    Returns HSV (H, S, V) of dominant color.
    """
    hsv = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape(-1, 3)
    v_min = 5 if allow_black else 30
    if exclude_white:
        mask = (pixels[:, 1] > 20) & (pixels[:, 2] > v_min) & (pixels[:, 2] < 250)
        pixels = pixels[mask]
    if len(pixels) == 0:
        return (120, 200, 200)  # default blue
    # Use median to avoid outliers
    h_med = int(np.median(pixels[:, 0]))
    s_med = int(np.median(pixels[:, 1]))
    v_med = int(np.median(pixels[:, 2]))
    return (h_med, s_med, v_med)


def _mask_to_centroids(mask: np.ndarray) -> np.ndarray:
    """Extract (x, y) centroids per X-column from binary mask. Returns Nx2 array sorted by x."""
    h, w = mask.shape
    points = []
    for x in range(w):
        col = mask[:, x]
        ys = np.where(col > 0)[0]
        if len(ys) == 0:
            continue
        y_med = float(np.median(ys))
        points.append([x, y_med])
    if len(points) == 0:
        return np.array([]).reshape(0, 2)
    pts = np.array(points)
    return pts[np.argsort(pts[:, 0])]


def _find_clusters(ys: np.ndarray, gap: int = 3) -> list[tuple[int, int]]:
    """Split sorted y-indices into contiguous runs separated by *gap* pixels."""
    clusters: list[tuple[int, int]] = []
    start = ys[0]
    prev = start
    for y in ys[1:]:
        if y - prev > gap:
            clusters.append((start, prev))
            start = y
        prev = y
    clusters.append((start, prev))
    return clusters


def _mask_to_cluster_centroids(mask: np.ndarray, gap: int = 3) -> np.ndarray:
    """Extract per-column centroids using a trace-following heuristic.

    Two-pass algorithm:
      1. For each column pick the largest contiguous cluster → rough trace.
      2. Re-scan columns and pick the cluster closest to a running median
         of the rough trace from neighbouring columns. This prevents
         spurious pixel clusters (tick marks, other curves, anti-aliased
         edges) from hijacking columns where they happen to be ≥ 1 px larger
         than the actual curve cluster.
    """
    h, w = mask.shape

    # Pass 1: largest cluster per column → rough trace (may have outliers)
    raw: dict[int, float] = {}
    all_clusters: dict[int, list[tuple[int, int]]] = {}
    for x in range(w):
        ys = np.where(mask[:, x] > 0)[0]
        if len(ys) == 0:
            continue
        clusters = _find_clusters(ys, gap)
        all_clusters[x] = clusters
        best = max(clusters, key=lambda c: c[1] - c[0] + 1)
        raw[x] = (best[0] + best[1]) / 2.0

    if not raw:
        return np.array([]).reshape(0, 2)

    # Build a smoothed reference from the rough trace (running median, k=15)
    sorted_x = sorted(raw.keys())
    raw_y = np.array([raw[x] for x in sorted_x])
    try:
        from scipy.ndimage import median_filter
        ref_y = median_filter(raw_y, size=min(15, max(3, len(raw_y))))
    except ImportError:
        ref_y = raw_y
    ref_map = dict(zip(sorted_x, ref_y))

    # Pass 2: for each column, choose the cluster whose centroid is closest
    # to the smoothed reference value from Pass 1
    points = []
    for x in sorted_x:
        clusters = all_clusters[x]
        expected = ref_map[x]
        best_dist = float("inf")
        best_y = expected
        for c_start, c_end in clusters:
            c_mid = (c_start + c_end) / 2.0
            dist = abs(c_mid - expected)
            if dist < best_dist:
                best_dist = dist
                best_y = c_mid
        points.append([x, best_y])

    pts = np.array(points)
    return pts[np.argsort(pts[:, 0])]


def _apply_text_mask(
    mask: np.ndarray,
    text_regions: list[dict],
    crop_origin: tuple[int, int],
    upscale: float = 1.0,
) -> np.ndarray:
    """Zero out rectangles in *mask* where in-plot text labels sit.

    Args:
        mask: Binary mask in crop-pixel coordinates.
        text_regions: ``[{"x_min", "y_min", "x_max", "y_max"}, ...]``
            in **full-image** pixel coordinates (consistent with bounding_box).
        crop_origin: ``(x_offset, y_offset)`` of the crop in full-image coords.
        upscale: Factor if the crop was upscaled after cropping.
    """
    h, w = mask.shape
    for tr in text_regions:
        x1 = int((tr["x_min"] - crop_origin[0]) * upscale)
        y1 = int((tr["y_min"] - crop_origin[1]) * upscale)
        x2 = int((tr["x_max"] - crop_origin[0]) * upscale)
        y2 = int((tr["y_max"] - crop_origin[1]) * upscale)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 0
    return mask


def _smooth_and_interpolate(
    pts: np.ndarray,
    window: int = 5,
    max_deviation: float = 15.0,
) -> np.ndarray:
    """Median-filter the trace, reject outliers, and interpolate over gaps.

    Designed for post-processing after text-region masking, where gaps in the
    trace need to be filled and residual text artifacts cleaned up.
    """
    if len(pts) < window + 2:
        return pts

    from scipy.interpolate import interp1d
    from scipy.ndimage import median_filter

    x_vals = pts[:, 0]
    y_vals = pts[:, 1]

    smoothed = median_filter(y_vals, size=window)
    keep = np.abs(y_vals - smoothed) < max_deviation
    if np.sum(keep) < 10:
        return pts

    clean_x = x_vals[keep]
    clean_y = y_vals[keep]

    if len(clean_x) > 2:
        interp_func = interp1d(
            clean_x, clean_y, kind="linear", fill_value="extrapolate"
        )
        all_x = np.arange(int(clean_x.min()), int(clean_x.max()) + 1)
        all_y = interp_func(all_x)
        return np.column_stack([all_x, all_y])

    return np.column_stack([clean_x, clean_y])


def _apply_spatial_filter(mask: np.ndarray, min_aspect_ratio: float = 3.0) -> np.ndarray:
    """Keep only the largest connected component with line-like aspect ratio.
    Removes axes (frame-like) and isolated label blobs.
    """
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best_label = 0
    best_area = 0
    for i in range(1, num_labels):
        w, h = stats[i, 2], stats[i, 3]  # width, height
        area = stats[i, 4]
        if w < 1 or h < 1:
            continue
        aspect = max(w / h, h / w)
        if aspect >= min_aspect_ratio and area > best_area:
            best_area = area
            best_label = i
    if best_label == 0:
        return mask
    out = np.zeros_like(mask)
    out[labels == best_label] = 255
    return out


def extract_curve_centroids(
    cropped_bgr: np.ndarray,
    hsv_ranges: list[HSVRange],
    use_skeleton: bool = False,
    morph_open: bool = False,
    spatial_filter: bool = False,
    text_regions: list[dict] | None = None,
    crop_origin: tuple[int, int] = (0, 0),
    crop_upscale: float = 1.0,
    cluster_centroid: bool = False,
    debug_dir: Optional[Path] = None,
) -> np.ndarray:
    """
    Extract (x_pixel, y_pixel) trace by finding centroid per X-column.

    Args:
        cropped_bgr: BGR image of plot area only.
        hsv_ranges: List of (lower, upper) HSV bounds for color mask (handles red wraparound).
        use_skeleton: If True, skeletonize mask before extraction (slower, thinner lines).
        morph_open: If True, apply morphological opening to remove small text blobs.
        spatial_filter: If True, keep only largest line-like connected component.
        text_regions: Bounding boxes (full-image coords) of text labels to mask out.
        crop_origin: (x_offset, y_offset) of the crop in full-image coordinates.
        crop_upscale: Scale factor if the crop was upscaled.
        cluster_centroid: Use largest-cluster heuristic per column (robust to text).
        debug_dir: If set, save intermediate masks (debug_mask.png, debug_mask_processed.png).

    Returns:
        Nx2 array of (x, y) pixel coordinates, sorted by x.
    """
    hsv = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2HSV)
    mask = _hsv_mask(hsv, hsv_ranges)

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "debug_mask.png"), mask)

    # Mask out known text-label regions before any morphological processing
    if text_regions:
        mask = _apply_text_mask(mask, text_regions, crop_origin, crop_upscale)

    # Morphological opening removes small label blobs while preserving the trace.
    # Use smaller kernel for low-res images to avoid removing thin curves.
    if morph_open:
        h, w = mask.shape[:2]
        ksize = 1 if min(h, w) < 150 else 2
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # Connected-component filter removes axes and label blobs (curve same as axes)
    if spatial_filter:
        mask = _apply_spatial_filter(mask)

    # Optionally skeletonize for thin lines
    if use_skeleton:
        from skimage.morphology import skeletonize

        mask_uint = (mask > 0).astype(np.uint8)
        skeleton = skeletonize(mask_uint).astype(np.uint8) * 255
        mask = skeleton

    if debug_dir is not None:
        cv2.imwrite(str(debug_dir / "debug_mask_processed.png"), mask)

    if cluster_centroid:
        return _mask_to_cluster_centroids(mask)
    return _mask_to_centroids(mask)


def extract_curve_edges(
    cropped_bgr: np.ndarray,
    spatial_filter: bool = True,
    debug_dir: Optional[Path] = None,
) -> np.ndarray:
    """
    Extract curve via Canny edge detection. For thin dark lines on light background.
    """
    gray = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "debug_mask.png"), edges)
    if spatial_filter:
        edges = _apply_spatial_filter(edges)
    if debug_dir is not None:
        cv2.imwrite(str(debug_dir / "debug_mask_processed.png"), edges)
    return _mask_to_centroids(edges)


def extract_curve_edge_and_color(
    cropped_bgr: np.ndarray,
    hsv_ranges: list[HSVRange],
    spatial_filter: bool = True,
    debug_dir: Optional[Path] = None,
) -> np.ndarray:
    """
    Extract curve via Canny edges intersected with color mask. Reduces label/axis bleed.
    """
    hsv = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2HSV)
    color_mask = _hsv_mask(hsv, hsv_ranges)
    gray = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    combined = cv2.bitwise_and(color_mask, edges)
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "debug_mask.png"), combined)
    if spatial_filter:
        combined = _apply_spatial_filter(combined)
    if debug_dir is not None:
        cv2.imwrite(str(debug_dir / "debug_mask_processed.png"), combined)
    return _mask_to_centroids(combined)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract curve pixel coordinates from plot image via color masking"
    )
    parser.add_argument("image", help="Path to plot image (PNG, JPG)")
    parser.add_argument(
        "metadata",
        help="JSON file with plot metadata (must include bounding_box)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="pixels.csv",
        help="Output CSV path for (x_pixel, y_pixel) array (default: pixels.csv)",
    )
    parser.add_argument(
        "--color",
        help="Hex color of target curve (e.g. #1f77b4). If not set, auto-detect dominant color.",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=40,
        help="HSV hue/saturation/value tolerance for color mask. Increase (55-85) for JPEG artifacts "
        "or anti-aliased edges; decrease (20-30) if mask bleeds into nearby colors. (default: 40)",
    )
    parser.add_argument(
        "--skeletonize",
        action="store_true",
        help="Reduce thick curves to 1px skeleton. Use when trace is very thick (>5px) and you "
        "need a clean centerline. Rarely needed.",
    )
    parser.add_argument(
        "--morph-open",
        action="store_true",
        help="Erode-then-dilate to remove small same-color text blobs touching the curve. "
        "Use when in-plot labels share the curve color. "
        "CAUTION: destroys thin (<3px) curves — only safe on thick traces.",
    )
    parser.add_argument(
        "--allow-black",
        action="store_true",
        help="Include near-black pixels in color mask. Use when the data curve is black "
        "(same color as axes/frame).",
    )
    parser.add_argument(
        "--spatial-filter",
        action="store_true",
        help="Keep only the largest connected line-like component, discard everything else. "
        "Use when curve color matches the axis frame — removes axes/ticks that pass the color mask.",
    )
    parser.add_argument(
        "--upscale",
        type=float,
        default=1.0,
        metavar="FACTOR",
        help="Upscale the cropped region before extraction. Use for thin needle-like peaks "
        "(XRD, FTIR) that are <2px wide — try 2.0-4.0. (default: 1.0)",
    )
    parser.add_argument(
        "--curve-index",
        type=int,
        default=None,
        metavar="N",
        help="For multi-curve metadata: extract curve N from curves[] (region + color_hint)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save intermediate artifacts (crop, masks) for inspection",
    )
    parser.add_argument(
        "--debug-dir",
        default=None,
        metavar="DIR",
        help="Directory for debug artifacts (default: output file's parent)",
    )
    parser.add_argument(
        "--auto-lowres",
        action="store_true",
        help="Auto-apply upscale and higher tolerance when low resolution detected",
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
        "--text-mask",
        default=None,
        metavar="JSON",
        help="Separate JSON file with text bounding boxes to mask out. Overrides text_regions "
        "in metadata. Usually not needed — prefer adding text_regions to metadata directly.",
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
    args = parser.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        print(f"Error: Could not load image {args.image}", file=sys.stderr)
        sys.exit(1)

    meta = load_metadata(args.metadata, validate=False)
    bb = meta.get("bounding_box")
    if not bb:
        print("Error: metadata must include bounding_box", file=sys.stderr)
        sys.exit(1)

    x_min = max(0, int(bb["x_min"]))
    y_min = max(0, int(bb["y_min"]))
    x_max = min(img.shape[1], int(bb["x_max"]))
    y_max = min(img.shape[0], int(bb["y_max"]))

    curve_color_override = args.color
    if args.curve_index is not None:
        curves = meta.get("curves") or []
        if args.curve_index < 0 or args.curve_index >= len(curves):
            print(
                f"Error: curve-index {args.curve_index} out of range (curves has {len(curves)} entries)",
                file=sys.stderr,
            )
            sys.exit(1)
        c = curves[args.curve_index]
        reg = c.get("region", {})
        if reg:
            y_min = max(0, int(reg.get("y_min", y_min)))
            y_max = min(img.shape[0], int(reg.get("y_max", y_max)))
        if c.get("color_hint") and not curve_color_override:
            curve_color_override = c["color_hint"]

    crop_origin = (x_min, y_min)
    cropped = img[y_min:y_max, x_min:x_max]
    crop_h, crop_w = cropped.shape[:2]
    plot_px = crop_w * crop_h
    min_dim = min(crop_w, crop_h)

    # Resolve regions to mask:
    #   - --text-mask file overrides everything
    #   - otherwise: top-level text_regions + mask_regions (always applied),
    #     plus per-curve curves[i].mask_regions (only when --curve-index is used)
    mask_regions: list[dict] = []
    if args.text_mask:
        import json as _json
        mask_regions = _json.loads(Path(args.text_mask).read_text())
    else:
        mask_regions = list(meta.get("text_regions") or [])
        mask_regions.extend(meta.get("mask_regions") or [])
        if args.curve_index is not None:
            curves = meta.get("curves") or []
            if 0 <= args.curve_index < len(curves):
                curve_masks = curves[args.curve_index].get("mask_regions") or []
                mask_regions.extend(curve_masks)

    use_cluster = args.cluster_centroid or args.allow_black

    upscale = max(1.0, float(args.upscale))
    tolerance = args.tolerance
    is_lowres = plot_px < 50_000 or min_dim < 200
    if is_lowres:
        print(
            f"Low resolution detected ({crop_w}x{crop_h} px). "
            f"Consider: --upscale 2, --tolerance 50",
            file=sys.stderr,
        )
        if args.auto_lowres:
            upscale = max(upscale, 2.0)
            tolerance = min(60, tolerance + 10)
            print(
                f"Auto-lowres: using upscale={upscale}, tolerance={tolerance}",
                file=sys.stderr,
            )

    if upscale > 1.0:
        cropped = cv2.resize(
            cropped,
            None,
            fx=upscale,
            fy=upscale,
            interpolation=cv2.INTER_CUBIC,
        )

    debug_dir = None
    if args.debug:
        debug_dir = Path(args.debug_dir) if args.debug_dir else Path(args.output).parent
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "debug_crop.png"), cropped)
        print(f"Debug: saved crop to {debug_dir / 'debug_crop.png'}", file=sys.stderr)

    method = args.extraction_method
    if method == "edge":
        pts = extract_curve_edges(
            cropped,
            spatial_filter=True,
            debug_dir=debug_dir,
        )
    else:
        if curve_color_override:
            hsv_ranges = hex_to_hsv_ranges(curve_color_override, tolerance=tolerance)
        else:
            # Auto-detect color; use per-curve sub-region for multi-curve plots
            color_detect_region = cropped
            if args.curve_index is not None:
                n_curves = len(meta.get("curves", []))
                if n_curves > 1:
                    ch = cropped.shape[0]
                    slice_h = ch // n_curves
                    y_start = args.curve_index * slice_h
                    y_end = min((args.curve_index + 1) * slice_h, ch)
                    color_detect_region = cropped[y_start:y_end, :]
                    print(
                        f"Auto-detecting color for curve {args.curve_index} "
                        f"from rows {y_start}-{y_end} of crop",
                        file=sys.stderr,
                    )
            h, s, v = detect_dominant_curve_color(color_detect_region, allow_black=args.allow_black)
            hsv_ranges = _hsv_ranges(h, s, v, tolerance)

        if method == "edge+color":
            pts = extract_curve_edge_and_color(
                cropped,
                hsv_ranges,
                spatial_filter=True,
                debug_dir=debug_dir,
            )
        else:
            pts = extract_curve_centroids(
                cropped,
                hsv_ranges,
                use_skeleton=args.skeletonize,
                morph_open=args.morph_open,
                spatial_filter=args.spatial_filter,
                text_regions=mask_regions,
                crop_origin=crop_origin,
                crop_upscale=upscale,
                cluster_centroid=use_cluster,
                debug_dir=debug_dir,
            )

    if len(pts) == 0:
        print(
            "Warning: No pixels found for the specified color. Try --color with a hex value or --tolerance.",
            file=sys.stderr,
        )
    elif len(pts) < 10 and args.morph_open:
        print(
            "Warning: morph-open may have removed the thin curve. Re-run without --morph-open",
            file=sys.stderr,
        )
    elif len(pts) < 20:
        print(
            f"Very few curve pixels ({len(pts)} points). Try higher --tolerance or --upscale 2",
            file=sys.stderr,
        )

    # Post-process: smooth trace and interpolate gaps left by text masking
    if args.smooth and len(pts) > 10:
        pts = _smooth_and_interpolate(
            pts,
            window=args.smooth_window,
            max_deviation=args.smooth_deviation,
        )

    # Scale back to original crop coordinates if upscaled
    if upscale > 1.0:
        pts = pts / upscale

    # Convert back to full-image coordinates
    pts[:, 0] += x_min
    pts[:, 1] += y_min

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(
        out_path,
        pts,
        delimiter=",",
        header="x_pixel,y_pixel",
        comments="",
        fmt="%.1f",
    )
    print(f"Extracted {len(pts)} points to {args.output}")
    if args.debug and debug_dir is not None:
        print(f"Debug: artifacts saved to {debug_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
