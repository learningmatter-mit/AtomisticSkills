"""
ArXiv Search Tool
A Python tool for searching and retrieving papers from ArXiv.
Uses the ArXiv API and feedparser to retrieve and parse research papers.

Usage:
    python arxiv_search.py "machine learning" --max_results 5 --output results.json

Requirements:
    - Environment: cpu (run with: venv/run cpu python ...)
    - Required packages: feedparser, requests
"""

import sys
import argparse
import json
import re
import urllib.parse
import urllib.request
import feedparser
from typing import List, Dict, Any, Optional
import time


class ArXivSearcher:
    """Interface for ArXiv research paper search."""

    BASE_URL = "https://export.arxiv.org/api/query?"

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
        "ai": "cs.AI",
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _log(self, message: str):
        if self.verbose:
            print(f"[INFO] {message}", file=sys.stderr)

    @staticmethod
    def _split_terms(texts: List[str]) -> List[str]:
        """Split free text into search terms, keeping "double-quoted phrases" intact."""
        terms = []
        for text in texts:
            for phrase, word in re.findall(r'"([^"]+)"|(\S+)', text):
                terms.append(phrase or word)
        return terms

    @staticmethod
    def _field_term(field: str, term: str) -> str:
        """Prefix one term with its field, quoting it if it contains spaces."""
        term = " ".join(term.split())
        return f'{field}:"{term}"' if " " in term else f"{field}:{term}"

    def build_query(
        self,
        keywords: Optional[List[str]] = None,
        authors: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        title_keywords: Optional[List[str]] = None,
    ) -> str:
        """
        Construct a search query string for the ArXiv API.

        The API applies a field prefix only to the term that directly follows it
        and treats a bare space as a separator, so every term gets its own prefix
        and multi-word phrases are double-quoted.

        Args:
            keywords: Free-text strings searched in all fields; every word must
                match (AND), and "double-quoted phrases" must match verbatim.
            authors: Author names; every author must match (AND), and each name
                is matched as one phrase.
            categories: Category shortcuts or full names; any may match (OR).
            title_keywords: Free-text strings searched in titles, with the same
                rules as ``keywords``.

        Returns:
            The search_query string, e.g. ``(all:graphene AND all:strain) AND (cat:cond-mat.mtrl-sci)``.
        """
        query_parts = []

        if keywords:
            terms = self._split_terms(keywords)
            query_parts.append(" AND ".join(self._field_term("all", t) for t in terms))

        if authors:
            query_parts.append(" AND ".join(self._field_term("au", a) for a in authors))

        if categories:
            cat_list = [self.CATEGORIES.get(c, c) for c in categories]
            query_parts.append(
                " OR ".join(self._field_term("cat", c) for c in cat_list)
            )

        if title_keywords:
            terms = self._split_terms(title_keywords)
            query_parts.append(" AND ".join(self._field_term("ti", t) for t in terms))

        return " AND ".join([f"({p})" for p in query_parts])

    def search(
        self,
        query: str,
        max_results: int = 10,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> List[Dict[str, Any]]:
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
            "sortOrder": sort_order,
        }

        url = self.BASE_URL + urllib.parse.urlencode(params)
        self._log(f"Requesting: {url}")

        # Respectful rate limiting
        time.sleep(0.5)

        # HTTP errors (e.g. 429 rate limiting) propagate instead of silently
        # producing an empty result list.
        response = urllib.request.urlopen(url, timeout=60).read()
        feed = feedparser.parse(response)

        papers = []
        for entry in feed.entries:
            paper = {
                "id": entry.id.split("/abs/")[-1],
                "url": entry.id,
                "title": " ".join(entry.title.split()),
                "authors": [author.name for author in entry.authors],
                "summary": entry.summary.replace("\n", " ").strip(),
                "published": entry.published,
                "updated": entry.updated,
                "categories": [tag.term for tag in entry.tags],
                "doi": entry.get("arxiv_doi", None),
                "journal_ref": entry.get("arxiv_journal_ref", None),
                "primary_category": entry.arxiv_primary_category["term"]
                if hasattr(entry, "arxiv_primary_category")
                else None,
            }
            papers.append(paper)

        self._log(f"Found {len(papers)} papers")
        return papers


def main():
    parser = argparse.ArgumentParser(description="Search ArXiv for research papers.")
    parser.add_argument(
        "query",
        nargs="?",
        help="Keywords searched in all fields; all words must match, "
        '"double-quoted phrases" must match verbatim',
    )
    parser.add_argument(
        "--authors",
        nargs="+",
        help='Author names, each matched as one phrase (e.g. "Gabor Csanyi"); all must match',
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        help="Filter by categories (e.g. mtrl-sci, ml); any may match",
    )
    parser.add_argument(
        "--title",
        nargs="+",
        help="Keywords searched in titles, with the same rules as the query",
    )
    parser.add_argument(
        "--max_results", type=int, default=10, help="Maximum number of results"
    )
    parser.add_argument("--output", help="Path to save results in JSON format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    searcher = ArXivSearcher(verbose=args.verbose)

    search_query = searcher.build_query(
        keywords=[args.query] if args.query else None,
        authors=args.authors,
        categories=args.categories,
        title_keywords=args.title,
    )
    searcher._log(f"search_query: {search_query}")

    if not search_query:
        print("Error: No search criteria provided.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    results = searcher.search(search_query, max_results=args.max_results)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(results)} results to {args.output}")
    else:
        # Print a summary to console
        for i, paper in enumerate(results, 1):
            print(f"\n[{i}] {paper['title']}")
            print(
                f"    Authors: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}"
            )
            print(f"    ID: {paper['id']} | Published: {paper['published']}")
            print(f"    URL: {paper['url']}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs

    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
