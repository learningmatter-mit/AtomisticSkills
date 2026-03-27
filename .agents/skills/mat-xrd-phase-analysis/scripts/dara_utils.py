import os
from pathlib import Path
from typing import Optional

try:
    from dara.xrd import XYFile
except ImportError:
    raise ImportError(
        "DARA is not installed. Install with: pip install dara-xrd\n"
        "See https://idocx.github.io/dara/install.html for details."
    )


def load_xrd_file(xrd_path: Path) -> XYFile:
    """
    Load XRD data from .xy file.

    Args:
        xrd_path: Path to .xy file (two columns: 2θ, intensity)

    Returns:
        XYFile object
    """
    return XYFile.from_file(xrd_path)
