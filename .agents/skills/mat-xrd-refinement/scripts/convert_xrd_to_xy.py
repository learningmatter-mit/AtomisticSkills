"""
Convert XRD data from JSON (xrd-spectrum output) or DIF files to .xy format for DARA.

Usage:
    python convert_xrd_to_xy.py input_xrd.json output.xy
    python convert_xrd_to_xy.py input.dif output.xy  # or .txt DIF file

Requirements:
    - Conda environment: base-agent
    - Required packages: json
"""

import argparse
import json
import re
from pathlib import Path


def convert_dif_to_xy(dif_path: Path) -> None:
    """
    Convert a DIF-format XRD file to .xy format for DARA.

    DIF files typically have a header (title, cell parameters, etc.), a line
    with column labels like "2-THETA      INTENSITY    D-SPACING   H   K   L",
    then data rows with 2-theta and intensity as the first two numeric columns.
    Parsing stops at a separator line (e.g. "===...") or when a line fails to
    parse as two floats.

    Args:
        dif_path: Path to DIF file (.txt or .dif).
    """
    with open(dif_path) as f:
        lines = f.readlines()

    # Find the line that marks the start of the data (contains 2-THETA and INTENSITY)
    data_start = None
    for i, line in enumerate(lines):
        if re.search(r"2[- ]?THETA|2THETA", line, re.IGNORECASE) and re.search(
            r"INTENSITY", line, re.IGNORECASE
        ):
            data_start = i + 1
            break

    if data_start is None:
        raise ValueError(
            "DIF file must contain a header line with '2-THETA' and 'INTENSITY' column labels"
        )

    pairs = []
    for line in lines[data_start:]:
        line = line.strip()
        # Stop at separator or empty line
        if not line or line.startswith("=") or line.startswith("-"):
            break
        # Split on whitespace; expect at least two numeric fields (2-theta, intensity)
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            two_theta = float(parts[0])
            intensity = float(parts[1])
            pairs.append((two_theta, intensity))
        except ValueError:
            # Not a data line (e.g. copyright), stop
            break

    if not pairs:
        raise ValueError(
            f"No 2-theta/intensity data found in DIF file after line {data_start}"
        )

    output_path = Path(dif_path.parent / (dif_path.stem + ".xy"))
    with open(output_path, "w") as f:
        for two_theta, intensity in pairs:
            f.write(f"{two_theta:.6f} {intensity:.6f}\n")

    print(f"Converted {len(pairs)} data points from {dif_path} to {output_path}")


def convert_json_to_xy(json_path: Path) -> None:
    """
    Convert XRD JSON output to .xy format.
    
    Args:
        json_path: Path to JSON file from xrd-spectrum skill
    """
    with open(json_path) as f:
        data = json.load(f)
    
    # Extract 2θ (x) and intensity (y) arrays
    x = data.get("x", [])
    y = data.get("y", [])
    
    if not x or not y:
        raise ValueError("JSON file must contain 'x' and 'y' arrays")
    
    if len(x) != len(y):
        raise ValueError(f"x and y arrays must have same length: {len(x)} vs {len(y)}")
    
    # Write .xy file (two space-separated columns)
    output_path = Path(json_path.parent / (json_path.stem + ".xy"))
    with open(output_path, "w") as f:
        for angle, intensity in zip(x, y):
            f.write(f"{angle:.6f} {intensity:.6f}\n")
    
    print(f"Converted {len(x)} data points from {json_path} to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert XRD data (JSON or DIF) to .xy format for DARA"
    )
    parser.add_argument(
        "--input_file",
        help="Path to XRD file: JSON (from xrd-spectrum skill) or experimental DIF (.txt)"
    )
    parser.add_argument(
        "--format",
        choices=("auto", "json", "dif"),
        default="auto",
        help="Input format; 'auto' infers from extension (default: auto)"
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    fmt = args.format
    if fmt == "auto":
        suf = input_path.suffix.lower()
        if suf == ".json":
            fmt = "json"
        elif suf in (".txt", ".dif"):
            fmt = "dif"
        else:
            with open(input_path) as f:
                content = f.read()
            fmt = "dif" if ("2-THETA" in content or "2THETA" in content) else "json"

    if fmt == "json":
        convert_json_to_xy(input_path)
    elif fmt == "dif":
        convert_dif_to_xy(input_path)
    else:
        raise ValueError(f"Invalid format: {fmt}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
