"""
Query Google Patents using web scraping.

Usage:
    python query_google_patents.py "query string" --limit 10

Requirements:
    - Conda environment: base-agent
    - Required packages: requests, beautifulsoup4
"""

import argparse
import html
import json
import sys
import urllib.request
import urllib.parse

def search_google_patents(query: str, limit: int = 10) -> list:
    """
    Search Google Patents using the undocumented JSON endpoint.
    
    Args:
        query: Search string
        limit: Maximum number of results
        
    Returns:
        List of dictionaries containing patent results from Google Patents
    """
    # Google Patents uses an XHR endpoint that returns JSON data
    # Format: https://patents.google.com/xhr/query?url=q%3D<query>%26num%3D<limit>
    
    encoded_query = urllib.parse.quote_plus(query)
    # The URL parameter requires its own distinct encoding
    url_param = f"q={encoded_query}&num={limit}"
    encoded_url_param = urllib.parse.quote(url_param)
    
    url = f"https://patents.google.com/xhr/query?url={encoded_url_param}"
    
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    })
    
    patents = []
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
            # The JSON structure contains nested results lists
            # data['results']['cluster'][0]['result'] usually contains the patent hits
            if 'results' in data and 'cluster' in data['results']:
                for cluster in data['results']['cluster']:
                    if 'result' in cluster:
                        for hit in cluster['result']:
                            patent = hit.get('patent', {})
                            
                            p_info = {
                                'publication_number': patent.get('publication_number', 'N/A'),
                                'title': html.unescape(patent.get('title', 'N/A')),
                                'assignee': html.unescape(patent.get('assignee', 'N/A')),
                                'inventor': patent.get('inventor', 'N/A'),
                                'priority_date': patent.get('priority_date', 'N/A'),
                                'snippet': hit.get('snippet', 'N/A')
                            }
                            patents.append(p_info)
                            
    except Exception as e:
        print(f"Error querying Google Patents: {e}")
        
    return patents

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Google Patents")
    parser.add_argument("query", help="Keywords or chemical names to search for")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of patents to retrieve")
    parser.add_argument("--output", type=str, default=None, help="Optional path to save results as JSON")

    args = parser.parse_args()

    print(f"Searching Google Patents for: '{args.query}' (limit: {args.limit})")
    results = search_google_patents(args.query, limit=args.limit)
    results = results[:args.limit]

    print(f"\nFound {len(results)} results:")
    print("-" * 80)

    if results:
        for i, p in enumerate(results, 1):
            print(f"[{i}] Patent #: {p.get('publication_number')} | Priority Date: {p.get('priority_date')}")
            print(f"    Title:    {p.get('title')}")
            print(f"    Assignee: {p.get('assignee')}")
            # Clean up snippet: remove bold HTML tags Google sometimes returns
            snippet = html.unescape(str(p.get('snippet', 'N/A'))).replace('<b>', '').replace('</b>', '')
            print(f"    Snippet:  {snippet[:200]}...")
            print()
    else:
        print("No patents found matching the query.")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump({'query': args.query, 'limit': args.limit, 'results': results}, f, indent=2)
        print(f"Results saved to: {args.output}")
