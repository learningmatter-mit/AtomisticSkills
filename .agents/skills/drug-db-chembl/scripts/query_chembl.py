"""
ChEMBL Database Query Tool (REST API)

This script queries the official ChEMBL web services to retrieve:
- Targets (by free-text query or UniProt accession)
- Molecule records (by ChEMBL ID or InChIKey)
- Bioactivity measurements (by target ChEMBL ID), with common curation filters

Usage examples:
    # Search targets
    python query_chembl.py --target "EGFR" --max_results 20 --output egfr_targets.json

    # Resolve targets by UniProt accession (more precise)
    python query_chembl.py --uniprot "P00533" --target_type "SINGLE PROTEIN" --output egfr_targets_uniprot.json

    # Get activities for a target (IC50 binding, nM, equality, pChEMBL)
    python query_chembl.py --target_id "CHEMBL203" --activity_type "IC50" --assay_type "B" \\
        --standard_units "nM" --standard_relation "=" --require_pchembl --pchembl_min 5 \\
        --max_results 200 --output egfr_ic50.json

    # Get a molecule record
    python query_chembl.py --chembl_id "CHEMBL25" --output aspirin.json

    # Similarity search by SMILES
    python query_chembl.py --smiles "CC(=O)Oc1ccccc1C(=O)O" --smiles_mode similarity --similarity 80 --output sim.json

Requirements:
    - Conda environment: base-agent
    - Required packages: standard library only (urllib, json, csv, argparse)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from urllib.error import HTTPError, URLError


BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
MAX_SERVER_LIMIT = 1000

# pChEMBL is computed for these types when standardized
PCHEMBL_TYPES = {"IC50", "XC50", "EC50", "AC50", "Ki", "Kd", "Potency", "ED50"}


@dataclass(frozen=True)
class HttpConfig:
    timeout: int = 30
    delay: float = 0.3
    retries: int = 3
    backoff: float = 0.8
    user_agent: str = "AtomisticSkills-db-chembl/1.0 (+https://github.com/bowen-bd)"


def _sleep(cfg: HttpConfig) -> None:
    if cfg.delay > 0:
        time.sleep(cfg.delay)


def _api_get_json(url: str, cfg: HttpConfig) -> Dict[str, Any]:
    """Make a GET request and parse JSON with basic retry/backoff for transient errors."""
    headers = {
        "Accept": "application/json",
        "User-Agent": cfg.user_agent,
    }

    attempt = 0
    while True:
        _sleep(cfg)
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except HTTPError as e:
            if e.code in {429, 500, 502, 503, 504} and attempt < cfg.retries:
                wait = cfg.backoff * (2 ** attempt)
                time.sleep(wait)
                attempt += 1
                continue
            raise
        except URLError:
            if attempt < cfg.retries:
                wait = cfg.backoff * (2 ** attempt)
                time.sleep(wait)
                attempt += 1
                continue
            raise


def _build_url(endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    url = BASE_URL + endpoint
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"
    return url


def _clamp_limit(limit: int) -> int:
    if limit <= 0:
        return 20
    return min(limit, MAX_SERVER_LIMIT)


def _paged_get(
    endpoint: str,
    list_key: str,
    params: Dict[str, Any],
    max_results: int,
    cfg: HttpConfig,
) -> List[Dict[str, Any]]:
    """Fetch up to max_results from a paginated ChEMBL endpoint using limit/offset."""
    if max_results <= 0:
        return []

    results: List[Dict[str, Any]] = []

    page_limit = _clamp_limit(int(params.get("limit", 20)))
    offset = int(params.get("offset", 0))

    while len(results) < max_results:
        remaining = max_results - len(results)
        params_page = dict(params)
        params_page["limit"] = _clamp_limit(min(page_limit, remaining))
        params_page["offset"] = offset

        url = _build_url(endpoint, params_page)
        envelope = _api_get_json(url, cfg)

        chunk = envelope.get(list_key, [])
        if not isinstance(chunk, list) or not chunk:
            break

        results.extend(chunk)

        meta = envelope.get("page_meta") or {}
        total_count = meta.get("total_count")
        offset += params_page["limit"]

        if total_count is not None and isinstance(total_count, int) and offset >= total_count:
            break
        if len(chunk) < params_page["limit"]:
            break

    return results[:max_results]


def search_targets(
    query: str,
    max_results: int,
    cfg: HttpConfig,
    target_type: Optional[str] = None,
    organism: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search targets by free-text query using /target/search.json?q=..."""
    params = {"q": query, "limit": _clamp_limit(min(max_results, MAX_SERVER_LIMIT))}
    url = _build_url("/target/search.json", params)
    data = _api_get_json(url, cfg)
    targets = data.get("targets", []) or []

    out: List[Dict[str, Any]] = []
    for t in targets:
        if target_type and t.get("target_type") != target_type:
            continue
        if organism and t.get("organism") != organism:
            continue

        entry = {
            "target_chembl_id": t.get("target_chembl_id"),
            "pref_name": t.get("pref_name"),
            "target_type": t.get("target_type"),
            "organism": t.get("organism"),
            "target_components": [],
        }
        for comp in t.get("target_components", []) or []:
            entry["target_components"].append(
                {
                    "accession": comp.get("accession"),
                    "component_description": comp.get("component_description"),
                }
            )
        out.append(entry)

    return out[:max_results]


def targets_by_uniprot(
    accession: str,
    max_results: int,
    cfg: HttpConfig,
    target_type: Optional[str] = "SINGLE PROTEIN",
) -> List[Dict[str, Any]]:
    """Retrieve targets mapped to a UniProt accession."""
    params: Dict[str, Any] = {
        "target_components__accession": accession,
        "limit": _clamp_limit(min(max_results, MAX_SERVER_LIMIT)),
    }
    if target_type:
        params["target_type"] = target_type

    targets = _paged_get("/target.json", "targets", params, max_results, cfg)
    out: List[Dict[str, Any]] = []
    for t in targets:
        entry = {
            "target_chembl_id": t.get("target_chembl_id"),
            "pref_name": t.get("pref_name"),
            "target_type": t.get("target_type"),
            "organism": t.get("organism"),
            "target_components": [],
        }
        for comp in t.get("target_components", []) or []:
            entry["target_components"].append(
                {
                    "accession": comp.get("accession"),
                    "component_description": comp.get("component_description"),
                }
            )
        out.append(entry)
    return out


def _maybe_compute_pchembl(activity: Dict[str, Any]) -> Optional[float]:
    """
    Compute pChEMBL from standardized fields only under ChEMBL-style conditions:
    - standard_type in PCHEMBL_TYPES
    - standard_relation == '='
    - standard_units == 'nM'
    - standard_value > 0
    - data_validity_comment is null/None OR 'Manually validated'
    """
    try:
        stype = activity.get("standard_type")
        if stype not in PCHEMBL_TYPES:
            return None
        if activity.get("standard_relation") != "=":
            return None
        if activity.get("standard_units") != "nM":
            return None

        val = activity.get("standard_value")
        if val is None:
            return None
        val_f = float(val)
        if val_f <= 0:
            return None

        dvc = activity.get("data_validity_comment")
        if dvc not in (None, "", "Manually validated"):
            return None

        # standard_value is in nM => molar = nM * 1e-9
        # p = -log10(molar) = -log10(val*1e-9) = 9 - log10(val)
        return 9.0 - math.log10(val_f)
    except (ValueError, TypeError):
        return None


def get_activities_for_target(
    target_id: str,
    max_results: int,
    cfg: HttpConfig,
    activity_type: Optional[str] = None,
    assay_type: Optional[str] = None,
    standard_units: Optional[str] = None,
    standard_relation: Optional[str] = None,
    pchembl_min: Optional[float] = None,
    pchembl_max: Optional[float] = None,
    require_pchembl: bool = False,
    compute_pchembl: bool = True,
    extra_params: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve bioactivity data for a target ChEMBL ID from /activity.json."""
    params: Dict[str, Any] = {
        "target_chembl_id": target_id,
        "limit": _clamp_limit(min(max_results, MAX_SERVER_LIMIT)),
    }
    if activity_type:
        params["standard_type"] = activity_type
    if assay_type:
        params["assay_type"] = assay_type
    if standard_units:
        params["standard_units"] = standard_units
    if standard_relation:
        params["standard_relation"] = standard_relation
    if pchembl_min is not None:
        params["pchembl_value__gte"] = str(pchembl_min)
    if pchembl_max is not None:
        params["pchembl_value__lte"] = str(pchembl_max)
    if extra_params:
        params.update(extra_params)

    activities = _paged_get("/activity.json", "activities", params, max_results, cfg)

    out: List[Dict[str, Any]] = []
    for a in activities:
        record: Dict[str, Any] = {
            "molecule_chembl_id": a.get("molecule_chembl_id"),
            "canonical_smiles": a.get("canonical_smiles"),
            "standard_type": a.get("standard_type"),
            "standard_value": a.get("standard_value"),
            "standard_units": a.get("standard_units"),
            "standard_relation": a.get("standard_relation"),
            "pchembl_value": a.get("pchembl_value"),
            "assay_chembl_id": a.get("assay_chembl_id"),
            "assay_type": a.get("assay_type"),
            "assay_description": a.get("assay_description"),
            "document_chembl_id": a.get("document_chembl_id"),
            "data_validity_comment": a.get("data_validity_comment"),
            "activity_comment": a.get("activity_comment"),
            "potential_duplicate": a.get("potential_duplicate"),
        }

        if record["pchembl_value"] is None and compute_pchembl:
            computed = _maybe_compute_pchembl(record)
            if computed is not None:
                record["pchembl_value"] = round(computed, 4)

        if require_pchembl and record.get("pchembl_value") is None:
            continue

        out.append(record)

    return out


def get_molecule(identifier: str, cfg: HttpConfig) -> Optional[Dict[str, Any]]:
    """Retrieve a molecule record by ChEMBL ID or standard InChIKey."""
    url = _build_url(f"/molecule/{urllib.parse.quote(identifier, safe='')}.json")
    try:
        data = _api_get_json(url, cfg)
    except HTTPError as e:
        if e.code == 404:
            return None
        raise

    structs = data.get("molecule_structures") or {}
    props = data.get("molecule_properties") or {}
    return {
        "molecule_chembl_id": data.get("molecule_chembl_id"),
        "pref_name": data.get("pref_name"),
        "molecule_type": data.get("molecule_type"),
        "max_phase": data.get("max_phase"),
        "canonical_smiles": structs.get("canonical_smiles"),
        "standard_inchi": structs.get("standard_inchi"),
        "standard_inchi_key": structs.get("standard_inchi_key"),
        "molecular_weight": props.get("full_mwt"),
        "alogp": props.get("alogp"),
        "hba": props.get("hba"),
        "hbd": props.get("hbd"),
        "psa": props.get("psa"),
        "ro5_violations": props.get("num_ro5_violations"),
        "qed_weighted": props.get("qed_weighted"),
    }


def smiles_search(
    smiles: str,
    mode: str,
    max_results: int,
    cfg: HttpConfig,
    similarity: int = 70,
) -> List[Dict[str, Any]]:
    """
    Chemical search by SMILES using documented ChEMBL endpoints:
    - similarity: /similarity/<smiles>/<cutoff>
    - substructure: /substructure/<smiles>
    - exact: attempt /molecule/<smiles>.json (canonical SMILES lookup)
    """
    enc = urllib.parse.quote(smiles, safe="")

    if mode == "similarity":
        endpoint = f"/similarity/{enc}/{int(similarity)}.json"
        data = _api_get_json(
            _build_url(endpoint, {"limit": _clamp_limit(min(max_results, MAX_SERVER_LIMIT))}), cfg
        )
        molecules = data.get("molecules", []) or []
        return [_format_molecule_summary(m) for m in molecules][:max_results]

    if mode == "substructure":
        endpoint = f"/substructure/{enc}.json"
        data = _api_get_json(
            _build_url(endpoint, {"limit": _clamp_limit(min(max_results, MAX_SERVER_LIMIT))}), cfg
        )
        molecules = data.get("molecules", []) or []
        return [_format_molecule_summary(m) for m in molecules][:max_results]

    # mode == "exact"
    endpoint = f"/molecule/{enc}.json"
    try:
        data = _api_get_json(_build_url(endpoint), cfg)
    except HTTPError:
        return []

    if isinstance(data, dict) and "molecules" in data:
        molecules = data.get("molecules", []) or []
        return [_format_molecule_summary(m) for m in molecules][:max_results]

    return [_format_molecule_summary(data)]


def _format_molecule_summary(m: Dict[str, Any]) -> Dict[str, Any]:
    structs = m.get("molecule_structures") or {}
    props = m.get("molecule_properties") or {}
    return {
        "molecule_chembl_id": m.get("molecule_chembl_id"),
        "pref_name": m.get("pref_name"),
        "molecule_type": m.get("molecule_type"),
        "max_phase": m.get("max_phase"),
        "canonical_smiles": structs.get("canonical_smiles"),
        "standard_inchi_key": structs.get("standard_inchi_key"),
        "molecular_weight": props.get("full_mwt"),
        "alogp": props.get("alogp"),
        "qed_weighted": props.get("qed_weighted"),
    }


def _parse_extra_params(pairs: Optional[List[str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not pairs:
        return out
    for p in pairs:
        if "=" not in p:
            raise ValueError(f"--api_param must be KEY=VALUE, got: {p}")
        k, v = p.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _write_output(
    results: Union[List[Dict[str, Any]], Dict[str, Any]],
    output_path: str,
) -> None:
    if output_path.lower().endswith(".csv"):
        if not isinstance(results, list):
            raise ValueError("CSV output expects a list of dict records.")
        fieldnames: List[str] = sorted({k for r in results for k in r.keys()})
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in results:
                w.writerow(r)
        return

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query ChEMBL targets, molecules, and activities via REST API."
    )
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument("--target", help="Search targets by gene/protein name (free-text search)")
    group.add_argument("--uniprot", help="Find targets by UniProt accession (e.g., P00533 for EGFR)")
    group.add_argument("--target_id", help="Get activities for a ChEMBL target ID (e.g., CHEMBL203)")
    group.add_argument("--chembl_id", help="Look up molecule by ChEMBL molecule ID (e.g., CHEMBL25)")
    group.add_argument("--inchi_key", help="Look up molecule by standard InChIKey (exact identity)")
    group.add_argument("--smiles", help="Chemical search by SMILES (similarity/substructure/exact)")

    parser.add_argument("--max_results", type=int, default=20, help="Maximum number of results to return")
    parser.add_argument("--output", help="Path to save results (.json or .csv). If omitted, prints summary only.")

    parser.add_argument("--delay", type=float, default=0.3, help="Delay (seconds) between requests (API etiquette)")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout (seconds)")
    parser.add_argument("--retries", type=int, default=3, help="Retries for transient errors (429/5xx)")

    parser.add_argument("--target_type", help='Filter target_type (e.g., "SINGLE PROTEIN")')
    parser.add_argument("--organism", help='Filter organism (e.g., "Homo sapiens")')

    parser.add_argument("--activity_type", help="Filter standardized activity type (e.g., IC50, Ki, EC50)")
    parser.add_argument("--assay_type", help="Filter assay type (e.g., B for binding, F for functional)")
    parser.add_argument("--standard_units", help='Filter standard_units (e.g., "nM")')
    parser.add_argument("--standard_relation", help='Filter standard_relation (e.g., "=")')
    parser.add_argument("--pchembl_min", type=float, help="Filter pchembl_value >= this value")
    parser.add_argument("--pchembl_max", type=float, help="Filter pchembl_value <= this value")
    parser.add_argument(
        "--require_pchembl", action="store_true",
        help="Drop records without pchembl_value (or computed pChEMBL)",
    )
    parser.add_argument(
        "--no_compute_pchembl", action="store_true",
        help="Do not compute pChEMBL from standardized fields",
    )
    parser.add_argument(
        "--api_param", action="append",
        help="Extra arbitrary ChEMBL filter(s) as KEY=VALUE, repeatable (advanced).",
    )

    parser.add_argument(
        "--smiles_mode", choices=["similarity", "substructure", "exact"], default="similarity",
        help="SMILES search mode (default: similarity)",
    )
    parser.add_argument("--similarity", type=int, default=70, help="Similarity cutoff for similarity mode (0-100)")

    args = parser.parse_args()
    cfg = HttpConfig(timeout=args.timeout, delay=args.delay, retries=args.retries)

    extra_params = {}
    if args.api_param:
        try:
            extra_params = _parse_extra_params(args.api_param)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)

    results: Union[List[Dict[str, Any]], Dict[str, Any]] = []

    if args.target:
        print(f"Searching targets for query: {args.target}")
        results = search_targets(
            query=args.target,
            max_results=args.max_results,
            cfg=cfg,
            target_type=args.target_type,
            organism=args.organism,
        )

    elif args.uniprot:
        print(f"Searching targets for UniProt accession: {args.uniprot}")
        results = targets_by_uniprot(
            accession=args.uniprot,
            max_results=args.max_results,
            cfg=cfg,
            target_type=args.target_type or "SINGLE PROTEIN",
        )

    elif args.target_id:
        print(f"Retrieving activities for target: {args.target_id}")
        results = get_activities_for_target(
            target_id=args.target_id,
            max_results=args.max_results,
            cfg=cfg,
            activity_type=args.activity_type,
            assay_type=args.assay_type,
            standard_units=args.standard_units,
            standard_relation=args.standard_relation,
            pchembl_min=args.pchembl_min,
            pchembl_max=args.pchembl_max,
            require_pchembl=args.require_pchembl,
            compute_pchembl=not args.no_compute_pchembl,
            extra_params=extra_params,
        )

    elif args.chembl_id:
        print(f"Looking up molecule by ChEMBL ID: {args.chembl_id}")
        mol = get_molecule(args.chembl_id, cfg)
        results = [mol] if mol else []

    elif args.inchi_key:
        print(f"Looking up molecule by InChIKey: {args.inchi_key}")
        mol = get_molecule(args.inchi_key, cfg)
        results = [mol] if mol else []

    elif args.smiles:
        print(f"SMILES search ({args.smiles_mode}) for: {args.smiles}")
        results = smiles_search(
            smiles=args.smiles,
            mode=args.smiles_mode,
            max_results=args.max_results,
            cfg=cfg,
            similarity=args.similarity,
        )

    n = len(results) if isinstance(results, list) else 1
    if isinstance(results, list) and not results:
        print("No results found.")
    else:
        print(f"Retrieved {n} record(s).")

    if args.output:
        _write_output(results, args.output)
        print(f"Saved output to: {args.output}")

        # Save input configs for reproducibility
        from src.utils.config_utils import save_skill_inputs
        save_skill_inputs(args, args.output_dir)
        _params_path.parent.mkdir(parents=True, exist_ok=True)
        _params_path.write_text(json.dumps(_config, indent=2, default=str))


if __name__ == "__main__":
    main()
