import argparse
import json
from pathlib import Path

from pymatgen.core import Structure
from atomate2.vasp.flows.lobster import VaspLobsterMaker
from jobflow import Flow

def main():
    parser = argparse.ArgumentParser(description="Generate an atomate2 LOBSTER VASP+LOBSTER workflow DAG.")
    parser.add_argument("--output", type=str, default="lobster_flow.json", help="Path to save the JSON flow definition.")
    # We could add an input structure, but for this example, we generate GaAs automatically
    args = parser.parse_args()

    # 1. Define the structure
    # GaAs zincblende standard primitive structure
    gaas = Structure(
        lattice=[[0.0, 2.827, 2.827], [2.827, 0.0, 2.827], [2.827, 2.827, 0.0]],
        species=["Ga", "As"],
        coords=[[0, 0, 0], [0.25, 0.25, 0.25]]
    )

    # 2. Instantiate the Lobster workflow maker
    # This automatically creates a RelaxMaker -> StaticMaker (with accurate basis info) -> LobsterMaker
    # The default delete_wavecars=True ensures the WAVECAR is cleaned up after projection
    maker = VaspLobsterMaker()

    # 3. Generate the workflow topology from the structure
    flow = maker.make(gaas)

    # Serialize to JSON to inspect the DAG nodes (Jobs) without executing natively
    with open(args.output, "w") as f:
        json.dump(flow.as_dict(), f, indent=4)

    print(f"✅ Generated LOBSTER workflow DAG with {len(flow.jobs)} top-level job nodes.")
    print(f"Saved flow schema to {args.output}.")
    print("To execute this workflow, submit `flow` via a Jobflow/Fireworks execution manager on a remote HPC.")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(json.dumps(_config, indent=2, default=str))

if __name__ == "__main__":
    main()
