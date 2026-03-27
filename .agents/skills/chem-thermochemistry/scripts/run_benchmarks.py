
import os
import subprocess
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("Benchmark")

def run_command(command):
    logger.info(f"Running: {command}")
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        logger.error(f"Command failed with return code {process.returncode}")
        logger.error(f"Stderr: {stderr}")
    return stdout, stderr

def parse_results(output_dir):
    results_file = os.path.join(output_dir, "thermochemistry_results.json")
    if not os.path.exists(results_file):
        logger.error(f"Results file not found: {results_file}")
        return None
    with open(results_file, "r") as f:
        data = json.load(f)
    return data

import sys

def main():
    base_cmd = f"{sys.executable} .agents/skills/chem-thermochemistry/scripts/calculate_thermochemistry.py"
    model_type = "fairchem"
    model_name = "uma-s-1p1" # Supports omol task for organic molecules
    task = "omol"
    output_base_dir = ".agents/skills/chem-thermochemistry/examples/benchmarks_uma-s-1p1-omol"

    benchmarks = [
        {
            "name": "water_formation",
            "reaction": "2H2 + O2 -> 2H2O",
            "reference": {"delta_H": -483.65, "delta_G": -457.22}
        },
        {
            "name": "ammonia_synthesis",
            "reaction": "N2 + 3H2 -> 2NH3",
            "reference": {"delta_H": -91.80, "delta_G": -32.90}
        },
        {
            "name": "methanol_synthesis",
            "reaction": "CO + 2H2 -> CH3OH",
            "reference": {"delta_H": -90.20, "delta_G": -24.80}
        },
        {
            "name": "methane_combustion",
            "reaction": "CH4 + 2O2 -> CO2 + 2H2O",
            "reference": {"delta_H": -802.30, "delta_G": -800.90}
        }
    ]

    summary_results = []

    for bench in benchmarks:
        name = bench["name"]
        reaction = bench["reaction"]
        output_dir = os.path.join(output_base_dir, name)
        
        cmd = f"{base_cmd} --reaction '{reaction}' --model_type {model_type} --model_name {model_name} --task {task} --output_dir {output_dir}"
        run_command(cmd)
        
        data = parse_results(output_dir)
        if data:
            thermo = data["reaction_thermodynamics"]
            delta_H = thermo["delta_H_kJmol"]
            delta_G = thermo["delta_G_kJmol"]
            
            ref_H = bench["reference"]["delta_H"]
            ref_G = bench["reference"]["delta_G"]
            
            error_H = abs(delta_H - ref_H)
            error_G = abs(delta_G - ref_G)
            
            summary_results.append({
                "name": name,
                "reaction": reaction,
                "delta_H_calc": delta_H,
                "delta_H_ref": ref_H,
                "error_H": error_H,
                "delta_G_calc": delta_G,
                "delta_G_ref": ref_G,
                "error_G": error_G
            })

    # Print Summary Table
    print(f"\nBenchmark Summary ({model_name} - {task})")
    print(f"{'Reaction':<30} | {'dH Calc':<10} | {'dH Ref':<10} | {'Error':<8} | {'dG Calc':<10} | {'dG Ref':<10} | {'Error':<8}")
    print("-" * 110)
    for res in summary_results:
        print(f"{res['name']:<30} | {res['delta_H_calc']:<10.2f} | {res['delta_H_ref']:<10.2f} | {res['error_H']:<8.2f} | {res['delta_G_calc']:<10.2f} | {res['delta_G_ref']:<10.2f} | {res['error_G']:<8.2f}")

if __name__ == "__main__":
    main()
