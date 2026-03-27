"""
Analyze GCMC results and generate phase diagrams.

This script processes the results from GCMC chemical potential sweeps and
generates visualizations including composition vs. chemical potential curves
and temperature-composition phase diagrams.

Usage:
    python analyze_gcmc_results.py \\
        --results_file gcmc_results/results_summary.json \\
        --output_dir gcmc_results/ \\
        --element Ag

Requirements:
    - Conda environment: smol-agent  
    - Required packages: matplotlib, numpy, json
"""

import argparse
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict


def load_results(results_file: str) -> Dict[str, Any]:
    """Load GCMC results from JSON file."""
    with open(results_file, 'r') as f:
        data = json.load(f)
    return data


def plot_mu_vs_composition(
    results: List[Dict],
    element: str,
    output_file: str
):
    """
    Plot chemical potential vs. composition for each temperature.
    
    Args:
        results: List of result dictionaries
        element: Element name
        output_file: Output PNG file path
    """
    # Group by temperature
    temp_data = defaultdict(lambda: {"mu": [], "x": [], "x_std": []})
    
    for res in results:
        T = res["temperature"]
        mu = res["chemical_potential"]
        x = res["mean_composition"]
        x_std = res["std_composition"]
        
        temp_data[T]["mu"].append(mu)
        temp_data[T]["x"].append(x)
        temp_data[T]["x_std"].append(x_std)
    
    # Sort temperatures
    temperatures = sorted(temp_data.keys())
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 7))
    
    cmap = plt.cm.viridis
    colors = [cmap(i / len(temperatures)) for i in range(len(temperatures))]
    
    for T, color in zip(temperatures, colors):
        data = temp_data[T]
        # Sort by mu
        indices = np.argsort(data["mu"])
        mu = np.array(data["mu"])[indices]
        x = np.array(data["x"])[indices]
        x_std = np.array(data["x_std"])[indices]
        
        ax.plot(mu, x, 'o-', color=color, label=f'{T:.0f} K', markersize=6, linewidth=2)
        ax.fill_between(mu, x - x_std, x + x_std, color=color, alpha=0.2)
    
    ax.set_xlabel(f'Chemical Potential μ({element}) (eV)', fontsize=14)
    ax.set_ylabel(f'Composition x({element})', fontsize=14)
    ax.set_title('Chemical Potential vs. Composition', fontsize=16, fontweight='bold')
    ax.legend(fontsize=11, loc='best')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-0.05, 1.05)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved: {output_file}")


def plot_phase_diagram(
    results: List[Dict],
    element: str,
    output_file: str
):
    """
    Plot temperature-composition phase diagram.
    
    Args:
        results: List of result dictionaries
        element: Element name
        output_file: Output PNG file path
    """
    # Group by temperature
    temp_data = defaultdict(lambda: {"x": [], "mu": []})
    
    for res in results:
        T = res["temperature"]
        x = res["mean_composition"]
        mu = res["chemical_potential"]
        
        temp_data[T]["x"].append(x)
        temp_data[T]["mu"].append(mu)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 8))
    
    temperatures = sorted(temp_data.keys())
    
    # Plot composition traces for each temperature
    for T in temperatures:
        data = temp_data[T]
        x = np.array(data["x"])
        indices = np.argsort(x)
        x_sorted = x[indices]
        
        # Plot horizontal line at this temperature spanning composition range
        ax.scatter([T] * len(x_sorted), x_sorted, s=40, alpha=0.6, c='steelblue')
    
    # Create filled contour if enough data points
    if len(temperatures) >= 3:
        # Create grid
        T_grid = []
        x_grid = []
        for T in temperatures:
            x = sorted(temp_data[T]["x"])
            T_grid.extend([T] * len(x))
            x_grid.extend(x)
        
        ax.scatter(T_grid, x_grid, s=50, c='darkblue', alpha=0.7, edgecolors='white', linewidth=0.5)
    
    ax.set_xlabel('Temperature (K)', fontsize=14)
    ax.set_ylabel(f'Composition x({element})', fontsize=14)
    ax.set_title('Temperature-Composition Phase Diagram', fontsize=16, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-0.05, 1.05)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved: {output_file}")


def plot_contour_phase_diagram(
    results: List[Dict],
    element: str,
    output_file: str
):
    """
    Plot temperature-chemical potential contour phase diagram.
    
    Creates a 2D contour plot showing composition as a function of
    temperature and chemical potential.
    
    Args:
        results: List of result dictionaries
        element: Element name
        output_file: Output PNG file path
    """
    # Extract unique temperatures and chemical potentials
    temps = sorted(list(set(r["temperature"] for r in results)))
    mus = sorted(list(set(r["chemical_potential"] for r in results)))
    
    # Create meshgrid
    T_grid, mu_grid = np.meshgrid(temps, mus)
    comp_grid = np.zeros_like(T_grid)
    
    # Fill composition grid
    for result in results:
        T_idx = temps.index(result["temperature"])
        mu_idx = mus.index(result["chemical_potential"])
        comp_grid[mu_idx, T_idx] = result["mean_composition"]
    
    # Create phase diagram
    fig, ax = plt.subplots(figsize=(10, 7))
    
    # Contour plot with smooth color gradients
    levels = np.linspace(0, 1, 21)
    contourf = ax.contourf(T_grid, mu_grid, comp_grid, levels=levels,
                            cmap='RdYlBu_r', extend='both')
    
    # Add contour lines at key compositions
    contour_lines = ax.contour(T_grid, mu_grid, comp_grid,
                                levels=[0.1, 0.25, 0.5, 0.75, 0.9],
                                colors='black', linewidths=1.5, alpha=0.6)
    ax.clabel(contour_lines, inline=True, fontsize=10, fmt='%0.2f')
    
    # Colorbar
    cbar = plt.colorbar(contourf, ax=ax, label=f'{element} Composition (mole fraction)')
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
    
    # Labels
    ax.set_xlabel('Temperature [K]', fontsize=13, fontweight='bold')
    ax.set_ylabel(f'Chemical Potential μ({element}) [eV]', fontsize=13, fontweight='bold')
    ax.set_title(f'{element} Composition: T-μ Phase Diagram', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved: {output_file}")


def plot_energy_vs_mu(
    results: List[Dict],
    element: str,
    output_file: str
):
    """
    Plot energy per atom vs. chemical potential.
    
    Args:
        results: List of result dictionaries
        element: Element name
        output_file: Output PNG file path
    """
    # Group by temperature
    temp_data = defaultdict(lambda: {"mu": [], "energy": [], "energy_std": []})
    
    for res in results:
        T = res["temperature"]
        mu = res["chemical_potential"]
        E = res["mean_energy"]
        E_std = res["std_energy"]
        
        temp_data[T]["mu"].append(mu)
        temp_data[T]["energy"].append(E)
        temp_data[T]["energy_std"].append(E_std)
    
    # Sort temperatures
    temperatures = sorted(temp_data.keys())
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 7))
    
    cmap = plt.cm.plasma
    colors = [cmap(i / len(temperatures)) for i in range(len(temperatures))]
    
    for T, color in zip(temperatures, colors):
        data = temp_data[T]
        # Sort by mu
        indices = np.argsort(data["mu"])
        mu = np.array(data["mu"])[indices]
        E = np.array(data["energy"])[indices]
        E_std = np.array(data["energy_std"])[indices]
        
        ax.plot(mu, E, 'o-', color=color, label=f'{T:.0f} K', markersize=6, linewidth=2)
        ax.fill_between(mu, E - E_std, E + E_std, color=color, alpha=0.2)
    
    ax.set_xlabel(f'Chemical Potential μ({element}) (eV)', fontsize=14)
    ax.set_ylabel('Energy per Atom (eV)', fontsize=14)
    ax.set_title('Energy vs. Chemical Potential', fontsize=16, fontweight='bold')
    ax.legend(fontsize=11, loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved: {output_file}")


def print_summary_statistics(data: Dict[str, Any]):
    """Print summary statistics of the GCMC sweep."""
    metadata = data["metadata"]
    results = data["results"]
    
    print(f"\n{'='*60}")
    print("GCMC Sweep Summary")
    print(f"{'='*60}")
    print(f"Element: {metadata['element']}")
    print(f"Supercell: {metadata['supercell']}")
    print(f"Temperatures: {metadata['temperatures']}")
    print(f"Chemical potential range: {metadata['mu_range'][0]:.3f} to {metadata['mu_range'][1]:.3f} eV")
    print(f"MC steps: {metadata['steps']} (equilibration: {metadata['equilibration_steps']})")
    print(f"\nTotal simulations: {len(results)}")
    
    # Composition range
    compositions = [r["mean_composition"] for r in results]
    print(f"Composition range: {min(compositions):.4f} to {max(compositions):.4f}")
    
    # Energy range
    energies = [r["mean_energy"] for r in results]
    print(f"Energy range: {min(energies):.4f} to {max(energies):.4f} eV/atom")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze GCMC results and generate phase diagrams"
    )
    parser.add_argument(
        "--results_file",
        type=str,
        required=True,
        help="Path to results_summary.json from GCMC sweep"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./",
        help="Output directory for plots"
    )
    parser.add_argument(
        "--element",
        type=str,
        required=True,
        help="Element name (e.g., 'Ag')"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load results
    print(f"\nLoading results from: {args.results_file}")
    data = load_results(args.results_file)
    results = data["results"]
    
    # Print summary
    print_summary_statistics(data)
    
    # Generate plots
    print("Generating plots...")
    
    plot_mu_vs_composition(
        results,
        args.element,
        str(output_dir / "mu_vs_composition.png")
    )
    
    plot_phase_diagram(
        results,
        args.element,
        str(output_dir / "phase_diagram.png")
    )
    
    plot_energy_vs_mu(
        results,
        args.element,
        str(output_dir / "energy_vs_mu.png")
    )
    
    plot_contour_phase_diagram(
        results,
        args.element,
        str(output_dir / "contour_phase_diagram.png")
    )
    
    print(f"\n✓ Analysis complete! Plots saved to: {output_dir}\n")


if __name__ == "__main__":
    main()
