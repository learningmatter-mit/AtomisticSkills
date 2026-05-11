
import argparse
import os
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.transformations.standard_transformations import ConventionalCellTransformation

def create_supercell(input_path, output_path, min_length=20.0, scaling_override=None):
    """
    Converts a unit cell into a rectangular supercell with a minimum block length.
    """
    print(f"Loading structure from {input_path}...")
    struct = Structure.from_file(input_path)
    
    # 1. Convert to conventional rectangular cell
    print("Converting to conventional rectangular cell...")
    conv_trans = ConventionalCellTransformation()
    struct = conv_trans.apply_transformation(struct)
    
    # 2. Scale
    if scaling_override:
        scaling = scaling_override
    else:
        lattice = struct.lattice
        abc = lattice.abc
        if isinstance(min_length, (int, float)):
            min_lengths = [min_length] * 3
        else:
            min_lengths = min_length
            
        scaling = [max(1, int(round(ml / x))) for ml, x in zip(min_lengths, abc)]
        
    print(f"Lattice constants: {struct.lattice.abc}")
    print(f"Scaling supercell by: {scaling}")
    
    struct.make_supercell(scaling)
    
    # Save output
    print(f"Saving supercell to {output_path}...")
    struct.to(fmt="cif", filename=output_path)
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a rectangular supercell for melting point simulations.")
    parser.add_argument("input", help="Input structure file (e.g. Al_stable.cif)")
    parser.add_argument("output", help="Output supercell file (e.g. Al_supercell.cif)")
    parser.add_argument("--min_length", type=float, help="Minimum length for all sides (default 20.0 A)")
    parser.add_argument("--min_lengths", type=float, nargs=3, help="Minimum length for [Lx, Ly, Lz]")
    parser.add_argument("--scaling", type=int, nargs=3, help="Explicit scaling factors [nx, ny, nz]")
    
    args = parser.parse_args()
    
    target_min = args.min_lengths if args.min_lengths else (args.min_length if args.min_length else 20.0)
    create_supercell(args.input, args.output, target_min, args.scaling)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)
