"""
Generate and serialize the Jobflow DAG for computing electronic transport properties using AMSET and VASP.

Usage:
    python generate_inputs.py --output amset_flow.json

Requirements:
    - Conda environment: atomate2-agent
    - Required packages: atomate2, pymatgen, jobflow, amset
"""

import argparse
import json
from pymatgen.core import Structure
from atomate2.vasp.flows.amset import VaspAmsetMaker

def main():
    parser = argparse.ArgumentParser(description="Generate VaspAmsetMaker flow DAG for GaAs.")
    parser.add_argument("--output", default="amset_flow.json", help="Output JSON path to save the DAG representation.")
    args = parser.parse_args()

    # GaAs primitive cell (FCC lattice)
    gaas = Structure(
        lattice=[[0.0, 2.825, 2.825], [2.825, 0.0, 2.825], [2.825, 2.825, 0.0]],
        species=["Ga", "As"],
        coords=[[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )

    # Initialize the automated AMSET workflow
    # This automatically includes:
    # 1. Structure relaxation
    # 2. Dense uniform band structure
    # 3. Elastic tensor calculation
    # 4. Deformation potential calculation
    # 5. Static & dielectric constants
    # 6. Final AMSET execution
    maker = VaspAmsetMaker(
        name="GaAs_AMSET_Transport",
        doping=(1e16, 1e17, 1e18),      # Carrier concentrations in cm^-3
        temperatures=(300.0, 400.0),    # Temperatures in K
        use_hse_gap=False               # Keep fast PBE for demonstration
    )

    flow = maker.make(gaas)

    # Submit workflow to remote worker
    from jobflow_remote import submit_flow
    flow_ids = submit_flow(flow, project="remote_perlmutter", worker="perlmutter_worker")

    print(f"✅ Submitted Amset workflow DAG with {len(flow.jobs)} top-level job nodes.")
    print(f"Flow IDs: {flow_ids}")

if __name__ == "__main__":
    main()
