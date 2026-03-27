import argparse
import numpy as np
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

def prep_supercell(input_file, output_file, target_atoms=100):
    struct = Structure.from_file(input_file)
    
    # 1. Get conventional standard structure (often orthorhombic/cubic)
    sga = SpacegroupAnalyzer(struct)
    conv_struct = sga.get_conventional_standard_structure()
    n_conv = len(conv_struct)
    
    # 2. Estimate supercell scaling factors to get close to target_atoms
    # We want Nx * Ny * Nz * n_conv ~ target_atoms
    # Nx * Ny * Nz ~ target_atoms / n_conv
    total_scaling = target_atoms / n_conv
    scale_each = total_scaling**(1/3)
    factors = [max(1, int(round(scale_each))) for _ in range(3)]
    
    # Adjust factors to get closer to target
    current_n = n_conv * np.prod(factors)
    while current_n < target_atoms * 0.8: # Allow some flexibility
        # Increment the factor for the shortest lattice vector
        lengths = conv_struct.lattice.abc
        idx = np.argmin([l * f for l, f in zip(lengths, factors)])
        factors[idx] += 1
        current_n = n_conv * np.prod(factors)
        
    conv_struct.make_supercell(factors)
    conv_struct.to(output_file, "cif")
    print(f"Created conventional supercell with scaling {factors} ({len(conv_struct)} atoms) at {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target_atoms", type=int, default=100)
    args = parser.parse_args()
    prep_supercell(args.input, args.output, args.target_atoms)
