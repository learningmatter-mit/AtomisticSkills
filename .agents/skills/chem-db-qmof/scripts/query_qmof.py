import argparse
import os
from mpcontribs.client import Client

def main():
    parser = argparse.ArgumentParser(description="Query the QMOF database on Materials Project.")
    parser.add_argument("--formula", type=str, help="Chemical formula to search for (e.g., Zn,O,C).")
    parser.add_argument("--identifier", type=str, help="Specific CSD Refcode or MOF name.")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum number of structures to download.")
    parser.add_argument("--output-dir", type=str, default="./qmof_results", help="Directory to save downloaded CIFs.")
    args = parser.parse_args()

    api_key = os.environ.get("MP_API_KEY")
    if not api_key:
        print("Error: MP_API_KEY environment variable is not set. Please set it to use this tool.")
        return

    print("Initializing MPContribs client...")
    client = Client(api_key, project="qmof")

    query = {}
    if args.formula:
        # mpcontribs client allows filtering by elements in the formula
        query["formula__contains"] = args.formula
    if args.identifier:
        # filter by identifier directly
        query["identifier__contains"] = args.identifier

    print(f"Querying QMOF with parameters: {query}")
    try:
        # Retrieve the matching contributions
        results = client.contributions.queryContributions(
            project="qmof",
            _fields=["id", "identifier", "formula", "structures"],
            _limit=args.max_results,
            **query
        ).result()
    except Exception as e:
        print(f"Failed to query MPContribs: {e}")
        return

    if not results or "data" not in results or len(results["data"]) == 0:
        print("No matching MOFs found in QMOF database.")
        return

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Found {len(results['data'])} matching MOFs. Downloading CIFs to {args.output_dir}...")

    # For each found contribution, we download the structure
    for contrib in results["data"]:
        contrib_id = contrib["id"]
        identifier = contrib["identifier"]
        formula = contrib["formula"]
        
        print(f"Downloading {identifier} (Formula: {formula})...")
        try:
            if "structures" not in contrib or not contrib["structures"]:
                print(f"  No structures listed for {identifier}.")
                continue
                
            structure_id = contrib["structures"][0]["id"]
            
            # MPContribs structures are accessible via their ID
            structure_data = client.structures.getStructureById(
                pk=structure_id,
                _fields=["cif"]
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

    print("Done.")

if __name__ == "__main__":
    main()
