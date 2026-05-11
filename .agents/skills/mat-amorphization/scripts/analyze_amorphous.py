import numpy as np
import matplotlib.pyplot as plt
from ase.io import read
from ase.geometry import get_distances
import os

def calculate_rdf(atoms, r_max=10.0, n_bins=100):
    n_atoms = len(atoms)
    vol = atoms.get_volume()
    rho = n_atoms / vol
    
    bin_width = r_max / n_bins
    r = np.linspace(bin_width/2, r_max - bin_width/2, n_bins)
    rdf = np.zeros(n_bins)
    
    for i in range(n_atoms - 1):
        dists = atoms.get_distances(i, range(i+1, n_atoms), mic=True)
        for d in dists:
            if d < r_max:
                bin_idx = int(d / bin_width)
                if bin_idx < n_bins:
                    rdf[bin_idx] += 2
                    
    for i in range(n_bins):
        shell_vol = 4 * np.pi * r[i]**2 * bin_width
        rdf[i] = rdf[i] / (n_atoms * rho * shell_vol)
        
    return r, rdf

from pymatgen.analysis.local_env import CrystalNN

def check_cn(atoms):
    from pymatgen.io.ase import AseAtomsAdaptor
    struct = AseAtomsAdaptor.get_structure(atoms)
    cnn = CrystalNN()
    cns = []
    for i in range(len(struct)):
        try:
            cn = cnn.get_cn(struct, i)
            cns.append(cn)
        except:
            pass
    return np.mean(cns), np.bincount(cns).tolist()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to structure file (traj or cif)")
    parser.add_argument("--initial", help="Path to initial crystalline structure for comparison")
    parser.add_argument("--output_dir", default=".", help="Directory to save plots")
    args = parser.parse_args()
    
    atoms = read(args.input, index=-1)
    r, rdf = calculate_rdf(atoms)
    
    plt.figure(figsize=(10, 6))
    
    # Plot initial RDF if provided
    if args.initial:
        try:
            atoms_initial = read(args.initial)
            r_init, rdf_init = calculate_rdf(atoms_initial)
            plt.plot(r_init, rdf_init, 'r--', label="Initial (Crystalline)", alpha=0.7)
            print(f"Calculated RDF for initial structure: {args.initial}")
        except Exception as e:
            print(f"Failed to read initial structure: {e}")

    # Plot final RDF
    plt.plot(r, rdf, 'b-', label="Final (Amorphous)", linewidth=2)
    
    plt.xlabel("r (Å)", fontsize=12)
    plt.ylabel("g(r)", fontsize=12)
    plt.title(f"RDF Analysis: Amorphorization", fontsize=14)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    plot_path = os.path.join(args.output_dir, "rdf_plot.png")
    plt.savefig(plot_path)
    print(f"RDF plot saved to {plot_path}")
    
    avg_cn, cn_dist = check_cn(atoms)
    print(f"Average Coordination Number: {avg_cn:.2f}")
    print(f"CN Distribution: {cn_dist}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(_json.dumps(_config, indent=2, default=str))

if __name__ == "__main__":
    main()
