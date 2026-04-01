"""
Transform pixel coordinates to data-space coordinates using plot metadata.

Maps (x_pixel, y_pixel) arrays to (X_data, Y_data) using axis tick ranges
and scale (linear/log). Handles inverted Y-axis (image origin top-left).

Usage:
    python pixel_to_data.py pixels.csv metadata.json --output data.csv

Requirements:
    - Conda environment: base-agent
    - Required packages: numpy, pandas
"""

import argparse
import sys
from pathlib import Path

import numpy as np

from plot_utils import load_metadata


def pixel_to_data(
    x_pixel: np.ndarray,
    y_pixel: np.ndarray,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    x0: int,
    y0: int,
    x_max_pixel: int,
    y_max_pixel: int,
    x_scale: str = "linear",
    y_scale: str = "linear",
    x_reversed: bool = False,
    y_reversed: bool = False,
    y_calibration: str = "axis",
    x_calibration_points: list[dict] | None = None,
    y_calibration_points: list[dict] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Map pixel coordinates to data-space coordinates.

    Image coordinates: origin (0,0) top-left, y increases downward.
    Plot coordinates: origin bottom-left, y increases upward.

    Args:
        x_pixel: X pixel coordinates (left-to-right in image).
        y_pixel: Y pixel coordinates (top-to-bottom in image).
        x_min, x_max: Data values at left and right edges (x_tick_min, x_tick_max).
        y_min, y_max: Data values at bottom and top edges (y_tick_min, y_tick_max).
        x0, y0: Pixel coordinates of plot origin (bottom-left of data area).
        x_max_pixel, y_max_pixel: Pixel coordinates of top-right of data area.
        x_scale, y_scale: "linear" or "log".
        x_reversed: True if X increases right-to-left (left has larger value).
        y_reversed: True if Y increases top-to-bottom (top has larger value).
        y_calibration: "axis" for axis ticks, "per_curve_normalized" for baseline=0, peak=1.

    Returns:
        (X_data, Y_data) arrays in scientific units.
    """
    x_pixel = np.asarray(x_pixel, dtype=float)
    y_pixel = np.asarray(y_pixel, dtype=float)

    if x_calibration_points and len(x_calibration_points) >= 2:
        cal = sorted(x_calibration_points, key=lambda p: p["pixel"])
        p1, p2 = cal[0], cal[-1]
        px1, v1 = p1["pixel"], p1["value"]
        px2, v2 = p2["pixel"], p2["value"]

        dx_px = px2 - px1
        if np.abs(dx_px) < 1e-9:
            dx_px = 1.0

        t_x = (x_pixel - px1) / dx_px

        if x_scale == "log":
            if v1 <= 0 or v2 <= 0:
                raise ValueError("Log scale requires positive calibration values")
            log_v1 = np.log10(v1)
            log_v2 = np.log10(v2)
            X_data = 10 ** (log_v1 + t_x * (log_v2 - log_v1))
        else:
            X_data = v1 + t_x * (v2 - v1)
    else:
        # X: left pixel = x_min, right pixel = x_max
        dx_pixel = x_max_pixel - x0
        if np.abs(dx_pixel) < 1e-9:
            dx_pixel = 1.0  # avoid division by zero
        t_x = (x_pixel - x0) / dx_pixel

        if x_reversed:
            t_x = 1.0 - t_x  # left -> max, right -> min

        if x_scale == "log":
            if x_min <= 0 or x_max <= 0:
                raise ValueError("Log scale requires positive x_min and x_max")
            log_x_min = np.log10(x_min)
            log_x_max = np.log10(x_max)
            X_data = 10 ** (log_x_min + t_x * (log_x_max - log_x_min))
        else:
            X_data = x_min + t_x * (x_max - x_min)

    if y_calibration_points and len(y_calibration_points) >= 2 and y_calibration != "per_curve_normalized":
        cal = sorted(y_calibration_points, key=lambda p: p["pixel"])
        p1, p2 = cal[0], cal[-1]
        px1, v1 = p1["pixel"], p1["value"]
        px2, v2 = p2["pixel"], p2["value"]

        dy_px = px2 - px1
        if np.abs(dy_px) < 1e-9:
            dy_px = 1.0

        t_y = (y_pixel - px1) / dy_px

        if y_scale == "log":
            if v1 <= 0 or v2 <= 0:
                raise ValueError("Log scale requires positive calibration values")
            log_v1 = np.log10(v1)
            log_v2 = np.log10(v2)
            Y_data = 10 ** (log_v1 + t_y * (log_v2 - log_v1))
        else:
            Y_data = v1 + t_y * (v2 - v1)
    else:
        # Y: image y is inverted; top of plot (y_min) = Y_max, bottom (y_max) = Y_min
        dy_pixel = y_max_pixel - y0  # y_min - y_max (negative)
        if np.abs(dy_pixel) < 1e-9:
            dy_pixel = 1.0
        t_y = (y_pixel - y0) / dy_pixel  # 0 at bottom (y_max), 1 at top (y_min)

        if y_reversed:
            t_y = 1.0 - t_y  # bottom -> max, top -> min

        if y_calibration == "per_curve_normalized":
            # Stacked spectra: map trace baseline=0, peak=1
            y_min_trace = float(np.min(y_pixel))
            y_max_trace = float(np.max(y_pixel))
            dy = y_max_trace - y_min_trace
            if np.abs(dy) < 1e-9:
                Y_data = np.zeros_like(y_pixel)
            else:
                Y_data = (y_max_trace - y_pixel) / dy  # baseline (large y) -> 0, peak (small y) -> 1
        elif y_scale == "log":
            if y_min <= 0 or y_max <= 0:
                raise ValueError("Log scale requires positive y_min and y_max")
            log_y_min = np.log10(y_min)
            log_y_max = np.log10(y_max)
            Y_data = 10 ** (log_y_min + t_y * (log_y_max - log_y_min))
        else:
            Y_data = y_min + t_y * (y_max - y_min)

    return X_data, Y_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Map pixel coordinates to data-space using plot metadata"
    )
    parser.add_argument(
        "pixels",
        help="CSV file with columns x_pixel,y_pixel (or x,y). Header optional.",
    )
    parser.add_argument("metadata", help="JSON file with plot metadata")
    parser.add_argument(
        "--output",
        "-o",
        default="digitized_data.csv",
        help="Output CSV path (default: digitized_data.csv)",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="Delimiter for pixel CSV (default: ,)",
    )
    parser.add_argument(
        "--y-calibration",
        choices=["axis", "per_curve_normalized"],
        default="axis",
        help="Y mapping: axis ticks or per-curve normalized 0-1 (default: axis)",
    )
    args = parser.parse_args()

    meta = load_metadata(args.metadata)
    bb = meta["bounding_box"]
    x0 = bb["x_min"]
    y0 = bb["y_max"]  # plot origin bottom-left: y_max in image coords
    x_max_px = bb["x_max"]
    y_max_px = bb["y_min"]  # top of plot in image coords

    # Load pixel data (skip header if present)
    try:
        data = np.loadtxt(
            args.pixels,
            delimiter=args.delimiter,
            comments="#",
            dtype=float,
        )
    except (ValueError, TypeError):
        try:
            data = np.loadtxt(
                args.pixels,
                delimiter=args.delimiter,
                comments="#",
                dtype=float,
                skiprows=1,
            )
        except Exception as e:
            print(f"Error loading pixels from {args.pixels}: {e}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error loading pixels from {args.pixels}: {e}", file=sys.stderr)
        sys.exit(1)

    if data.ndim != 2 or data.shape[1] < 2:
        print(
            "Pixel file must have at least 2 columns (x_pixel, y_pixel)",
            file=sys.stderr,
        )
        sys.exit(1)

    x_pixel = data[:, 0]
    y_pixel = data[:, 1]

    y_cal = meta.get("y_calibration", "axis")
    if args.y_calibration != "axis":
        y_cal = args.y_calibration

    X_data, Y_data = pixel_to_data(
        x_pixel,
        y_pixel,
        x_min=meta.get("x_tick_min", 0.0),
        x_max=meta.get("x_tick_max", 1.0),
        y_min=meta.get("y_tick_min", 0.0),
        y_max=meta.get("y_tick_max", 1.0),
        x0=x0,
        y0=y0,
        x_max_pixel=x_max_px,
        y_max_pixel=y_max_px,
        x_scale=meta.get("x_scale", "linear"),
        y_scale=meta.get("y_scale", "linear"),
        x_reversed=meta.get("x_reversed", False),
        y_reversed=meta.get("y_reversed", False),
        y_calibration=y_cal,
        x_calibration_points=meta.get("x_calibration_points"),
        y_calibration_points=meta.get("y_calibration_points"),
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(
        out_path,
        np.column_stack((X_data, Y_data)),
        delimiter=",",
        header="x,y",
        comments="",
        fmt="%.6f",
    )
    print(f"Saved {len(X_data)} data points to {args.output}")


if __name__ == "__main__":
    main()
