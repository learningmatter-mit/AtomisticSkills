"""
Run an ORCA calculation from a user-provided input file.

Handles execution of the ORCA binary, captures output, and extracts the
final electronic energy from the output file.

Usage:
    python run_orca_input.py --input_file calculation.inp
    python run_orca_input.py --input_file calculation.inp --output_dir results

Requirements:
    - Conda environment: orca-agent
    - Required packages: ase (optional, for structure handling)
    - Environment variable: ORCA_BINARY_PATH
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ORCA-Advanced")

ENERGY_PATTERN = re.compile(r"FINAL SINGLE POINT ENERGY\s+([-\d.]+)")
SCF_CONVERGED_PATTERN = re.compile(r"SCF CONVERGED AFTER\s+(\d+)\s+CYCLES")
SCF_NOT_CONVERGED_PATTERN = re.compile(r"SCF NOT CONVERGED")
TOTAL_RUN_TIME_PATTERN = re.compile(r"TOTAL RUN TIME:\s+(.+)")


def validate_input_file(input_path: str) -> list[str]:
    """
    Basic validation of an ORCA input file.

    Returns a list of warnings (empty if everything looks fine).
    """
    warnings = []
    with open(input_path, "r") as f:
        content = f.read()

    if not content.strip():
        warnings.append("Input file is empty")
        return warnings

    if "!" not in content:
        warnings.append("No keyword line found (expected a line starting with '!')")

    if "*" not in content:
        warnings.append("No coordinate block found (expected '*' block)")

    if "%pal" not in content.lower() and "nprocs" not in content.lower():
        warnings.append(
            "No %pal block found — ORCA will run with 1 core. "
            "Consider adding: %pal nprocs N end"
        )

    if "%maxcore" not in content.lower():
        warnings.append(
            "No %maxcore directive found — ORCA will use default memory. "
            "Consider adding: %maxcore 4000  (memory per core in MB)"
        )

    return warnings


def parse_final_energy(output_path: str) -> dict:
    """
    Extract key results from an ORCA output file.

    Returns a dict with energy, SCF convergence info, and timing.
    """
    result = {
        "energy_hartree": None,
        "scf_converged": None,
        "scf_cycles": None,
        "total_run_time": None,
    }

    with open(output_path, "r") as f:
        content = f.read()

    energy_matches = ENERGY_PATTERN.findall(content)
    if energy_matches:
        result["energy_hartree"] = float(energy_matches[-1])
        result["energy_eV"] = result["energy_hartree"] * 27.211386245988

    scf_match = SCF_CONVERGED_PATTERN.search(content)
    if scf_match:
        result["scf_converged"] = True
        result["scf_cycles"] = int(scf_match.group(1))
    elif SCF_NOT_CONVERGED_PATTERN.search(content):
        result["scf_converged"] = False

    time_match = TOTAL_RUN_TIME_PATTERN.search(content)
    if time_match:
        result["total_run_time"] = time_match.group(1).strip()

    return result


def run_orca(input_file: str, output_dir: str) -> dict:
    """
    Execute ORCA with the given input file.

    Args:
        input_file: Path to the ORCA .inp file
        output_dir: Directory to run the calculation in

    Returns:
        Dictionary with calculation results and file paths
    """
    from src.utils.dft.orca_utils import check_orca_binary

    orca_binary = check_orca_binary()
    os.makedirs(output_dir, exist_ok=True)

    input_basename = os.path.basename(input_file)
    input_stem = os.path.splitext(input_basename)[0]
    dest_input = os.path.join(output_dir, input_basename)

    if os.path.abspath(input_file) != os.path.abspath(dest_input):
        shutil.copy2(input_file, dest_input)

    warnings = validate_input_file(dest_input)
    for w in warnings:
        logger.warning(f"Input validation: {w}")

    output_file = os.path.join(output_dir, f"{input_stem}.out")

    logger.info(f"Running ORCA: {orca_binary} {input_basename}")
    logger.info(f"Working directory: {output_dir}")

    with open(output_file, "w") as out_f:
        proc = subprocess.run(
            [orca_binary, input_basename],
            cwd=output_dir,
            stdout=out_f,
            stderr=subprocess.STDOUT,
        )

    success = proc.returncode == 0
    if success:
        logger.info("ORCA finished successfully.")
    else:
        logger.error(f"ORCA exited with return code {proc.returncode}")

    parsed = parse_final_energy(output_file)

    if parsed["energy_hartree"] is not None:
        logger.info(
            f"Final energy: {parsed['energy_hartree']:.10f} Hartree "
            f"= {parsed['energy_eV']:.6f} eV"
        )
    else:
        logger.warning("Could not extract final energy from output.")

    if parsed["scf_converged"] is False:
        logger.error("SCF did NOT converge. Check the output file for details.")

    result = {
        "input_file": input_basename,
        "output_file": f"{input_stem}.out",
        "orca_return_code": proc.returncode,
        "success": success,
        "input_warnings": warnings,
        **parsed,
    }

    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run ORCA from a custom input file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--input_file", required=True, help="Path to ORCA .inp file")
    parser.add_argument("--output_dir", default=None, help="Output/working directory")

    args = parser.parse_args()

    if not args.output_dir:
        from src.utils.research_utils import get_current_research_dir
        args.output_dir = str(get_current_research_dir() / "orca_advanced")
    os.makedirs(args.output_dir, exist_ok=True)

    result = run_orca(args.input_file, args.output_dir)

    results_file = os.path.join(args.output_dir, "calculation_results.json")
    with open(results_file, "w") as f:
        json.dump(result, f, indent=4)
    logger.info(f"Results saved to {results_file}")


if __name__ == "__main__":
    main()
