#!/usr/bin/env python3
"""
Fetch the averaged elemental price (from Wikipedia) and a vendor ordering link (from PubChem).

Usage:
    python get_pricing.py "Lithium carbonate"
    python get_pricing.py Li
    python get_pricing.py "Gold"

Requirements:
    - Conda environment: base-agent
    - Required packages: pubchempy, beautifulsoup4, requests
"""

import argparse
import sys
import pubchempy as pcp
import requests
from bs4 import BeautifulSoup

def get_element_price_wikipedia(query):
    """
    Looks up the averaged elemental price from the Wikipedia 'Prices of chemical elements' page.
    Args:
        query: Element symbol or name (e.g. 'Li' or 'Lithium')
    Returns:
        String with price in USD/kg or None
    """
    url = "https://en.wikipedia.org/wiki/Prices_of_chemical_elements"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        html = requests.get(url, headers=headers).text
        soup = BeautifulSoup(html, 'html.parser')
        tables = soup.find_all('table', {'class': 'wikitable'})
        if not tables:
            return None
        
        target_table = tables[0]
        query_lower = query.lower()
        
        # Parse table rows skipping headers (usually first 2 rows are headers)
        for tr in target_table.find_all('tr'):
            cells = [th.text.strip() for th in tr.find_all(['th', 'td'])]
            if len(cells) >= 8:
                z = cells[0]
                # Skip header rows
                if not z.isdigit():
                    continue
                symbol = cells[1].split('(')[0].strip().lower() # Handle like '2H (D)'
                name = cells[2].lower()
                price_usd_kg = cells[5]
                year = cells[7]
                
                if query_lower == symbol or query_lower == name:
                    return f"${price_usd_kg}/kg (Year: {year})"
    except Exception as e:
        print(f"Warning: Failed to fetch Wikipedia price: {e}", file=sys.stderr)
    
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Get chemical pricing and vendor links for elements and compound precursors."
    )
    parser.add_argument("query", help="Element symbol, name, or chemical compound name (e.g., 'Li', 'Lithium', 'Li2CO3')")
    args = parser.parse_args()
    
    query = args.query
    print(f"Searching pricing information for: {query}\n")
    
    # 1. Search for generic element price via Wikipedia
    element_price = get_element_price_wikipedia(query)
    if element_price:
        print("=== Elemental Bulk Pricing ===")
        print(f"Averaged bulk price for {query}: {element_price}")
        print("(Source: USGS Mineral Commodity Summaries via Wikipedia)\n")
    else:
        pass
    
    # 2. Search PubChem for vendor links (both for pure elements and compounds)
    print("=== Compound / Precursor Vendor Link ===")
    try:
        # First try searching by name
        compounds = pcp.get_compounds(query, 'name')
        if not compounds:
            # Fallback to formula
            compounds = pcp.get_compounds(query, 'formula')
        
        if compounds:
            comp = compounds[0]
            cid = comp.cid
            smiles = comp.smiles
            print(f"PubChem CID: {cid}")
            print(f"SMILES: {smiles}")
            vendor_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}#section=Chemical-Vendors"
            print(f"Vendor Order Link: {vendor_url}")
            print("Note: Follow the link to see a list of commercial suppliers and purchase the compound.")
        else:
            print("Could not find the compound in PubChem database to generate a vendor link.")
    except Exception as e:
        print(f"PubChem search failed: {e}")

if __name__ == "__main__":
    main()
