"""
Calculate homolytic bond dissociation energies (BDEs) for a molecule.

Uses RDKit to identify bonds and fragment the molecule, then relaxes
the intact molecule and each pair of radical fragments with an MLIP.
BDE = E(frag1) + E(frag2) - E(intact).

Usage:
    python calculate_bde.py --smiles CCO --all_bonds --output_dir results/

Requirements:
    - Conda environment: mace-agent
    - Required packages: ase, rdkit, mace-torch (or matgl/fairchem)
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Import torch early to avoid OpenMP conflicts with RDKit
import torch  # noqa: F401

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np
from ase import Atoms
from ase.io import write
from ase.optimize import FIRE
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors, rdmolops

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("BDE-Skill")

# Unit conversion constants
EV_TO_KJ_MOL = 96.485
EV_TO_KCAL_MOL = 23.0605


from src.utils.mlips.loader import load_wrapper

def smiles_to_mol(smiles: str) -> Chem.Mol:
    """
    Parse SMILES and return an RDKit molecule with explicit Hs and 3D coordinates.

    Args:
        smiles: SMILES string

    Returns:
        RDKit Mol object with 3D coordinates and explicit hydrogens
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Failed to parse SMILES: {smiles}")

    mol = Chem.AddHs(mol)

    # Generate 3D coordinates
    params = AllChem.ETKDGv3()
    status = AllChem.EmbedMolecule(mol, params)
    if status == -1:
        # Retry with random coords
        params.useRandomCoords = True
        status = AllChem.EmbedMolecule(mol, params)
        if status == -1:
            raise RuntimeError(f"Failed to generate 3D coordinates for SMILES: {smiles}")

    # Quick MMFF optimization for a reasonable starting geometry
    AllChem.MMFFOptimizeMolecule(mol, maxIters=200)

    return mol


def mol_to_atoms(mol: Chem.Mol, conf_id: int = 0) -> Atoms:
    """
    Convert RDKit Mol to ASE Atoms.

    Args:
        mol: RDKit Mol object with 3D coordinates
        conf_id: Conformer ID to use

    Returns:
        ASE Atoms object (non-periodic)
    """
    conf = mol.GetConformer(conf_id)
    symbols = [atom.GetSymbol() for atom in mol.GetAtoms()]
    positions = conf.GetPositions()
    atoms = Atoms(symbols=symbols, positions=positions, pbc=False)
    return atoms


def relax_atoms(atoms: Atoms, wrapper: Any, fmax: float = 0.01, steps: int = 500, label: str = "") -> Tuple[Atoms, float]:
    """
    Relax an ASE Atoms object with an MLIP and return the energy.

    Args:
        atoms: ASE Atoms object
        wrapper: MLIP wrapper
        fmax: Force convergence criterion (eV/Å)
        steps: Maximum optimization steps
        label: Label for logging

    Returns:
        Tuple of (relaxed Atoms, energy in eV)
    """
    calc = wrapper.create_calculator()
    atoms.calc = calc

    opt = FIRE(atoms, logfile=None)
    converged = opt.run(fmax=fmax, steps=steps)
    energy = atoms.get_potential_energy()

    status = "converged" if converged else f"NOT converged after {steps} steps"
    logger.info(f"  {label}: E = {energy:.4f} eV ({status}, {opt.nsteps} steps)")

    return atoms, energy


def enumerate_bonds(mol: Chem.Mol, include_h_bonds: bool = False) -> List[Dict]:
    """
    Enumerate all single bonds in a molecule that can be cleaved.

    Args:
        mol: RDKit Mol with explicit Hs
        include_h_bonds: If True, include X-H bonds

    Returns:
        List of dicts with bond info: bond_idx, atom_indices, atom_symbols, in_ring, bond_type
    """
    bonds = []

    for bond in mol.GetBonds():
        # Only cleave single bonds
        if bond.GetBondType() != Chem.rdchem.BondType.SINGLE:
            continue

        idx_i = bond.GetBeginAtomIdx()
        idx_j = bond.GetEndAtomIdx()
        sym_i = mol.GetAtomWithIdx(idx_i).GetSymbol()
        sym_j = mol.GetAtomWithIdx(idx_j).GetSymbol()

        # Skip H bonds unless requested
        if not include_h_bonds:
            if sym_i == "H" or sym_j == "H":
                continue

        in_ring = bond.IsInRing()

        bonds.append({
            "bond_idx": bond.GetIdx(),
            "atom_indices": [idx_i, idx_j],
            "atom_symbols": [sym_i, sym_j],
            "in_ring": in_ring,
            "bond_type": str(bond.GetBondType()),
        })

    return bonds


def fragment_molecule(mol: Chem.Mol, bond_idx: int) -> Tuple[Chem.Mol, Chem.Mol]:
    """
    Fragment a molecule by breaking a bond, producing two radical fragments.

    Uses RDKit's FragmentOnBonds which replaces the broken bond ends with
    dummy atoms (*). We then remove the dummy atoms to produce radicals.

    Args:
        mol: RDKit Mol with explicit Hs
        bond_idx: Index of the bond to break

    Returns:
        Tuple of (frag1_mol, frag2_mol) as RDKit Mol objects with 3D coords
    """
    bond = mol.GetBondWithIdx(bond_idx)
    idx_i = bond.GetBeginAtomIdx()
    idx_j = bond.GetEndAtomIdx()

    # FragmentOnBonds returns a single mol with dummy atoms at break points
    fragmented = Chem.FragmentOnBonds(mol, [bond_idx], addDummies=True)

    # Get the two separate fragment mols
    frag_mols = Chem.GetMolFrags(fragmented, asMols=True, sanitizeFrags=False)

    if len(frag_mols) != 2:
        raise RuntimeError(
            f"Expected 2 fragments from bond {bond_idx} ({idx_i}-{idx_j}), "
            f"got {len(frag_mols)}. This may be a ring bond."
        )

    # Remove dummy atoms from each fragment
    result_frags = []
    for frag in frag_mols:
        result_frags.append(_remove_dummy_atoms(frag))

    return result_frags[0], result_frags[1]


def _remove_dummy_atoms(mol: Chem.Mol) -> Chem.Mol:
    """
    Remove dummy atoms (*) from a molecule fragment.

    After FragmentOnBonds, dummy atoms mark where bonds were broken.
    We remove them to create radical fragments. The atom that was bonded
    to the dummy gets a radical electron set.

    Args:
        mol: RDKit Mol potentially containing dummy atoms

    Returns:
        RDKit Mol with dummy atoms removed
    """
    # Find dummy atom indices (atomic number 0) and their neighbors
    dummy_indices = []
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 0:
            dummy_indices.append(atom.GetIdx())

    if not dummy_indices:
        return mol

    # Build an editable mol
    emol = Chem.RWMol(mol)

    # For each dummy, set radical on its neighbor before removing
    for dummy_idx in dummy_indices:
        dummy_atom = emol.GetAtomWithIdx(dummy_idx)
        for neighbor in dummy_atom.GetNeighbors():
            neighbor.SetNumRadicalElectrons(neighbor.GetNumRadicalElectrons() + 1)

    # Remove dummy atoms in reverse order to preserve indices
    for idx in sorted(dummy_indices, reverse=True):
        emol.RemoveAtom(idx)

    result = emol.GetMol()
    return result


def fragment_to_atoms(frag_mol: Chem.Mol) -> Atoms:
    """
    Convert an RDKit fragment mol to ASE Atoms.

    If 3D coordinates are available from the parent molecule, use them.
    Otherwise, generate new 3D coordinates.

    Args:
        frag_mol: RDKit Mol fragment

    Returns:
        ASE Atoms object (non-periodic)
    """
    # Check if conformer exists
    if frag_mol.GetNumConformers() > 0:
        conf = frag_mol.GetConformer(0)
        positions = conf.GetPositions()
    else:
        # Generate 3D coords for this fragment
        params = AllChem.ETKDGv3()
        params.useRandomCoords = True
        AllChem.EmbedMolecule(frag_mol, params)
        if frag_mol.GetNumConformers() == 0:
            raise RuntimeError("Failed to generate 3D coordinates for fragment")
        positions = frag_mol.GetConformer(0).GetPositions()

    symbols = [atom.GetSymbol() for atom in frag_mol.GetAtoms()]
    atoms = Atoms(symbols=symbols, positions=positions, pbc=False)
    return atoms


def get_formula_from_atoms(atoms: Atoms) -> str:
    """
    Get the molecular formula from an ASE Atoms object.

    Args:
        atoms: ASE Atoms object

    Returns:
        Molecular formula string (e.g., 'CH3', 'C2H5O')
    """
    return atoms.get_chemical_formula(mode="hill")


def compute_single_bde(
    mol: Chem.Mol,
    bond_info: Dict,
    wrapper: Any,
    intact_energy: float,
    fmax: float,
    output_dir: str,
) -> Dict:
    """
    Compute BDE for a single bond.

    Args:
        mol: RDKit Mol of the intact molecule (with explicit Hs, 3D coords)
        bond_info: Dict with bond metadata from enumerate_bonds
        wrapper: MLIP wrapper
        intact_energy: Energy of the relaxed intact molecule (eV)
        fmax: Force convergence for fragment relaxation
        output_dir: Directory to save fragment structures

    Returns:
        Dict with BDE results for this bond
    """
    bond_idx = bond_info["bond_idx"]
    idx_i, idx_j = bond_info["atom_indices"]
    sym_i, sym_j = bond_info["atom_symbols"]
    bond_label = f"{sym_i}({idx_i})-{sym_j}({idx_j})"

    logger.info(f"\nBond {bond_idx}: {bond_label}")

    if bond_info["in_ring"]:
        logger.warning(f"  Skipping ring bond {bond_label} (ring-opening produces a single diradical, not two fragments)")
        return {
            **bond_info,
            "skipped": True,
            "skip_reason": "ring_bond",
        }

    # Fragment the molecule
    frag1_mol, frag2_mol = fragment_molecule(mol, bond_idx)

    # Convert fragments to ASE Atoms
    frag1_atoms = fragment_to_atoms(frag1_mol)
    frag2_atoms = fragment_to_atoms(frag2_mol)

    frag1_formula = get_formula_from_atoms(frag1_atoms)
    frag2_formula = get_formula_from_atoms(frag2_atoms)

    logger.info(f"  Fragments: {frag1_formula} + {frag2_formula}")

    # Relax fragments
    frag1_atoms, e_frag1 = relax_atoms(frag1_atoms, wrapper, fmax=fmax, label=f"Frag1 ({frag1_formula})")
    frag2_atoms, e_frag2 = relax_atoms(frag2_atoms, wrapper, fmax=fmax, label=f"Frag2 ({frag2_formula})")

    # Compute BDE
    bde_eV = e_frag1 + e_frag2 - intact_energy
    bde_kJ_mol = bde_eV * EV_TO_KJ_MOL
    bde_kcal_mol = bde_eV * EV_TO_KCAL_MOL

    logger.info(f"  BDE = {bde_kcal_mol:.1f} kcal/mol ({bde_eV:.4f} eV)")

    # Save fragment structures (strip calculator to avoid stale array issues)
    frag1_path = os.path.join(output_dir, f"frag_bond{bond_idx}_1.xyz")
    frag2_path = os.path.join(output_dir, f"frag_bond{bond_idx}_2.xyz")
    frag1_clean = frag1_atoms.copy()
    frag2_clean = frag2_atoms.copy()
    frag1_clean.calc = None
    frag2_clean.calc = None
    frag1_clean.info = {}
    frag2_clean.info = {}
    frag1_clean.arrays = {k: v for k, v in frag1_clean.arrays.items() if k in ("numbers", "positions")}
    frag2_clean.arrays = {k: v for k, v in frag2_clean.arrays.items() if k in ("numbers", "positions")}
    write(frag1_path, frag1_clean)
    write(frag2_path, frag2_clean)

    return {
        **bond_info,
        "skipped": False,
        "frag1_formula": frag1_formula,
        "frag2_formula": frag2_formula,
        "frag1_energy_eV": float(e_frag1),
        "frag2_energy_eV": float(e_frag2),
        "bde_eV": float(bde_eV),
        "bde_kJ_mol": float(bde_kJ_mol),
        "bde_kcal_mol": float(bde_kcal_mol),
        "frag1_file": os.path.basename(frag1_path),
        "frag2_file": os.path.basename(frag2_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate homolytic bond dissociation energies (BDEs) using MLIPs."
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--smiles", help="SMILES string of the molecule")
    input_group.add_argument("--structure", help="Path to a structure file (.xyz, .sdf, .mol2)")

    parser.add_argument("--bond", help="Specific bond as atom indices, e.g. 0-1 (0-indexed, includes H)")
    parser.add_argument("--all_bonds", action="store_true", default=True,
                        help="Compute BDE for all single bonds (default: True)")
    parser.add_argument("--include_h_bonds", action="store_true", default=False,
                        help="Include X-H bonds (by default only heavy-atom bonds)")

    parser.add_argument("--model_type", default="mace", choices=["mace", "matgl", "fairchem"],
                        help="MLIP backend (default: mace)")
    parser.add_argument("--model_name", default=None,
                        help="Specific model name (default: MACE-OFF23-small for mace)")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")
    parser.add_argument("--task_name", default=None,
                        help="Task head for multi-task models (e.g. omol for FairChem UMA)")

    parser.add_argument("--fmax", type=float, default=0.01,
                        help="Force convergence for relaxation (eV/A, default: 0.01)")
    parser.add_argument("--output_dir", required=True, help="Output directory")

    args = parser.parse_args()

    # Setup output
    os.makedirs(args.output_dir, exist_ok=True)

    # Default model for organics
    if args.model_type == "mace" and args.model_name is None:
        args.model_name = "MACE-OFF23-small"
        logger.info(f"Using default organic model: {args.model_name}")

    # ── Step 1: Parse molecule ──
    logger.info("=" * 60)
    logger.info("Step 1: Parsing molecule")
    logger.info("=" * 60)

    if args.smiles:
        mol = smiles_to_mol(args.smiles)
        smiles_canonical = Chem.MolToSmiles(Chem.RemoveHs(mol))
        logger.info(f"Canonical SMILES: {smiles_canonical}")
    else:
        # Read structure file
        # For structure files, we need RDKit to identify bonds
        if args.structure.endswith(".sdf") or args.structure.endswith(".mol"):
            mol = Chem.MolFromMolFile(args.structure, removeHs=False)
        elif args.structure.endswith(".mol2"):
            mol = Chem.MolFromMol2File(args.structure, removeHs=False)
        else:
            # For XYZ and other formats, read with ASE and use RDKit for connectivity
            from ase.io import read as ase_read
            atoms_from_file = ase_read(args.structure)
            # Build SMILES from ASE (needs xyz2mol or similar)
            raise NotImplementedError(
                "Direct .xyz reading not yet supported. "
                "Please provide SMILES or .sdf/.mol file."
            )

        if mol is None:
            raise ValueError(f"Failed to read molecule from {args.structure}")
        mol = Chem.AddHs(mol, addCoords=True)
        smiles_canonical = Chem.MolToSmiles(Chem.RemoveHs(mol))

    formula = rdMolDescriptors.CalcMolFormula(mol)
    n_atoms = mol.GetNumAtoms()
    logger.info(f"Formula: {formula} ({n_atoms} atoms including H)")

    # ── Step 2: Load MLIP ──
    logger.info("=" * 60)
    logger.info("Step 2: Loading MLIP")
    logger.info("=" * 60)
    wrapper = load_wrapper(args.model_type, args.model_name, args.device, task_name=args.task_name)

    # ── Step 3: Relax intact molecule ──
    logger.info("=" * 60)
    logger.info("Step 3: Relaxing intact molecule")
    logger.info("=" * 60)
    intact_atoms = mol_to_atoms(mol)
    intact_atoms, intact_energy = relax_atoms(
        intact_atoms, wrapper, fmax=args.fmax, label="Intact molecule"
    )
    intact_path = os.path.join(args.output_dir, "intact_relaxed.xyz")
    write(intact_path, intact_atoms)
    logger.info(f"Intact molecule energy: {intact_energy:.4f} eV")

    # ── Step 4: Enumerate bonds ──
    logger.info("=" * 60)
    logger.info("Step 4: Enumerating bonds")
    logger.info("=" * 60)

    if args.bond:
        # Single specific bond
        parts = args.bond.split("-")
        idx_i, idx_j = int(parts[0]), int(parts[1])
        bond_obj = mol.GetBondBetweenAtoms(idx_i, idx_j)
        if bond_obj is None:
            raise ValueError(f"No bond found between atoms {idx_i} and {idx_j}")
        bonds = [{
            "bond_idx": bond_obj.GetIdx(),
            "atom_indices": [idx_i, idx_j],
            "atom_symbols": [mol.GetAtomWithIdx(idx_i).GetSymbol(),
                             mol.GetAtomWithIdx(idx_j).GetSymbol()],
            "in_ring": bond_obj.IsInRing(),
            "bond_type": str(bond_obj.GetBondType()),
        }]
    else:
        bonds = enumerate_bonds(mol, include_h_bonds=args.include_h_bonds)

    logger.info(f"Found {len(bonds)} bonds to analyze:")
    for b in bonds:
        ring_tag = " (ring)" if b["in_ring"] else ""
        logger.info(f"  Bond {b['bond_idx']}: {b['atom_symbols'][0]}({b['atom_indices'][0]})"
                     f"-{b['atom_symbols'][1]}({b['atom_indices'][1]}){ring_tag}")

    # ── Step 5: Compute BDEs ──
    logger.info("=" * 60)
    logger.info("Step 5: Computing BDEs")
    logger.info("=" * 60)

    results = []
    for bond_info in bonds:
        result = compute_single_bde(
            mol=mol,
            bond_info=bond_info,
            wrapper=wrapper,
            intact_energy=intact_energy,
            fmax=args.fmax,
            output_dir=args.output_dir,
        )
        results.append(result)

    # ── Step 6: Rank and save ──
    logger.info("=" * 60)
    logger.info("Step 6: Results summary")
    logger.info("=" * 60)

    # Filter out skipped bonds for ranking
    computed = [r for r in results if not r.get("skipped", False)]
    computed.sort(key=lambda x: x["bde_kcal_mol"])

    # Find weakest bond
    weakest = computed[0] if computed else None

    logger.info(f"\n{'Bond':<20} {'BDE (kcal/mol)':>15} {'BDE (kJ/mol)':>13} {'BDE (eV)':>10}")
    logger.info("-" * 60)
    for r in computed:
        sym_i, sym_j = r["atom_symbols"]
        idx_i, idx_j = r["atom_indices"]
        label = f"{sym_i}({idx_i})-{sym_j}({idx_j})"
        marker = " ← weakest" if r is weakest else ""
        logger.info(f"{label:<20} {r['bde_kcal_mol']:>15.1f} {r['bde_kJ_mol']:>13.1f} {r['bde_eV']:>10.4f}{marker}")

    # Save JSON
    output = {
        "metadata": {
            "smiles": args.smiles,
            "structure_file": args.structure,
            "formula": formula,
            "n_atoms": n_atoms,
            "model_type": args.model_type,
            "model_name": wrapper.model_name,
            "fmax": args.fmax,
            "include_h_bonds": args.include_h_bonds,
        },
        "intact_energy_eV": float(intact_energy),
        "bonds": results,
        "bonds_ranked_by_bde": [
            {
                "bond_label": f"{r['atom_symbols'][0]}({r['atom_indices'][0]})-{r['atom_symbols'][1]}({r['atom_indices'][1]})",
                "bde_kcal_mol": r["bde_kcal_mol"],
                "bde_kJ_mol": r["bde_kJ_mol"],
                "bde_eV": r["bde_eV"],
            }
            for r in computed
        ],
        "weakest_bond": {
            "bond_label": f"{weakest['atom_symbols'][0]}({weakest['atom_indices'][0]})-{weakest['atom_symbols'][1]}({weakest['atom_indices'][1]})",
            "bde_kcal_mol": weakest["bde_kcal_mol"],
        } if weakest else None,
    }

    json_path = os.path.join(args.output_dir, "bde_results.json")
    with open(json_path, "w") as f:
        json.dump(output, f, indent=4)

    logger.info(f"\nResults saved to: {json_path}")
    if weakest:
        logger.info(f"Weakest bond: {weakest['atom_symbols'][0]}({weakest['atom_indices'][0]})"
                     f"-{weakest['atom_symbols'][1]}({weakest['atom_indices'][1]}) "
                     f"= {weakest['bde_kcal_mol']:.1f} kcal/mol")


if __name__ == "__main__":
    main()
