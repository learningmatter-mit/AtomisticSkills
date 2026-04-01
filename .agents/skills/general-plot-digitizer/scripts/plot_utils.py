"""
Shared utilities for the plot digitizer pipeline.

Usage:
    # As a library
    from plot_utils import load_metadata, scale_metadata_bbox

    # As a CLI tool (draw pixel grid for VLM coordinate reading)
    python plot_utils.py plot.png --draw-grid
    python plot_utils.py plot.png --draw-grid --grid-size 50

Requirements:
    - Conda environment: base-agent
    - Required packages: json (stdlib), copy (stdlib), opencv (cv2, for --draw-grid)
"""

import copy
import json


def load_metadata(metadata_path: str, validate: bool = True) -> dict:
    """
    Load plot metadata from JSON file.

    Args:
        metadata_path: Path to metadata.json
        validate: If True (default), validate required fields. If False, return raw JSON.

    Returns:
        Metadata dict.

    Raises:
        ValueError: If validate=True and required fields are missing.
    """
    with open(metadata_path) as f:
        meta = json.load(f)
    if not validate:
        return meta
        
    if "x_calibration_points" not in meta:
        for key in ("x_tick_min", "x_tick_max"):
            if key not in meta:
                raise ValueError(f"Metadata missing required field: {key} (or x_calibration_points)")
                
    if "y_calibration_points" not in meta:
        for key in ("y_tick_min", "y_tick_max"):
            if key not in meta:
                raise ValueError(f"Metadata missing required field: {key} (or y_calibration_points)")
                
    for key in ("x_scale", "y_scale", "bounding_box"):
        if key not in meta:
            raise ValueError(f"Metadata missing required field: {key}")
            
    bb = meta["bounding_box"]
    for k in ("x_min", "y_min", "x_max", "y_max"):
        if k not in bb:
            raise ValueError(f"bounding_box missing: {k}")
    return meta


def scale_metadata_bbox(meta: dict, factor: float) -> dict:
    """
    Scale bounding box and curve regions by factor. Returns a new dict.

    Used when pre-upscaling images: metadata coordinates must match the
    upscaled image dimensions.

    Args:
        meta: Metadata dict with bounding_box and optionally curves.
        factor: Scale factor (e.g. 2.0 for 2x upscale).

    Returns:
        New metadata dict with scaled coordinates.
    """
    result = copy.deepcopy(meta)

    bb = result["bounding_box"]
    for k in ("x_min", "y_min", "x_max", "y_max"):
        if k in bb:
            bb[k] = int(round(bb[k] * factor))

    for curve in result.get("curves", []):
        reg = curve.get("region")
        if reg:
            if "y_min" in reg:
                reg["y_min"] = int(round(reg["y_min"] * factor))
            if "y_max" in reg:
                reg["y_max"] = int(round(reg["y_max"] * factor))
        for mr in curve.get("mask_regions", []):
            for k in ("x_min", "y_min", "x_max", "y_max"):
                if k in mr:
                    mr[k] = int(round(mr[k] * factor))

    for region_key in ("text_regions", "mask_regions"):
        for tr in result.get(region_key, []):
            for k in ("x_min", "y_min", "x_max", "y_max"):
                if k in tr:
                    tr[k] = int(round(tr[k] * factor))

    for cal_key in ("x_calibration_points", "y_calibration_points"):
        for cp in result.get(cal_key, []):
            if "pixel" in cp:
                cp["pixel"] = int(round(cp["pixel"] * factor))

    if "image_width" in result and result["image_width"] is not None:
        result["image_width"] = int(round(result["image_width"] * factor))
    if "image_height" in result and result["image_height"] is not None:
        result["image_height"] = int(round(result["image_height"] * factor))

    return result

def draw_grid_on_image(image_path: str, output_path: str, grid_size: int = 100) -> None:
    """
    Draw a labeled pixel grid on an image for precise coordinate reading.

    Overlays horizontal and vertical lines at regular intervals with pixel
    coordinate labels, enabling the VLM to report bounding boxes and
    calibration points accurately.

    Args:
        image_path: Path to the input image.
        output_path: Path where the annotated grid image will be saved.
        grid_size: Spacing between grid lines in pixels (default 100).

    Raises:
        ValueError: If the image cannot be read.
    """
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image {image_path}")
    
    h, w = img.shape[:2]
    # Draw horizontal lines
    for y in range(0, h, grid_size):
        cv2.line(img, (0, y), (w, y), (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(img, str(y), (5, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
    # Draw vertical lines
    for x in range(0, w, grid_size):
        cv2.line(img, (x, 0), (x, h), (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(img, str(x), (x + 5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
    cv2.imwrite(output_path, img)


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    import sys

    parser = argparse.ArgumentParser(description="Utilities for plot digitization")
    parser.add_argument("image", nargs="?", help="Input image path")
    parser.add_argument("--draw-grid", action="store_true", help="Draw a 100x100 grid on the image for pixel estimation")
    parser.add_argument("--grid-size", type=int, default=100, help="Grid size in pixels (default: 100)")
    
    args = parser.parse_args()
    
    if args.draw_grid:
        if not args.image:
            print("Error: --draw-grid requires an input image path.", file=sys.stderr)
            sys.exit(1)
            
        img_path = Path(args.image)
        if not img_path.exists():
            print(f"Error: Image not found: {args.image}", file=sys.stderr)
            sys.exit(1)
            
        out_path = img_path.with_name(f"{img_path.stem}_grid.png")
        try:
            draw_grid_on_image(str(img_path), str(out_path), grid_size=args.grid_size)
            print(f"Grid image saved to {out_path}")
        except Exception as e:
            print(f"Error drawing grid: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
