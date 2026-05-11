import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
import time

def extract_property(props, label, name=None):
    """Safely extract a property from the PubChem properties list."""
    for p in props:
        urn = p.get("urn", {})
        if urn.get("label") == label:
            if name is None or urn.get("name") == name:
                val = p.get("value", {})
                return val.get("sval") or val.get("fval") or val.get("ival")
    return None

def query_fastsimilarity_2d(identifier, namespace="smiles", threshold=90, max_records=10):
    """Query PubChem PUG REST for 2D fast similarity."""
    
    # URL encode the identifier properly
    safe_id = urllib.parse.quote(str(identifier))
    base_url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/fastsimilarity_2d"
    url = f"{base_url}/{namespace}/{safe_id}/JSON?Threshold={threshold}&MaxRecords={max_records}"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "AtomisticSkills/1.0 (SimilaritySearch)")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            if e.code in [503, 504]:
                wait_time = (attempt + 1) * 2
                print(f"PubChem server busy (HTTP {e.code}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            elif e.code == 404:
                print(f"HTTP 404: No similar compounds found for {identifier}.")
                return None
            elif e.code == 400:
                print(f"HTTP 400: Bad request. Possibly invalid SMILES or CID: {identifier}.")
                return None
            else:
                print(f"HTTP Error: {e.code} - {e.reason}")
                return None
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
            return None
            
    print("Maximum retries exceeded.")
    return None

def main():
    parser = argparse.ArgumentParser(description="Query PubChem for fast 2D chemical similarity.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--smiles", help="SMILES string of the target molecule")
    group.add_argument("--cid", type=int, help="PubChem CID of the target molecule")
    
    parser.add_argument("--threshold", type=int, default=95, help="Similarity threshold (0-100, default: 95)")
    parser.add_argument("--max_records", type=int, default=10, help="Maximum number of records to return (default: 10)")
    parser.add_argument("--outdir", required=True, help="Directory to save the results")
    parser.add_argument("--output", default="similarity_results.json", help="Output filename")
    
    args = parser.parse_args()
    
    # Create output directory
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine namespace and identifier
    if args.smiles:
        namespace = "smiles"
        identifier = args.smiles
    else:
        namespace = "cid"
        identifier = str(args.cid)
        
    print(f"Querying PubChem fastsimilarity_2d for ({namespace}): {identifier}")
    print(f"Parameters: Threshold={args.threshold}, MaxRecords={args.max_records}")
    
    data = query_fastsimilarity_2d(identifier, namespace, args.threshold, args.max_records)
    
    if not data or "PC_Compounds" not in data:
        print("No matches found or query failed.")
        return
        
    compounds = data["PC_Compounds"]
    print(f"\nFound {len(compounds)} similar compounds.")
    
    results = []
    for comp in compounds:
        cid = comp.get("id", {}).get("id", {}).get("cid")
        props = comp.get("props", [])
        
        smiles = extract_property(props, "SMILES", "Canonical")
        if not smiles:
            smiles = extract_property(props, "SMILES", "Absolute")
            
        iupac = extract_property(props, "IUPAC Name", "Preferred")
        mw = extract_property(props, "Molecular Weight")
        formula = extract_property(props, "Molecular Formula")
        
        result_item = {
            "cid": cid,
            "smiles": smiles,
            "iupac_name": iupac,
            "formula": formula,
            "molecular_weight": mw,
            "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
        }
        results.append(result_item)
        print(f"CID: {cid:<10} MW: {mw:<8} Formula: {str(formula):<8} SMILES: {smiles}")

    output_path = out_dir / args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
        
    print(f"\nResults saved to: {output_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(json.dumps(_config, indent=2, default=str))

if __name__ == "__main__":
    main()
