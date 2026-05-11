"""
Identify and rank ligandable pockets on a protein structure.

Wraps fpocket (default) or P2Rank (optional ML backend) and emits a unified
ranked-pocket JSON containing residues, geometric center, bounding box,
volume (when reported), and a druggability score for each pocket. Does not
perform docking.

Usage:
    python detect_pockets.py \
        --protein receptor.pdb \
        --backend fpocket \
        --output_json pockets.json \
        --top_n 5

    python detect_pockets.py \
        --protein receptor.pdb \
        --backend p2rank \
        --output_json pockets.json

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: numpy, MDAnalysis
    - External CLI tools (one of):
        - fpocket: `conda install -c conda-forge fpocket` (default backend)
        - prank (P2Rank): download from https://github.com/rdk/p2rank/releases,
          unpack, and ensure `prank` is on PATH (optional ML backend).
          Java requirement is version-specific (P2Rank 2.5 needs Java 17+).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any

import numpy as np

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import MDAnalysis as mda
    from MDAnalysis.lib.distances import capped_distance


THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def _check_cli(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(
            f"ERROR: '{name}' not found on PATH. See SKILL.md install notes."
        )
    return path


def _backend_version(name: str) -> str | None:
    """Best-effort backend version string for provenance."""
    path = shutil.which(name)
    if not path:
        return None
    for flag in ("--version", "-v", "-h"):
        try:
            r = subprocess.run([path, flag], capture_output=True, text=True, timeout=10)
        except Exception:
            continue
        text = (r.stdout or "") + (r.stderr or "")
        if name == "fpocket":
            m = re.search(r"fpocket\s*([0-9][0-9.]*)", text, re.IGNORECASE)
        else:
            m = re.search(r"(?:p2rank|prank)\s*([0-9][0-9.]*)", text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _residues_within(
    universe: mda.Universe, query_coords: np.ndarray, cutoff: float
) -> list[dict[str, Any]]:
    """Return unique protein residues with any heavy atom within `cutoff` A of any query coord.

    Uses MDAnalysis' capped_distance (KD-tree-based) to avoid the
    n_atoms * n_points memory blow-up of a brute-force pairwise matrix.
    """
    protein = universe.select_atoms("protein and not name H*")
    if len(protein) == 0 or len(query_coords) == 0:
        return []
    pairs = capped_distance(
        protein.positions.astype(np.float32),
        query_coords.astype(np.float32),
        max_cutoff=cutoff,
        return_distances=False,
    )
    if len(pairs) == 0:
        return []
    near_idx = np.unique(pairs[:, 0])
    near = protein[near_idx]
    seen: dict[tuple, dict[str, Any]] = {}
    for atom in near:
        chain = atom.chainID or atom.segid or ""
        icode = (atom.icode or "").strip()
        key = (chain, atom.resnum, atom.resname, icode)
        if key in seen:
            continue
        seen[key] = {
            "chain": chain,
            "resnum": int(atom.resnum),
            "resname": atom.resname,
            "icode": icode,
            "one_letter": THREE_TO_ONE.get(atom.resname, "X"),
            "label": (
                f"{chain}:{atom.resname}{atom.resnum}{icode}"
                if chain
                else f"{atom.resname}{atom.resnum}{icode}"
            ),
        }
    return sorted(seen.values(), key=lambda r: (r["chain"], r["resnum"], r["icode"]))


def _bounding_box(coords: np.ndarray) -> dict[str, list[float]] | None:
    if len(coords) == 0:
        return None
    mn = coords.min(axis=0)
    mx = coords.max(axis=0)
    return {
        "min": [float(mn[0]), float(mn[1]), float(mn[2])],
        "max": [float(mx[0]), float(mx[1]), float(mx[2])],
    }


# ---------------------------------------------------------------------------
# fpocket
# ---------------------------------------------------------------------------

def _parse_fpocket_info(info_path: Path) -> list[dict[str, Any]]:
    """Parse `<input>_info.txt` written by fpocket.

    Returns one dict per pocket containing the keyed metrics fpocket reports
    (Druggability Score, Volume, Hydrophobicity score, Polarity score,
    Number of Alpha Spheres, Score, etc.). Pocket indices are 1-based to
    match the `pocket<N>_atm.pdb` filenames in current fpocket releases.
    """
    pockets: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    with open(info_path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.lower().startswith("pocket "):
                if current is not None:
                    pockets.append(current)
                idx = int(line.split()[1])
                current = {"_pocket_index": idx}
                continue
            if current is None or ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            try:
                current[key] = float(val.strip())
            except ValueError:
                current[key] = val.strip()
        if current is not None:
            pockets.append(current)
    return pockets


def _alpha_sphere_centers(pqr_path: Path) -> np.ndarray:
    """Read alpha-sphere centers from an fpocket pocket vertex PQR file."""
    coords: list[list[float]] = []
    with open(pqr_path) as fh:
        for line in fh:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            coords.append([x, y, z])
    return np.array(coords) if coords else np.zeros((0, 3))


def _pqr_path_for(pockets_dir: Path, idx: int) -> Path | None:
    """Return the alpha-sphere PQR file for pocket `idx`, supporting old + new fpocket layouts."""
    candidates = [
        pockets_dir / f"pocket{idx}_vert.pqr",          # current fpocket (1-indexed)
        pockets_dir / f"pocket{idx - 1}_vert.pqr",      # legacy 0-indexed releases
        pockets_dir / f"pocket{idx}_vert.pdb",          # very old releases
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _run_fpocket(
    protein: Path,
    work_dir: Path,
    min_alpha_sphere_radius: float | None,
    max_alpha_sphere_radius: float | None,
    min_clust_radius: float | None,
) -> tuple[Path, list[str]]:
    """Invoke fpocket and return (output dir, command line).

    fpocket writes its output next to the input PDB, so we copy the protein
    into a clean temporary directory before invoking it. This avoids
    polluting the user's working directory and avoids a stale `_out/` from a
    prior run.
    """
    fpocket_bin = _check_cli("fpocket")
    work_dir.mkdir(parents=True, exist_ok=True)

    local_pdb = work_dir / protein.name
    if not local_pdb.exists() or local_pdb.resolve() != protein.resolve():
        shutil.copy(protein, local_pdb)

    out_dir = work_dir / f"{local_pdb.stem}_out"
    if out_dir.exists():
        shutil.rmtree(out_dir)

    cmd: list[str] = [fpocket_bin, "-f", str(local_pdb)]
    if min_alpha_sphere_radius is not None:
        cmd += ["-m", str(min_alpha_sphere_radius)]
    if max_alpha_sphere_radius is not None:
        cmd += ["-M", str(max_alpha_sphere_radius)]
    if min_clust_radius is not None:
        cmd += ["-D", str(min_clust_radius)]

    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        sys.exit(f"fpocket failed (exit {proc.returncode}).")
    if not out_dir.is_dir():
        sys.exit(f"fpocket succeeded but output dir not found at {out_dir}.")
    return out_dir, cmd


def _collect_fpocket_results(
    protein: Path,
    out_dir: Path,
    residue_cutoff: float,
    top_n: int | None,
) -> list[dict[str, Any]]:
    info_path = out_dir / f"{protein.stem}_info.txt"
    if not info_path.exists():
        sys.exit(f"fpocket info file not found: {info_path}")
    raw_pockets = _parse_fpocket_info(info_path)
    if not raw_pockets:
        return []

    universe = mda.Universe(str(protein))
    pockets_dir = out_dir / "pockets"

    results: list[dict[str, Any]] = []
    for entry in raw_pockets:
        idx = int(entry["_pocket_index"])
        pqr = _pqr_path_for(pockets_dir, idx)
        if pqr is None:
            print(f"WARN: missing alpha-sphere file for pocket {idx} under {pockets_dir}; skipping.")
            continue
        centers = _alpha_sphere_centers(pqr)
        if len(centers) == 0:
            continue
        center = centers.mean(axis=0)
        bbox = _bounding_box(centers)
        residues = _residues_within(universe, centers, residue_cutoff)

        druggability = entry.get("Druggability Score")
        volume = entry.get("Volume") or entry.get("Real volume (Monte Carlo)")
        n_spheres_raw = entry.get("Number of Alpha Spheres")
        results.append({
            "rank": None,  # filled after sorting
            "id": f"pocket_{idx}",
            "fpocket_index": idx,
            "druggability_score": (
                float(druggability) if isinstance(druggability, (int, float)) else None
            ),
            "fpocket_score": (
                float(entry["Score"]) if isinstance(entry.get("Score"), (int, float)) else None
            ),
            "volume_a3": float(volume) if isinstance(volume, (int, float)) else None,
            "n_alpha_spheres": (
                int(n_spheres_raw) if isinstance(n_spheres_raw, (int, float)) else int(len(centers))
            ),
            "hydrophobicity_score": (
                float(entry["Hydrophobicity score"])
                if isinstance(entry.get("Hydrophobicity score"), (int, float))
                else None
            ),
            "polarity_score": (
                float(entry["Polarity score"])
                if isinstance(entry.get("Polarity score"), (int, float))
                else None
            ),
            "center": {"x": float(center[0]), "y": float(center[1]), "z": float(center[2])},
            "bounding_box": bbox,
            "residues": residues,
            "n_residues": len(residues),
            "raw_metrics": {
                k: v for k, v in entry.items() if not k.startswith("_")
            },
        })

    # Rank by druggability score (fpocket's headline number); tie-break on volume.
    results.sort(
        key=lambda p: (
            -(p["druggability_score"] if p["druggability_score"] is not None else -1.0),
            -(p["volume_a3"] if p["volume_a3"] is not None else -1.0),
        )
    )
    if top_n is not None:
        results = results[:top_n]
    for i, r in enumerate(results, start=1):
        r["rank"] = i
    return results


# ---------------------------------------------------------------------------
# P2Rank
# ---------------------------------------------------------------------------

_P2RANK_RES_RE = re.compile(r"^([A-Za-z0-9]+)_(-?\d+)([A-Za-z]?)$")


def _parse_p2rank_residue_ids(field: str) -> list[tuple[str, int, str]]:
    """Parse a P2Rank `residue_ids` field like "A_25 A_28 B_50A"."""
    out: list[tuple[str, int, str]] = []
    if not field:
        return out
    for token in field.replace(",", " ").split():
        m = _P2RANK_RES_RE.match(token.strip())
        if not m:
            continue
        chain, resnum, icode = m.group(1), int(m.group(2)), m.group(3)
        out.append((chain, resnum, icode))
    return out


def _residues_from_p2rank_ids(
    universe: mda.Universe, ids: list[tuple[str, int, str]]
) -> list[dict[str, Any]]:
    """Look up residue metadata for P2Rank-reported residue ids in the protein."""
    if not ids:
        return []
    out: dict[tuple, dict[str, Any]] = {}
    for chain, resnum, icode in ids:
        sel = f"protein and resid {resnum} and chainID {chain}"
        atoms = universe.select_atoms(sel)
        if len(atoms) == 0 and not chain:
            atoms = universe.select_atoms(f"protein and resid {resnum}")
        if len(atoms) == 0:
            continue
        atom = atoms[0]
        key = (chain, resnum, atom.resname, icode)
        out[key] = {
            "chain": chain,
            "resnum": int(resnum),
            "resname": atom.resname,
            "icode": icode,
            "one_letter": THREE_TO_ONE.get(atom.resname, "X"),
            "label": (
                f"{chain}:{atom.resname}{resnum}{icode}"
                if chain
                else f"{atom.resname}{resnum}{icode}"
            ),
        }
    return sorted(out.values(), key=lambda r: (r["chain"], r["resnum"], r["icode"]))


def _run_p2rank(
    protein: Path,
    work_dir: Path,
    config: str | None,
    visualizations: bool,
) -> tuple[Path, list[str]]:
    """Invoke `prank predict` and return (output dir, command line)."""
    prank_bin = _check_cli("prank")
    work_dir.mkdir(parents=True, exist_ok=True)
    cmd = [prank_bin, "predict", "-f", str(protein), "-o", str(work_dir)]
    if config:
        cmd += ["-c", config]
    if not visualizations:
        cmd += ["-visualizations", "0"]
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        sys.exit(f"P2Rank failed (exit {proc.returncode}).")
    return work_dir, cmd


def _collect_p2rank_results(
    protein: Path,
    work_dir: Path,
    residue_cutoff: float,
    top_n: int | None,
) -> list[dict[str, Any]]:
    csv_path = work_dir / f"{protein.name}_predictions.csv"
    if not csv_path.exists():
        candidates = list(work_dir.rglob(f"{protein.name}_predictions.csv"))
        if not candidates:
            sys.exit(f"P2Rank predictions CSV not found under {work_dir}.")
        csv_path = candidates[0]

    universe = mda.Universe(str(protein))
    results: list[dict[str, Any]] = []
    with open(csv_path) as fh:
        reader = csv.DictReader(fh, skipinitialspace=True)
        for row in reader:
            row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            try:
                rank = int(row["rank"])
                cx = float(row["center_x"])
                cy = float(row["center_y"])
                cz = float(row["center_z"])
                score = float(row["score"])
            except (KeyError, ValueError):
                continue
            probability = (
                float(row["probability"]) if row.get("probability") not in (None, "") else None
            )
            sas_points = (
                int(float(row["sas_points"])) if row.get("sas_points") not in (None, "") else None
            )

            # Prefer the residues P2Rank itself reports; fall back to a geometric
            # shell only if that column is empty or unparseable.
            res_ids_field = row.get("residue_ids") or row.get("adjacent_residues") or ""
            ids = _parse_p2rank_residue_ids(res_ids_field)
            if ids:
                residues = _residues_from_p2rank_ids(universe, ids)
                residue_source = "p2rank"
            else:
                residues = _residues_within(
                    universe, np.array([[cx, cy, cz]]), residue_cutoff
                )
                residue_source = "geometric_shell"

            results.append({
                "rank": rank,
                "id": row.get("name") or f"pocket_{rank}",
                "p2rank_score": score,
                "druggability_score": probability,  # P2Rank's calibrated probability
                "n_sas_points": sas_points,
                "volume_a3": None,  # P2Rank does not report pocket volume
                "center": {"x": cx, "y": cy, "z": cz},
                "bounding_box": None,
                "residues": residues,
                "residue_source": residue_source,
                "n_residues": len(residues),
                "raw_metrics": {
                    k: v for k, v in row.items() if k != "rank"
                },
            })

    results.sort(key=lambda p: p["rank"])
    if top_n is not None:
        results = results[:top_n]
    return results


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Identify and rank ligandable pockets on a protein structure."
    )
    parser.add_argument("--protein", required=True, help="Receptor PDB (prepared, no waters/ions ideally).")
    parser.add_argument(
        "--backend", choices=["fpocket", "p2rank"], default="fpocket",
        help="Pocket detection backend (default: fpocket).",
    )
    parser.add_argument("--output_json", required=True, help="Output JSON file with ranked pockets.")
    parser.add_argument(
        "--top_n", type=int, default=10,
        help="Keep at most this many pockets in the output (default: 10).",
    )
    parser.add_argument(
        "--residue_cutoff", type=float, default=5.0,
        help="Distance (A) from pocket points used to define lining residues "
             "(default: 5.0). For P2Rank, only used as a fallback when the "
             "predictions CSV lacks a residue_ids column.",
    )
    parser.add_argument(
        "--work_dir", default=None,
        help="Directory for backend scratch files (default: temp dir, deleted on exit).",
    )
    # fpocket-only knobs (passed through if set; otherwise fpocket's own
    # compiled defaults apply, currently -m 3.4 -M 6.2 -D 2.4 in fpocket 4.x)
    parser.add_argument("--fp_min_radius", type=float, default=None,
                        help="fpocket -m: minimum alpha-sphere radius (A). Unset = use fpocket default.")
    parser.add_argument("--fp_max_radius", type=float, default=None,
                        help="fpocket -M: maximum alpha-sphere radius (A). Unset = use fpocket default.")
    parser.add_argument("--fp_min_clust_radius", type=float, default=None,
                        help="fpocket -D: clustering distance for alpha spheres (A). Unset = use fpocket default.")
    # P2Rank-only knobs
    parser.add_argument(
        "--p2rank_config", default=None,
        help="P2Rank `-c` config/profile, e.g. 'alphafold' for predicted "
             "structures. Unset = P2Rank default profile.",
    )
    parser.add_argument(
        "--p2rank_visualizations", action="store_true",
        help="Keep P2Rank visualization files (slower). Default: disabled.",
    )
    args = parser.parse_args()

    if args.top_n is not None and args.top_n <= 0:
        sys.exit("--top_n must be positive.")
    if args.residue_cutoff <= 0:
        sys.exit("--residue_cutoff must be positive.")
    for label, val in (
        ("--fp_min_radius", args.fp_min_radius),
        ("--fp_max_radius", args.fp_max_radius),
        ("--fp_min_clust_radius", args.fp_min_clust_radius),
    ):
        if val is not None and val <= 0:
            sys.exit(f"{label} must be positive when set.")

    protein = Path(args.protein).resolve()
    if not protein.exists():
        sys.exit(f"Protein file not found: {protein}")
    output_json = Path(args.output_json).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)

    if args.work_dir is None:
        tmp = tempfile.TemporaryDirectory(prefix="pocket_detect_")
        work_dir = Path(tmp.name)
        cleanup = tmp
    else:
        work_dir = Path(args.work_dir).resolve()
        cleanup = None

    try:
        if args.backend == "fpocket":
            out_dir, backend_cmd = _run_fpocket(
                protein, work_dir,
                args.fp_min_radius, args.fp_max_radius, args.fp_min_clust_radius,
            )
            pockets = _collect_fpocket_results(
                protein, out_dir, args.residue_cutoff, args.top_n,
            )
            backend_version = _backend_version("fpocket")
        else:
            out_dir, backend_cmd = _run_p2rank(
                protein, work_dir, args.p2rank_config, args.p2rank_visualizations,
            )
            pockets = _collect_p2rank_results(
                protein, out_dir, args.residue_cutoff, args.top_n,
            )
            backend_version = _backend_version("prank")

        result = {
            "protein": str(protein),
            "backend": args.backend,
            "backend_version": backend_version,
            "backend_command": backend_cmd,
            "n_pockets": len(pockets),
            "residue_cutoff_a": args.residue_cutoff,
            "pockets": pockets,
        }
        with open(output_json, "w") as fh:
            json.dump(result, fh, indent=4)
        print(f"\nWrote {len(pockets)} pocket(s) to {output_json}")
        if pockets:
            top = pockets[0]
            print(
                f"Top pocket: {top['id']} "
                f"druggability={top.get('druggability_score')} "
                f"center=({top['center']['x']:.1f}, {top['center']['y']:.1f}, {top['center']['z']:.1f}) "
                f"residues={top['n_residues']}"
            )
    finally:
        if cleanup is not None:
            cleanup.cleanup()


if __name__ == "__main__":
    main()
