"""
This script simulates conservative spinodal decomposition using the Cahn-Hilliard equation.

Usage:
    python run_spinodal_decomposition.py --grid-size 100 --dx 0.25 --steps 200 --dt 0.01 --output examples/benchmark-spinodal/classic_spinodal.gif

Requirements:
    - Conda environment: phasefield-agent
    - Required packages: fipy, numpy, imageio, tqdm, matplotlib
"""

import argparse
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import imageio
from tqdm import tqdm

from fipy import CellVariable, Grid2D, GaussianNoiseVariable, DiffusionTerm, TransientTerm

def main():
    parser = argparse.ArgumentParser(description="Simulate 2D Spinodal Decomposition using Cahn-Hilliard equations in FiPy")
    parser.add_argument("--grid-size", type=int, default=50, help="Number of cells in x and y")
    parser.add_argument("--dx", type=float, default=0.25, help="Grid spacing")
    parser.add_argument("--steps", type=int, default=100, help="Number of time steps")
    parser.add_argument("--dt", type=float, default=0.01, help="Time step size")
    parser.add_argument("--output", type=str, default="spinodal.gif", help="Output gif or png path")
    args = parser.parse_args()

    nx = ny = args.grid_size
    dx = dy = args.dx
    mesh = Grid2D(nx=nx, ny=ny, dx=dx, dy=dy)
    
    # Phase field variable (1: phase A, -1: phase B)
    phi = CellVariable(name="phase", mesh=mesh, hasOld=True)
    
    # Initialize with small random fluctuations
    np.random.seed(42)
    noise = GaussianNoiseVariable(mesh=mesh, mean=0., variance=0.1)
    phi.setValue(noise)

    # Chemical potential variable
    mu = CellVariable(name="mu", mesh=mesh)

    gamma = 1.0 # Gradient energy coefficient
    D = 1.0     # Mobility

    # Free energy f = 0.25 * (phi^2 - 1)^2
    # df/dphi = phi^3 - phi
    # Coupled formulation:
    # \partial phi / \partial t = \nabla * (D \nabla mu)
    # mu = phi^3 - phi - \gamma \nabla^2 phi
    
    # To improve implicit solver stability, we separate phi^3 into phi * (phi^2) where phi^2 is old value
    from fipy.terms.implicitSourceTerm import ImplicitSourceTerm
    
    eq_mu = ImplicitSourceTerm(coeff=1., var=mu) == \
            ImplicitSourceTerm(coeff=phi**2, var=phi) - ImplicitSourceTerm(coeff=1., var=phi) - DiffusionTerm(coeff=gamma, var=phi)
            
    eq_phi = TransientTerm(var=phi) == DiffusionTerm(coeff=D, var=mu)

    eqn = eq_phi & eq_mu

    import tempfile

    # Prepare for plotting
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
    frames = []

    print("Running Cahn-Hilliard Phase Field Simulation...")
    with tempfile.TemporaryDirectory() as temp_dir:
        for step in tqdm(range(args.steps)):
            phi.updateOld()
            # Sweep multiple times to converge the coupled implicit equations
            res = 1e5
            sweeps = 0
            while res > 1e-4 and sweeps < 20:
                res = eqn.sweep(dt=args.dt)
                sweeps += 1
                
            # Save frame every 5 steps
            if step % 5 == 0:
                plt.figure(figsize=(5,5))
                # Shape matches grid
                field = phi.value.reshape((nx, ny))
                plt.imshow(field, cmap='coolwarm', origin='lower', vmin=-1, vmax=1)
                plt.axis('off')
                plt.title(f"Step {step}")
                frame_path = os.path.join(temp_dir, f"frame_{step:04d}.png")
                plt.savefig(frame_path, bbox_inches='tight', pad_inches=0.1)
                plt.close()
                frames.append(frame_path)

        # Save output
        if args.output.endswith('.gif'):
            print(f"Creating GIF at {args.output}...")
            import imageio.v2 as iio
            with imageio.get_writer(args.output, mode='I', duration=100) as writer:
                for frame in frames:
                    image = iio.imread(frame)
                    writer.append_data(image)
        else:
            # Save last frame
            import shutil
            shutil.copy(frames[-1], args.output)

    print(f"Simulation complete. Saved to {args.output}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)

if __name__ == '__main__':
    main()
