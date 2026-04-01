"""
Protein Preparation Tool (protein-prep)

Prepare macromolecular receptor structures for docking/simulation:
- Fetch from RCSB by PDB ID (PDB or mmCIF; optional biological assembly), OR read a local file
- Fix common PDB issues using PDBFixer (OpenMM): missing atoms, nonstandard residues, hydrogens
- Optional heterogen/water handling suitable for docking workflows
- Optionally generate receptor PDBQT using Meeko's mk_prepare_receptor.py
  (recommended by AutoDock Vina documentation)

Usage:
    python prepare_protein.py --pdb_id 1iep --chains A --output_dir prep/
    python prepare_protein.py --pdb_file receptor.pdb --heterogens none --output_dir prep/
    python prepare_protein.py --pdb_id 1iep --assembly 1 --output_dir prep/

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: pdbfixer, openmm
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pdbfixer import PDBFixer
from openmm.app import Modeller, PDBFile

LOGGER = logging.getLogger("protein-prep")

WATER_RESNAMES = {"HOH", "WAT", "H2O", "TIP3", "SOL"}

STANDARD_AA = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    "HID", "HIE", "HIP", "CYX",
}
STANDARD_NA = {
    "A", "C", "G", "U", "I",
    "DA", "DC", "DG", "DT", "DU",
}


def _safe_version(mod: Any) -> Optional[str]:
    return getattr(mod, "__version__", None)


def fetch_rcsb_structure(
    pdb_id: str,
    output_path: Path,
    fmt: str = "auto",
    assembly: Optional[int] = None,
) -> Tuple[Path, str]:
    """Download a coordinate file from RCSB.

    Returns (local_path, url_used).
    """
    pdb_id_clean = pdb_id.strip()
    if not pdb_id_clean:
        raise ValueError("Empty PDB ID")

    pdb_id_upper = pdb_id_clean.upper()
    pdb_id_lower = pdb_id_clean.lower()

    def _url_for(fmt_: str) -> str:
        if fmt_ == "pdb":
            if assembly is None:
                return f"https://files.rcsb.org/download/{pdb_id_upper}.pdb"
            return f"https://files.rcsb.org/download/{pdb_id_upper}.pdb{assembly}"
        if fmt_ == "cif":
            if assembly is None:
                return f"https://files.rcsb.org/download/{pdb_id_upper}.cif"
            return f"https://files.rcsb.org/download/{pdb_id_lower}-assembly{assembly}.cif"
        raise ValueError(f"Unsupported fmt: {fmt_}")

    tried: List[str] = []
    fmts_to_try: List[str]
    if fmt == "auto":
        fmts_to_try = ["pdb", "cif"]
    else:
        fmts_to_try = [fmt]

    last_err: Optional[Exception] = None
    for fmt_try in fmts_to_try:
        url = _url_for(fmt_try)
        tried.append(url)
        try:
            LOGGER.info("Fetching RCSB: %s", url)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, str(output_path))
            return output_path, url
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(
        f"Failed to download {pdb_id_upper}. Tried: {tried}. Last error: {last_err}"
    )


def _chain_ids(fixer: PDBFixer) -> List[str]:
    return [ch.id for ch in fixer.topology.chains()]


def remove_chains_keep(
    fixer: PDBFixer,
    keep_chain_ids: Sequence[str],
) -> Dict[str, Any]:
    """Keep only chains listed in keep_chain_ids."""
    keep_set = {c for c in keep_chain_ids if c is not None}
    all_chains = list(fixer.topology.chains())
    all_ids = [c.id for c in all_chains]

    missing = sorted(list(keep_set - set(all_ids)))
    if missing:
        raise ValueError(
            f"Requested chains not present: {missing}. Available: {all_ids}"
        )

    to_remove = [i for i, ch in enumerate(all_chains) if ch.id not in keep_set]
    if to_remove:
        fixer.removeChains(to_remove)

    return {
        "chains_kept": sorted(list(keep_set)),
        "chains_removed": [all_ids[i] for i in to_remove],
    }


def handle_missing_residues(
    fixer: PDBFixer,
    mode: str,
) -> Dict[str, Any]:
    """Control whether missing residues (from SEQRES with no coordinates) are built.

    PDBFixer inserts residues in missingResidues when addMissingAtoms() is called.
    """
    fixer.findMissingResidues()

    chains = list(fixer.topology.chains())
    missing_list = []
    for (chain_index, insert_index), names in fixer.missingResidues.items():
        chain_id = chains[chain_index].id if chain_index < len(chains) else None
        missing_list.append({
            "chain_index": int(chain_index),
            "chain_id": chain_id,
            "insert_index": int(insert_index),
            "residue_names": list(names),
        })

    if mode == "ignore":
        fixer.missingResidues = {}
    elif mode == "ignore_terminal":
        filtered = {}
        for (chain_index, insert_index), names in fixer.missingResidues.items():
            chain = chains[chain_index]
            n_res = len(list(chain.residues()))
            if insert_index == 0 or insert_index == n_res:
                continue
            filtered[(chain_index, insert_index)] = names
        fixer.missingResidues = filtered
    elif mode == "build":
        pass
    else:
        raise ValueError(f"Unknown missing_residues mode: {mode}")

    return {
        "missing_residues_mode": mode,
        "missing_residues_detected": missing_list,
        "missing_residues_detected_count": len(missing_list),
        "missing_residues_will_be_built": (
            mode in {"build", "ignore_terminal"} and len(fixer.missingResidues) > 0
        ),
    }


def replace_nonstandard_residues(
    fixer: PDBFixer,
    enabled: bool,
) -> Dict[str, Any]:
    if not enabled:
        return {"replace_nonstandard": False, "nonstandard_residues": []}

    fixer.findNonstandardResidues()
    nonstd = []
    for residue, replacement in fixer.nonstandardResidues:
        nonstd.append({
            "chain_id": residue.chain.id,
            "residue_id": residue.id,
            "resname": residue.name,
            "replacement": replacement,
        })
    fixer.replaceNonstandardResidues()
    return {"replace_nonstandard": True, "nonstandard_residues": nonstd}


def _is_polymer_resname(resname: str) -> bool:
    r = resname.strip().upper()
    return (r in STANDARD_AA) or (r in STANDARD_NA) or (r == "UNK")


def apply_heterogen_policy(
    fixer: PDBFixer,
    heterogens: str,
    keep_resname: Sequence[str],
    delete_resname: Sequence[str],
) -> Dict[str, Any]:
    """Apply heterogen/water handling policy.

    heterogens modes:
        all       : keep all residues (protein + heterogens + water)
        none      : keep only polymer residues (and any keep_resname)
        water     : keep polymer + water (and keep_resname); remove other heterogens
        non-water : keep everything except water
    """
    keep_set = {x.strip().upper() for x in keep_resname if x}
    delete_set = {x.strip().upper() for x in delete_resname if x}

    if heterogens in {"none", "water"} and not keep_set and not delete_set:
        keep_water = heterogens == "water"
        fixer.removeHeterogens(keep_water)
        return {
            "heterogens_mode": heterogens,
            "keep_resname": [],
            "delete_resname": [],
            "policy_impl": "pdbfixer.removeHeterogens",
        }

    modeller = Modeller(fixer.topology, fixer.positions)
    to_delete = []

    for res in modeller.topology.residues():
        name = res.name.strip().upper()

        if name in delete_set:
            to_delete.append(res)
            continue

        if heterogens == "all":
            continue

        if heterogens == "non-water":
            if name in WATER_RESNAMES:
                to_delete.append(res)
            continue

        if heterogens == "none":
            if _is_polymer_resname(name) or (name in keep_set):
                continue
            to_delete.append(res)
            continue

        if heterogens == "water":
            if _is_polymer_resname(name) or (name in WATER_RESNAMES) or (name in keep_set):
                continue
            to_delete.append(res)
            continue

        raise ValueError(f"Unknown heterogens mode: {heterogens}")

    if to_delete:
        modeller.delete(to_delete)
        fixer.topology = modeller.topology
        fixer.positions = modeller.positions

    return {
        "heterogens_mode": heterogens,
        "keep_resname": sorted(list(keep_set)),
        "delete_resname": sorted(list(delete_set)),
        "deleted_residue_count": len(to_delete),
        "policy_impl": "custom(Modeller.delete)",
    }


def add_missing_atoms_and_hydrogens(
    fixer: PDBFixer,
    ph: float,
) -> Dict[str, Any]:
    fixer.findMissingAtoms()

    missing_atoms_count = sum(len(v) for v in fixer.missingAtoms.values())
    missing_terminals_count = sum(len(v) for v in fixer.missingTerminals.values())

    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(ph)

    return {
        "missing_atoms_count": int(missing_atoms_count),
        "missing_terminals_count": int(missing_terminals_count),
        "ph": float(ph),
    }


def write_pdb(
    fixer: PDBFixer,
    pdb_path: Path,
    keep_ids: bool = True,
) -> None:
    pdb_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pdb_path, "w", encoding="utf-8") as f:
        try:
            PDBFile.writeFile(fixer.topology, fixer.positions, f, keepIds=keep_ids)
        except TypeError:
            PDBFile.writeFile(fixer.topology, fixer.positions, f)




def prepare_protein(
    pdb_path: Path,
    output_dir: Path,
    name: str,
    chains: Optional[List[str]] = None,
    heterogens: str = "none",
    keep_resname: Optional[List[str]] = None,
    delete_resname: Optional[List[str]] = None,
    missing_residues: str = "ignore",
    replace_nonstandard: bool = True,
    ph: float = 7.0,
) -> Dict[str, Any]:
    """Prepare a receptor structure and return a summary dictionary."""
    keep_resname = keep_resname or []
    delete_resname = delete_resname or []

    summary: Dict[str, Any] = {
        "name": name,
        "input_file": str(pdb_path),
        "success": False,
        "settings": {
            "chains": chains,
            "heterogens": heterogens,
            "keep_resname": keep_resname,
            "delete_resname": delete_resname,
            "missing_residues": missing_residues,
            "replace_nonstandard": replace_nonstandard,
            "ph": ph,
        },
    }

    fixer = PDBFixer(filename=str(pdb_path))

    if chains:
        summary["chain_selection"] = remove_chains_keep(fixer, chains)

    summary["missing_residues"] = handle_missing_residues(fixer, missing_residues)
    summary["nonstandard_residues"] = replace_nonstandard_residues(
        fixer, replace_nonstandard
    )
    summary["heterogens_policy"] = apply_heterogen_policy(
        fixer, heterogens, keep_resname, delete_resname
    )
    summary["atom_completion"] = add_missing_atoms_and_hydrogens(fixer, ph)

    summary["final_counts"] = {
        "chains": sum(1 for _ in fixer.topology.chains()),
        "residues": sum(1 for _ in fixer.topology.residues()),
        "atoms": sum(1 for _ in fixer.topology.atoms()),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    pdb_out = output_dir / f"{name}_prepared.pdb"
    write_pdb(fixer, pdb_out, keep_ids=True)
    summary["pdb_file"] = str(pdb_out)


    summary["success"] = True
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare protein receptors for docking/simulation (PDBFixer + Meeko)."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--pdb_id", help="PDB ID to fetch from RCSB (e.g., 1iep)")
    input_group.add_argument("--pdb_file", help="Path to local PDB/mmCIF file")

    parser.add_argument(
        "--assembly", type=int, default=None,
        help="RCSB biological assembly index (e.g., 1)",
    )
    parser.add_argument(
        "--rcsb_format", choices=["auto", "pdb", "cif"], default="auto",
        help="Download format",
    )
    parser.add_argument(
        "--chains", nargs="+",
        help="Chain IDs to keep (e.g., --chains A B)",
    )

    parser.add_argument(
        "--heterogens", choices=["all", "none", "water", "non-water"], default="none",
        help="Heterogen handling: all | none | water (keep water, drop other) | non-water (drop water only)",
    )
    parser.add_argument(
        "--keep_resname", nargs="*", default=[],
        help="Residue names to keep even if heterogens removed (e.g., ZN HEM)",
    )
    parser.add_argument(
        "--delete_resname", nargs="*", default=[],
        help="Residue names to delete (e.g., SO4 GOL)",
    )

    parser.add_argument(
        "--missing_residues", choices=["ignore", "ignore_terminal", "build"],
        default="ignore",
        help="Missing residue policy: ignore (default) | ignore_terminal | build",
    )
    parser.add_argument(
        "--no_replace_nonstandard", action="store_true",
        help="Disable replacement of nonstandard residues",
    )
    parser.add_argument(
        "--ph", type=float, default=7.0,
        help="pH used for adding hydrogens (default: 7.0)",
    )


    parser.add_argument("--output_dir", default=".", help="Output directory")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.pdb_id:
        name = args.pdb_id.strip().upper()
        raw_ext = "pdb" if args.rcsb_format in {"auto", "pdb"} else "cif"
        raw_path = output_dir / f"{name}_raw.{raw_ext}"
        raw_path, url_used = fetch_rcsb_structure(
            pdb_id=args.pdb_id,
            output_path=raw_path,
            fmt=args.rcsb_format,
            assembly=args.assembly,
        )
        input_path = raw_path
    else:
        input_path = Path(args.pdb_file).expanduser().resolve()
        if not input_path.exists():
            raise FileNotFoundError(str(input_path))
        name = input_path.stem
        url_used = None

    summary = prepare_protein(
        pdb_path=input_path,
        output_dir=output_dir,
        name=name,
        chains=args.chains,
        heterogens=args.heterogens,
        keep_resname=args.keep_resname,
        delete_resname=args.delete_resname,
        missing_residues=args.missing_residues,
        replace_nonstandard=not args.no_replace_nonstandard,
        ph=args.ph,

    )
    if url_used:
        summary["rcsb_url"] = url_used

    try:
        import openmm
        import pdbfixer as _pdbfixer
        import meeko as _meeko

        summary["versions"] = {
            "openmm": (
                getattr(openmm, "version", None).version
                if getattr(openmm, "version", None)
                else _safe_version(openmm)
            ),
            "pdbfixer": _safe_version(_pdbfixer),

        }
    except Exception:
        pass

    summary_path = output_dir / f"{name}_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    print(json.dumps(summary, indent=4))


if __name__ == "__main__":
    main()
