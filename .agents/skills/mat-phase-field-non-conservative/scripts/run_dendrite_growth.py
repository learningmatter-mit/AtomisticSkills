import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import tempfile
import os
import argparse
import imageio
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description="Simulate Dendrite Growth (Kobayashi 1993)")
    parser.add_argument("--grid-size", type=int, default=300, help="Number of cells in x and y")
    parser.add_argument("--steps", type=int, default=12000, help="Number of time steps")
    parser.add_argument("--dt", type=float, default=5e-5, help="Time step size")
    parser.add_argument("--output", type=str, default=".agents/skills/mat-phase-field-allen-cahn/examples/benchmark-dendrite/dendrite.gif", help="Output gif or png path")
    args = parser.parse_args()

    nx = ny = args.grid_size
    dx = dy = 0.03
    dt = args.dt
    
    # Parameters for Kobayashi
    tau = 0.0003
    epsilon_bar = 0.01
    kappa = 1.8
    delta = 0.02
    aniso = 4.0
    alpha = 0.9
    gamma = 10.0
    teq = 1.0

    phi = np.zeros((nx, ny))
    T = np.zeros((nx, ny))

    # Initialize a small spherical seed in the center
    cx, cy = nx//2, ny//2
    Y, X = np.ogrid[:nx, :ny]
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
    phi[dist < 5] = 1.0

    def grad_x(A):
        return (np.roll(A, -1, axis=1) - np.roll(A, 1, axis=1)) / (2*dx)

    def grad_y(A):
        return (np.roll(A, -1, axis=0) - np.roll(A, 1, axis=0)) / (2*dy)

    def laplacian(A):
        return (np.roll(A, 1, axis=0) + np.roll(A, -1, axis=0) + 
                np.roll(A, 1, axis=1) + np.roll(A, -1, axis=1) - 4*A) / (dx*dx)

    frames = []
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
    
    print("Running Dendrite Phase Field Simulation...")
    with tempfile.TemporaryDirectory() as temp_dir:
        for step in tqdm(range(args.steps)):
            phix = grad_x(phi)
            phiy = grad_y(phi)
            
            # Avoid divide by zero
            phix[phix == 0] = 1e-12
            
            theta = np.arctan2(phiy, phix)
            epsilon = epsilon_bar * (1.0 + delta * np.cos(aniso * theta))
            epsilon_der = -epsilon_bar * aniso * delta * np.sin(aniso * theta)
            
            term1 = epsilon * epsilon_der * phiy
            term2 = -(epsilon * epsilon_der * phix)
            
            term1_x = grad_x(term1)
            term2_y = grad_y(term2)
            
            # Compute main laplacian securely
            lap_phi = laplacian(phi)
            
            # Chain rule for anisotropic divergence: div(eps^2 grad phi) = eps^2 * lap(phi) + grad(eps^2) . grad(phi)
            eps2 = epsilon**2
            laplacian_term = eps2 * lap_phi + grad_x(eps2) * phix + grad_y(eps2) * phiy
            
            m = (alpha / np.pi) * np.arctan(gamma * (teq - T))
            
            dphi_dt = (term1_x + term2_y + laplacian_term + phi * (1.0 - phi) * (phi - 0.5 + m)) / tau
            dT_dt = laplacian(T) + kappa * dphi_dt
            
            phi += dphi_dt * dt
            T += dT_dt * dt
            
            if step % 150 == 0:
                plt.figure(figsize=(5,5))
                plt.imshow(phi, cmap='viridis', origin='lower', vmin=0, vmax=1)
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

    print(f"Simulation complete. Saved to {args.output}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)

if __name__ == '__main__':
    main()
