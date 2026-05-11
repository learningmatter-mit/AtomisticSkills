"""
Collect docking results into a single ranked CSV.

Reads either a combined docking_results.json produced by run_docking.py
(shape: {meta, results: [...]}) or a directory of per-ligand *_result.json
files (SLURM array style). Joins each result with a library CSV to pull
SMILES and optional label / parent_compound_id columns, ranks by best
affinity (most negative first), and writes a docking_ranked.csv that is
directly consumable by drug-docking-analysis.

Usage:
    # Combined JSON from run_docking.py
    python collect_results.py \
        --results docking/results/docking_results.json \
        --library_csv library/library_master.csv \
        --output_dir docking/analysis/

    # Per-ligand JSON files from a SLURM array
    python collect_results.py \
        --results docking/results/ \
        --library_csv library/library_master.csv \
        --output_dir docking/analysis/

The library CSV must have a `compound_id` column. The following columns
are picked up if present and passed through: `smiles`, `label`,
`parent_compound_id`, `microstate_id`, `pchembl`. Join key is `compound_id`,
which must match the `ligand` field in the docking JSON (this is the
PDBQT filename stem set by drug-ligand-prep).

Requirements:
    - Conda environment: drugdisc-agent (stdlib-only; any env works)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List


PASSTHROUGH_COLS = ("smiles", "label", "parent_compound_id", "microstate_id", "pchembl")


def load_library_metadata(library_csv: Path) -> Dict[str, Dict[str, str]]:
    """Load library CSV into a dict keyed by compound_id, preserving passthrough columns."""
    metadata: Dict[str, Dict[str, str]] = {}
    with open(library_csv) as f:
        reader = csv.DictReader(f)
        if "compound_id" not in (reader.fieldnames or []):
            sys.exit("library_csv must have a 'compound_id' column")
        for row in reader:
            cid = row["compound_id"]
            metadata[cid] = {col: row[col] for col in PASSTHROUGH_COLS if col in row}
    return metadata


def iter_docking_results(results_path: Path) -> Iterable[Dict[str, Any]]:
    """Yield per-ligand result dicts from either a combined JSON or a directory of *_result.json."""
    if results_path.is_file():
        with open(results_path) as f:
            payload = json.load(f)
        if "results" in payload:
            yield from payload["results"]
        else:
            yield payload
        return

    if results_path.is_dir():
        json_files = sorted(results_path.glob("*_result.json"))
        if not json_files:
            sys.exit(f"No *_result.json files found in {results_path}")
        for jf in json_files:
            with open(jf) as f:
                yield json.load(f)
        return

    sys.exit(f"results path does not exist: {results_path}")


def collect(results_path: Path, library_csv: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    library = load_library_metadata(library_csv)

    rows: List[Dict[str, Any]] = []
    missing_in_library: List[str] = []
    n_failed = 0

    for result in iter_docking_results(results_path):
        cid = result.get("ligand")
        if cid is None:
            continue

        if not result.get("success"):
            n_failed += 1
            continue

        best_aff = result.get("best_affinity_kcal_mol")
        if best_aff is None:
            n_failed += 1
            continue

        meta = library.get(cid)
        if meta is None:
            missing_in_library.append(cid)
            meta = {}

        row: Dict[str, Any] = {
            "compound_id": cid,
            "best_affinity": best_aff,
            "n_poses": result.get("n_poses_returned"),
            "runtime_s": result.get("runtime_s"),
        }
        for col in PASSTHROUGH_COLS:
            if col in meta:
                row[col] = meta[col]
        rows.append(row)

    rows.sort(key=lambda r: float(r["best_affinity"]))

    present_passthrough = [
        col for col in PASSTHROUGH_COLS if any(col in r for r in rows)
    ]
    fieldnames = ["rank", "compound_id", "best_affinity"] + present_passthrough + ["n_poses", "runtime_s"]

    csv_path = output_dir / "docking_ranked.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for i, r in enumerate(rows):
            writer.writerow({"rank": i + 1, **r})

    summary: Dict[str, Any] = {
        "n_successful": len(rows),
        "n_failed": n_failed,
        "n_missing_in_library": len(missing_in_library),
        "output_csv": str(csv_path),
        "passthrough_columns": present_passthrough,
    }
    if rows:
        summary["top_10"] = [
            {"rank": i + 1, "compound_id": r["compound_id"], "best_affinity": r["best_affinity"]}
            for i, r in enumerate(rows[:10])
        ]
    if missing_in_library:
        summary["missing_in_library_sample"] = missing_in_library[:10]

    summary_path = output_dir / "docking_collect_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=4)

    print(json.dumps(summary, indent=4))
    print(f"\nWrote: {csv_path}")
    if missing_in_library:
        print(
            f"Warning: {len(missing_in_library)} docking results had no match in library_csv.",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect drug-docking-vina results into a ranked CSV for analysis."
    )
    parser.add_argument(
        "--results",
        required=True,
        type=Path,
        help="Either a combined docking_results.json file or a directory of *_result.json files.",
    )
    parser.add_argument(
        "--library_csv",
        required=True,
        type=Path,
        help="Library CSV with a compound_id column. smiles, label, parent_compound_id, microstate_id, and pchembl are passed through when present.",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        type=Path,
        help="Output directory for docking_ranked.csv and docking_collect_summary.json.",
    )
    args = parser.parse_args()
    collect(args.results, args.library_csv, args.output_dir)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
