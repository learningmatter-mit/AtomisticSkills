"""
Query the QMOF database (MPContribs project ``qmof``) and download DFT-relaxed CIFs
together with the tabulated properties (PBE band gap, density, pore sizes, source).

Usage:
    python query_qmof.py --identifier DOTSOV01 --max-results 1 --output-dir ./qmof_hkust1
    python query_qmof.py --formula Zn --max-results 5 --output-dir ./qmof_zn

Requirements:
    - Environment: cpu
    - Required packages: mpcontribs-client
    - MP_API_KEY environment variable
"""

import argparse
import json
import os
from mpcontribs.client import Client

# Tabulated QMOF columns written to qmof_properties.json, with their MPContribs units.
PROPERTY_UNITS = {
    "filename": None,
    "csdRefcode": None,
    "source": None,
    "doi": None,
    "synthesized": None,
    "reducedFormula": None,
    "spacegroup": None,
    "spacegroupNumber": None,
    "natoms": None,
    "volume": "A^3",
    "density": "g/cm^3",
    "pld": "A",
    "lcd": "A",
    "EgPBE": "eV",
    "EgHLE17": "eV",
    "EgHSE06star": "eV",
    "EgHSE06": "eV",
    "netPBEMagmom": None,
}


def _flatten_data(data: dict) -> dict:
    """
    Collapse MPContribs quantity entries ({"display", "value", "unit", ...}) to their value.

    Args:
        data: The ``data`` block of an MPContribs contribution.

    Returns:
        Dictionary mapping each QMOF column name to a plain string or float.
    """
    return {
        key: (val["value"] if isinstance(val, dict) and "value" in val else val)
        for key, val in data.items()
    }


def main():
    parser = argparse.ArgumentParser(
        description="Query the QMOF database on Materials Project."
    )
    parser.add_argument(
        "--formula", type=str, help="Chemical formula to search for (e.g., Zn,O,C)."
    )
    parser.add_argument(
        "--identifier",
        type=str,
        help="QMOF ID (e.g., qmof-8b5bb88) or a CSD refcode / source-filename substring "
        "(e.g., KAXQIL, DOTSOV01). Case-sensitive.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum number of structures to download.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./qmof_results",
        help="Directory to save downloaded CIFs.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("MP_API_KEY")
    if not api_key:
        print(
            "Error: MP_API_KEY environment variable is not set. Please set it to use this tool."
        )
        return

    print("Initializing MPContribs client...")
    client = Client(api_key, project="qmof")

    query = {}
    if args.formula:
        # mpcontribs client allows filtering by elements in the formula
        query["formula__contains"] = args.formula
    if args.identifier:
        if args.identifier.lower().startswith("qmof-"):
            # The MPContribs identifier is the QMOF ID (e.g. qmof-8b5bb88)
            query["identifier__contains"] = args.identifier
        else:
            # CSD refcodes and other source names are stored in data.filename
            # (e.g. "DOTSOV01_FSR", "core_KAXQIL_freeONLY")
            query["data__filename__contains"] = args.identifier

    print(f"Querying QMOF with parameters: {query}")
    try:
        # Retrieve the matching contributions
        results = client.contributions.queryContributions(
            project="qmof",
            _fields=["id", "identifier", "formula", "structures"]
            + [f"data.{key}" for key in PROPERTY_UNITS],
            _limit=args.max_results,
            **query,
        ).result()
    except Exception as e:
        print(f"Failed to query MPContribs: {e}")
        return

    if not results or "data" not in results or len(results["data"]) == 0:
        print("No matching MOFs found in QMOF database.")
        return

    os.makedirs(args.output_dir, exist_ok=True)
    print(
        f"Found {len(results['data'])} matching MOFs. Downloading CIFs to {args.output_dir}..."
    )

    # For each found contribution, record its tabulated properties and download the structure
    records = []
    for contrib in results["data"]:
        identifier = contrib["identifier"]
        formula = contrib["formula"]
        records.append(
            {
                "qmof_id": identifier,
                "formula": formula,
                **_flatten_data(contrib.get("data", {})),
            }
        )

        print(f"Downloading {identifier} (Formula: {formula})...")
        try:
            if "structures" not in contrib or not contrib["structures"]:
                print(f"  No structures listed for {identifier}.")
                continue

            structure_id = contrib["structures"][0]["id"]

            # MPContribs structures are accessible via their ID
            structure_data = client.structures.getStructureById(
                pk=structure_id, _fields=["cif"]
            ).result()
            cif_string = structure_data.get("cif")

            if cif_string:
                filepath = os.path.join(args.output_dir, f"{identifier}.cif")
                with open(filepath, "w") as f:
                    f.write(cif_string)
                print(f"  Saved to {filepath}")
            else:
                print(f"  No CIF structure found for {identifier}.")

        except Exception as e:
            print(f"  Error downloading {identifier}: {e}")

    props_path = os.path.join(args.output_dir, "qmof_properties.json")
    units = {key: unit for key, unit in PROPERTY_UNITS.items() if unit}
    with open(props_path, "w") as f:
        json.dump({"units": units, "entries": records}, f, indent=2)
    print(f"Saved tabulated properties to {props_path}")

    print("Done.")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs

    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
