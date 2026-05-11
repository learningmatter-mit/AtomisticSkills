import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
import time
import http.client

def query_xrefs(cid, xref_types):
    """Fetch cross-references (e.g. PubMedID, PatentID) for a CID."""
    type_str = ",".join(xref_types)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/xrefs/{type_str}/JSON"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "AtomisticSkills/1.0 (XRefs)")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, http.client.RemoteDisconnected) as e:
            if isinstance(e, urllib.error.HTTPError):
                if e.code in [503, 504, 429]:
                    wait_time = (attempt + 1) * 3
                    print(f"PubChem server busy {e.code}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif e.code == 404:
                    print(f"HTTP 404: No XRef records found for CID {cid}.")
                    return None
                else:
                    print(f"HTTP Error: {e.code} - {e.reason}")
                    return None
            else:
                wait_time = (attempt + 1) * 3
                print(f"Connection Error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
                
    print("Maximum retries from PubChem exceeded.")
    return None

def main():
    parser = argparse.ArgumentParser(description="Query PubChem for literature and patent cross-references.")
    parser.add_argument("--cid", type=int, required=True, help="PubChem CID of the target molecule")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of IDs to save (default 1000 to prevent massive JSONs)")
    parser.add_argument("--outdir", required=True, help="Directory to save the results")
    parser.add_argument("--output", default="xrefs.json", help="Output filename")
    
    args = parser.parse_args()
    
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching PubMed and Patent Cross-References for CID: {args.cid}...")
    
    data = query_xrefs(args.cid, ["PubMedID", "PatentID"])
    
    if not data or "InformationList" not in data:
        print("Failed to retrieve or parse cross-reference data.")
        return
        
    info_list = data["InformationList"].get("Information", [])
    if not info_list:
        print("No information blocks found.")
        return
        
    info = info_list[0]
    pmids = info.get("PubMedID", [])
    patents = info.get("PatentID", [])
    
    print(f"\n--- Cross-References Summary ---")
    print(f"PubMed Articles Found: {len(pmids)}")
    print(f"Patents Found: {len(patents)}")
    
    # Construct actionable URLs for the top 5
    print("\nTop 5 literature links:")
    for pmid in pmids[:5]:
        print(f" - https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        
    print("\nTop 5 patent links:")
    for pat in patents[:5]:
        print(f" - https://patents.google.com/patent/{pat}/en")
        
    results = {
        "cid": args.cid,
        "pubmed_ids": pmids[:args.limit],
        "patent_ids": patents[:args.limit],
        "total_pubmed_found": len(pmids),
        "total_patents_found": len(patents),
        "capped_at": args.limit
    }
        
    output_path = out_dir / args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
        
    print(f"\nResults saved to: {output_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

if __name__ == "__main__":
    main()
