"""
Suggest dominant curve colors from a plot image for use with --curve-color.

Samples the cropped plot region and returns top hex colors with pixel counts,
excluding near-white/gray background. Use output with isolate_curves --color.

Usage:
    python suggest_colors.py plot.png metadata.json
    python suggest_colors.py plot.png --bounding-box 48,28,252,162
    python suggest_colors.py plot.png metadata.json --exclude-labels

Requirements:
    - Conda environment: base-agent
    - Required packages: opencv, numpy
"""

import argparse
import sys
import cv2
import numpy as np

from plot_utils import load_metadata


def _hsv_to_hex(h: int, s: int, v: int) -> str:
    """Convert HSV (H 0-179, S/V 0-255) to hex string."""
    bgr = cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)
    b, g, r = bgr[0, 0]
    return f"#{r:02x}{g:02x}{b:02x}"


def suggest_colors(
    cropped_bgr: np.ndarray,
    n_colors: int = 5,
    exclude_white: bool = True,
    allow_black: bool = False,
) -> list[tuple[str, int]]:
    """
    Find dominant non-background colors in cropped plot.

    Returns list of (hex_str, pixel_count) sorted by count descending.
    """
    hsv = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape(-1, 3).astype(np.float32)

    v_min = 5 if allow_black else 30
    if exclude_white:
        mask = (
            (pixels[:, 1] > 20)
            & (pixels[:, 2] > v_min)
            & (pixels[:, 2] < 250)
        )
        pixels = pixels[mask]

    if len(pixels) < n_colors:
        return []

    # K-means clustering
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(
        pixels, n_colors, None, criteria, 3, cv2.KMEANS_PP_CENTERS
    )

    # Count pixels per cluster, convert center to hex
    result = []
    for i in range(n_colors):
        count = int(np.sum(labels == i))
        if count < 10:
            continue
        h, s, v = int(centers[i, 0]), int(centers[i, 1]), int(centers[i, 2])
        h = max(0, min(179, h))
        s = max(0, min(255, s))
        v = max(0, min(255, v))
        hex_color = _hsv_to_hex(h, s, v)
        result.append((hex_color, count))

    result.sort(key=lambda x: -x[1])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Suggest dominant curve colors from plot image for --curve-color"
    )
    parser.add_argument("image", help="Path to plot image (PNG, JPG)")
    parser.add_argument(
        "metadata",
        nargs="?",
        default=None,
        help="JSON file with bounding_box, or use --bounding-box",
    )
    parser.add_argument(
        "--bounding-box",
        metavar="X_MIN,Y_MIN,X_MAX,Y_MAX",
        help="Pixel coords if metadata not used (e.g. 48,28,252,162)",
    )
    parser.add_argument(
        "--exclude-labels",
        action="store_true",
        help="Use smaller central region to avoid legend/labels at edges",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=5,
        help="Number of colors to suggest (default 5)",
    )
    parser.add_argument(
        "--allow-black",
        action="store_true",
        help="Include near-black in suggestions",
    )
    args = parser.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        print(f"Error: Could not load image {args.image}", file=sys.stderr)
        sys.exit(1)

    if args.bounding_box:
        parts = args.bounding_box.split(",")
        if len(parts) != 4:
            print("Error: --bounding-box must be X_MIN,Y_MIN,X_MAX,Y_MAX", file=sys.stderr)
            sys.exit(1)
        x_min, y_min, x_max, y_max = [int(p.strip()) for p in parts]
    elif args.metadata:
        meta = load_metadata(args.metadata, validate=False)
        bb = meta.get("bounding_box")
        if not bb:
            print("Error: metadata must include bounding_box", file=sys.stderr)
            sys.exit(1)
        x_min = max(0, int(bb["x_min"]))
        y_min = max(0, int(bb["y_min"]))
        x_max = min(img.shape[1], int(bb["x_max"]))
        y_max = min(img.shape[0], int(bb["y_max"]))
    else:
        print("Error: provide metadata.json or --bounding-box", file=sys.stderr)
        sys.exit(1)

    cropped = img[y_min:y_max, x_min:x_max]

    if args.exclude_labels:
        h, w = cropped.shape[:2]
        margin_x = int(w * 0.15)
        margin_y = int(h * 0.15)
        cropped = cropped[margin_y : h - margin_y, margin_x : w - margin_x]

    results = suggest_colors(
        cropped,
        n_colors=args.n,
        exclude_white=True,
        allow_black=args.allow_black,
    )

    if not results:
        print("No distinct colors found. Try --allow-black or check bounding box.", file=sys.stderr)
        sys.exit(0)

    parts = [f"{hex_c} ({cnt} px)" for hex_c, cnt in results]
    print(" ".join(parts))
    print("Use with: --curve-color \"<hex>\"", file=sys.stderr)


if __name__ == "__main__":
    main()
