import argparse
from ase.io import read, write
from ase.build import stack
import numpy as np

def create_interface(solid_path, liquid_path, axis, output_path):
    """
    Concatenate a solid and a liquid structure along a given axis.
    """
    print(f"Loading solid from {solid_path} and liquid from {liquid_path}...")
    solid = read(solid_path)
    liquid = read(liquid_path)
    
    # Ensure they have similar cross-sections if stacking
    # This is a simplified version; in practice, users should ensure 
    # the cells are compatible.
    
    print(f"Stacking structures along axis {axis}...")
    # axis 0=x, 1=y, 2=z
    combined = stack(solid, liquid, axis=axis, distance=2.0, maxstrain=2.0) # Allow up to 200% strain for melting
    
    # Alternatively, use pbc and cell info for a more rigid stack
    # But stack() is generally good for simple solid-liquid interfaces.
    
    print(f"Combined structure has {len(combined)} atoms.")
    write(output_path, combined)
    print(f"Saved interface structure to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a solid-liquid interface by stacking two structures.")
    parser.add_argument("solid", help="Path to solid structure file")
    parser.add_argument("liquid", help="Path to liquid structure file")
    parser.add_argument("--axis", type=int, default=2, help="Axis along which to stack (0=x, 1=y, 2=z, default: 2)")
    parser.add_argument("--output", default="interface.cif", help="Output file path (default: interface.cif)")
    
    args = parser.parse_args()
    
    create_interface(args.solid, args.liquid, args.axis, args.output)
