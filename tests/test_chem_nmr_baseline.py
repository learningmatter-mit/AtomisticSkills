"""Tests for the chem-nmr-analysis baseline and ppm-range helpers.

Synthetic two-component 1H spectra with a known composition check that the
window baseline recovers the true fractions where the legacy minimum
subtraction (``--baseline-correct``) does not.
"""

import os
import sys

import numpy as np
import pytest

SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../skills/chem-nmr-analysis/scripts")
)
sys.path.insert(0, SCRIPTS)

from deconvolve import deconvolve_spectra  # noqa: E402
from spectra import (  # noqa: E402
    min_baseline,
    preprocess_spectrum,
    restrict_ppm,
    window_baseline,
)

GRID = np.linspace(0.5, 4.5, 1600)
SIGNAL_FREE = (2.2, 3.2)
TRUE_FRACTION_A = 0.3


def _peaks(
    centres_heights: list[tuple[float, float]], width: float = 0.01
) -> np.ndarray:
    """Sum of Gaussian lines on GRID."""
    return sum(h * np.exp(-0.5 * ((GRID - c) / width) ** 2) for c, h in centres_heights)


def _unit_area(intensity: np.ndarray) -> np.ndarray:
    """Normalize a spectrum to unit area on GRID."""
    return intensity / np.trapezoid(intensity, GRID)


# Two components with the same proton count: A (4.00 ppm diagnostic), B (3.60 ppm)
COMP_A = _unit_area(_peaks([(4.0, 1.0), (1.0, 3.0), (1.6, 2.0)]))
COMP_B = _unit_area(_peaks([(3.6, 1.0), (1.2, 3.0), (1.8, 2.0)]))


def _spectrum(intensity: np.ndarray) -> np.ndarray:
    return np.column_stack([GRID, intensity])


def _noisy_mixture(
    offset: float = -0.5, sigma: float = 0.1, seed: int = 0
) -> np.ndarray:
    """Mixture with a known composition, a constant offset and white noise."""
    rng = np.random.default_rng(seed)
    clean = TRUE_FRACTION_A * COMP_A + (1.0 - TRUE_FRACTION_A) * COMP_B
    return _spectrum(clean + offset + rng.normal(0.0, sigma, GRID.size))


def _fraction_a(mixture: np.ndarray, refs: list[np.ndarray]) -> float:
    return deconvolve_spectra(mixture, refs, [1, 1])["proportions"][0]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_window_median_recovers_fraction_on_noisy_offset_mixture(seed: int) -> None:
    """Median of a signal-free window removes the offset; the fraction is recovered."""
    refs = [_spectrum(COMP_A), _spectrum(COMP_B)]
    mixture, value = window_baseline(_noisy_mixture(seed=seed), SIGNAL_FREE, "median")

    assert value == pytest.approx(-0.5, abs=0.02)
    assert _fraction_a(mixture, refs) == pytest.approx(TRUE_FRACTION_A, abs=0.025)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_min_subtraction_is_biased_on_noisy_offset_mixture(seed: int) -> None:
    """The minimum sits several sigma below the baseline and biases the fraction."""
    refs = [_spectrum(COMP_A), _spectrum(COMP_B)]
    mixture, value = min_baseline(_noisy_mixture(seed=seed))

    assert value < -0.5 - 2 * 0.1
    assert _fraction_a(mixture, refs) - TRUE_FRACTION_A > 0.05


def test_window_max_removes_one_sided_reference_floor() -> None:
    """A positive digitization-like floor on the references needs the max statistic."""
    floor = 0.2 + 0.2 * ((GRID * 30.0) % 1.0)  # sawtooth between 0.2 and 0.4
    refs_raw = [_spectrum(COMP_A + floor), _spectrum(COMP_B + floor)]
    mixture = _spectrum(TRUE_FRACTION_A * COMP_A + (1.0 - TRUE_FRACTION_A) * COMP_B)

    refs_max = [window_baseline(r, SIGNAL_FREE, "max")[0] for r in refs_raw]
    refs_median = [window_baseline(r, SIGNAL_FREE, "median")[0] for r in refs_raw]

    err_max = abs(_fraction_a(mixture, refs_max) - TRUE_FRACTION_A)
    err_median = abs(_fraction_a(mixture, refs_median) - TRUE_FRACTION_A)
    assert err_max < 0.005
    assert err_median > 0.02


def test_window_without_samples_uses_bounding_points() -> None:
    """A window inside a gap of dropped zero-intensity points gives a zero baseline."""
    keep = (GRID < 2.0) | (GRID > 3.4)
    gapped = _spectrum(COMP_A)[keep]
    corrected, value = window_baseline(gapped, SIGNAL_FREE, "median")

    assert value == pytest.approx(0.0, abs=1e-6)
    assert np.array_equal(corrected[:, 0], gapped[:, 0])


def test_negatives_are_clipped_and_ppm_range_applied_after_baseline() -> None:
    """Window baseline clips negatives; the ppm range is cut after the baseline step."""
    processed, value = preprocess_spectrum(
        _noisy_mixture(),
        baseline_window=SIGNAL_FREE,
        ppm_range=(3.5, 4.1),
    )

    assert value == pytest.approx(-0.5, abs=0.02)
    assert processed[:, 1].min() >= 0.0
    assert processed[:, 0].min() >= 3.5 and processed[:, 0].max() <= 4.1


def test_restrict_ppm_rejects_empty_range() -> None:
    with pytest.raises(ValueError):
        restrict_ppm(_spectrum(COMP_A), (10.0, 11.0))


def test_baseline_options_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError):
        preprocess_spectrum(
            _spectrum(COMP_A), baseline_correct=True, baseline_window=SIGNAL_FREE
        )
    with pytest.raises(ValueError):
        window_baseline(_spectrum(COMP_A), SIGNAL_FREE, "mean")
