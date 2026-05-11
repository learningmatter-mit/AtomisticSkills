import argparse
import requests
import json
import os
from bs4 import BeautifulSoup

def search_formula(formula):
    """Search NIST WebBook by formula and return the ID of the first match."""
    url = f'https://webbook.nist.gov/cgi/cbook.cgi?Formula={formula}&NoIon=on&Units=SI'
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    if 'Name:' in resp.text:
        links = soup.find_all('a', href=True)
        for link in links:
            if 'cbook.cgi?ID=C' in link['href']:
                import urllib.parse
                parsed = urllib.parse.urlparse(link['href'])
                qs = urllib.parse.parse_qs(parsed.query)
                if 'ID' in qs:
                    return qs['ID'][0], soup.find('h1', id='Top').text.strip()
        return None, None
    else:
        list_items = soup.find_all('li')
        for item in list_items:
            a = item.find('a', href=True)
            if a and 'cbook.cgi?ID=' in a['href']:
                import urllib.parse
                parsed = urllib.parse.urlparse(a['href'])
                qs = urllib.parse.parse_qs(parsed.query)
                if 'ID' in qs:
                    return qs['ID'][0], a.text.strip()
    return None, None

def download_spectrum(compound_id, spec_type, index, output_dir):
    """Download a JCAMP-DX spectrum file. Returns True if successful."""
    url = f'https://webbook.nist.gov/cgi/cbook.cgi?JCAMP={compound_id}&Type={spec_type}&Index={index}'
    resp = requests.get(url)
    
    if resp.status_code == 200 and "Spectrum not found" not in resp.text:
        filename = os.path.join(output_dir, f"{compound_id}_{spec_type}_{index}.jdx")
        with open(filename, 'w') as f:
            f.write(resp.text)
        print(f"Downloaded {spec_type} spectrum (Index {index}) -> {filename}")
        return True
    return False

def main():
    """
    Search NIST WebBook for a chemical formula and extract experimental JCAMP-DX spectra.
    """
    parser = argparse.ArgumentParser(description="Query NIST WebBook for Experimental Spectra.")
    parser.add_argument("formula", help="Chemical formula (e.g. CH4)")
    parser.add_argument("output_dir", help="Directory to save the .jdx spectrum files")
    parser.add_argument("--type", choices=['IR', 'Mass', 'UVVis', 'All'], default='All',
                        help="Type of spectrum to download (default: All)")
    args = parser.parse_args()
    
    print(f"Searching NIST WebBook for '{args.formula}'...")
    compound_id, name = search_formula(args.formula)
    
    if not compound_id:
        print("No matching compound found.")
        return
        
    print(f"Found match: {name} (ID: {compound_id})")
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        
    types_to_check = ['IR', 'Mass', 'UVVis'] if args.type == 'All' else [args.type]
    
    found_any = False
    for t in types_to_check:
        print(f"Checking for {t} spectra...")
        index = 0
        while True:
            success = download_spectrum(compound_id, t, index, args.output_dir)
            if not success:
                break
            found_any = True
            index += 1
            
    if not found_any:
        print("No spectra found in JCAMP-DX format for this compound.")
    else:
        print("All available spectra downloaded successfully.")

        # Save input configs for reproducibility
        from src.utils.config_utils import save_skill_inputs
        save_skill_inputs(args, args.output_dir)
        _params_path.parent.mkdir(parents=True, exist_ok=True)
        _params_path.write_text(json.dumps(_config, indent=2, default=str))

if __name__ == "__main__":
    main()
