"""
RCSB PDB Query Tool
Search and retrieve macromolecular structure metadata from the RCSB Protein Data Bank (PDB),
and optionally download coordinate files and wwPDB validation reports.

Usage:
    python query_pdb.py --search "kinase inhibitor" --max_results 10 --output results.json
    python query_pdb.py --search "ACE2" --organism "Homo sapiens" --resolution 2.5 --method "X-RAY DIFFRACTION"
    python query_pdb.py --pdb_id 1HSG --download mmcif --download_dir ./structures --output 1hsg.json
    python query_pdb.py --pdb_id 1HSG --download_validation --download_dir ./validation --output 1hsg.json

Requirements:
    - Conda environment: base-agent
    - Required packages: Python standard library only (urllib, json, argparse, time, pathlib, typing)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
DATA_CORE = "https://data.rcsb.org/rest/v1/core"
DOWNLOAD_BASE = "https://files.rcsb.org/download"
VALIDATION_BASE = "https://files.rcsb.org/validation/view"

USER_AGENT = "AtomisticSkills-db-pdb/0.2 (github: bowen-bd)"

_LAST_REQUEST_T = 0.0


def _rate_limit(min_interval_s: float) -> None:
    """Ensure at most ~1/min_interval_s requests per second."""
    global _LAST_REQUEST_T
    min_interval_s = max(0.0, float(min_interval_s))
    now = time.time()
    dt = now - _LAST_REQUEST_T
    if dt < min_interval_s:
        time.sleep(min_interval_s - dt)
    _LAST_REQUEST_T = time.time()


def _http(
    url: str,
    *,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout_s: int = 30,
    retries: int = 5,
    min_interval_s: float = 0.25,
) -> bytes:
    """HTTP request with rate limiting and exponential backoff on 429/5xx."""
    headers = dict(headers or {})
    headers.setdefault("User-Agent", USER_AGENT)

    backoff = 0.5
    attempt = 0
    while True:
        _rate_limit(min_interval_s)
        if attempt > 0:
            time.sleep(min(backoff, 10.0))
            backoff *= 2

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            code = int(getattr(e, "code", 0) or 0)
            retriable = code in {429, 500, 502, 503, 504}
            if retriable and attempt < retries:
                attempt += 1
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries:
                attempt += 1
                continue
            raise


def _get_json(url: str, **kwargs: Any) -> Dict[str, Any]:
    raw = _http(url, headers={"Accept": "application/json"}, **kwargs)
    return json.loads(raw.decode("utf-8"))


def _post_json(url: str, payload: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    raw = _http(
        url,
        method="POST",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        **kwargs,
    )
    return json.loads(raw.decode("utf-8"))


def _first_or_none(v: Any) -> Any:
    return v[0] if isinstance(v, list) and v else v


def _parse_methods(method_args: Optional[List[str]]) -> Optional[List[str]]:
    """Parse --method entries (repeatable or comma-separated)."""
    if not method_args:
        return None
    out: List[str] = []
    for m in method_args:
        out.extend([p.strip() for p in m.split(",") if p.strip()])
    return out or None


def search_pdb_ids(
    query: str,
    *,
    organism: Optional[str],
    resolution: Optional[float],
    methods: Optional[List[str]],
    max_results: int,
    **http_kw: Any,
) -> List[Tuple[str, Optional[float]]]:
    """Search RCSB PDB Search API v2 and return [(PDB_ID, score), ...]."""
    nodes: List[Dict[str, Any]] = [
        {"type": "terminal", "service": "full_text", "parameters": {"value": query}}
    ]

    if organism:
        nodes.append(
            {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "rcsb_entity_source_organism.scientific_name",
                    "operator": "exact_match",
                    "value": organism,
                },
            }
        )

    if resolution is not None:
        nodes.append(
            {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "rcsb_entry_info.resolution_combined",
                    "operator": "less_or_equal",
                    "value": float(resolution),
                },
            }
        )

    if methods:
        nodes.append(
            {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "exptl.method",
                    "operator": "in",
                    "value": methods,
                },
            }
        )

    query_node = (
        nodes[0]
        if len(nodes) == 1
        else {"type": "group", "logical_operator": "and", "nodes": nodes}
    )

    payload: Dict[str, Any] = {
        "query": query_node,
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": int(max_results)},
            "sort": [{"sort_by": "score", "direction": "desc"}],
            "results_verbosity": "minimal",
        },
    }

    data = _post_json(SEARCH_URL, payload, **http_kw)
    result_set = data.get("result_set", []) or []

    hits: List[Tuple[str, Optional[float]]] = []
    for r in result_set:
        pid = r.get("identifier")
        if not pid:
            continue
        score = r.get("score")
        hits.append((str(pid).upper(), float(score) if score is not None else None))
    return hits


def get_entry_info(
    pdb_id: str,
    *,
    include_ligands: bool = True,
    **http_kw: Any,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve entry metadata via Data API core/entry/<PDB_ID>.

    Ligands are enumerated from rcsb_entry_container_identifiers.non_polymer_entity_ids,
    then each is queried via core/nonpolymer_entity/<PDB_ID>/<entity_id>.
    """
    entry_id = pdb_id.upper()
    try:
        data = _get_json(f"{DATA_CORE}/entry/{entry_id}", **http_kw)
    except urllib.error.HTTPError as e:
        if int(getattr(e, "code", 0) or 0) == 404:
            return None
        raise

    entry_info = data.get("rcsb_entry_info", {}) or {}
    accession = data.get("rcsb_accession_info", {}) or {}
    struct = data.get("struct", {}) or {}
    exptl = data.get("exptl", []) or []
    container = data.get("rcsb_entry_container_identifiers", {}) or {}

    exp_method = entry_info.get("experimental_method")
    if not exp_method and isinstance(exptl, list) and exptl:
        exp_method = exptl[0].get("method")

    out: Dict[str, Any] = {
        "pdb_id": entry_id,
        "title": struct.get("title", "N/A"),
        "experimental_method": exp_method,
        "resolution": _first_or_none(entry_info.get("resolution_combined")),
        "deposit_date": accession.get("deposit_date"),
        "initial_release_date": accession.get("initial_release_date"),
        "revision_date": accession.get("revision_date"),
        "polymer_entity_count": entry_info.get("polymer_entity_count"),
        "nonpolymer_entity_count": entry_info.get("nonpolymer_entity_count"),
        "assembly_count": entry_info.get("assembly_count"),
    }

    cell = data.get("cell") or {}
    if cell:
        out["unit_cell"] = {
            "a": cell.get("length_a"),
            "b": cell.get("length_b"),
            "c": cell.get("length_c"),
            "alpha": cell.get("angle_alpha"),
            "beta": cell.get("angle_beta"),
            "gamma": cell.get("angle_gamma"),
        }

    if include_ligands:
        lig_entity_ids = container.get("non_polymer_entity_ids") or []
        ligands: List[Dict[str, Any]] = []

        for ent_id in lig_entity_ids:
            try:
                lig = _get_json(f"{DATA_CORE}/nonpolymer_entity/{entry_id}/{ent_id}", **http_kw)
                ent = lig.get("pdbx_entity_nonpoly", {}) or {}
                ligands.append(
                    {
                        "entity_id": ent_id,
                        "comp_id": ent.get("comp_id"),
                        "name": ent.get("name"),
                    }
                )
            except Exception:
                continue

        if ligands:
            out["ligands"] = ligands

    return out


def download_structure(
    pdb_id: str,
    fmt: str,
    download_dir: Path,
    **http_kw: Any,
) -> Optional[Path]:
    """Download coordinate file (PDB or mmCIF)."""
    entry_id = pdb_id.upper()
    download_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "pdb":
        url = f"{DOWNLOAD_BASE}/{entry_id}.pdb"
        out_path = download_dir / f"{entry_id}.pdb"
    elif fmt == "mmcif":
        url = f"{DOWNLOAD_BASE}/{entry_id}.cif"
        out_path = download_dir / f"{entry_id}.cif"
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    try:
        content = _http(url, **http_kw)
    except urllib.error.HTTPError as e:
        if int(getattr(e, "code", 0) or 0) == 404:
            return None
        raise

    out_path.write_bytes(content)
    return out_path


def download_validation_report(
    pdb_id: str,
    download_dir: Path,
    **http_kw: Any,
) -> Optional[Path]:
    """Download wwPDB validation report PDF if available."""
    pid = pdb_id.lower()
    download_dir.mkdir(parents=True, exist_ok=True)

    url = f"{VALIDATION_BASE}/{pid}_full_validation.pdf"
    out_path = download_dir / f"{pid}_full_validation.pdf"

    try:
        content = _http(url, **http_kw)
    except urllib.error.HTTPError as e:
        if int(getattr(e, "code", 0) or 0) == 404:
            return None
        raise

    out_path.write_bytes(content)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the RCSB PDB Search/Data APIs and download files.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", help="Full-text search query (e.g. 'HIV-1 protease').")
    group.add_argument("--pdb_id", help="Look up a specific PDB ID (e.g. 1HSG).")

    parser.add_argument("--organism", help="Filter by source organism scientific name (exact match).")
    parser.add_argument("--resolution", type=float, help="Maximum resolution in Angstroms (<=).")
    parser.add_argument(
        "--method",
        action="append",
        help="Experimental method filter (repeatable or comma-separated), e.g. --method 'X-RAY DIFFRACTION'.",
    )
    parser.add_argument("--max_results", type=int, default=10, help="Maximum number of search hits.")
    parser.add_argument("--ids_only", action="store_true", help="Only return PDB IDs (skip Data API lookups).")
    parser.add_argument("--no_ligands", action="store_true", help="Skip ligand retrieval (fewer API calls).")

    parser.add_argument("--download", choices=["pdb", "mmcif"], help="Download coordinate file format.")
    parser.add_argument("--download_validation", action="store_true", help="Download wwPDB validation report PDF.")
    parser.add_argument("--download_dir", default=".", help="Directory for downloaded files (default: .).")

    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds.")
    parser.add_argument("--min_interval", type=float, default=0.25, help="Minimum seconds between HTTP requests.")
    parser.add_argument("--retries", type=int, default=5, help="Max retries on transient errors (429/5xx).")
    parser.add_argument("--output", help="Write JSON results to this path.")

    args = parser.parse_args()

    http_kw = dict(timeout_s=args.timeout, retries=args.retries, min_interval_s=args.min_interval)

    methods = _parse_methods(args.method)

    payload: Dict[str, Any]
    if args.search:
        hits = search_pdb_ids(
            args.search,
            organism=args.organism,
            resolution=args.resolution,
            methods=methods,
            max_results=args.max_results,
            **http_kw,
        )
        pdb_ids = [pid for pid, _ in hits]

        results: List[Dict[str, Any]] = []
        if not args.ids_only:
            for pid, score in hits:
                info = get_entry_info(pid, include_ligands=not args.no_ligands, **http_kw)
                if info:
                    info["search_score"] = score
                    results.append(info)

        payload = {
            "mode": "search",
            "query": {
                "text": args.search,
                "organism": args.organism,
                "resolution_max": args.resolution,
                "methods": methods,
                "max_results": args.max_results,
            },
            "pdb_ids": pdb_ids,
            "results": results,
        }

    else:
        pid = args.pdb_id.upper()
        info = get_entry_info(pid, include_ligands=not args.no_ligands, **http_kw)

        payload = {"mode": "entry", "pdb_ids": [pid], "results": [info] if info else []}

        dl_dir = Path(args.download_dir)

        if info and args.download:
            p = download_structure(pid, args.download, dl_dir, **http_kw)
            if p:
                payload["results"][0]["downloaded_structure_file"] = str(p)

        if info and args.download_validation:
            p = download_validation_report(pid, dl_dir, **http_kw)
            if p:
                payload["results"][0]["downloaded_validation_report_pdf"] = str(p)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8")

    print(
        json.dumps(
            {"pdb_ids": payload.get("pdb_ids", []), "n_results": len(payload.get("results", []))},
            indent=4,
        )
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
