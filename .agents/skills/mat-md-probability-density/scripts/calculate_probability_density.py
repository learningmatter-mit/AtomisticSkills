import argparse
import numpy as np
import os
from ase.io import read
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.analysis.diffusion.aimd.pathway import ProbabilityDensityAnalysis
from scipy.ndimage import gaussian_filter
from typing import Optional

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
            t0 = float(lines[1].split()[0])
            t1 = float(lines[2].split()[0])
            dt_ps = t1 - t0
            print(f"Auto-detected frame interval from log: {dt_ps:.4f} ps")
            return dt_ps
    except Exception as e:
        print(f"Error parsing log file: {e}")
        return None

def calculate_probability_density(
    traj_path: str,
    species: str,
    interval: float = 0.2,
    time_step: float = 1.0,
    log_interval: int = 100,
    ignore_ps: float = 5.0,
    sigma: float = 1.0,
    log_compression: bool = False,
    output_chgcar: str = "CHGCAR_proba"
) -> None:
    """
    Generate the probability density CHGCAR using pymatgen's ProbabilityDensityAnalysis.
    Applies Gaussian smoothing to make sparse trajectory sampling visually coherent.
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
    
    if len(atoms_list) - n_skip < 2:
        print("Error: Not enough frames after skipping equilibration.")
        return

    print(f"Extracting fractional coordinates from {len(atoms_list) - n_skip} frames...")
    
    adaptor = AseAtomsAdaptor()
    structure = adaptor.get_structure(atoms_list[n_skip])
    
    # Align framework and extract fractional coordinates
    print("Aligning frameworks to remove center-of-mass drift...")
    framework_indices = [atom.index for atom in atoms_list[n_skip] if atom.symbol != species]
    if len(framework_indices) > 0:
        ref_com = atoms_list[n_skip][framework_indices].get_center_of_mass()
        for i in range(n_skip + 1, len(atoms_list)):
            com = atoms_list[i][framework_indices].get_center_of_mass()
            shift = ref_com - com
            atoms_list[i].positions += shift
            
    # ProbabilityDensityAnalysis expects fractional coordinates
    trajectories = np.array([atoms.get_scaled_positions() for atoms in atoms_list[n_skip:]])
    
    print("Running ProbabilityDensityAnalysis...")
    pda = ProbabilityDensityAnalysis(
        structure=structure,
        trajectories=trajectories,
        interval=interval,
        species=[species]
    )
    
    if log_compression:
        print("Applying logarithmic compression to enhance visualize continuous paths...")
        original_max = np.max(pda.Pr)
        if original_max > 0:
            data_scaled = pda.Pr / original_max * 1000.0
            data_log = np.log1p(data_scaled)
            # Compress max back to original max so VESTA scaling feels standard
            data_log = data_log * (original_max / np.max(data_log))
            pda.Pr = data_log

    if sigma > 0:
        print(f"Applying Gaussian smoothing with sigma={sigma}...")
        pda.Pr = gaussian_filter(pda.Pr, sigma=sigma, mode='wrap')
    
    # FIX: VESTA expects CHGCAR atoms to be grouped by species. We swap the structure 
    # to a sorted one right before saving, while keeping the original ordering during Pr computation.
    pda.structure = pda.structure.get_sorted_structure()
    
    print(f"Saving probability density to {output_chgcar}...")
    pda.to_chgcar(output_chgcar)
    print("Done!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate ionic probability density from MD trajectories."
    )
    parser.add_argument("traj_path", help="Path to the ASE trajectory file (.traj)")
    parser.add_argument("--species", required=True, help="Atomic species to analyze (e.g., Li)")
    parser.add_argument("--interval", type=float, default=0.2, help="Grid interval in Angstroms (default: 0.2)")
    parser.add_argument("--time_step", type=float, default=1.0, help="MD time step in fs (default: 1.0)")
    parser.add_argument("--log_interval", type=int, default=100, help="Steps between logged frames (default: 100)")
    parser.add_argument("--ignore_ps", type=float, default=5.0, help="Initial equilibration time to ignore in ps")
    parser.add_argument("--sigma", type=float, default=1.0, help="Gaussian smoothing sigma in grid units (default: 1.0)")
    parser.add_argument('--log', action='store_true', help='Apply logarithmic compression to enhance saddle points (best for <50ps MD)')
    parser.add_argument("--output_chgcar", default="CHGCAR_proba", help="Output path for the CHGCAR file")
    
    args = parser.parse_args()
    
    calculate_probability_density(
        traj_path=args.traj_path,
        species=args.species,
        interval=args.interval,
        time_step=args.time_step,
        log_interval=args.log_interval,
        ignore_ps=args.ignore_ps,
        sigma=args.sigma,
        log_compression=args.log,
        output_chgcar=args.output_chgcar
    )
