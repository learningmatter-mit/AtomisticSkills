import numpy as np


def caglioti_fwhm(theta, U, V, W):
    """
    Calculate the FWHM using the Caglioti formula.
    theta: float, the angle in degrees
    U, V, W: Caglioti parameters
    """
    rad_theta = np.radians(theta / 2)  # Convert theta to radians
    return (U * np.tan(rad_theta)**2 + V * np.tan(rad_theta) + W)**0.5

def pseudo_voigt(x, center, amplitude, U, V, W, eta):
    """
    Pseudo-Voigt function using Caglioti FWHM.
    x: array-like, the independent variable
    center: float, the center of the peak
    amplitude: float, the height of the peak
    U, V, W: Caglioti parameters
    eta: float, the fraction of the Lorentzian component (0 <= eta <= 1)
    """
    fwhm = caglioti_fwhm(center, U, V, W)
    sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))  # Convert FWHM to sigma for Gaussian
    
    lorentzian = amplitude * (fwhm**2 / ((x - center)**2 + fwhm**2))
    gaussian = amplitude * np.exp(-(x - center)**2 / (2 * sigma**2))
    return eta * lorentzian + (1 - eta) * gaussian


def superimposed_pseudo_voigt(x, xy_merge, U, V, W, eta):
    """
    Superimpose multiple pseudo-Voigt functions using Caglioti FWHM.
    x: array-like, the independent variable
    xy_merge: nx2 array, first column is peak locations, second column is intensities
    U, V, W: Caglioti parameters
    eta: float, the fraction of the Lorentzian component (0 <= eta <= 1)
    """
    total = np.zeros_like(x)
    for row in xy_merge:
        center, amplitude = row
        total += pseudo_voigt(x, center, amplitude, U, V, W, eta)
    total = total / max(total)
    return total


def simulate_pv_xrd_for_row(xy_merge, U, V, W, eta, bin=0.05):
    """
    Simulate a pseudo-Voigt XRD pattern for a given set of peaks.

    Args:
    xy_merge: array-like, the 2D array of peak locations and intensities
    U, V, W: float, the Caglioti parameters
    noise: float, the standard deviation of the noise

    Returns:
    sim_xrd: array-like, the simulated XRD pattern
    """

    x = np.arange(5, 90, bin)
    sim_xrd = superimposed_pseudo_voigt(x, xy_merge, U, V, W, eta)

    return sim_xrd, x


def get_sim_xrd_from_pattern(pattern, eta, caglioti_params, bin=0.05):
    """
    Get the simulated XRD pattern for pymatgen generated pattern object
    """
    x = np.array(pattern.x)
    y = np.array(pattern.y)

    xy_merge = np.column_stack((x, y))

    U, V, W = caglioti_params[0], caglioti_params[1], caglioti_params[2] 

    sim_xrd, theta = simulate_pv_xrd_for_row(xy_merge, U, V, W, eta, bin=bin)
    return sim_xrd, theta