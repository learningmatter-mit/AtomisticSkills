"""
Calculate ionic activation energy and RT conductivity from diffusion data.

This script fits diffusivity results from multiple temperatures to the 
Arrhenius equation. it includes robust error propagation for both the 
activation energy (Ea) and extrapolated room-temperature conductivity (sigma_RT).

Usage:
    python calculate_activation_energy.py <root_dir>

Requirements:
    - Conda environment: base-agent
    - Required packages: numpy, matplotlib, pymatgen
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import argparse
import os
from typing import Optional, List, Tuple
from pymatgen.analysis.diffusion.analyzer import fit_arrhenius, get_extrapolated_conductivity, get_extrapolated_diffusivity
from pymatgen.core import Structure
import json
import glob

def plot_arrhenius_custom(
    temps: np.ndarray, 
    diffs: np.ndarray, 
    diff_errs: Optional[np.ndarray], 
    Ea: float, 
    D0: float, 
    std_Ea: float, 
    sigma_RT: Optional[float] = None, 
    sigma_RT_err: Optional[float] = None, 
    output_file: str = "arrhenius_plot.png"
) -> None:
    """
    Generate a publication-quality Arrhenius plot with error bars and annotations.
    
    Args:
        temps: Array of temperatures (K)
        diffs: Array of diffusivities (cm^2/s)
        diff_errs: Optional array of diffusivity standard deviations
        Ea: Activation energy (eV)
        D0: Pre-exponential factor (cm^2/s)
        std_Ea: Standard deviation of Ea (eV)
        sigma_RT: Extrapolated RT conductivity (mS/cm)
        sigma_RT_err: Uncertainty in sigma_RT (mS/cm)
        output_file: Filename to save the plot
    """
    kB = 8.617333262e-5  # eV/K
    inv_temp = 1000 / temps
    
    plt.figure(figsize=(8, 6))
    
    # Plot data points with error bars
    if diff_errs is not None:
        plt.errorbar(inv_temp, diffs, yerr=diff_errs, fmt='ko', capsize=5, label=None, markersize=8)
    else:
        plt.plot(inv_temp, diffs, 'ko', label=None, markersize=8)
    
    # Plot fit line
    t_fit = np.linspace(min(temps)-50, max(temps)+100, 100)
    inv_t_fit = 1000 / t_fit
    d_fit = D0 * np.exp(-Ea / (kB * t_fit))
    plt.plot(inv_t_fit, d_fit, 'r-', linewidth=2, label=f'$E_a = {Ea:.3f} \pm {std_Ea:.3f}$ eV')
    
    plt.yscale('log')
    plt.xlabel('1000 / T (K$^{-1}$)', fontsize=18)
    plt.ylabel('Diffusivity (cm$^2$/s)', fontsize=18)
    plt.xticks(fontsize=18)
    
    ax = plt.gca()
    ax.yaxis.set_major_formatter(matplotlib.ticker.LogFormatterSciNotation())
    for tick in ax.yaxis.get_major_ticks():
        tick.label1.set_fontsize(18)
    for tick in ax.yaxis.get_minor_ticks():
        tick.label1.set_fontsize(18)
        
    plt.grid(True, which="both", ls="-", alpha=0.3)
    
    # Annotation text
    if sigma_RT:
        if sigma_RT_err:
            text_str = f"$\sigma_{{RT}}$: {sigma_RT:.2f} $\pm$ {sigma_RT_err:.2f} mS/cm"
        else:
            text_str = f"$\sigma_{{RT}}$: {sigma_RT:.2f} mS/cm"
        plt.text(0.05, 0.05, text_str, transform=ax.transAxes, fontsize=18, 
                 verticalalignment='bottom', fontweight='bold',
                 bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))
    
    plt.legend(fontsize=18, loc='upper right')
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f"Saved {output_file}")


def get_extrapolation_uncertainty(
    temps: np.ndarray, 
    diffs: np.ndarray, 
    target_temp: float, 
    diff_errs: Optional[np.ndarray] = None
) -> float:
    """
    Calculate the fractional uncertainty (Delta D / D) at a target temperature.
    
    Uses weighted linear regression residuals and covariance matrix.
    
    Args:
        temps: Temperatures (K)
        diffs: Diffusivities (cm^2/s)
        target_temp: Target temperature for extrapolation (K)
        diff_errs: Optional diffusivity uncertainties
        
    Returns:
        The fractional uncertainty sigma_lnD at the target temperature.
    """
    x = 1000.0 / temps
    y = np.log(diffs)
    
    # Use weights if provided
    if diff_errs is not None and any(diff_errs > 0):
        weights = 1.0 / (diff_errs / diffs)**2
        p, cov = np.polyfit(x, y, 1, w=np.sqrt(weights), cov=True)
    else:
        p, cov = np.polyfit(x, y, 1, cov=True)
    
    x_target = 1000.0 / target_temp
    var_y = (x_target**2 * cov[0,0] + cov[1,1] + 2 * x_target * cov[0,1])
    return np.sqrt(var_y)

def calculate_activation_energy(root_dir: str = ".", struct_path: str = None) -> None:
    """
    Read diffusion results from directory, fit Arrhenius, and save plot.
    
    Args:
        root_dir: Directory containing md_*K/diffusion*.json files.
    """
    json_files = glob.glob(os.path.join(root_dir, "*md_*K/diffusion*.json"))
    if not json_files:
        print(f"No diffusion_results.json files found in {root_dir}/md_*K/")
        return

    temps, diffs, diff_errs = [], [], []
    for jf in json_files:
        try:
            with open(jf, "r") as f:
                data = json.load(f)
                if data["diffusivity"] > 0:
                    temps.append(data["temperature"])
                    diffs.append(data["diffusivity"])
                    diff_errs.append(data.get("diffusivity_std_dev", 0.0))
        except Exception as e:
            print(f"Error reading {jf}: {e}")
    
    if len(temps) < 2:
        print("Not enough valid data points for fit.")
        return

    temps_arr = np.array(temps)
    diffs_arr = np.array(diffs)
    diff_errs_arr = np.array(diff_errs)
    
    print(f"Fitting Arrhenius equation to {len(temps)} points...")
    has_err = any(d > 0 for d in diff_errs_arr)
    Ea, D0, std_Ea = fit_arrhenius(temps_arr, diffs_arr, mode="linear", 
                                   diffusivity_errors=diff_errs_arr if has_err else None)
                                   
    # Calculate R-squared to warn about bad fits or outliers
    x = 1000.0 / temps_arr
    y = np.log(diffs_arr)
    y_mean = np.mean(y)
    ss_tot = np.sum((y - y_mean)**2)
    kB = 8.617333262e-5
    y_fit = np.log(D0) - Ea / (kB * temps_arr)
    ss_res = np.sum((y - y_fit)**2)
    r2 = 1.0 if ss_tot == 0 else 1 - (ss_res / ss_tot)
    
    if r2 < 0.95:
        print(f"\n[WARNING] The Arrhenius fit shows significant deviations (R^2 = {r2:.3f}).")
        print("This could be due to phase transitions, melting, non-linear diffusion regimes, or isolated outliers.")
        print("Please review the generated arrhenius_plot.png visually.\n")
    else:
        print(f"Fit quality (R^2): {r2:.3f}")
    
    RT = 300.0
    D_RT = get_extrapolated_diffusivity(temps_arr, diffs_arr, RT, mode="linear")
    sigma_lnD_RT = get_extrapolation_uncertainty(temps_arr, diffs_arr, RT, 
                                                diff_errs_arr if has_err else None)
    
    sigma_RT, sigma_RT_err = None, None
    if struct_path is None:
        struct_path = os.path.join(root_dir, "LGPS_221.cif")
    if struct_path and os.path.exists(struct_path):
        structure = Structure.from_file(struct_path)
        sigma_RT = get_extrapolated_conductivity(temps_arr, diffs_arr, RT, structure, "Li")
        sigma_RT_err = sigma_RT * sigma_lnD_RT
        print(f"Extrapolated RT (300K) Conductivity: {sigma_RT:.3f} +/- {sigma_RT_err:.3f} mS/cm")

    print("-" * 30)
    print(f"Activation Energy (Ea): {Ea:.3f} +/- {std_Ea:.3f} eV")
    print(f"Pre-exponential factor (D0): {D0:.3e} cm^2/s")
    print(f"Extrapolated D at 300K: {D_RT:.3e} cm^2/s")
    print("-" * 30)
    
    plot_arrhenius_custom(temps_arr, diffs_arr, diff_errs_arr if has_err else None, 
                          Ea, D0, std_Ea, sigma_RT, sigma_RT_err)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate Activation Energy ($E_a$) and RT conductivity from diffusion data."
    )
    parser.add_argument("root_dir", nargs="?", default=".", 
                        help="Root directory containing md_*K/diffusion*.json")
    parser.add_argument("--structure", type=str, default=None, help="Path to structural CIF for conductivity computation")
    args = parser.parse_args()
    calculate_activation_energy(args.root_dir, args.structure)

