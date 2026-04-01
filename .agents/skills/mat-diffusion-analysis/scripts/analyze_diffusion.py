"""
Analyze ionic diffusion from Molecular Dynamics (MD) trajectories.

This script uses pymatgen's DiffusionAnalyzer to calculate the Mean Square 
Displacement (MSD) and diffusivity (D) of a specific atomic species. It 
automatically detects the MD logging interval from the simulation log file.

Usage:
    python analyze_diffusion.py <traj_path> --species <specie> --temperature <T> [options]

Requirements:
    - Conda environment: base-agent
    - Required packages: ase, numpy, matplotlib, pymatgen
"""

import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ase.io import read
from ase import Atoms
import os
import json
from typing import Optional, List
from pymatgen.analysis.diffusion.analyzer import DiffusionAnalyzer
from pymatgen.io.ase import AseAtomsAdaptor

def get_md_params(traj_path: str) -> Optional[float]:
    """
    Attempt to find the log file and extract the time interval between frames.
    
    Args:
        traj_path: Path to the ASE trajectory file (.traj)
        
    Returns:
        The detected frame interval in picoseconds (ps), or None if not found.
    """
    log_path = traj_path.replace(".traj", ".log")
    if not os.path.exists(log_path):
        print(f"Warning: Log file {log_path} not found. Using provided/default time parameters.")
        return None
    
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
            if len(lines) < 3:
                return None
            # Find the header line and the first two data lines
            # Example format:
            # Time[ps]      Etot[eV] ...
            # 0.0000         -848.722 ...
            # 0.2000         -846.817 ...
            t0 = float(lines[1].split()[0])
            t1 = float(lines[2].split()[0])
            dt_ps = t1 - t0
            print(f"Auto-detected frame interval from log: {dt_ps:.4f} ps")
            return dt_ps
    except Exception as e:
        print(f"Error parsing log file: {e}")
        return None

def analyze_diffusion(
    traj_path: str, 
    species: str, 
    temperature: float, 
    time_step: float = 1.0, 
    log_interval: int = 100, 
    ignore_ps: float = 5.0, 
    output_dir: str = "."
) -> None:
    """
    Analyze diffusion from ASE trajectory using pymatgen-analysis-diffusion.
    
    Saves MSD plots and diffusion results (JSON) to the output directory.
    
    Args:
        traj_path: Path to the ASE trajectory file
        species: Atomic species to analyze (e.g., 'Li')
        temperature: Simulation temperature (K)
        time_step: MD time step used in simulation (fs) - used only if log detection fails
        log_interval: Number of MD steps between trajectory frames - used only if log detection fails
        ignore_ps: Amount of initial simulation time to ignore for equilibration (ps)
        output_dir: Directory to save plots and result files
    """
    print(f"Loading trajectory from {traj_path}...")
    try:
        atoms_list = read(traj_path, index=":")
    except Exception as e:
        print(f"Error reading trajectory: {e}")
        return

    # Try to auto-detect dt_ps from log
    dt_ps_detected = get_md_params(traj_path)
    if dt_ps_detected:
        dt_ps = dt_ps_detected
    else:
        dt_ps = time_step * log_interval / 1000.0
    
    total_time_ps = len(atoms_list) * dt_ps
    
    if total_time_ps <= ignore_ps:
        print(f"Error: Trajectory total time ({total_time_ps:.2f} ps) <= ignore_ps ({ignore_ps:.2f} ps).")
        return

    # Calculate step skip to ignore_ps
    n_skip = int(ignore_ps / dt_ps)
    print(f"Ignoring first {ignore_ps} ps ({n_skip} frames) of {total_time_ps:.2f} ps trajectory...")
    
    # Convert ASE atoms to pymatgen structures
    print(f"Converting {len(atoms_list) - n_skip} ASE atoms to pymatgen structures...")
    adaptor = AseAtomsAdaptor()
    structures = [adaptor.get_structure(atoms) for atoms in atoms_list[n_skip:]]
    
    print(f"Running DiffusionAnalyzer.from_structures...")
    analyzer = DiffusionAnalyzer.from_structures(
        structures=structures,
        specie=species,
        temperature=temperature,
        time_step=dt_ps * 1000.0, # interval in fs
        step_skip=1,
        smoothed=False
    )
    
    D = analyzer.diffusivity
    D_err = analyzer.diffusivity_std_dev
    
    print(f"Diffusivity (D): {D:.5e} +/- {D_err:.5e} cm^2/s")
    
    # Plot
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    plt.figure(figsize=(8, 6))
    times_ps = analyzer.dt / 1000.0
    msd = analyzer.msd
    
    plt.plot(times_ps, msd, 'k-', label=f"{species} MSD")
    
    # D is in cm^2/s. MSD(ps) = 6 * D * 10^4 * t(ps)
    slope_ps = 6 * D * 1e4
    plt.plot(times_ps, slope_ps * times_ps, 'r--', label=f"Fit (D={D:.2e} $\pm$ {D_err:.2e} cm^2/s)")
    
    plt.xlabel("Time (ps)", fontsize=18)
    plt.ylabel("MSD ($\AA^2$)", fontsize=18)
    plt.xticks(fontsize=18)
    plt.yticks(fontsize=18)
    plt.title(f"{temperature}K (skip={ignore_ps}ps)", fontsize=18)
    plt.legend(fontsize=18)
    
    output_plot_path = os.path.join(output_dir, f"msd_{species}.png")
    plt.tight_layout()
    plt.savefig(output_plot_path)
    plt.close()

    # Save results to JSON
    output_json_path = os.path.join(output_dir, "diffusion_results.json")
    results = {
        "temperature": temperature,
        "species": species,
        "diffusivity": D,
        "diffusivity_std_dev": D_err,
        "unit": "cm^2/s",
        "ignore_ps": ignore_ps
    }
    with open(output_json_path, "w") as f:
        json.dump(results, f, indent=4)
    print(f"Saved results and plot to {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate ionic diffusivity and MSD from MD trajectories."
    )
    parser.add_argument("traj_path", help="Path to the ASE trajectory file (.traj)")
    parser.add_argument("--species", required=True, help="Atomic species to analyze (e.g., Li)")
    parser.add_argument("--temperature", type=float, required=True, help="Simulation temperature (K)")
    parser.add_argument("--time_step", type=float, default=1.0, help="MD time step in fs (default: 1.0)")
    parser.add_argument("--log_interval", type=int, default=100, help="Steps between logged frames (default: 100)")
    parser.add_argument("--ignore_ps", type=float, default=5.0, help="Initial equilibration time to ignore in ps")
    parser.add_argument("--output_dir", default=".", help="Directory to save output files")
    
    args = parser.parse_args()
    
    analyze_diffusion(
        args.traj_path,
        args.species,
        args.temperature,
        args.time_step,
        args.log_interval,
        args.ignore_ps,
        args.output_dir
    )



