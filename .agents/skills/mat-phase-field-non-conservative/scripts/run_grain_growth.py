"""
This script simulates non-conservative phase-field evolution (Allen-Cahn equation)
demonstrating the classic curvature-driven shrinkage of a circular grain.

Usage:
    python run_grain_growth.py --grid-size 100 --radius 30 --steps 300 --dt 0.5 --output out.gif

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

from fipy import CellVariable, Grid2D, TransientTerm, DiffusionTerm

def main():
    parser = argparse.ArgumentParser(description="Simulate 2D Curvature-driven Grain Shrinkage using Allen-Cahn equation in FiPy")
    parser.add_argument("--grid-size", type=int, default=50, help="Number of cells in x and y")
    parser.add_argument("--radius", type=float, default=15.0, help="Initial radius of the grain")
    parser.add_argument("--steps", type=int, default=150, help="Number of time steps")
    parser.add_argument("--dt", type=float, default=0.1, help="Time step size")
    parser.add_argument("--output", type=str, default="grain_growth.gif", help="Output gif or png path")
    args = parser.parse_args()

    nx = ny = args.grid_size
    dx = dy = 1.0
    mesh = Grid2D(nx=nx, ny=ny, dx=dx, dy=dy)
    
    # Phase field variable (1: Solid Grain, 0: Liquid Matrix)
    phi = CellVariable(name="phase", mesh=mesh, hasOld=True)
    
    # Initialize a circular grain in the center
    x = mesh.cellCenters[0]
    y = mesh.cellCenters[1]
    r_sq = (x - nx*dx/2.0)**2 + (y - ny*dy/2.0)**2
    # Smooth interface initialization
    phi.setValue(0.5 * (1.0 - np.tanh((np.sqrt(r_sq) - args.radius) / 2.0)))

    M = 1.0       # Mobility
    epsilon = 2.0 # Gradient energy coefficient (controls interface thickness)
    W = 1.0       # Double well potential height
    
    # Allen-Cahn Equation:
    # \partial \phi / \partial t = M * [ \epsilon^2 \nabla^2 \phi - W * \phi * (1 - \phi) * (1 - 2\phi) ]
    # The source term is S = - W * \phi * (1-\phi) * (1-2\phi)
    # To improve implicit stability, we linearize S or part of it.
    
    from fipy.terms.implicitSourceTerm import ImplicitSourceTerm
    
    # Using explicit formulation with small implicit stabilization
    # S = W * phi * (1 - phi) * (2*phi - 1)
    #   = W * (2*phi^3 - 3*phi^2 + phi)
    # This can be made implicit:
    # We can write S as a source term. The standard FiPy way:
    # phi * (1 - phi) * (phi - 0.5) * (-2*W)
    
    # phi_old = phi.old
    # Explicit source:
    # S = - W * phi * (1 - phi) * (1 - 2 * phi)
    
    # Simple explicit-implicit mix:
    # eq = TransientTerm() == DiffusionTerm(coeff=M * epsilon**2) \
    #      + M * W * (phi * (1 - phi) * (2 * phi - 1))
    
    # The correct source term:
    # S = - f'(phi) = -2 * W * phi * (1 - phi) * (1 - 2*phi)
    # The previous implementation lacked the negative sign (acting as a double barrier instead of double well).
    # Since DiffusionTerm is unconditionally stable, and dt is small, explicit source is sufficient and avoids ImplicitSourceTerm positive-coeff warnings.
    S0 = -2.0 * M * W * phi.old * (1.0 - phi.old) * (1.0 - 2.0 * phi.old)
    eq = TransientTerm(var=phi) == DiffusionTerm(coeff=M * epsilon**2, var=phi) + S0

    import tempfile

    # Prepare for plotting
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
    frames = []
    times = []
    areas = []

    print("Running Allen-Cahn Phase Field Simulation...")
    with tempfile.TemporaryDirectory() as temp_dir:
        for step in tqdm(range(args.steps)):
            phi.updateOld()
            res = 1e5
            sweeps = 0
            while res > 1e-4 and sweeps < 20:
                res = eq.sweep(dt=args.dt)
                sweeps += 1
                
            area = float(np.sum(phi.value) * dx * dy)
            times.append(step * args.dt)
            areas.append(area)

            if step % 5 == 0:
                plt.figure(figsize=(5,5))
                field = phi.value.reshape((nx, ny))
                plt.imshow(field, cmap='viridis', origin='lower', vmin=0, vmax=1)
                plt.axis('off')
                plt.title(f"Step {step}")
                frame_path = os.path.join(temp_dir, f"frame_{step:04d}.png")
                plt.savefig(frame_path, bbox_inches='tight', pad_inches=0.1)
                plt.close()
                frames.append(frame_path)

        if args.output.endswith('.gif'):
            print(f"Creating GIF at {args.output}...")
            import imageio.v2 as iio
            with imageio.get_writer(args.output, mode='I', duration=100) as writer:
                for frame in frames:
                    image = iio.imread(frame)
                    writer.append_data(image)
        else:
            import shutil
            shutil.copy(frames[-1], args.output)
            
    plt.figure(figsize=(6, 4))
    plt.plot(times, areas, 'k-', linewidth=2)
    plt.xlabel('Time')
    plt.ylabel('Grain Area')
    plt.title('Curvature-Driven Area Decay (Allen-Cahn)')
    plt.grid(True)
    area_out = args.output.replace('.gif', '_area_decay.png').replace('.png', '_area_decay.png')
    plt.savefig(area_out, bbox_inches='tight')
    plt.close()
    
    print(f"Simulation complete. Saved to {args.output} and {area_out}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)

if __name__ == '__main__':
    main()
