"""
ArXiv Search Tool
A Python tool for searching and retrieving papers from ArXiv.
Uses the ArXiv API and feedparser to retrieve and parse research papers.

Usage:
    python arxiv_search.py "machine learning" --max_results 5 --output results.json

Requirements:
    - Conda environment: base-agent
    - Required packages: feedparser, requests
"""

import sys
import argparse
import json
import urllib.parse
import urllib.request
import feedparser
from typing import List, Dict, Any, Optional
import time

class ArXivSearcher:
    """Interface for ArXiv research paper search."""
    
    BASE_URL = "http://export.arxiv.org/api/query?"
    
    # Common categories for Materials Science and Physics
    CATEGORIES = {
        "mtrl-sci": "cond-mat.mtrl-sci",
        "mes-hall": "cond-mat.mes-hall",
        "soft-matter": "cond-mat.soft",
        "stat-mech": "cond-mat.stat-mech",
        "str-el": "cond-mat.str-el",
        "supr-con": "cond-mat.supr-con",
        "comp-phys": "physics.comp-ph",
        "chem-phys": "physics.chem-ph",
        "nano": "physics.app-ph",
        "ml": "cs.LG",
        "ai": "cs.AI"
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _log(self, message: str):
        if self.verbose:
            print(f"[INFO] {message}", file=sys.stderr)

    def build_query(self, 
                    keywords: Optional[List[str]] = None, 
                    authors: Optional[List[str]] = None, 
                    categories: Optional[List[str]] = None,
                    title_keywords: Optional[List[str]] = None) -> str:
        """Construct a search query string for the ArXiv API."""
        query_parts = []
        
        if keywords:
            query_parts.append(f"all:{' AND '.join(keywords)}")
        
        if authors:
            query_parts.append(f"au:{' AND '.join(authors)}")
            
        if categories:
            cat_list = [self.CATEGORIES.get(c, c) for c in categories]
            query_parts.append(f"cat:{' OR '.join(cat_list)}")
            
        if title_keywords:
            query_parts.append(f"ti:{' AND '.join(title_keywords)}")
            
        return " AND ".join([f"({p})" for p in query_parts])

    def search(self, 
               query: str, 
               max_results: int = 10, 
               sort_by: str = "relevance", 
               sort_order: str = "descending") -> List[Dict[str, Any]]:
        """
        Execute search on ArXiv.
        
        Args:
            query: The search query string.
            max_results: Maximum number of results to return.
            sort_by: Field to sort by ('relevance', 'lastUpdatedDate', 'submittedDate').
            sort_order: Order of sorting ('ascending', 'descending').
            
        Returns:
            List of papers as dictionaries.
        """
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order
        }
        
        url = self.BASE_URL + urllib.parse.urlencode(params)
        self._log(f"Requesting: {url}")
        
        try:
            # Respectful rate limiting
            time.sleep(0.5)
            
            response = urllib.request.urlopen(url).read()
            feed = feedparser.parse(response)
            
            papers = []
            for entry in feed.entries:
                paper = {
                    "id": entry.id.split('/abs/')[-1],
                    "url": entry.id,
                    "title": entry.title.replace('\n', ' ').strip(),
                    "authors": [author.name for author in entry.authors],
                    "summary": entry.summary.replace('\n', ' ').strip(),
                    "published": entry.published,
                    "updated": entry.updated,
                    "categories": [tag.term for tag in entry.tags],
                    "doi": entry.get("arxiv_doi", None),
                    "journal_ref": entry.get("arxiv_journal_ref", None),
                    "primary_category": entry.arxiv_primary_category['term'] if hasattr(entry, 'arxiv_primary_category') else None
                }
                papers.append(paper)
                
            self._log(f"Found {len(papers)} papers")
            return papers
            
        except Exception as e:
            self._log(f"Error during ArXiv search: {e}")
            return []

def main():
    parser = argparse.ArgumentParser(description="Search ArXiv for research papers.")
    parser.add_argument("query", nargs="?", help="General keywords search")
    parser.add_argument("--authors", nargs="+", help="Search by authors")
    parser.add_argument("--categories", nargs="+", help="Filter by categories (e.g. mtrl-sci, ml)")
    parser.add_argument("--title", nargs="+", help="Search in title")
    parser.add_argument("--max_results", type=int, default=10, help="Maximum number of results")
    parser.add_argument("--output", help="Path to save results in JSON format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    searcher = ArXivSearcher(verbose=args.verbose)
    
    # If a direct query string is provided, use it, otherwise build from parts
    if args.query and not (args.authors or args.categories or args.title):
        search_query = f"all:{args.query}"
    else:
        search_query = searcher.build_query(
            keywords=[args.query] if args.query else None,
            authors=args.authors,
            categories=args.categories,
            title_keywords=args.title
        )
    
    if not search_query:
        print("Error: No search criteria provided.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
        
    results = searcher.search(search_query, max_results=args.max_results)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(results)} results to {args.output}")
    else:
        # Print a summary to console
        for i, paper in enumerate(results, 1):
            print(f"\n[{i}] {paper['title']}")
            print(f"    Authors: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}")
            print(f"    ID: {paper['id']} | Published: {paper['published']}")
            print(f"    URL: {paper['url']}")

if __name__ == "__main__":
    main()
