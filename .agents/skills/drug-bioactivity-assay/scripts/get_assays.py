import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
import time
import http.client
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
import time

def query_assay_summary(cid):
    """Fetch assay summary for a CID from PubChem PUG REST."""
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/assaysummary/JSON"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "AtomisticSkills/1.0 (AssaySummary)")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.loads(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, http.client.RemoteDisconnected) as e:
            if isinstance(e, urllib.error.HTTPError):
                if e.code in [503, 504, 429]:
                    wait_time = (attempt + 1) * 3
                    print(f"PubChem server busy (HTTP {e.code}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif e.code == 404:
                    print(f"HTTP 404: No assay records found for CID {cid}.")
                    return None
                else:
                    print(f"HTTP Error: {e.code} - {e.reason}")
                    return None
            else:
                # Handle URLError or RemoteDisconnected
                wait_time = (attempt + 1) * 3
                print(f"Connection Error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            
    print("Maximum retries from PubChem exceeded.")
    return None

def process_table(table, active_only):
    """Convert PubChem Table dictionary to list of records."""
    columns = table.get("Columns", {}).get("Column", [])
    rows = table.get("Row", [])
    
    results = []
    
    for row in rows:
        cells = row.get("Cell", [])
        record = dict(zip(columns, cells))
        
        # Determine active
        outcome = record.get("Activity Outcome", "")
        if active_only and outcome.lower() != "active":
            continue
            
        results.append(record)
        
    return results

def main():
    parser = argparse.ArgumentParser(description="Query PubChem for molecular bioactivity and target assays.")
    parser.add_argument("--cid", type=int, required=True, help="PubChem CID of the target molecule")
    parser.add_argument("--active_only", action="store_true", help="Only return assays where the compound was 'Active'")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of assay records to save (default: 1000)")
    parser.add_argument("--outdir", required=True, help="Directory to save the results")
    parser.add_argument("--output", default="assay_summary.json", help="Output filename")
    
    args = parser.parse_args()
    
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching assay summaries for CID: {args.cid}...")
    
    data = query_assay_summary(args.cid)
    
    if not data or "Table" not in data:
        print("Failed to retrieve or parse assay data.")
        return
        
    table = data["Table"]
    records = process_table(table, args.active_only)
    
    print(f"\nFound {len(records)} assays matching criteria.")
    
    # Print a summary of the top records
    print(f"\nTop 5 Results:")
    print("-" * 80)
    for i, r in enumerate(records[:5]):
        aid = r.get("AID", "N/A")
        outcome = r.get("Activity Outcome", "N/A")
        gene = r.get("Target GeneID", "N/A")
        val = r.get("Activity Value [uM]", "")
        name = r.get("Assay Name", "N/A")
        print(f"[{i+1}] AID: {aid} | Outcome: {outcome} | Target GeneID: {gene} | Activity Val [uM]: {val}")
        print(f"    Assay: {name[:70]}{'...' if len(name) > 70 else ''}")
        print("-" * 80)
        
    # Cap the results based on the provided limit to prevent huge JSONs
    records = records[:args.limit]
        
    output_path = out_dir / args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4)
        
    print(f"\nResults saved to: {output_path} (capped at {args.limit})")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(json.dumps(_config, indent=2, default=str))

if __name__ == "__main__":
    main()
