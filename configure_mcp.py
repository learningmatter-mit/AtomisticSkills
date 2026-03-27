#!/usr/bin/env python3
"""Adapt mcp_config.json paths to the local machine.

Rewrites the ``command`` (conda env Python binary) and ``PYTHONPATH``
entries in mcp_config.json so they match the current machine's
directory layout.

Usage:
    python configure_mcp.py                      # auto-detect conda base
    python configure_mcp.py /path/to/miniforge3  # explicit conda base
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ENV_PATTERN = re.compile(r".*/envs/([^/]+)/bin/python$")
PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "mcp_config.json"


def detect_conda_base() -> str | None:
    """Return the conda / mamba base prefix, or *None* if undetectable."""
    for cmd in ("conda", "mamba"):
        try:
            result = subprocess.run(
                [cmd, "info", "--base"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                base = result.stdout.strip()
                if base and Path(base).is_dir():
                    return base
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    home = Path.home()
    for name in ("miniforge3", "mambaforge", "miniconda3", "anaconda3"):
        candidate = home / name
        if candidate.is_dir():
            return str(candidate)

    return None


def rewrite_config(conda_base: str) -> None:
    """Read, patch, and overwrite *mcp_config.json* in-place."""
    with open(CONFIG_PATH) as fh:
        config = json.load(fh)

    project_root = str(PROJECT_ROOT)

    for server in config.get("mcpServers", {}).values():
        match = ENV_PATTERN.match(server.get("command", ""))
        if match:
            env_name = match.group(1)
            server["command"] = f"{conda_base}/envs/{env_name}/bin/python"

        env = server.get("env", {})
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = project_root

    with open(CONFIG_PATH, "w") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Patch mcp_config.json with local paths."
    )
    parser.add_argument(
        "conda_base",
        nargs="?",
        default=None,
        help="Path to the conda/mamba base directory (auto-detected if omitted).",
    )
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    conda_base: str | None = args.conda_base
    if conda_base is not None:
        if not Path(conda_base).is_dir():
            print(f"Error: {conda_base} is not a valid directory.", file=sys.stderr)
            sys.exit(1)
    else:
        conda_base = detect_conda_base()
        if conda_base is None:
            print(
                "Error: Could not auto-detect a conda/mamba installation.\n"
                "Please provide the base path explicitly:\n"
                f"  python {sys.argv[0]} /path/to/miniforge3",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Project root : {PROJECT_ROOT}")
    print(f"Conda base   : {conda_base}")

    rewrite_config(conda_base)

    print(f"Updated      : {CONFIG_PATH}")


if __name__ == "__main__":
    main()
