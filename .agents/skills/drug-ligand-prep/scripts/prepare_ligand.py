"""
Ligand Preparation Tool

Prepare small molecules for docking/analysis:
- Input: SMILES, SMILES file, or SDF (multi-molecule supported)
- Optional: keep largest fragment (salt stripping)
- Optional: enumerate protonation states in a pH window (Dimorphite-DL)
- Optional: enumerate tautomers (RDKit MolStandardize)
- Add hydrogens
- Generate conformers with ETKDGv3 (RDKit)
- Minimize with MMFF94 (fallback UFF)
- Select lowest-energy conformer
- Output: SDF (best conformer), optional all-conformer SDF, and PDBQT (Meeko)

Usage:
    python prepare_ligand.py --smiles "CCO" --name ethanol --output_dir prep/
    python prepare_ligand.py --sdf ligands.sdf --output_dir prep/
    python prepare_ligand.py --smiles_file ligands.smi --output_dir prep/

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: rdkit, meeko
    - Optional packages:
        - dimorphite_dl (for protonation-state enumeration)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors


LOGGER = logging.getLogger("ligand_prep")


@dataclass
class PrepResult:
    name: str
    success: bool
    input_smiles: Optional[str] = None
    canonical_smiles: Optional[str] = None
    formal_charge: Optional[int] = None
    num_atoms: Optional[int] = None
    num_heavy_atoms: Optional[int] = None
    molecular_weight: Optional[float] = None
    num_rotatable_bonds: Optional[int] = None

    # state bookkeeping
    state_index: Optional[int] = None
    protomer_index: Optional[int] = None
    tautomer_index: Optional[int] = None

    state_index: Optional[int] = None
    protomer_index: Optional[int] = None
    tautomer_index: Optional[int] = None
    
    # outputs
    sdf_file: Optional[str] = None

    # warnings/errors
    warnings: List[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["warnings"] is None:
            d["warnings"] = []
        return d


def safe_stem(name: str) -> str:
    """Make a filesystem-safe stem."""
    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return name or "ligand"


def configure_logging(level: str) -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(levelname)s | %(message)s",
        stream=sys.stdout,
    )


def mol_from_smiles(smiles: str, sanitize: bool = True) -> Optional[Chem.Mol]:
    try:
        mol = Chem.MolFromSmiles(smiles, sanitize=sanitize)
        return mol
    except Exception:
        return None


def iter_smiles_file(path: Path) -> Iterable[Tuple[str, str]]:
    """
    Yield (smiles, name) from a SMILES file.

    Supported formats:
      - SMILES<TAB>NAME
      - SMILES NAME
      - SMILES (name auto-generated)
    """
    with path.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                smi, nm = line.split("\t", 1)
                smi = smi.strip()
                nm = nm.strip()
            else:
                parts = line.split(None, 1)
                smi = parts[0].strip()
                nm = parts[1].strip() if len(parts) > 1 else f"ligand_{i:05d}"
            yield smi, nm


def get_mol_name_from_sdf(mol: Chem.Mol, fallback: str) -> str:
    nm = mol.GetProp("_Name").strip() if mol.HasProp("_Name") else ""
    return nm if nm else fallback


def check_unassigned_stereo(mol: Chem.Mol) -> List[str]:
    warnings: List[str] = []
    try:
        centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
        unassigned = [(idx, tag) for idx, tag in centers if tag == "?"]
        if unassigned:
            warnings.append(
                f"Unassigned stereocenters detected: {[idx for idx, _ in unassigned]}. "
                "Docking may be meaningless unless stereochemistry is resolved."
            )
    except Exception:
        pass
    return warnings


def keep_largest_fragment(mol: Chem.Mol) -> Chem.Mol:
    """Keep largest fragment by heavy-atom count; helpful for salts/solvents."""
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
    if len(frags) <= 1:
        return mol
    frags_sorted = sorted(frags, key=lambda m: m.GetNumHeavyAtoms(), reverse=True)
    return frags_sorted[0]


def enumerate_tautomers(mol: Chem.Mol, max_tautomers: int) -> List[Chem.Mol]:
    """Enumerate tautomers (heuristic) using RDKit MolStandardize if available."""
    try:
        from rdkit.Chem.MolStandardize import rdMolStandardize

        enumerator = rdMolStandardize.TautomerEnumerator()
        tset = enumerator.Enumerate(mol)
        out: List[Chem.Mol] = []
        for i, tm in enumerate(tset):
            if i >= max_tautomers:
                break
            out.append(Chem.Mol(tm))
        return out if out else [mol]
    except Exception:
        return [mol]


def enumerate_protomers_from_smiles(
    smiles: str,
    ph_min: float,
    ph_max: float,
    precision: float,
    max_variants: int,
) -> List[str]:
    """Enumerate ionization states using Dimorphite-DL, if available. Returns list of SMILES."""
    try:
        from dimorphite_dl import protonate_smiles

        protomers: List[str] = protonate_smiles(
            smiles,
            ph_min=ph_min,
            ph_max=ph_max,
            precision=precision,
            max_variants=max_variants,
            label_states=False,
        )
        if isinstance(protomers, str):
            return [protomers]
        return list(dict.fromkeys(protomers))
    except ImportError as e:
        raise RuntimeError(
            "Dimorphite-DL not installed but --enumerate_protomers was requested. "
            "Install with: pip install dimorphite_dl"
        ) from e


def embed_conformers(
    mol: Chem.Mol,
    num_confs: int,
    prune_rms: float,
    seed: int,
) -> List[int]:
    """Embed multiple conformers using ETKDGv3. Returns conformer IDs."""
    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed)
    params.pruneRmsThresh = float(prune_rms)
    params.numThreads = 0

    conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=int(num_confs), params=params))
    if conf_ids:
        return conf_ids

    # fallback: random coordinates
    params.useRandomCoords = True
    conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=max(1, int(num_confs)), params=params))
    return conf_ids


def optimize_conformers_mmff(
    mol: Chem.Mol,
    max_iters: int,
    mmff_variant: str,
) -> Optional[List[Tuple[int, float]]]:
    """Optimize all conformers with MMFF. Returns list of (status, energy) or None if unavailable."""
    props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant=mmff_variant)
    if props is None:
        return None
    try:
        res = AllChem.MMFFOptimizeMoleculeConfs(
            mol,
            numThreads=0,
            maxIters=int(max_iters),
            mmffVariant=mmff_variant,
        )
        return [(int(status), float(energy)) for status, energy in res]
    except Exception:
        return None


def optimize_conformers_uff(mol: Chem.Mol, max_iters: int) -> Optional[List[Tuple[int, float]]]:
    """Optimize all conformers with UFF. Returns list of (status, energy) or None if fails."""
    try:
        res = AllChem.UFFOptimizeMoleculeConfs(mol, numThreads=0, maxIters=int(max_iters))
        return [(int(status), float(energy)) for status, energy in res]
    except Exception:
        return None


def select_best_conformer(
    mol: Chem.Mol,
    opt_results: List[Tuple[int, float]],
) -> Tuple[int, float, bool]:
    """Select best conformer by lowest energy. Returns (best_conf_id, best_energy, converged_any)."""
    energies = [(i, e, s) for i, (s, e) in enumerate(opt_results)]
    best_idx, best_e, _ = min(energies, key=lambda t: t[1])
    converged_any = any(status == 0 for status, _ in opt_results)
    conf_id = mol.GetConformer(int(best_idx)).GetId()
    return conf_id, float(best_e), bool(converged_any)


def write_best_sdf(mol: Chem.Mol, out_path: Path, conf_id: int, name: str, energy: Optional[float]) -> None:
    mol.SetProp("_Name", name)
    if energy is not None:
        mol.SetProp("RDKit_BestEnergy_kcal_mol", f"{energy:.6f}")

    w = Chem.SDWriter(str(out_path))
    w.write(mol, confId=int(conf_id))
    w.close()


def write_all_confs_sdf(
    mol: Chem.Mol,
    out_path: Path,
    name: str,
    energies: Optional[List[Tuple[int, float]]] = None,
) -> None:
    """Write each conformer as a separate SDF record."""
    w = Chem.SDWriter(str(out_path))
    for i, conf in enumerate(mol.GetConformers()):
        tmp = Chem.Mol(mol)
        tmp.RemoveAllConformers()
        tmp.AddConformer(Chem.Conformer(conf), assignId=True)
        tmp.SetProp("_Name", f"{name}_conf{i:03d}")
        if energies is not None and i < len(energies):
            status, e = energies[i]
            tmp.SetProp("RDKit_OptimizeStatus", str(int(status)))
            tmp.SetProp("RDKit_Energy_kcal_mol", f"{float(e):.6f}")
        w.write(tmp)
    w.close()


def mol_with_single_conformer(mol: Chem.Mol, conf_id: int) -> Chem.Mol:
    """Return a copy of mol with only the chosen conformer."""
    out = Chem.Mol(mol)
    conf = mol.GetConformer(int(conf_id))
    out.RemoveAllConformers()
    out.AddConformer(Chem.Conformer(conf), assignId=True)
    return out


def write_pdbqt_with_meeko(mol: Chem.Mol, out_path: Path) -> None:
    """Convert molecule to PDBQT using Meeko."""
    from meeko import MoleculePreparation, PDBQTWriterLegacy

    preparator = MoleculePreparation()
    setups = preparator.prepare(mol)
    if not setups:
        raise RuntimeError("Meeko did not produce any MoleculeSetup objects.")

    pdbqt_string, is_ok, error_msg = PDBQTWriterLegacy.write_string(setups[0])
    if not is_ok:
        raise RuntimeError(f"Meeko PDBQTWriterLegacy failed: {error_msg}")

    out_path.write_text(pdbqt_string, encoding="utf-8")


def write_sdf(mol: Chem.Mol, out_path: Path, name: str) -> None:
    """Write molecule to SDF."""
    mol.SetProp("_Name", name)
    w = Chem.SDWriter(str(out_path))
    w.write(mol)
    w.close()


def prepare_one_state(
    base_mol: Chem.Mol,
    name: str,
    output_dir: Path,
) -> PrepResult:
    res = PrepResult(name=name, success=False, warnings=[])

    try:
        res.canonical_smiles = Chem.MolToSmiles(Chem.RemoveHs(base_mol))
    except Exception:
        res.canonical_smiles = None

    try:
        res.formal_charge = int(Chem.GetFormalCharge(base_mol))
    except Exception:
        res.formal_charge = None

    res.num_atoms = int(base_mol.GetNumAtoms())
    res.num_heavy_atoms = int(base_mol.GetNumHeavyAtoms())
    res.molecular_weight = float(round(Descriptors.ExactMolWt(base_mol), 6))
    try:
        res.num_rotatable_bonds = int(Descriptors.NumRotatableBonds(base_mol))
    except Exception:
        res.num_rotatable_bonds = None

    res.warnings.extend(check_unassigned_stereo(base_mol))

    # Just save the 2D file
    # Add hydrogens and 2D coords for downstream usage (e.g. Meeko)
    mol_to_write = Chem.AddHs(base_mol)
    AllChem.Compute2DCoords(mol_to_write)

    output_dir.mkdir(parents=True, exist_ok=True)
    sdf_path = output_dir / f"{safe_stem(name)}.sdf"
    write_sdf(mol_to_write, sdf_path, name=name)
    res.sdf_file = str(sdf_path)

    res.success = True
    return res


def main() -> None:
    p = argparse.ArgumentParser(description="Prepare ligands for docking/analysis (SDF + optional PDBQT).")
    inp = p.add_mutually_exclusive_group(required=True)
    inp.add_argument("--smiles", help="SMILES string for a single molecule")
    inp.add_argument("--sdf", help="Path to input SDF file (multi-molecule supported)")
    inp.add_argument("--smiles_file", help="File with one SMILES per line (optionally with name)")

    p.add_argument("--name", default="ligand", help="Name for single-molecule inputs (SMILES or single SDF record)")
    p.add_argument("--output_dir", default="ligand_prep", help="Output directory")

    # chemistry options
    p.add_argument("--keep_largest_fragment", action="store_true", help="Keep only the largest fragment (salt stripping)")
    p.add_argument("--enumerate_tautomers", action="store_true", help="Enumerate tautomers (heuristic, RDKit MolStandardize)")
    p.add_argument("--max_tautomers", type=int, default=8, help="Max tautomers per protomer to consider")

    p.add_argument("--enumerate_protomers", action="store_true", help="Enumerate ionization states in pH window (Dimorphite-DL)")
    p.add_argument("--ph_min", type=float, default=6.8, help="Min pH for protomer enumeration")
    p.add_argument("--ph_max", type=float, default=7.4, help="Max pH for protomer enumeration")
    p.add_argument("--precision", type=float, default=1.0, help="Dimorphite-DL pKa precision factor")
    p.add_argument("--max_variants", type=int, default=16, help="Max protomers per input (Dimorphite-DL)")

    # outputs
    p.add_argument("--log_level", default="info", choices=["debug", "info", "warning", "error"], help="Logging level")

    args = p.parse_args()
    configure_logging(args.log_level)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: List[PrepResult] = []

    def run_for_smiles(smiles: str, base_name: str, state_index_base: int = 0) -> None:
        nonlocal results

        # optionally enumerate protomers first (from SMILES)
        protomer_smiles: List[str]
        if args.enumerate_protomers:
            protomer_smiles = enumerate_protomers_from_smiles(
                smiles=smiles,
                ph_min=args.ph_min,
                ph_max=args.ph_max,
                precision=args.precision,
                max_variants=args.max_variants,
            )
            LOGGER.info("Enumerated %d protomer(s) for %s", len(protomer_smiles), base_name)
        else:
            protomer_smiles = [smiles]

        state_counter = state_index_base

        for pidx, psmi in enumerate(protomer_smiles):
            pmol = mol_from_smiles(psmi, sanitize=True)
            if pmol is None:
                r = PrepResult(name=f"{base_name}_p{pidx:02d}", success=False, input_smiles=psmi, warnings=[])
                r.error = "Invalid SMILES after protomer enumeration" if args.enumerate_protomers else "Invalid SMILES"
                results.append(r)
                continue

            if args.keep_largest_fragment:
                pmol = keep_largest_fragment(pmol)

            # tautomer enumeration (optional)
            tautomers: List[Chem.Mol]
            if args.enumerate_tautomers:
                tautomers = enumerate_tautomers(pmol, max_tautomers=args.max_tautomers)
                LOGGER.info("Enumerated %d tautomer(s) for %s protomer %d", len(tautomers), base_name, pidx)
            else:
                tautomers = [pmol]

            for tidx, tmol in enumerate(tautomers):
                state_name = base_name
                if args.enumerate_protomers:
                    state_name += f"_p{pidx:02d}"
                if args.enumerate_tautomers:
                    state_name += f"_t{tidx:02d}"

                if state_name == base_name:
                    state_out = out_dir / safe_stem(base_name)
                else:
                    state_out = out_dir / safe_stem(base_name) / safe_stem(state_name)
                r = prepare_one_state(
                    base_mol=tmol,
                    name=state_name,
                    output_dir=state_out,
                )
                r.input_smiles = smiles
                r.state_index = state_counter
                r.protomer_index = pidx if args.enumerate_protomers else None
                r.tautomer_index = tidx if args.enumerate_tautomers else None
                results.append(r)
                state_counter += 1

    if args.smiles:
        base_name = safe_stem(args.name)
        run_for_smiles(args.smiles, base_name)

    elif args.smiles_file:
        smi_path = Path(args.smiles_file)
        for i, (smi, nm) in enumerate(iter_smiles_file(smi_path)):
            base_name = safe_stem(nm)
            LOGGER.info("Preparing %s (%d)", base_name, i)
            run_for_smiles(smi, base_name, state_index_base=i * 1000)

    elif args.sdf:
        sdf_path = Path(args.sdf)
        suppl = Chem.SDMolSupplier(str(sdf_path), removeHs=False, sanitize=True)
        for i, mol in enumerate(suppl):
            if mol is None:
                r = PrepResult(name=f"sdf_mol_{i:05d}", success=False, warnings=[])
                r.error = "Failed to read molecule from SDF (None returned by RDKit)"
                results.append(r)
                continue

            nm = get_mol_name_from_sdf(mol, fallback=f"sdf_mol_{i:05d}")
            nm = safe_stem(nm)

            if args.enumerate_protomers:
                try:
                    smi = Chem.MolToSmiles(Chem.RemoveHs(mol))
                except Exception:
                    smi = None
                if smi is None:
                    r = PrepResult(name=nm, success=False, warnings=[])
                    r.error = "Cannot derive SMILES from SDF record for protomer enumeration"
                    results.append(r)
                    continue
                run_for_smiles(smi, nm, state_index_base=i * 1000)
                continue

            m = mol
            if args.keep_largest_fragment:
                m = keep_largest_fragment(m)

            tautomers = enumerate_tautomers(m, max_tautomers=args.max_tautomers) if args.enumerate_tautomers else [m]
            for tidx, tmol in enumerate(tautomers):
                state_name = nm + (f"_t{tidx:02d}" if args.enumerate_tautomers else "")
                if state_name == nm:
                    state_out = out_dir / safe_stem(nm)
                else:
                    state_out = out_dir / safe_stem(nm) / safe_stem(state_name)
                r = prepare_one_state(
                    base_mol=tmol,
                    name=state_name,
                    output_dir=state_out,
                )
                r.state_index = i
                results.append(r)

    summary_path = out_dir / "preparation_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)

    ok = sum(1 for r in results if r.success)
    LOGGER.info("Done. %d/%d succeeded. Summary: %s", ok, len(results), str(summary_path))


if __name__ == "__main__":
    main()
