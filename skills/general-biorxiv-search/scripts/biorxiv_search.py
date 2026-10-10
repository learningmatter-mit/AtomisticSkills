"""
bioRxiv / medRxiv Search Tool
Search and retrieve preprint metadata from bioRxiv and medRxiv via the official API.

Usage:
    python biorxiv_search.py "CRISPR gene editing" --max_results 5 --output results.json
    python biorxiv_search.py --category neuroscience --days 30 --max_results 10
    python biorxiv_search.py --server medrxiv "COVID vaccine" --max_results 5

Requirements:
    - Environment: cpu (run with: venv/run cpu python ...)
    - Required packages: requests
"""

import sys
import argparse
import json
import time
import urllib.parse
from typing import List, Dict, Any, Optional

import requests


class BioRxivSearcher:
    """Interface for bioRxiv/medRxiv preprint search via the official API."""

    BASE_URL = "https://api.biorxiv.org/details/{server}/{interval}/{cursor}/json"
    SEARCH_URL = "https://api.biorxiv.org/details/{server}/{interval}/{cursor}/json"

    # bioRxiv subject categories
    CATEGORIES = {
        "biochemistry": "biochemistry",
        "bioinformatics": "bioinformatics",
        "biophysics": "biophysics",
        "cancer": "cancer_biology",
        "cell-bio": "cell_biology",
        "dev-bio": "developmental_biology",
        "ecology": "ecology",
        "epidemiology": "epidemiology",
        "evolution": "evolutionary_biology",
        "genetics": "genetics",
        "genomics": "genomics",
        "immunology": "immunology",
        "microbiology": "microbiology",
        "molecular-bio": "molecular_biology",
        "neuroscience": "neuroscience",
        "pharmacology": "pharmacology",
        "physiology": "physiology",
        "plant-bio": "plant_biology",
        "synthetic-bio": "synthetic_biology",
        "systems-bio": "systems_biology",
    }

    def __init__(self, server: str = "biorxiv", verbose: bool = False):
        self.server = server.lower()
        self.verbose = verbose

    def _log(self, message: str):
        if self.verbose:
            print(f"[INFO] {message}", file=sys.stderr)

    def _fetch_page(self, interval: str, cursor: int = 0) -> Dict[str, Any]:
        """Fetch one page (up to 30 results) from bioRxiv API."""
        url = self.BASE_URL.format(
            server=self.server,
            interval=urllib.parse.quote(interval, safe="/"),
            cursor=cursor,
        )
        self._log(f"Requesting: {url}")
        time.sleep(0.5)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def search_by_date_range(
        self,
        start_date: str,
        end_date: str,
        keywords: Optional[List[str]] = None,
        category: Optional[str] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve preprints posted in a date range, optionally filtered by keyword/category.

        Args:
            start_date: Start date YYYY-MM-DD.
            end_date: End date YYYY-MM-DD.
            keywords: Filter results whose title or abstract contain all keywords.
            category: bioRxiv subject category (use CATEGORIES shortcuts or full name).
            max_results: Max papers to return.

        Returns:
            List of paper dicts.
        """
        interval = f"{start_date}/{end_date}"
        papers = []
        cursor = 0

        while len(papers) < max_results:
            data = self._fetch_page(interval, cursor)
            collection = data.get("collection", [])
            if not collection:
                break

            for item in collection:
                if len(papers) >= max_results:
                    break
                paper = self._parse_item(item)
                if self._matches(paper, keywords, category):
                    papers.append(paper)

            total = int(data.get("messages", [{}])[0].get("total", 0))
            cursor += 30
            if cursor >= total:
                break

        self._log(f"Found {len(papers)} papers")
        return papers

    def search_recent(
        self,
        days: int = 30,
        keywords: Optional[List[str]] = None,
        category: Optional[str] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve preprints from last N days, optionally filtered.

        Args:
            days: Number of recent days to search.
            keywords: Filter by keywords in title/abstract.
            category: Subject category filter.
            max_results: Max papers to return.
        """
        interval = f"{days}d"
        papers = []
        cursor = 0

        while len(papers) < max_results:
            data = self._fetch_page(interval, cursor)
            collection = data.get("collection", [])
            if not collection:
                break

            for item in collection:
                if len(papers) >= max_results:
                    break
                paper = self._parse_item(item)
                if self._matches(paper, keywords, category):
                    papers.append(paper)

            total = int(data.get("messages", [{}])[0].get("total", 0))
            cursor += 30
            if cursor >= total:
                break

        self._log(f"Found {len(papers)} papers")
        return papers

    def search_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for the latest version of a preprint by DOI.

        The API returns one record per posted version; the latest version is
        the one the DOI resolves to and carries the current title and authors.
        """
        url = self.BASE_URL.format(server=self.server, interval=doi, cursor=0)
        self._log(f"Requesting DOI: {url}")
        time.sleep(0.5)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        collection = data.get("collection", [])
        if collection:
            latest = max(collection, key=lambda item: int(item.get("version", 1)))
            return self._parse_item(latest)
        return None

    def _parse_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize API response item to standard paper dict."""
        doi = item.get("doi", "")
        return {
            "doi": doi,
            "url": f"https://www.{self.server}.org/content/{doi}v{item.get('version', 1)}"
            if doi
            else "",
            "title": item.get("title", "").strip(),
            "authors": item.get("authors", "").strip(),
            "abstract": item.get("abstract", "").strip(),
            "date": item.get("date", ""),
            "category": item.get("category", ""),
            "server": item.get("server", self.server),
            "version": item.get("version", ""),
            "license": item.get("license", ""),
            "published": item.get("published", ""),
        }

    def _matches(
        self,
        paper: Dict[str, Any],
        keywords: Optional[List[str]],
        category: Optional[str],
    ) -> bool:
        """Check if paper matches keyword and category filters."""
        if category:
            # The API reports categories with spaces ("cell biology"), while the
            # shortcuts and its query parameter use underscores ("cell_biology").
            full_cat = self.CATEGORIES.get(category, category).replace("_", " ")
            if full_cat.lower() not in paper.get("category", "").lower():
                return False

        if keywords:
            text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
            for kw in keywords:
                if kw.lower() not in text:
                    return False

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Search bioRxiv/medRxiv for preprints."
    )
    parser.add_argument("query", nargs="?", help="Keywords to search in title/abstract")
    parser.add_argument(
        "--server",
        default="biorxiv",
        choices=["biorxiv", "medrxiv"],
        help="Preprint server (default: biorxiv)",
    )
    parser.add_argument(
        "--category", help="Subject category (e.g. neuroscience, genetics)"
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Search last N days (default: 30)"
    )
    parser.add_argument("--start", help="Start date YYYY-MM-DD for date range search")
    parser.add_argument("--end", help="End date YYYY-MM-DD for date range search")
    parser.add_argument("--doi", help="Retrieve specific preprint by DOI")
    parser.add_argument(
        "--max_results", type=int, default=10, help="Max results to return"
    )
    parser.add_argument("--output", help="Path to save results as JSON")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    searcher = BioRxivSearcher(server=args.server, verbose=args.verbose)
    keywords = args.query.split() if args.query else None

    if args.doi:
        result = searcher.search_by_doi(args.doi)
        results = [result] if result else []
    elif args.start and args.end:
        results = searcher.search_by_date_range(
            start_date=args.start,
            end_date=args.end,
            keywords=keywords,
            category=args.category,
            max_results=args.max_results,
        )
    else:
        results = searcher.search_recent(
            days=args.days,
            keywords=keywords,
            category=args.category,
            max_results=args.max_results,
        )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(results)} results to {args.output}")
    else:
        for i, paper in enumerate(results, 1):
            print(f"\n[{i}] {paper['title']}")
            authors = paper.get("authors", "")
            print(f"    Authors: {authors[:100]}{'...' if len(authors) > 100 else ''}")
            print(
                f"    DOI: {paper['doi']} | Date: {paper['date']} | Category: {paper['category']}"
            )
            print(f"    URL: {paper['url']}")

    try:
        from src.utils.config_utils import save_skill_inputs

        save_skill_inputs(args, args.output)
    except ImportError:
        pass


if __name__ == "__main__":
    main()
