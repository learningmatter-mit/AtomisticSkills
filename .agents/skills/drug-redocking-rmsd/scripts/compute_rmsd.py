"""
Compute symmetry-corrected heavy-atom RMSD between docked poses and a reference ligand.

Given a docked multi-model PDBQT and a reference crystal ligand (PDB or SDF),
computes heavy-atom RMSD for each pose using RDKit's `CalcRMS`, which enumerates
molecular automorphisms and returns the minimum in-place RMSD. "In place" means
no rigid-body alignment is performed between the probe and the reference, which
is the correct comparison for docking validation: in a self-docking experiment
the docked pose and the crystal reference share the receptor's coordinate frame,
so any alignment step would artificially deflate the RMSD and hide failures.

Usage:
    python compute_rmsd.py \\
        --docked docked_poses.pdbqt \\
        --reference crystal_ligand.pdb \\
        --smiles "NS(=O)(=O)c1ccc(Nc2nc3[nH]cnc3c(OCC3CCCCC3)n2)cc1" \\
        --output_dir rmsd_results/

    python compute_rmsd.py \\
        --docked docked_poses.pdbqt \\
        --reference crystal_ligand.sdf \\
        --threshold 1.5 \\
        --output_dir rmsd_results/

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: rdkit (>= 2022.09 for symmetrizeConjugatedTerminalGroups default), meeko, numpy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolAlign


DEFAULT_THRESHOLD_ANGSTROM = 2.0


def load_reference(
    ref_path: Path,
    smiles: str | None = None,
) -> Chem.Mol:
    """
    Load the reference ligand with proper bond orders.

    If the reference is an SDF, load directly. If it is a PDB (HETATM records
    from a crystal structure without bond orders), use the provided SMILES as
    a template to assign bond orders.

    Args:
        ref_path: Path to reference ligand file (PDB or SDF).
        smiles: SMILES string for bond-order assignment when reference is PDB.

    Returns:
        RDKit Mol with 3D coordinates and correct bond orders.
    """
    suffix = ref_path.suffix.lower()

    if suffix == ".sdf":
        suppl = Chem.SDMolSupplier(str(ref_path), removeHs=False)
        mol = next(suppl)
        if mol is None:
            raise ValueError(f"Failed to read SDF: {ref_path}")
        mol = Chem.RemoveHs(mol)
        return mol

    if suffix == ".pdb":
        if smiles is None:
            raise ValueError(
                "Reference is a PDB file (no bond orders). "
                "Provide --smiles to assign bond orders via template matching."
            )
        pdb_mol = Chem.MolFromPDBFile(str(ref_path), removeHs=True, sanitize=False)
        if pdb_mol is None:
            raise ValueError(f"Failed to read PDB: {ref_path}")

        template = Chem.MolFromSmiles(smiles)
        if template is None:
            raise ValueError(f"Invalid SMILES: {smiles}")

        ref_mol = AllChem.AssignBondOrdersFromTemplate(template, pdb_mol)
        ref_mol = Chem.RemoveHs(ref_mol)
        return ref_mol

    raise ValueError(f"Unsupported reference format: {suffix} (use .sdf or .pdb)")


def load_docked_poses(docked_path: Path) -> list[Chem.Mol]:
    """
    Load docked poses from a multi-model PDBQT file.

    Uses Meeko's PDBQTMolecule to properly parse PDBQT atom types and bond
    orders. Meeko returns a single RDKit Mol with N conformers (one per pose);
    this function splits them into separate Mol objects. Poses are in the
    order Vina wrote them, which is sorted by predicted affinity (pose 1 is
    the top-scored pose).

    Args:
        docked_path: Path to docked PDBQT with one or more MODEL blocks.

    Returns:
        List of RDKit Mols (heavy atoms only), one per pose, in score order.
    """
    from meeko import PDBQTMolecule, RDKitMolCreate

    pdbqt_mol = PDBQTMolecule.from_file(str(docked_path), skip_typing=True)
    rdmols = RDKitMolCreate.from_pdbqt_mol(pdbqt_mol, only_cluster_leads=False)

    if not rdmols or rdmols[0] is None:
        raise ValueError(f"Failed to convert PDBQT to RDKit: {docked_path}")

    combined = Chem.RemoveHs(rdmols[0])
    n_confs = combined.GetNumConformers()

    poses = []
    for conf_idx in range(n_confs):
        pose = Chem.RWMol(combined)
        pose.RemoveAllConformers()
        pose.AddConformer(Chem.Conformer(combined.GetConformer(conf_idx)), assignId=True)
        poses.append(pose.GetMol())

    return poses


def check_molecule_identity(ref: Chem.Mol, probe: Chem.Mol) -> None:
    """
    Verify that the reference and probe molecules represent the same compound.

    Compares InChIKeys (first 14 characters, the connectivity-only block) to
    catch the silent-failure mode where a user passes a docked pose of
    compound A against a reference of compound B: CalcRMS will happily produce
    a plausible-looking number if the atom counts line up, but the number is
    meaningless. We compare only the connectivity block so that protonation
    or tautomer differences between the docked form and the crystal form do
    not trigger a false mismatch.

    Args:
        ref: Reference molecule (crystal ligand).
        probe: Docked pose molecule.

    Raises:
        ValueError: If the molecules appear to be different compounds.
    """
    try:
        ref_key = Chem.inchi.MolToInchiKey(ref)
        probe_key = Chem.inchi.MolToInchiKey(probe)
    except Exception as e:
        raise ValueError(f"Cannot compute InChIKey for identity check: {e}")

    ref_connectivity = ref_key.split("-")[0]
    probe_connectivity = probe_key.split("-")[0]

    if ref_connectivity != probe_connectivity:
        raise ValueError(
            f"Reference and docked pose appear to be different molecules. "
            f"Reference InChIKey: {ref_key}, "
            f"docked pose InChIKey: {probe_key}. "
            f"Check that --reference and --docked correspond to the same compound."
        )


def symmetry_corrected_rmsd(
    ref: Chem.Mol,
    probe: Chem.Mol,
) -> float:
    """
    Compute the minimum heavy-atom RMSD over all valid atom mappings.

    Uses RDKit's CalcRMS, which enumerates molecular automorphisms (symmetry
    mappings) and returns the minimum RMSD *without* performing rigid-body
    alignment between probe and reference. This is the correct comparison
    for docking validation: the docked pose and the crystal reference are
    expected to share the receptor's coordinate frame, so any alignment step
    would artificially deflate the RMSD and mask a failing protocol.

    `symmetrizeConjugatedTerminalGroups=True` (default since RDKit 2022.09)
    correctly handles carboxylates, nitro groups, amidinium groups, and other
    conjugated terminal groups where the oxygens or nitrogens are chemically
    equivalent but formally labelled differently. Passed explicitly here for
    provenance and version independence.

    Args:
        ref: Reference molecule with 3D coordinates.
        probe: Docked pose with 3D coordinates.

    Returns:
        Minimum in-place heavy-atom RMSD in Angstroms.
    """
    return float(
        rdMolAlign.CalcRMS(
            probe,
            ref,
            symmetrizeConjugatedTerminalGroups=True,
        )
    )


def compute_all_rmsd(
    docked_path: Path,
    ref_path: Path,
    smiles: str | None,
    output_dir: Path,
    threshold: float = DEFAULT_THRESHOLD_ANGSTROM,
) -> dict:
    """
    Compute RMSD for all docked poses against the reference.

    Args:
        docked_path: Path to docked PDBQT. Poses must be in Vina order (pose 1
            is the top-scored pose).
        ref_path: Path to reference ligand (PDB or SDF).
        smiles: SMILES for bond-order assignment (required if ref is PDB).
        output_dir: Directory to write results.
        threshold: RMSD pass/fail threshold in Angstroms. Applied both to the
            top-pose gate (`gate_pass`) and to each per-pose `pass` flag.

    Returns:
        Dictionary with per-pose RMSD values, top-pose gate verdict, and
        best-of-all-poses diagnostic.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    ref_mol = load_reference(ref_path, smiles)
    poses = load_docked_poses(docked_path)

    if not poses:
        raise ValueError(f"No valid poses loaded from {docked_path}")

    check_molecule_identity(ref_mol, poses[0])

    results = []
    for i, pose in enumerate(poses):
        pose_num = i + 1
        try:
            rmsd = symmetry_corrected_rmsd(ref_mol, pose)
            results.append({
                "pose": pose_num,
                "rmsd_heavy_atom": round(rmsd, 3),
                "pass": rmsd < threshold,
            })
        except Exception as e:
            results.append({
                "pose": pose_num,
                "rmsd_heavy_atom": None,
                "pass": False,
                "error": str(e),
            })

    valid_rmsds = [r["rmsd_heavy_atom"] for r in results if r["rmsd_heavy_atom"] is not None]
    best_rmsd = min(valid_rmsds) if valid_rmsds else None
    best_pose = None
    if best_rmsd is not None:
        best_pose = next(r["pose"] for r in results if r["rmsd_heavy_atom"] == best_rmsd)

    top_pose_result = results[0] if results else None
    top_pose_rmsd = top_pose_result["rmsd_heavy_atom"] if top_pose_result else None

    summary = {
        "reference": str(ref_path.name),
        "docked": str(docked_path.name),
        "n_poses": len(poses),
        "threshold": threshold,
        "top_pose_rmsd": top_pose_rmsd,
        "gate_pass": top_pose_rmsd is not None and top_pose_rmsd < threshold,
        "gate_criterion": (
            "Top-scored docked pose (pose 1) heavy-atom RMSD below threshold. "
            "Standard self-docking validation metric: a near-native pose "
            "somewhere in the pose ensemble is not sufficient if the scoring "
            "function cannot rank it first."
        ),
        "best_rmsd": best_rmsd,
        "best_pose": best_pose,
        "best_rmsd_note": (
            "best_rmsd is the minimum RMSD across all poses. Use as a "
            "diagnostic only: if best_pose > 1 but best_rmsd < threshold, "
            "the docking is sampling near-native conformations but the "
            "scoring function is failing to prioritize them."
        ),
        "poses": results,
    }

    out_file = output_dir / "rmsd_results.json"
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=4)

    print(json.dumps(summary, indent=4))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute symmetry-corrected in-place heavy-atom RMSD between docked poses and a reference ligand."
    )
    parser.add_argument(
        "--docked", required=True, type=Path,
        help="Path to docked poses (multi-model PDBQT, poses in Vina score order).",
    )
    parser.add_argument(
        "--reference", required=True, type=Path,
        help="Path to reference crystal ligand (PDB or SDF).",
    )
    parser.add_argument(
        "--smiles", default=None,
        help="SMILES for bond-order assignment (required if reference is PDB).",
    )
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD_ANGSTROM,
        help=(
            "RMSD pass/fail threshold in Angstroms (default: 2.0). "
            "Consider 1.5 for small rigid fragments or 2.5-3.0 for large flexible ligands. "
            "See SKILL.md for guidance."
        ),
    )
    parser.add_argument(
        "--output_dir", type=Path, default=Path("rmsd_results"),
        help="Directory to write results.",
    )

    args = parser.parse_args()
    compute_all_rmsd(
        args.docked,
        args.reference,
        args.smiles,
        args.output_dir,
        threshold=args.threshold,
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
