"""
Unified MOF database query tool supporting QMOF and ARC-MOF (DB7/Majumdar subset).

Supported databases:
  qmof            - Quantum MOF database (~20,000 DFT-relaxed structures) via MPContribs
  arcmof-majumdar - ARC-MOF DB7 subset (12,316 hypothetical MOFs, Majumdar et al. 2021)
                    via Zenodo (DOI: 10.5281/zenodo.6908727)

Usage:
    python query_mof_db.py --database qmof --formula Zn --max-results 10 --output-dir ./results
    python query_mof_db.py --database arcmof-majumdar --elements Zn,O,C --max-results 20 --output-dir ./results
    python query_mof_db.py --database arcmof-majumdar --identifier MOFID-12345 --output-dir ./results

Requirements:
    - Conda environment: base-agent
    - Required packages: requests, pandas, pymatgen, mpcontribs-client
    - MP_API_KEY environment variable (for qmof only)
"""

import argparse
import io
import json
import os
import sys
import tarfile
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARCMOF_ZENODO_RECORD = "6908727"
ARCMOF_ZENODO_API = f"https://zenodo.org/api/records/{ARCMOF_ZENODO_RECORD}"

# File basenames on Zenodo (confirmed from API listing)
ARCMOF_GEOM_CSV_NAME = "geometric_properties.csv"
ARCMOF_STRUCTURES_NAME = "ARCMOF_20241004.tar.gz"

# Materials Cloud Archive — Majumdar et al. 2021 original data (149 MB, much smaller)
# Used as the primary CIF source for arcmof-majumdar queries.
MAJUMDAR_MATERIALS_CLOUD_URL = "https://archive.materialscloud.org/api/records/et2ts-zxh44/files/mof_data.tar.gz/content"
MAJUMDAR_TARBALL_CACHE_NAME = "majumdar_mof_data.tar.gz"

# Local cache directory — shared across runs to avoid repeated downloads
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "arcmof"

# DB7 (Majumdar et al.) structure filename prefix in ARC-MOF
ARCMOF_DB7_PREFIX = "DB7-"
ARCMOF_DB7_SOURCE_LABELS = {"DB7", "Majumdar", "majumdar"}


# ---------------------------------------------------------------------------
# QMOF query (via MPContribs)
# ---------------------------------------------------------------------------

def query_qmof(formula: str | None, identifier: str | None, max_results: int, output_dir: Path) -> list[str]:
    """
    Query the QMOF database on Materials Project via MPContribs.

    Args:
        formula: Element filter string (e.g., "Zn,O,C").
        identifier: CSD refcode or MOF name (e.g., "KAXQIL").
        max_results: Maximum number of structures to download.
        output_dir: Directory to save downloaded CIF files.

    Returns:
        List of saved CIF file paths.
    """
    try:
        from mpcontribs.client import Client
    except ImportError:
        print("Error: mpcontribs-client is not installed. Run: pip install mpcontribs-client")
        sys.exit(1)

    api_key = os.environ.get("MP_API_KEY")
    if not api_key:
        print("Error: MP_API_KEY environment variable is not set.")
        sys.exit(1)

    print("Initializing MPContribs client for QMOF...")
    client = Client(api_key, project="qmof")

    query: dict = {}
    if formula:
        query["formula__contains"] = formula
    if identifier:
        query["identifier__contains"] = identifier

    print(f"Querying QMOF with: {query or '(no filter — returning first results)'}")
    try:
        results = client.contributions.queryContributions(
            project="qmof",
            _fields=["id", "identifier", "formula", "structures"],
            _limit=max_results,
            **query,
        ).result()
    except Exception as e:
        print(f"Failed to query MPContribs: {e}")
        sys.exit(1)

    if not results or "data" not in results or len(results["data"]) == 0:
        print("No matching MOFs found in QMOF database.")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    print(f"Found {len(results['data'])} MOFs. Downloading CIFs to {output_dir}...")

    for contrib in results["data"]:
        contrib_id = contrib["id"]
        identifier_name = contrib["identifier"]
        formula_name = contrib["formula"]
        print(f"  {identifier_name} ({formula_name})")

        if "structures" not in contrib or not contrib["structures"]:
            print(f"    No structures available for {identifier_name}.")
            continue

        structure_id = contrib["structures"][0]["id"]
        try:
            structure_data = client.structures.getStructureById(
                pk=structure_id,
                _fields=["cif"],
            ).result()
            cif_string = structure_data.get("cif")
            if cif_string:
                filepath = output_dir / f"{identifier_name}.cif"
                filepath.write_text(cif_string)
                saved.append(str(filepath))
                print(f"    Saved: {filepath}")
            else:
                print(f"    No CIF data for {identifier_name}.")
        except Exception as e:
            print(f"    Error downloading {identifier_name}: {e}")

    return saved


# ---------------------------------------------------------------------------
# ARC-MOF DB7 (Majumdar et al.) query via Zenodo
# ---------------------------------------------------------------------------

def _get_zenodo_file_url(filename: str) -> str:
    """
    Fetch the download URL for a specific file from the ARC-MOF Zenodo record
    via the Zenodo REST API. This handles version redirects automatically.
    """
    print(f"Resolving Zenodo download URL for '{filename}' ...")
    resp = requests.get(ARCMOF_ZENODO_API, timeout=30)
    resp.raise_for_status()
    record = resp.json()
    for f in record.get("files", []):
        if f.get("key") == filename:
            url = f["links"]["self"]
            print(f"  Resolved: {url}")
            return url
    raise FileNotFoundError(
        f"'{filename}' not found in Zenodo record {ARCMOF_ZENODO_RECORD}. "
        f"Available files: {[f['key'] for f in record.get('files', [])]}"
    )


def _download_arcmof_metadata(cache_dir: Path) -> pd.DataFrame:
    """
    Download and cache geometric_properties.csv from ARC-MOF Zenodo record.
    Returns a DataFrame with all entries.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_cache = cache_dir / ARCMOF_GEOM_CSV_NAME

    if csv_cache.exists():
        print(f"Using cached metadata: {csv_cache}")
    else:
        url = _get_zenodo_file_url(ARCMOF_GEOM_CSV_NAME)
        print(f"Downloading ARC-MOF metadata CSV (~110 MB) to {csv_cache} ...")
        print("(This is a one-time download; subsequent runs use the cache.)")
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(csv_cache, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):  # 1 MB chunks
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = 100 * downloaded / total
                        print(f"\r  {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({pct:.0f}%)", end="", flush=True)
        print()
        print("Metadata download complete.")

    df = pd.read_csv(csv_cache, low_memory=False)
    return df


def _identify_db7_source_column(df: pd.DataFrame) -> str | None:
    """
    Detect the column in the ARC-MOF CSV that identifies the source database.
    Returns the column name or None if not found.
    """
    # Common column names used in ARC-MOF papers
    for candidate in ["source_db", "source", "database", "db", "origin", "Source_DB", "Database"]:
        if candidate in df.columns:
            return candidate
    return None


def _filter_db7(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter the metadata DataFrame for DB7 (Majumdar et al.) structures.
    Primary strategy: match the 'DB7-' filename prefix in the identifier column.
    Fallback: match a source_db column if present.
    """
    id_col = _detect_id_column(df)

    # Primary: filename prefix "DB7-" (confirmed naming convention in ARC-MOF)
    if id_col:
        mask = df[id_col].astype(str).str.startswith(ARCMOF_DB7_PREFIX)
        db7 = df[mask].copy()
        if not db7.empty:
            print(f"Found {len(db7)} DB7 (Majumdar) entries via prefix '{ARCMOF_DB7_PREFIX}' in column '{id_col}'.")
            return db7

    # Fallback: source database column
    source_col = _identify_db7_source_column(df)
    if source_col:
        mask = df[source_col].astype(str).str.strip().isin(ARCMOF_DB7_SOURCE_LABELS)
        db7 = df[mask].copy()
        if not db7.empty:
            print(f"Found {len(db7)} DB7 (Majumdar) entries via column '{source_col}'.")
            return db7

    print("Warning: Could not identify DB7 structures. Inspect CSV columns:")
    print(list(df.columns[:20]))
    if id_col:
        print(f"Sample values in '{id_col}':", df[id_col].head(5).tolist())
    sys.exit(1)


def _detect_id_column(df: pd.DataFrame) -> str | None:
    """Find the column that holds MOF structure identifiers."""
    for candidate in ["MOFid", "mofid", "name", "id", "structure_id", "filename", "ID"]:
        if candidate in df.columns:
            return candidate
    # Fall back to first column
    return df.columns[0] if len(df.columns) > 0 else None


def _filter_by_elements(df: pd.DataFrame, elements: list[str], id_col: str) -> pd.DataFrame:
    """
    Filter structures to those containing ALL specified elements.
    Uses the identifier string or a formula column if available.
    """
    if not elements:
        return df

    formula_col = None
    for candidate in ["formula", "chemical_formula", "Formula"]:
        if candidate in df.columns:
            formula_col = candidate
            break

    if formula_col:
        mask = pd.Series([True] * len(df), index=df.index)
        for el in elements:
            mask &= df[formula_col].astype(str).str.contains(el, regex=False)
        result = df[mask]
        print(f"After element filter {elements}: {len(result)} structures.")
        return result
    else:
        print(f"Warning: no formula column found; cannot filter by elements {elements}. Returning all DB7 entries.")
        return df


def _elements_from_cif_bytes(cif_bytes: bytes) -> set[str]:
    """
    Extract element symbols from CIF file content by parsing the
    _atom_site_type_symbol loop. Falls back to _atom_site_label parsing.
    This avoids a full pymatgen CifParser call for speed.
    """
    import re
    text = cif_bytes.decode("utf-8", errors="ignore")

    # Look for _atom_site_type_symbol values (most reliable)
    symbols = re.findall(r"_atom_site_type_symbol\s+([\s\S]+?)(?=_atom_site|\Z)", text)
    if symbols:
        raw = symbols[0].split()
        elements = {re.sub(r"[^A-Za-z]", "", s).capitalize() for s in raw if s and not s.startswith("_")}
        elements = {e for e in elements if e.isalpha() and len(e) <= 2}
        if elements:
            return elements

    # Fallback: _atom_site_label (strip trailing digits/signs)
    labels = re.findall(r"^\s*([A-Z][a-z]?\d*[+-]?)\s", text, re.MULTILINE)
    elements = {re.sub(r"[^A-Za-z]", "", l).capitalize() for l in labels}
    return {e for e in elements if e.isalpha() and 1 <= len(e) <= 2}


def _download_majumdar_tarball(cache_dir: Path) -> Path:
    """
    Download and cache the Majumdar et al. mof_data.tar.gz from Materials Cloud
    (149 MB, one-time). Returns the path to the cached tarball.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    tarball_path = cache_dir / MAJUMDAR_TARBALL_CACHE_NAME

    if tarball_path.exists():
        print(f"Using cached Majumdar tarball: {tarball_path}")
        return tarball_path

    print(f"Downloading Majumdar et al. CIF archive (~149 MB) from Materials Cloud ...")
    print("(One-time download; subsequent runs use the cache.)")
    with requests.get(MAJUMDAR_MATERIALS_CLOUD_URL, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(tarball_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = 100 * downloaded / total
                    print(f"\r  {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({pct:.0f}%)", end="", flush=True)
    print()
    print("Majumdar tarball download complete.")
    return tarball_path


def _load_majumdar_metadata(tarball_path: Path) -> pd.DataFrame:
    """
    Extract mof_data.csv from the Majumdar tarball.
    Contains MOF_name, metal_node, topology, and precomputed CO2/H2 adsorption properties.
    """
    with tarfile.open(tarball_path, "r:gz") as tar:
        f = tar.extractfile("mof_data/mof_data.csv")
        df = pd.read_csv(f)
    return df


def _extract_majumdar_cifs(
    output_dir: Path,
    cache_dir: Path,
    max_results: int,
    metals: list[str],
    identifier: str | None,
) -> list[str]:
    """
    Extract CIFs from the Majumdar et al. Materials Cloud tarball.

    Tarball structure:
      majumdar_mof_data.tar.gz
        mof_data/mof_data.csv           ← metadata + CO2 properties
        mof_data/mof_structures.tar     ← nested uncompressed tar with CIFs
          ddmof_cifs/ddmof_XXXXX.cif

    Workflow:
      1. Download and cache the tarball (one-time, ~149 MB).
      2. Optionally filter by identifier substring.
      3. Stream through the nested mof_structures.tar, parsing element symbols
         from _atom_site_type_symbol in each CIF to apply metal filter.
      4. Save matching CIFs and write metadata CSV for the downloaded subset.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Skip already-downloaded CIFs in the output dir
    existing = [str(p) for p in output_dir.glob("*.cif")]
    if len(existing) >= max_results:
        print(f"{len(existing)} CIFs already present (>= max_results={max_results}); skipping.")
        return existing[:max_results]

    tarball_path = _download_majumdar_tarball(cache_dir)

    # Load metadata CSV for output summary
    print("Loading mof_data.csv metadata ...")
    meta_df = _load_majumdar_metadata(tarball_path)
    meta_df["MOF_name"] = meta_df["MOF_name"].str.replace(".cif", "", regex=False)

    required_metals = {m.capitalize() for m in metals}
    saved_paths = list(existing)
    saved_stems: set[str] = {Path(p).stem for p in existing}
    saved_meta_rows: list[dict] = []

    print(f"Extracting CIFs from nested mof_structures.tar ...")
    if required_metals:
        print(f"  Metal filter (at least one required): {sorted(required_metals)}")
    if identifier:
        print(f"  Identifier filter: '{identifier}'")

    checked = 0
    with tarfile.open(tarball_path, "r:gz") as outer:
        inner_f = outer.extractfile("mof_data/mof_structures.tar")
        with tarfile.open(fileobj=inner_f, mode="r:") as inner:
            for member in inner:
                if not member.isfile() or not member.name.endswith(".cif"):
                    continue

                stem = Path(member.name).stem
                if stem in saved_stems:
                    continue

                # Identifier filter
                if identifier and identifier.lower() not in stem.lower():
                    continue

                f = inner.extractfile(member)
                if f is None:
                    continue

                cif_bytes = f.read()
                checked += 1

                # Metal element filter — parsed from CIF _atom_site_type_symbol
                if required_metals:
                    found = _elements_from_cif_bytes(cif_bytes)
                    # Require at least one of the requested metals to be present
                    if not required_metals.intersection(found):
                        continue

                out_path = output_dir / f"{stem}.cif"
                out_path.write_bytes(cif_bytes)
                saved_paths.append(str(out_path))
                saved_stems.add(stem)

                # Collect metadata row
                row = meta_df[meta_df["MOF_name"] == stem]
                if not row.empty:
                    saved_meta_rows.append(row.iloc[0].to_dict())

                print(f"  [{len(saved_paths)}] {stem}.cif")
                if len(saved_paths) >= max_results:
                    break

    print(f"Done. Checked {checked} CIFs, saved {len(saved_paths)} to {output_dir}.")

    # Save metadata summary for the downloaded subset
    if saved_meta_rows:
        meta_out = output_dir / "majumdar_metadata.csv"
        pd.DataFrame(saved_meta_rows).to_csv(meta_out, index=False)
        print(f"Metadata (incl. CO2 uptake, selectivity) saved: {meta_out}")

    if len(saved_paths) < max_results and not identifier:
        print(f"Note: only {len(saved_paths)} CIFs matched the filter across all {checked} checked.")

    return saved_paths[:max_results]


class _StreamWrapper(io.RawIOBase):
    """Wraps a requests streaming response as a readable file-like object for tarfile."""

    def __init__(self, response: requests.Response):
        self._iter = response.iter_content(chunk_size=1 << 16)  # 64 KB
        self._buf = b""

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            return b"".join(self._iter)
        while len(self._buf) < n:
            try:
                self._buf += next(self._iter)
            except StopIteration:
                break
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def readable(self) -> bool:
        return True


def query_arcmof_majumdar(
    elements: list[str],
    identifier: str | None,
    max_results: int,
    output_dir: Path,
    cache_dir: Path,
) -> list[str]:
    """
    Query the ARC-MOF DB7 (Majumdar et al. 2021) subset.

    Workflow:
      1. Download mof_data.tar.gz from Materials Cloud (149 MB, cached after first run).
      2. Stream through CIFs, filtering by element composition on-the-fly from CIF content.
      3. Optionally also download geometric_properties.csv from Zenodo for metadata.

    CIF source: Materials Cloud Archive record 2021.126 (original Majumdar data, 12,316 structures).
    Element filtering: parsed from _atom_site_type_symbol in each CIF — no formula CSV needed.

    Args:
        elements: List of required elements (e.g., ["Zn", "O", "C"]).
        identifier: Specific structure name/ID substring to retrieve.
        max_results: Maximum number of CIFs to download.
        output_dir: Directory to save CIF files.
        cache_dir: Local cache directory for downloaded archives.

    Returns:
        List of saved CIF file paths.
    """
    return _extract_majumdar_cifs(
        output_dir=output_dir,
        cache_dir=cache_dir,
        max_results=max_results,
        metals=elements,
        identifier=identifier,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Query MOF databases (QMOF or ARC-MOF DB7/Majumdar) and download CIF structures.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 10 Zn-containing MOFs from QMOF
  python query_mof_db.py --database qmof --formula Zn --max-results 10 --output-dir ./results/qmof

  # 20 Zn,O,C MOFs from ARC-MOF DB7 (Majumdar subset)
  python query_mof_db.py --database arcmof-majumdar --elements Zn,O,C --max-results 20 --output-dir ./results/arcmof

  # Specific structure by identifier from ARC-MOF DB7
  python query_mof_db.py --database arcmof-majumdar --identifier DB7_00042 --output-dir ./results/arcmof
        """,
    )
    parser.add_argument(
        "--database",
        type=str,
        choices=["qmof", "arcmof-majumdar"],
        required=True,
        help="Which MOF database to query.",
    )
    parser.add_argument(
        "--formula",
        type=str,
        default=None,
        help="[QMOF only] Element/formula filter string (e.g., 'Zn' or 'Zn,O,C').",
    )
    parser.add_argument(
        "--elements",
        type=str,
        default=None,
        help="[arcmof-majumdar] Comma-separated metal elements to filter by (e.g., 'Zn', 'Ni', 'Mg', or 'Zn,Ni'). "
             "Structures containing AT LEAST ONE of the listed metals are returned. "
             "Parsed from _atom_site_type_symbol in each CIF. "
             "Add more metals to broaden diversity (e.g., 'Zn,Ni,Mg,Cu,Fe').",
    )
    parser.add_argument(
        "--identifier",
        type=str,
        default=None,
        help="Specific structure name or ID substring to retrieve (e.g., 'KAXQIL' for QMOF, "
             "'DB7_00042' for ARC-MOF).",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum number of CIF structures to download (default: 10).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./mof_results",
        help="Directory to save downloaded CIF files (default: ./mof_results).",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=str(DEFAULT_CACHE_DIR),
        help=f"Local cache directory for ARC-MOF metadata (default: {DEFAULT_CACHE_DIR}).",
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    cache_dir = Path(args.cache_dir)

    if args.database == "qmof":
        saved = query_qmof(
            formula=args.formula,
            identifier=args.identifier,
            max_results=args.max_results,
            output_dir=output_dir,
        )

    elif args.database == "arcmof-majumdar":
        elements = [e.strip() for e in args.elements.split(",")] if args.elements else []
        saved = query_arcmof_majumdar(
            elements=elements,
            identifier=args.identifier,
            max_results=args.max_results,
            output_dir=output_dir,
            cache_dir=cache_dir,
        )

    print(f"\nDone. {len(saved)} CIF(s) saved to {output_dir}.")
    for p in saved:
        print(f"  {p}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
