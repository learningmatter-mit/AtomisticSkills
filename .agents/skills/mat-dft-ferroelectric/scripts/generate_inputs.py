"""
Generate and serialize the Jobflow DAG for computing spontaneous polarization (Ferroelectric flow).

Usage:
    python generate_inputs.py --output ferroelectric_flow.json

Requirements:
    - Conda environment: atomate2-agent
    - Required packages: atomate2, pymatgen, jobflow
"""

import argparse
import json
from pymatgen.core import Structure, Lattice
from atomate2.vasp.flows.ferroelectric import FerroelectricMaker

def main():
    parser = argparse.ArgumentParser(description="Generate FerroelectricMaker flow DAG for BaTiO3.")
    parser.add_argument("--output", default="ferroelectric_flow.json", help="Output JSON path to save the DAG representation.")
    args = parser.parse_args()

    # BaTiO3 Non-polar (Cubic) Phase (Idealized Perovskite)
    cubic_lattice = Lattice.cubic(4.0)
    nonpolar_struct = Structure(
        lattice=cubic_lattice,
        species=["Ba", "Ti", "O", "O", "O"],
        coords=[
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [0.5, 0.5, 0.0],
            [0.5, 0.0, 0.5],
            [0.0, 0.5, 0.5]
        ]
    )

    # BaTiO3 Polar (Tetragonal) Phase 
    # (P4mm symmetry, z-axis extended, atoms displaced along z)
    tet_lattice = Lattice.tetragonal(3.99, 4.03)
    polar_struct = Structure(
        lattice=tet_lattice,
        species=["Ba", "Ti", "O", "O", "O"],
        coords=[
            [0.0, 0.0, 0.0],            # Ba
            [0.5, 0.5, 0.515],          # Ti displaced
            [0.5, 0.5, -0.025],         # O1 displaced
            [0.5, 0.0, 0.48],           # O2 displaced
            [0.0, 0.5, 0.48]            # O3 displaced
        ]
    )

    # Initialize the automated Ferroelectric workflow
    # This automatically includes:
    # 1. Relaxation of both structures (optional depending on maker setup, defaults to True)
    # 2. Structure interpolation path (nimages=5 by default)
    # 3. LCALCPOL=True Berry phase calculations for all images
    # 4. Final polarization vector calculation mapping branches
    maker = FerroelectricMaker(
        name="BaTiO3_Spontaneous_Polarization",
        nimages=5,      # 5 intermediate distorted structures
        relax_maker=None # Disable relaxation strictly to lock our chosen experimental distortions
    )

    # Make the flow, specifying polar and nonpolar ends
    flow = maker.make(polar_struct, nonpolar_struct)

    # Submit workflow to remote worker
    from jobflow_remote import submit_flow
    flow_ids = submit_flow(flow, project="remote_perlmutter", worker="perlmutter_worker")

    print(f"✅ Submitted Ferroelectric workflow DAG with {len(flow.jobs)} top-level job nodes.")
    print(f"Flow IDs: {flow_ids}")

if __name__ == "__main__":
    main()
