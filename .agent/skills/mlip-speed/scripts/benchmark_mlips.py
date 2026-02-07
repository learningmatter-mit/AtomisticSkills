#!/usr/bin/env python3
import os
import sys
import time
import yaml
import torch
import numpy as np
import matplotlib.pyplot as plt
import argparse
import traceback
from typing import List, Dict, Any, Optional

# Add project root to sys.path to allow absolute imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ase import Atoms
from ase.build import bulk
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase.md.verlet import VelocityVerlet
from ase import units

# Optional imports will be handled within the benchmark loop
def get_hardware_name():
    """Detect the hardware name (GPU or CPU)."""
    if torch.cuda.is_available():
        return torch.cuda.get_device_name(0).replace(" ", "_").replace("/", "_")
    return "CPU"

def get_memory_usage():
    """Get current peak memory usage in GB."""
    if torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / (1024**3)
    else:
        try:
            import psutil
            return psutil.Process().memory_info().rss / (1024**3)
        except ImportError:
            return 0.0

def generate_nacl_supercell(num_atoms_target: int) -> Atoms:
    """
    Generate NaCl supercell with approximately num_atoms_target.
    The actual number of atoms will be nx * ny * nz * 8 (for rocksalt unit cell).
    """
    unit_cell = bulk("NaCl", "rocksalt", a=5.64)
    # unit_cell has 2 atoms (primitive rocksalt)
    n = (num_atoms_target / 2) ** (1/3)
    nx = max(1, int(round(n)))
    ny = max(1, int(round(n)))
    nz = max(1, int(round(n)))
    
    atoms = unit_cell * (nx, ny, nz)
    return atoms

def run_benchmark(wrapper, atoms: Atoms, steps: int = 10, name: str = ""):
    """Run benchmark for a given model and structure."""
    print(f"  Benchmarking {name} with {len(atoms)} atoms...", end="", flush=True)
    
    try:
        atoms.calc = wrapper.create_calculator()
        
        # Initialize velocities
        MaxwellBoltzmannDistribution(atoms, temperature_K=300)
        
        # VelocityVerlet (NVE) dynamics
        dyn = VelocityVerlet(atoms, timestep=1 * units.fs, logfile=None)
        
        times = []
        memories = []
        
        # Warmup and run steps
        for i in range(steps):
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
                
            start_time = time.time()
            dyn.run(1)
            end_time = time.time()
            
            if i >= steps - 5:
                times.append(end_time - start_time)
                memories.append(get_memory_usage())
        
        avg_time = np.mean(times)
        max_memory = np.max(memories)
        print(f" Done. {avg_time/(len(atoms)):.6f} s/atom, {max_memory:.2f} GB")
        return avg_time, max_memory
    except Exception as e:
        print(f" Failed: {e}")
        return None, None

def plot_results(results: Dict[str, Dict[str, List]], output_dir: str):
    """Generate plots for benchmark results with provider grouping and shading."""
    import matplotlib.colors as mcolors
    
    # 1. Prepare data and grouping
    grouped_data = {"mace": [], "matgl": [], "fairchem": []}
    for model_name, data in results.items():
        if not data.get("n_atoms"): continue
        provider = data.get("provider", "unknown")
        if provider not in grouped_data:
            grouped_data[provider] = []
        
        # Calculate metric for sorting (inference time per atom at the largest size)
        last_time_per_atom = data["times"][-1] / data["n_atoms"][-1]
        grouped_data[provider].append({
            "name": model_name,
            "data": data,
            "metric": last_time_per_atom
        })
    
    # Sort within each group by speed (fastest first)
    for p in grouped_data:
        grouped_data[p].sort(key=lambda x: x["metric"])
    
    provider_colors = {
        "mace": "Blues",
        "matgl": "Oranges",
        "fairchem": "Greens",
        "unknown": "Greys"
    }
    
    def get_shades(cmap_name, n):
        if n == 1:
            return [plt.get_cmap(cmap_name)(0.6)]
        cmap = plt.get_cmap(cmap_name)
        # Use range 0.4 to 0.9 for visible shades
        return [cmap(i) for i in np.linspace(0.4, 0.9, n)]

    # 2. Plotting loop for both plots
    for plot_type in ["inference_speed", "memory_usage"]:
        plt.figure(figsize=(12, 7))
        
        for provider, models in grouped_data.items():
            if not models: continue
            shades = get_shades(provider_colors.get(provider, "Greys"), len(models))
            
            for i, model in enumerate(models):
                data = model["data"]
                if plot_type == "inference_speed":
                    # Convert to ms/atom
                    y = [t * 1000 / n for t, n in zip(data["times"], data["n_atoms"])]
                    converged_val = y[-1]
                    label = f"[{provider.upper()}] {model['name']} ({converged_val:.3f} ms/atom)"
                    ylabel = "Inference Time / Atom (ms)"
                    hardware = get_hardware_name()
                    title = f"MLIP Inference Speed Benchmark on {hardware.replace('_', ' ')}"
                else:
                    y = data["memories"]
                    # Converged memory in MB / atom
                    converged_val = (y[-1] * 1024) / data["n_atoms"][-1]
                    label = f"[{provider.upper()}] {model['name']} ({converged_val:.2f} MB/atom)"
                    ylabel = "Memory Usage (GB)"
                    hardware = get_hardware_name()
                    title = f"MLIP Memory Usage Benchmark on {hardware.replace('_', ' ')}"
                
                plt.plot(data["n_atoms"], y, 'o-', color=shades[i], 
                         label=label, linewidth=2, markersize=5)

        plt.xlabel("Number of Atoms", fontsize=12)
        plt.ylabel(ylabel, fontsize=12)
        plt.title(title, fontsize=14, fontweight='bold')
        
        # Place legend outside if too many items
        if len(results) > 10:
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
            plt.tight_layout()
        else:
            plt.legend(fontsize=10)
            
        plt.grid(True, linestyle='--', alpha=0.6)
        hardware = get_hardware_name()
        plt.savefig(os.path.join(output_dir, f"{plot_type}_{hardware.lower()}.png"), dpi=300, bbox_inches='tight')
        plt.close()

def main():
    parser = argparse.ArgumentParser(description="Benchmark MLIP inference speed and memory.")
    parser.add_argument("--models", nargs="+", help="List of model names to benchmark. If not provided, will use defaults.")
    parser.add_argument("--providers", nargs="+", choices=["mace", "matgl", "fairchem"], help="Providers for models.")
    parser.add_argument("--device", default="auto", help="Device to use (auto, cpu, cuda).")
    parser.add_argument("--output_dir", default=".", help="Directory to save plots and yaml.")
    parser.add_argument("--max_atoms_limit", type=int, default=10000, help="Maximum atoms to test.")
    parser.add_argument("--only_plot", action="store_true", help="Only generate plots from existing speed_benchmark.yaml")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    all_results = {}
    yaml_path = os.path.join(args.output_dir, "speed_benchmark.yaml")
    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as f:
            try:
                existing_results = yaml.safe_load(f)
                if existing_results:
                    all_results.update(existing_results)
            except Exception:
                pass

    if args.only_plot:
        if not all_results:
            print(f"Error: No results found in {yaml_path}")
            return
        plot_results(all_results, args.output_dir)
        print(f"Plots updated in {args.output_dir}")
        return

    sizes = [50, 100, 200, 500, 1000, 1500, 2000, 3000, 4000, 5000]
    
    to_benchmark = []
    if args.models and args.providers:
        if len(args.models) != len(args.providers):
            print("Error: --models and --providers must have the same length.")
            sys.exit(1)
        for m, p in zip(args.models, args.providers):
            to_benchmark.append((m, p))
    else:
        # Use defaults for requested providers or all if none specified
        providers = args.providers if args.providers else ["mace", "matgl", "fairchem"]
        for p in providers:
            for m in default_models.get(p, []):
                to_benchmark.append((m, p))

    # Load existing results if they exist
    all_results = {}
    yaml_path = os.path.join(args.output_dir, "speed_benchmark_dgx_spark.yaml")
    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as f:
            try:
                existing_results = yaml.safe_load(f)
                if existing_results:
                    all_results.update(existing_results)
            except Exception:
                pass

    for model_name, provider in to_benchmark:
        print(f"\nStarting benchmark for {model_name} ({provider})")
        wrapper = None
        try:
            if provider == "mace":
                from src.utils.mlips.mace.mace_wrapper import MACEWrapper
                wrapper = MACEWrapper(model_name=model_name, device=args.device)
            elif provider == "matgl":
                from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
                wrapper = MatGLWrapper(model_name=model_name, device=args.device)
            elif provider == "fairchem":
                from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper
                wrapper = FAIRCHEMWrapper(model_name=model_name, device=args.device)
            
            wrapper.load()
        except ImportError as e:
            print(f"Skipping {model_name}: Required library not installed in this environment. ({e})")
            continue
        except Exception as e:
            print(f"Could not load model {model_name}: {e}")
            continue

        results = {
            "n_atoms": [],
            "times": [],
            "memories": [],
            "provider": provider
        }
        
        # Test standard sizes
        reached_oom = False
        last_success_size = 0
        
        for target_size in sizes:
            atoms = generate_nacl_supercell(target_size)
            actual_size = len(atoms)
            
            # Skip if we already hit OOM or exceeded limits
            if actual_size > args.max_atoms_limit:
                break
                
            avg_time, max_mem = run_benchmark(wrapper, atoms, steps=10, name=model_name)
            
            if avg_time is not None:
                results["n_atoms"].append(actual_size)
                results["times"].append(float(avg_time))
                results["memories"].append(float(max_mem))
                last_success_size = actual_size
            else:
                reached_oom = True
                break
        
        # Search for max atoms if not already failed
        if not reached_oom and last_success_size > 0:
            print(f"  Searching for max atoms for {model_name}...")
            # Try doubling until fail
            current_size = last_success_size
            while current_size < args.max_atoms_limit:
                current_size += 1000 # Increase by 1k for search
                if current_size > args.max_atoms_limit: break
                
                atoms = generate_nacl_supercell(current_size)
                actual_size = len(atoms)
                avg_time, max_mem = run_benchmark(wrapper, atoms, steps=10, name=model_name)
                if avg_time is not None:
                    results["n_atoms"].append(actual_size)
                    results["times"].append(float(avg_time))
                    results["memories"].append(float(max_mem))
                else:
                    break
        
        all_results[model_name] = results
        
        # Save intermediate results
        with open(yaml_path, "w") as f:
            yaml.dump(all_results, f, default_flow_style=False)
            
        # Clean up memory
        del wrapper
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Save results to YAML
    with open(yaml_path, "w") as f:
        yaml.dump(all_results, f, default_flow_style=False)
    
    # Plot results (all combined)
    plot_results(all_results, args.output_dir)
    print(f"\nBenchmark complete. Results saved to {args.output_dir}")

if __name__ == "__main__":
    main()
