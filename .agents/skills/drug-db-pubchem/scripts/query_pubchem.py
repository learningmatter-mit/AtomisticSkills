"""
PubChem Database Query Tool (PUG-REST)

Search and retrieve compound information from PubChem via the PUG-REST API.
Supports lookup by:
  - name (synonym search, complete or word match)
  - SMILES (POST-backed to avoid URL syntax issues)
  - InChI (POST-backed)
  - InChIKey
  - CID
  - molecular formula (fastformula)

Retrieves:
  - computed properties (batch)
  - optional synonyms (batch)
  - optional SDF downloads (2D or 3D record)

Usage:
    python .agents/skills/db-pubchem/scripts/query_pubchem.py --name "aspirin" --output aspirin.json
    python .agents/skills/db-pubchem/scripts/query_pubchem.py --smiles "CC(=O)Oc1ccccc1C(=O)O" --output aspirin.json
    python .agents/skills/db-pubchem/scripts/query_pubchem.py --cid 2244 --output cid_2244.json
    python .agents/skills/db-pubchem/scripts/query_pubchem.py --formula "C9H8O4" --max_results 10 --output formula.json
    python .agents/skills/db-pubchem/scripts/query_pubchem.py --name "ibuprofen" --download_sdf --outdir out --output ibuprofen.json

Requirements:
    - Conda environment: base-agent
    - Required packages: standard library only (urllib, json, argparse, etc.)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

DEFAULT_PROPERTIES = [
    "MolecularFormula",
    "MolecularWeight",
    "ExactMass",
    "XLogP",
    "TPSA",
    "HBondDonorCount",
    "HBondAcceptorCount",
    "RotatableBondCount",
    "InChI",
    "InChIKey",
    "CanonicalSMILES",
    "IsomericSMILES",
    "IUPACName",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chunked(items: List[int], chunk_size: int) -> List[List[int]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _worst_throttle_status(x_throttling_control: Optional[str]) -> Optional[str]:
    """Extract worst throttle status from PubChem's X-Throttling-Control header."""
    if not x_throttling_control:
        return None
    s = x_throttling_control.lower()
    for level in ("black", "red", "yellow", "green"):
        if level in s:
            return level
    return None


class RateLimiter:
    """Sliding-window rate limiter with adaptive delay from throttle feedback."""

    def __init__(self, max_rps: int = 5, max_rpm: int = 400) -> None:
        self.max_rps = max_rps
        self.max_rpm = max_rpm
        self.extra_delay: float = 0.0
        self._last_second: Deque[float] = deque()
        self._last_minute: Deque[float] = deque()
        self._last_request_time: Optional[float] = None

    def wait_for_slot(self) -> None:
        now = time.monotonic()

        if self._last_request_time is not None and self.extra_delay > 0:
            dt = now - self._last_request_time
            if dt < self.extra_delay:
                time.sleep(self.extra_delay - dt)
                now = time.monotonic()

        while self._last_second and (now - self._last_second[0]) >= 1.0:
            self._last_second.popleft()
        while self._last_minute and (now - self._last_minute[0]) >= 60.0:
            self._last_minute.popleft()

        sleep_for = 0.0
        if len(self._last_second) >= self.max_rps and self._last_second:
            sleep_for = max(sleep_for, 1.0 - (now - self._last_second[0]))
        if len(self._last_minute) >= self.max_rpm and self._last_minute:
            sleep_for = max(sleep_for, 60.0 - (now - self._last_minute[0]))

        if sleep_for > 0:
            time.sleep(sleep_for)
            now = time.monotonic()

        self._last_second.append(now)
        self._last_minute.append(now)
        self._last_request_time = now


class PubChemClient:
    """HTTP client for PubChem PUG-REST with rate limiting, retry, and throttle adaptation."""

    def __init__(
        self,
        timeout_s: float = 30.0,
        max_retries: int = 4,
        backoff_base_s: float = 0.5,
        user_agent: str = "AtomisticSkills-db-pubchem/1.0",
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.user_agent = user_agent
        self.rate_limiter = rate_limiter or RateLimiter()

    def _request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, str]] = None,
        accept: str = "application/json",
    ) -> Tuple[int, Dict[str, str], bytes]:
        """Make an HTTP request with throttling + retry/backoff on 503."""
        encoded_data = None
        headers = {
            "Accept": accept,
            "User-Agent": self.user_agent,
        }

        if data is not None:
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            self.rate_limiter.wait_for_slot()

            req = urllib.request.Request(
                url,
                data=encoded_data,
                headers=headers,
                method=method.upper(),
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    status = resp.getcode()
                    resp_headers = {k: v for k, v in resp.headers.items()}
                    body = resp.read()

                self._apply_throttle_feedback(resp_headers.get("X-Throttling-Control"))
                return status, resp_headers, body

            except urllib.error.HTTPError as e:
                status = int(getattr(e, "code", 0) or 0)
                resp_headers = {
                    k: v for k, v in (e.headers.items() if e.headers else [])
                }
                self._apply_throttle_feedback(
                    resp_headers.get("X-Throttling-Control")
                )

                if status == 503 and attempt < self.max_retries:
                    sleep_s = self._compute_backoff(resp_headers, attempt)
                    time.sleep(sleep_s)
                    last_error = e
                    continue

                raise

            except urllib.error.URLError as e:
                if attempt < self.max_retries:
                    sleep_s = self._compute_backoff({}, attempt)
                    time.sleep(sleep_s)
                    last_error = e
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError("Unexpected request failure without an exception.")

    def _compute_backoff(self, headers: Dict[str, str], attempt: int) -> float:
        retry_after = headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return self.backoff_base_s * (2**attempt) + random.uniform(
            0.0, self.backoff_base_s
        )

    def _apply_throttle_feedback(
        self, x_throttling_control: Optional[str]
    ) -> None:
        status = _worst_throttle_status(x_throttling_control)
        if status == "yellow":
            self.rate_limiter.extra_delay = max(
                self.rate_limiter.extra_delay, 0.2
            )
        elif status == "red":
            self.rate_limiter.extra_delay = max(
                self.rate_limiter.extra_delay, 1.0
            )
        elif status == "black":
            self.rate_limiter.extra_delay = max(
                self.rate_limiter.extra_delay, 3.0
            )
        elif status == "green":
            self.rate_limiter.extra_delay = max(
                0.0, self.rate_limiter.extra_delay - 0.1
            )

    def get_json(self, url: str) -> Tuple[Dict[str, Any], Dict[str, str]]:
        status, headers, body = self._request(
            "GET", url, data=None, accept="application/json"
        )
        return json.loads(body.decode("utf-8")), headers

    def post_json(
        self, url: str, data: Dict[str, str]
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        status, headers, body = self._request(
            "POST", url, data=data, accept="application/json"
        )
        return json.loads(body.decode("utf-8")), headers

    # ---- Search methods ----

    def search_by_name(
        self, name: str, name_type: str = "complete"
    ) -> List[int]:
        encoded = urllib.parse.quote(name, safe="")
        nt = urllib.parse.quote(name_type, safe="")
        url = f"{BASE_URL}/compound/name/{encoded}/cids/JSON?name_type={nt}"
        try:
            data, _ = self.get_json(url)
            return list(data.get("IdentifierList", {}).get("CID", []))
        except urllib.error.HTTPError as e:
            if getattr(e, "code", None) == 404:
                return []
            raise

    def search_by_inchikey(self, inchikey: str) -> List[int]:
        encoded = urllib.parse.quote(inchikey, safe="")
        url = f"{BASE_URL}/compound/inchikey/{encoded}/cids/JSON"
        try:
            data, _ = self.get_json(url)
            return list(data.get("IdentifierList", {}).get("CID", []))
        except urllib.error.HTTPError as e:
            if getattr(e, "code", None) == 404:
                return []
            raise

    def search_by_smiles(self, smiles: str) -> List[int]:
        url = f"{BASE_URL}/compound/smiles/cids/JSON"
        try:
            data, _ = self.post_json(url, {"smiles": smiles})
            return list(data.get("IdentifierList", {}).get("CID", []))
        except urllib.error.HTTPError as e:
            if getattr(e, "code", None) == 404:
                return []
            raise

    def search_by_inchi(self, inchi: str) -> List[int]:
        url = f"{BASE_URL}/compound/inchi/cids/JSON"
        try:
            data, _ = self.post_json(url, {"inchi": inchi})
            return list(data.get("IdentifierList", {}).get("CID", []))
        except urllib.error.HTTPError as e:
            if getattr(e, "code", None) == 404:
                return []
            raise

    def search_by_formula(
        self, formula: str, allow_other_elements: bool = False
    ) -> List[int]:
        encoded = urllib.parse.quote(formula, safe="")
        url = f"{BASE_URL}/compound/fastformula/{encoded}/cids/JSON"
        if allow_other_elements:
            url += "?AllowOtherElements=true"
        try:
            data, _ = self.get_json(url)
            return list(data.get("IdentifierList", {}).get("CID", []))
        except urllib.error.HTTPError as e:
            if getattr(e, "code", None) == 404:
                return []
            raise

    # ---- Retrieval methods ----

    def get_properties(
        self, cids: List[int], properties: List[str]
    ) -> List[Dict[str, Any]]:
        if not cids:
            return []
        cid_str = ",".join(str(c) for c in cids)
        prop_str = ",".join(properties)
        url = f"{BASE_URL}/compound/cid/{cid_str}/property/{prop_str}/JSON"
        data, _ = self.get_json(url)
        return list(data.get("PropertyTable", {}).get("Properties", []))

    def get_synonyms_batch(
        self, cids: List[int], max_synonyms: int = 10
    ) -> Dict[int, List[str]]:
        """Retrieve synonyms for many CIDs in one batched request."""
        if not cids:
            return {}
        cid_str = ",".join(str(c) for c in cids)
        url = f"{BASE_URL}/compound/cid/{cid_str}/synonyms/JSON"
        try:
            data, _ = self.get_json(url)
        except urllib.error.HTTPError:
            return {}

        info_list = data.get("InformationList", {}).get("Information", [])
        out: Dict[int, List[str]] = {}
        for entry in info_list:
            cid = entry.get("CID")
            syns = entry.get("Synonym", []) or []
            if isinstance(cid, int):
                out[cid] = list(syns[:max_synonyms])
        return out

    def download_sdf_record(
        self,
        cid: int,
        output_path: Path,
        record_type: str = "3d",
        fallback_to_2d: bool = True,
    ) -> Tuple[bool, str]:
        """Download PubChem SDF record for a CID. Falls back to 2D if 3D unavailable."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _try(rt: str) -> bool:
            rt_enc = urllib.parse.quote(rt, safe="")
            url = f"{BASE_URL}/compound/cid/{cid}/record/SDF?record_type={rt_enc}"
            try:
                _, _, body = self._request(
                    "GET", url, data=None, accept="chemical/x-mdl-sdfile"
                )
                if not body:
                    return False
                output_path.write_bytes(body)
                return True
            except urllib.error.HTTPError:
                return False

        rt0 = record_type.lower()
        if _try(rt0):
            return True, rt0

        if fallback_to_2d and rt0 != "2d":
            if _try("2d"):
                return True, "2d"

        return False, rt0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Query PubChem compound database via PUG-REST."
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--name", help="Search by compound name (synonym search).")
    g.add_argument("--smiles", help="Search by SMILES (POST-backed).")
    g.add_argument("--inchi", help="Search by InChI (POST-backed).")
    g.add_argument("--inchikey", help="Search by InChIKey.")
    g.add_argument("--cid", type=int, help="Look up by PubChem CID.")
    g.add_argument(
        "--formula", help="Search by molecular formula (fastformula)."
    )

    p.add_argument(
        "--name_type",
        default="complete",
        help="Name match type: complete or word (default: complete).",
    )
    p.add_argument(
        "--allow_other_elements",
        action="store_true",
        help="Formula search: AllowOtherElements=true.",
    )
    p.add_argument(
        "--max_results",
        type=int,
        default=5,
        help="Maximum number of CIDs to keep (default: 5).",
    )

    p.add_argument(
        "--properties",
        default=",".join(DEFAULT_PROPERTIES),
        help="Comma-separated list of PubChem properties to retrieve.",
    )

    p.add_argument(
        "--no_synonyms",
        action="store_true",
        help="Disable synonym retrieval.",
    )
    p.add_argument(
        "--max_synonyms",
        type=int,
        default=10,
        help="Max synonyms per CID (default: 10).",
    )

    p.add_argument(
        "--download_sdf",
        action="store_true",
        help="Download SDF structure files.",
    )
    p.add_argument(
        "--sdf_record_type",
        default="3d",
        help="SDF record_type: 3d or 2d (default: 3d).",
    )
    p.add_argument(
        "--no_sdf_fallback_2d",
        action="store_true",
        help="Disable 3d->2d SDF fallback.",
    )

    p.add_argument(
        "--outdir", default=".", help="Output directory for JSON + SDF files."
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output JSON filename (relative to --outdir). Default: pubchem_results.json.",
    )

    p.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30).",
    )
    p.add_argument(
        "--max_retries",
        type=int,
        default=4,
        help="Max retries on 503/network errors (default: 4).",
    )
    p.add_argument(
        "--max_rps",
        type=int,
        default=5,
        help="Max requests per second (default: 5).",
    )
    p.add_argument(
        "--max_rpm",
        type=int,
        default=400,
        help="Max requests per minute (default: 400).",
    )
    p.add_argument(
        "--user_agent",
        default="AtomisticSkills-db-pubchem/1.0",
        help="User-Agent header.",
    )

    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable console output.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    if args.output is None:
        output_path = outdir / "pubchem_results.json"
    else:
        op = Path(args.output)
        output_path = op if op.is_absolute() else (outdir / op)

    client = PubChemClient(
        timeout_s=args.timeout,
        max_retries=args.max_retries,
        user_agent=args.user_agent,
        rate_limiter=RateLimiter(max_rps=args.max_rps, max_rpm=args.max_rpm),
    )

    query: Dict[str, Any] = {"timestamp_utc": _utc_now_iso()}

    if args.cid is not None:
        cids = [args.cid]
        query.update({"type": "cid", "value": args.cid})
    elif args.name:
        cids = client.search_by_name(args.name, name_type=args.name_type)
        query.update(
            {"type": "name", "value": args.name, "name_type": args.name_type}
        )
    elif args.smiles:
        cids = client.search_by_smiles(args.smiles)
        query.update({"type": "smiles", "value": args.smiles})
    elif args.inchi:
        cids = client.search_by_inchi(args.inchi)
        query.update({"type": "inchi", "value": args.inchi})
    elif args.inchikey:
        cids = client.search_by_inchikey(args.inchikey)
        query.update({"type": "inchikey", "value": args.inchikey})
    elif args.formula:
        cids = client.search_by_formula(
            args.formula, allow_other_elements=args.allow_other_elements
        )
        query.update(
            {
                "type": "formula",
                "value": args.formula,
                "allow_other_elements": args.allow_other_elements,
            }
        )
    else:
        cids = []
        query.update({"type": "unknown", "value": None})

    cids = cids[: args.max_results]

    if not cids:
        if not args.quiet:
            print("No compounds found.", file=sys.stderr)
        payload = {
            "query": query,
            "cids": [],
            "results": [],
            "note": "No matches found.",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8"
        )
        if not args.quiet:
            print(f"Wrote: {output_path}", file=sys.stderr)
        return

    prop_list = [p.strip() for p in args.properties.split(",") if p.strip()]
    properties = client.get_properties(cids, prop_list)
    props_by_cid: Dict[int, Dict[str, Any]] = {}
    for p in properties:
        cid = p.get("CID")
        if isinstance(cid, int):
            props_by_cid[cid] = p

    synonyms_by_cid: Dict[int, List[str]] = {}
    if not args.no_synonyms:
        synonyms_by_cid = client.get_synonyms_batch(
            cids, max_synonyms=args.max_synonyms
        )

    results: List[Dict[str, Any]] = []
    for cid in cids:
        entry: Dict[str, Any] = {
            "CID": cid,
            "properties": props_by_cid.get(cid, {}),
            "synonyms": synonyms_by_cid.get(cid, []),
        }

        if args.download_sdf:
            sdf_name = f"CID_{cid}_record_{args.sdf_record_type.lower()}.sdf"
            sdf_path = outdir / sdf_name
            ok, used_rt = client.download_sdf_record(
                cid=cid,
                output_path=sdf_path,
                record_type=args.sdf_record_type,
                fallback_to_2d=not args.no_sdf_fallback_2d,
            )
            entry["sdf"] = {
                "requested_record_type": args.sdf_record_type.lower(),
                "used_record_type": used_rt,
                "path": str(sdf_path) if ok else None,
                "success": ok,
            }

        results.append(entry)

    payload = {
        "query": query,
        "cids": cids,
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8"
    )
    if not args.quiet:
        print(f"Wrote: {output_path}", file=sys.stderr)
        print(f"Found {len(cids)} CID(s): {cids}", file=sys.stderr)


if __name__ == "__main__":
    main()
