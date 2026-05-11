import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
import time

def find_section(node, target_heading):
    """Recursively search for a section with a specific TOCHeading."""
    if node.get("TOCHeading") == target_heading:
        return node
    for sec in node.get("Section", []):
        r = find_section(sec, target_heading)
        if r:
            return r
    return None

def extract_information(section, max_items=0):
    """Extract all text items from a section's Information fields."""
    results = []
    
    def _extract(node):
        info_list = node.get("Information", [])
        for info in info_list:
            if "Value" in info and "StringWithMarkup" in info["Value"]:
                for item in info["Value"]["StringWithMarkup"]:
                    val = item.get("String", "").strip()
                    if val and val not in results:
                        results.append(val)
        for sec in node.get("Section", []):
            _extract(sec)
            
    _extract(section)
    if max_items > 0:
        return results[:max_items]
    return results

def query_safety_data(cid):
    """Fetch safety and toxicity data for a CID from PubChem PUG VIEW."""
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "AtomisticSkills/1.0 (SafetyData)")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            if e.code in [503, 504, 429]:
                wait_time = (attempt + 1) * 3
                print(f"Server busy (HTTP {e.code}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            elif e.code == 404:
                print(f"HTTP 404: Record not found for CID {cid}.")
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
    parser = argparse.ArgumentParser(description="Query PubChem for safety, hazard, and toxicity data.")
    parser.add_argument("--cid", type=int, required=True, help="PubChem CID of the target molecule")
    parser.add_argument("--outdir", required=True, help="Directory to save the results")
    parser.add_argument("--output", default="safety_data.json", help="Output filename")
    
    args = parser.parse_args()
    
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching safety and toxicity records for CID: {args.cid}...")
    
    data = query_safety_data(args.cid)
    
    if not data or "Record" not in data:
        print("Failed to retrieve or parse data.")
        return
        
    record = data["Record"]
    
    result_dict = {
        "cid": args.cid,
        "ghs_classification": [],
        "hazard_classes": [],
        "toxicity": []
    }
    
    # 1. Look for Safety and Hazards
    safety_sec = find_section(record, "Safety and Hazards")
    if safety_sec:
        ghs = find_section(safety_sec, "GHS Classification")
        if ghs:
            result_dict["ghs_classification"] = extract_information(ghs, max_items=20)
            
        classes = find_section(safety_sec, "Hazard Classes and Categories")
        if classes:
            result_dict["hazard_classes"] = extract_information(classes, max_items=20)
            
    # 2. Look for Toxicity
    tox_sec = find_section(record, "Toxicity")
    if not tox_sec:
        # Sometimes under Toxicological Information
        tox_sec = find_section(record, "Toxicological Information")
        
    if tox_sec:
        result_dict["toxicity"] = extract_information(tox_sec, max_items=50)
        
    print("\n--- Summary of Findings ---")
    print(f"GHS Statements Found: {len(result_dict['ghs_classification'])}")
    print(f"Hazard Classes Found: {len(result_dict['hazard_classes'])}")
    print(f"Toxicity Records Found: {len(result_dict['toxicity'])}")
    
    if not any(result_dict.values()):
        print("Warning: No safety or toxicity information found for this CID.")

    output_path = out_dir / args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=4)
        
    print(f"\nResults saved to: {output_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

if __name__ == "__main__":
    main()
