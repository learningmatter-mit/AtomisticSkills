"""
Define a docking/simulation box from a co-crystal ligand, binding-site residues,
or a previously saved JSON specification.

Uses MDAnalysis for PDB/PDBQT/MOL2 (handles altlocs, multi-model, insertion
codes) and RDKit for SDF/MOL files.

Usage:
    python define_binding_site.py --mode ligand --ligand_file lig.sdf --output_json box.json
    python define_binding_site.py --mode residues --protein_file rec.pdb --residues "A:ASP25,A:THR26" --output_json box.json
    python define_binding_site.py --mode json --input_json box.json

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: MDAnalysis, numpy, rdkit
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import MDAnalysis as mda


# ---------------------------------------------------------------------------
# Coordinate extraction
# ---------------------------------------------------------------------------

def _filter_altlocs(atoms: mda.core.groups.AtomGroup) -> mda.core.groups.AtomGroup:
    """Keep only atoms with altloc blank or 'A', excluding B/C/etc."""
    mask = np.isin(atoms.altLocs, ["", " ", "A"])
    return atoms[mask]


def _extract_coords_mda(path: Path) -> np.ndarray:
    """Extract coordinates via MDAnalysis (PDB, PDBQT, MOL2)."""
    u = mda.Universe(str(path))
    atoms = _filter_altlocs(u.atoms)
    return atoms.positions


def _extract_coords_rdkit(path: Path) -> np.ndarray:
    """Extract coordinates via RDKit (SDF, MOL). Uses first molecule only."""
    from rdkit import Chem

    suffix = path.suffix.lower()
    if suffix == ".mol2":
        mol = Chem.MolFromMol2File(str(path), removeHs=False)
        if mol is None:
            raise ValueError(f"RDKit could not parse MOL2 file: {path}")
    else:
        suppl = Chem.SDMolSupplier(str(path), removeHs=False)
        mol = None
        n_mols = 0
        for m in suppl:
            if m is None:
                continue
            n_mols += 1
            if mol is None:
                mol = m
            elif n_mols == 2:
                print(
                    "WARNING: SDF contains multiple molecules; using only the first.",
                    file=sys.stderr,
                )
                break
        if mol is None:
            raise ValueError(f"No valid molecules found in {path}")

    conf = mol.GetConformer()
    return np.array([
        [conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z]
        for i in range(mol.GetNumAtoms())
    ])


_EXTRACTORS = {
    ".pdb": _extract_coords_mda,
    ".pdbqt": _extract_coords_mda,
    ".mol2": _extract_coords_mda,
    ".sdf": _extract_coords_rdkit,
    ".mol": _extract_coords_rdkit,
}


def extract_ligand_coords(ligand_file: Path) -> np.ndarray:
    """Extract coordinates from a ligand file (auto-detect format by extension)."""
    suffix = ligand_file.suffix.lower()
    extractor = _EXTRACTORS.get(suffix)
    if extractor is None:
        raise ValueError(
            f"Unsupported ligand format '{suffix}'. "
            f"Supported: {', '.join(_EXTRACTORS.keys())}"
        )
    positions = extractor(ligand_file)
    if len(positions) == 0:
        raise ValueError(f"No atom coordinates found in {ligand_file}")
    return positions


# ---------------------------------------------------------------------------
# Residue selection
# ---------------------------------------------------------------------------

def _parse_residue_spec(spec: str) -> Tuple[str, str, int, str]:
    """
    Parse a residue specification string into (chain, resname, resid, icode).

    Accepted formats:
        "A:ASP25"   -> ('A', 'ASP', 25, '')
        "A:ASP25A"  -> ('A', 'ASP', 25, 'A')
        "ASP25"     -> ('', 'ASP', 25, '')
        "A:25"      -> ('A', '', 25, '')
        "25A"       -> ('', '', 25, 'A')
        "25"        -> ('', '', 25, '')
    """
    spec = spec.strip()
    chain = ""
    if ":" in spec:
        chain, spec = spec.split(":", 1)

    match = re.match(r"([A-Za-z]*)(\d+)([A-Za-z]?)", spec)
    if not match:
        raise ValueError(f"Cannot parse residue spec: '{spec}'")

    resname = match.group(1).upper()
    resid = int(match.group(2))
    icode = match.group(3).upper()
    return chain.upper(), resname, resid, icode


def _build_mda_selection(residue_specs: List[str]) -> str:
    """
    Convert user residue specs into an MDAnalysis selection string.

    Insertion codes are handled via post-filtering since the MDA selection
    language has limited icode support.
    """
    parts = []
    for spec in residue_specs:
        chain, resname, resid, _icode = _parse_residue_spec(spec)
        clause = f"resid {resid}"
        if resname:
            clause += f" and resname {resname}"
        if chain:
            clause += f" and segid {chain}"
        parts.append(f"({clause})")
    return " or ".join(parts)


def extract_residue_coords(
    protein_file: Path, residue_specs: List[str]
) -> np.ndarray:
    """
    Extract coordinates of specified residues from a protein structure file.

    Returns an (N, 3) positions array. Warns about any residue specs that
    matched zero atoms.
    """
    u = mda.Universe(str(protein_file))
    sel_str = _build_mda_selection(residue_specs)
    atoms = _filter_altlocs(u.select_atoms(sel_str))

    # Post-filter for insertion codes if any specs include them
    parsed = [_parse_residue_spec(s) for s in residue_specs]
    has_icodes = any(p[3] for p in parsed)
    if has_icodes and hasattr(atoms, "icodes"):
        icode_masks = []
        for chain, resname, resid, icode in parsed:
            if not icode:
                continue
            mask = (atoms.resids == resid) & (atoms.icodes == icode)
            if chain:
                mask &= atoms.segids == chain
            if resname:
                mask &= atoms.resnames == resname
            icode_masks.append(mask)
        if icode_masks:
            combined = icode_masks[0]
            for m in icode_masks[1:]:
                combined |= m
            no_icode_specs = [p for p in parsed if not p[3]]
            if no_icode_specs:
                no_icode_sel = _build_mda_selection([
                    f"{p[0]}:{p[1]}{p[2]}" if p[0] else f"{p[1]}{p[2]}"
                    for p in no_icode_specs
                ])
                no_icode_atoms = u.select_atoms(no_icode_sel)
                combined |= np.isin(atoms.indices, no_icode_atoms.indices)
            atoms = atoms[combined]

    # Warn about unmatched residue specs
    for i, (chain, resname, resid, icode) in enumerate(parsed):
        clause = f"resid {resid}"
        if resname:
            clause += f" and resname {resname}"
        if chain:
            clause += f" and segid {chain}"
        if len(u.select_atoms(clause)) == 0:
            print(
                f"WARNING: No atoms found for residue: {residue_specs[i]}",
                file=sys.stderr,
            )

    if len(atoms) == 0:
        return np.empty((0, 3))
    return atoms.positions


# ---------------------------------------------------------------------------
# Box computation
# ---------------------------------------------------------------------------

def compute_box(
    positions: np.ndarray,
    padding: float,
    min_size: float,
) -> Dict[str, float]:
    """Compute bounding box center and size from an (N, 3) coordinate array."""
    if len(positions) == 0:
        raise ValueError("No coordinates provided for box computation")

    pos_min = positions.min(axis=0)
    pos_max = positions.max(axis=0)
    center = 0.5 * (pos_min + pos_max)
    size = np.maximum(pos_max - pos_min + 2.0 * padding, min_size)

    return {
        "center_x": round(float(center[0]), 4),
        "center_y": round(float(center[1]), 4),
        "center_z": round(float(center[2]), 4),
        "size_x": round(float(size[0]), 4),
        "size_y": round(float(size[1]), 4),
        "size_z": round(float(size[2]), 4),
        "padding": padding,
        "min_size": min_size,
    }


REQUIRED_BOX_KEYS = {"center_x", "center_y", "center_z", "size_x", "size_y", "size_z"}


def validate_box_json(data: dict) -> None:
    """Validate that a loaded JSON has the required box keys."""
    missing = REQUIRED_BOX_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Box JSON missing required keys: {missing}")
    for key in REQUIRED_BOX_KEYS:
        if not isinstance(data[key], (int, float)):
            raise ValueError(f"Box key '{key}' must be numeric, got {type(data[key])}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Define a docking/simulation box from ligand, residues, or saved JSON."
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["ligand", "residues", "json"],
        help="How to define the box: from a ligand file, protein residues, or saved JSON.",
    )
    parser.add_argument(
        "--ligand_file",
        default=None,
        help="Ligand file for 'ligand' mode (PDB, SDF, MOL2, PDBQT).",
    )
    parser.add_argument(
        "--protein_file",
        default=None,
        help="Protein structure file for 'residues' mode (PDB, mmCIF, PDBQT).",
    )
    parser.add_argument(
        "--residues",
        default=None,
        help="Comma-separated residue specs for 'residues' mode (e.g., 'A:ASP25,A:THR26').",
    )
    parser.add_argument(
        "--input_json",
        default=None,
        help="Input JSON file for 'json' mode.",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=6.0,
        help="Padding added to bounding box on each side in Angstroms (default: 6.0).",
    )
    parser.add_argument(
        "--min_size",
        type=float,
        default=20.0,
        help="Minimum box edge length per axis in Angstroms (default: 20.0).",
    )
    parser.add_argument(
        "--output_json",
        default=None,
        help="Output JSON path. If omitted, prints to stdout.",
    )
    args = parser.parse_args()

    if args.mode == "ligand":
        if not args.ligand_file:
            parser.error("--ligand_file is required for 'ligand' mode")
        ligand_path = Path(args.ligand_file)
        if not ligand_path.exists():
            parser.error(f"Ligand file not found: {ligand_path}")
        positions = extract_ligand_coords(ligand_path)
        box = compute_box(positions, padding=args.padding, min_size=args.min_size)
        box["mode"] = "ligand"
        box["source"] = ligand_path.name

    elif args.mode == "residues":
        if not args.protein_file:
            parser.error("--protein_file is required for 'residues' mode")
        if not args.residues:
            parser.error("--residues is required for 'residues' mode")
        protein_path = Path(args.protein_file)
        if not protein_path.exists():
            parser.error(f"Protein file not found: {protein_path}")
        residue_list = [r.strip() for r in args.residues.split(",")]
        positions = extract_residue_coords(protein_path, residue_list)
        if len(positions) == 0:
            print(
                "ERROR: No matching residue atoms found. Check residue specifications.",
                file=sys.stderr,
            )
            sys.exit(1)
        box = compute_box(positions, padding=args.padding, min_size=args.min_size)
        box["mode"] = "residues"
        box["source"] = protein_path.name
        box["residues"] = residue_list

    elif args.mode == "json":
        if not args.input_json:
            parser.error("--input_json is required for 'json' mode")
        input_path = Path(args.input_json)
        if not input_path.exists():
            parser.error(f"Input JSON not found: {input_path}")
        with open(input_path, "r", encoding="utf-8") as f:
            box = json.load(f)
        validate_box_json(box)

    else:
        parser.error(f"Unknown mode: {args.mode}")

    output_str = json.dumps(box, indent=4)

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output_str + "\n")
        print(f"Wrote: {out_path}")
    else:
        print(output_str)

        # Save input configs for reproducibility
        from src.utils.config_utils import save_skill_inputs
        save_skill_inputs(args, args.output_dir)
        _params_path.parent.mkdir(parents=True, exist_ok=True)
        _params_path.write_text(json.dumps(_config, indent=2, default=str))


if __name__ == "__main__":
    main()
