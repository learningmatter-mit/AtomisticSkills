"""
NMR spectrum I/O utilities: load single spectra or stacks of time-series spectra.

Usage:
    from spectra import load_spectrum, load_time_series

Requirements:
    - Environment: nmr-agent (conda)
    - Required packages: numpy
"""

import pathlib
import numpy as np
from typing import Tuple, List, Optional


def detect_delimiter(path: str) -> str:
    """Heuristic delimiter detection: .tsv -> tab, else sniff first line."""
    p = pathlib.Path(path)
    if p.suffix.lower() == ".tsv":
        return "\t"
    try:
        with open(path, "r", errors="ignore") as f:
            line = f.readline()
        return "\t" if "\t" in line else ","
    except Exception:
        return ","


def load_spectrum(path: str, delimiter: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load a two-column spectrum file (ppm, intensity).

    Args:
        path: Path to .csv or .xy file (two numeric columns: ppm, intensity).
        delimiter: Column delimiter. If None, auto-detected from file extension/content.

    Returns:
        Tuple of (ppm_array, intensity_array), both 1-D float64, sorted by ppm ascending.
    """
    if delimiter is None:
        delimiter = detect_delimiter(path)
    try:
        arr = np.loadtxt(path, delimiter=delimiter, usecols=[0, 1])
    except ValueError:
        arr = np.loadtxt(path, delimiter=delimiter, usecols=[0, 1], skiprows=1)
    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError(f"{path}: expected two numeric columns (ppm, intensity)")
    ppm, intensity = arr[:, 0], arr[:, 1]
    order = np.argsort(ppm)
    return ppm[order], intensity[order]


def interpolate_to_grid(
    ppm: np.ndarray,
    intensity: np.ndarray,
    grid: np.ndarray,
) -> np.ndarray:
    """
    Interpolate a spectrum to a common ppm grid (linear interpolation, zero outside range).

    Args:
        ppm: Source ppm values (sorted ascending).
        intensity: Source intensity values.
        grid: Target ppm grid (sorted ascending).

    Returns:
        Interpolated intensity array aligned to grid.
    """
    return np.interp(grid, ppm, intensity, left=0.0, right=0.0)


def load_time_series(
    paths: List[str],
    n_points: int = 2000,
    ppm_min: Optional[float] = None,
    ppm_max: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load multiple spectra and stack into a matrix on a common ppm grid.

    Args:
        paths: List of .csv/.xy file paths (time-ordered).
        n_points: Number of interpolation grid points.
        ppm_min: Minimum ppm for the common grid (default: min across all spectra).
        ppm_max: Maximum ppm for the common grid (default: max across all spectra).

    Returns:
        Tuple of:
            grid: 1-D array of shape (n_points,) — common ppm axis.
            matrix: 2-D array of shape (n_spectra, n_points) — interpolated intensities.
    """
    spectra = [load_spectrum(p) for p in paths]
    if ppm_min is None:
        ppm_min = float(min(s[0].min() for s in spectra))
    if ppm_max is None:
        ppm_max = float(max(s[0].max() for s in spectra))
    grid = np.linspace(ppm_min, ppm_max, n_points)
    matrix = np.stack([interpolate_to_grid(ppm, intens, grid) for ppm, intens in spectra])
    return grid, matrix
