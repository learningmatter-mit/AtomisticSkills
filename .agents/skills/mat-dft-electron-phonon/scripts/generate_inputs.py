"""
Generate and serialize the Jobflow DAG for computing electron-phonon coupling (Temperature bandgap shift).

Usage:
    python generate_inputs.py --output elph_flow.json

Requirements:
    - Conda environment: atomate2-agent
    - Required packages: atomate2, phonopy, pymatgen, jobflow
"""

import argparse
import json
from pymatgen.core import Structure
from atomate2.vasp.flows.elph import ElectronPhononMaker

def main():
    parser = argparse.ArgumentParser(description="Generate ElectronPhononMaker flow DAG for Silicon.")
    parser.add_argument("--output", default="elph_flow.json", help="Output JSON path to save the DAG representation.")
    args = parser.parse_args()

    # Silicon primitive cell (FCC)
    si_structure = Structure(
        lattice=[[0.0, 2.715, 2.715], [2.715, 0.0, 2.715], [2.715, 2.715, 0.0]],
        species=["Si", "Si"],
        coords=[[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )

    # Initialize the automated Electron-Phonon workflow
    # This automatically includes:
    # 1. Structure relaxation (Tight)
    # 2. Phonon execution (generating supercell displacements and extracting force constants)
    # 3. Supercell uniform random displacements based on Bose-Einstein occupations for specified temperatures
    # 4. Dense static bandgap calculations for each displaced configuration
    # 5. Averaging bandgaps to extract the ZGMR (Zero-Point Renormalization) and temperature shifts
    maker = ElectronPhononMaker(
        name="Si_Electron_Phonon",
        temperatures=(0, 300, 600),   # Evaluate T=0K (quantum fluctuations), 300K, and 600K
        min_supercell_length=10.0     # Minimum supercell length in Angstroms
    )

    flow = maker.make(si_structure)

    # Submit workflow to remote worker
    from jobflow_remote import submit_flow
    flow_ids = submit_flow(flow, project="remote_perlmutter", worker="perlmutter_worker")

    print(f"✅ Submitted Electron-Phonon workflow DAG with {len(flow.jobs)} top-level job nodes.")
    print(f"Flow IDs: {flow_ids}")

if __name__ == "__main__":
    main()
