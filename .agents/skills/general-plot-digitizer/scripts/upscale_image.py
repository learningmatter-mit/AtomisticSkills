"""
Upscale a plot image using bicubic interpolation.

Saves the upscaled image to disk. Used by the digitization pipeline
for low-resolution plot images before curve extraction.

Usage:
    python upscale_image.py plot.png --factor 2 --output plot_upscaled.png

Requirements:
    - Conda environment: base-agent
    - Required packages: opencv (cv2)
"""

import argparse
import sys
from pathlib import Path

import cv2


def upscale_image(
    image_path: str | Path,
    output_path: str | Path,
    factor: float = 2.0,
) -> Path:
    """
    Upscale an image by factor and save to output path.

    Uses cv2.INTER_CUBIC interpolation.

    Args:
        image_path: Path to input image.
        output_path: Path for saved upscaled image.
        factor: Scale factor (default 2.0).

    Returns:
        Path to the saved upscaled image.

    Raises:
        RuntimeError: If image cannot be loaded or saved.
    """
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"Could not load image: {image_path}")

    if factor <= 1.0:
        raise ValueError(f"Upscale factor must be > 1.0, got {factor}")

    upscaled = cv2.resize(
        img,
        None,
        fx=factor,
        fy=factor,
        interpolation=cv2.INTER_CUBIC,
    )

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not cv2.imwrite(str(out_path), upscaled):
        raise RuntimeError(f"Could not save image to: {output_path}")

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upscale plot image for low-resolution digitization"
    )
    parser.add_argument("image", help="Path to plot image (PNG, JPG)")
    parser.add_argument(
        "--factor",
        "-f",
        type=float,
        default=2.0,
        metavar="FACTOR",
        help="Upscale factor (default: 2.0)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output path for upscaled image (default: stem_upscaled.png in same dir)",
    )
    args = parser.parse_args()

    if args.factor <= 1.0:
        print(f"Error: factor must be > 1.0, got {args.factor}", file=sys.stderr)
        sys.exit(1)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = image_path.parent / f"{image_path.stem}_upscaled{image_path.suffix}"

    try:
        out_path = upscale_image(args.image, output_path, factor=args.factor)
        print(f"Saved upscaled image to {out_path}")
    except (RuntimeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
