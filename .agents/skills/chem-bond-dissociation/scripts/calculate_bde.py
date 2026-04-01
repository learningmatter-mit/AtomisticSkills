"""
Calculate homolytic and/or heterolytic bond dissociation energies (BDEs) for a molecule.

Uses RDKit to identify bonds and fragment the molecule, then relaxes the intact
molecule and each pair of radical/ionic fragments with an MLIP.

Homolytic BDE:
    BDE_homo(A-B) = E(A·) + E(B·) - E(A-B)

Heterolytic BDE (minimum over both polarity variants):
    BDE_hetero(A-B) = min(
        E(A+) + E(B-),
        E(A-) + E(B+)
    ) - E(A-B)

Heterolytic calculations require a model that honours charge and spin multiplicity
(``wrapper.supports_charge_spin == True``).  Supported models:
    - MACE-OMOL-extra-large, MACE-MH-1  (reads ``charge``/``spin`` from atoms.info)
    - FairChem UMA/ESEN with task_name="omol"  (reads ``charge``/``spin`` from atoms.info)

Usage:
    python calculate_bde.py --smiles CCO --all_bonds --cleavage both \\
        --model_type mace --model_name MACE-OMOL-extra-large \\
        --output_dir results/

Requirements:
    - Conda environment: mace-agent (for MACE) or fairchem-agent (for FairChem)
    - Required packages: ase, rdkit, mace-torch (or fairchem-core)
"""

import argparse
import json
import logging
import os
import sys
from copy import deepcopy
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


# ---------------------------------------------------------------------------
# Molecule helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Charge / spin helpers
# ---------------------------------------------------------------------------

# Mapping from (model_type, canonical_name_upper) → info key names.
# Confirmed from MACECalculator.__init__ source:
#   info_keys default = {"total_spin": "spin", "total_charge": "charge"}
# i.e., the calculator reads atoms.info["charge"] → total_charge, atoms.info["spin"] → total_spin
# For FairChem omol the calculator reads: atoms.info["charge"], atoms.info["spin"] (same)
_MACE_CHARGE_KEYS   = ("charge", "spin")    # MACE-OMOL, MACE-MH (omol head)
_FAIRCHEM_OMOL_KEYS = ("charge", "spin")


def _get_info_keys(model_type: str, model_name: str) -> Tuple[str, str]:
    """
    Return the (charge_key, spin_key) strings that the given model reads from atoms.info.

    Args:
        model_type: One of "mace", "fairchem", "matgl".
        model_name: Concrete model name (e.g. "MACE-OMOL-extra-large", "MACE-MH-1").

    Returns:
        Tuple of (charge_key, spin_key).
    """
    if model_type == "mace" and wrapper_supports_mace_charge(model_name):
        return _MACE_CHARGE_KEYS
    if model_type == "fairchem":
        return _FAIRCHEM_OMOL_KEYS
    # Should not be reached for models that don't support charge/spin
    raise ValueError(
        f"Model {model_name!r} (type={model_type!r}) does not support charge/spin. "
        "Check wrapper.supports_charge_spin before calling this function."
    )


def wrapper_supports_mace_charge(model_name: str) -> bool:
    """Return True for MACE models that use joint_embedding to condition on charge/spin."""
    name_upper = model_name.upper()
    return "OMOL" in name_upper or "MACE-MH" in name_upper


def set_charge_spin(
    atoms: Atoms,
    charge: int,
    spin_multiplicity: int,
    charge_key: str,
    spin_key: str,
) -> Atoms:
    """
    Return a copy of *atoms* with charge and spin multiplicity written to atoms.info.

    The correct key names depend on the MLIP backend (see _get_info_keys).

    Args:
        atoms: ASE Atoms object to annotate.
        charge: Total charge (+1 for cation, -1 for anion, 0 for neutral).
        spin_multiplicity: 1 = singlet (closed-shell), 2 = doublet (radical), etc.
        charge_key: Key to store charge in atoms.info.
        spin_key: Key to store spin multiplicity in atoms.info.

    Returns:
        New ASE Atoms with updated info dict.
    """
    atoms_copy = atoms.copy()
    atoms_copy.info[charge_key] = charge
    atoms_copy.info[spin_key] = spin_multiplicity
    return atoms_copy


# ---------------------------------------------------------------------------
# Relaxation
# ---------------------------------------------------------------------------

def relax_atoms(
    atoms: Atoms,
    wrapper: Any,
    fmax: float = 0.01,
    steps: int = 500,
    label: str = "",
) -> Tuple[Atoms, float]:
    """
    Relax an ASE Atoms object with an MLIP and return the energy.

    Args:
        atoms: ASE Atoms object (may contain charge/spin in atoms.info)
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


# ---------------------------------------------------------------------------
# Bond enumeration / fragmentation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# File saving helper
# ---------------------------------------------------------------------------

def _save_fragment(atoms: Atoms, path: str) -> None:
    """Write a fragment to an XYZ file, stripping calculator and non-essential arrays."""
    clean = atoms.copy()
    clean.calc = None
    clean.info = {}
    clean.arrays = {k: v for k, v in clean.arrays.items() if k in ("numbers", "positions")}
    write(path, clean)


# ---------------------------------------------------------------------------
# BDE computation: homolytic
# ---------------------------------------------------------------------------

def compute_single_bde_homolytic(
    mol: Chem.Mol,
    bond_info: Dict,
    wrapper: Any,
    intact_energy: float,
    fmax: float,
    output_dir: str,
    charge_key: Optional[str] = None,
    spin_key: Optional[str] = None,
) -> Dict:
    """
    Compute homolytic BDE for a single bond (radical + radical).

    BDE_homo = E(A·) + E(B·) - E(A-B)

    Args:
        mol: RDKit Mol of the intact molecule (with explicit Hs, 3D coords)
        bond_info: Dict with bond metadata from enumerate_bonds
        wrapper: MLIP wrapper
        intact_energy: Energy of the relaxed intact molecule (eV)
        fmax: Force convergence for fragment relaxation
        output_dir: Directory to save fragment structures

    Returns:
        Dict with homolytic BDE results; keys prefixed with nothing (backward-compat).
    """
    bond_idx = bond_info["bond_idx"]
    idx_i, idx_j = bond_info["atom_indices"]
    sym_i, sym_j = bond_info["atom_symbols"]
    bond_label = f"{sym_i}({idx_i})-{sym_j}({idx_j})"

    logger.info(f"\nBond {bond_idx}: {bond_label} — homolytic")

    if bond_info["in_ring"]:
        logger.warning(
            f"  Skipping ring bond {bond_label} "
            "(ring-opening produces a single diradical, not two fragments)"
        )
        return {**bond_info, "skipped": True, "skip_reason": "ring_bond"}

    # Fragment the molecule
    frag1_mol, frag2_mol = fragment_molecule(mol, bond_idx)

    # Convert fragments to ASE Atoms (neutral radicals: charge=0, spin=2)
    frag1_atoms = fragment_to_atoms(frag1_mol)
    frag2_atoms = fragment_to_atoms(frag2_mol)

    frag1_formula = get_formula_from_atoms(frag1_atoms)
    frag2_formula = get_formula_from_atoms(frag2_atoms)

    logger.info(f"  Fragments: {frag1_formula}· + {frag2_formula}·")

    # When the model supports charge/spin, annotate fragments as neutral radicals (charge=0, spin=1)
    # so the model doesn't warn about missing charge/spin keys in atoms.info.
    if charge_key is not None and spin_key is not None:
        frag1_atoms = set_charge_spin(frag1_atoms, 0, 1, charge_key, spin_key)
        frag2_atoms = set_charge_spin(frag2_atoms, 0, 1, charge_key, spin_key)

    # Relax fragments
    frag1_atoms, e_frag1 = relax_atoms(
        frag1_atoms, wrapper, fmax=fmax, label=f"Frag1 ({frag1_formula}·)"
    )
    frag2_atoms, e_frag2 = relax_atoms(
        frag2_atoms, wrapper, fmax=fmax, label=f"Frag2 ({frag2_formula}·)"
    )

    # Compute BDE
    bde_eV = e_frag1 + e_frag2 - intact_energy
    bde_kJ_mol = bde_eV * EV_TO_KJ_MOL
    bde_kcal_mol = bde_eV * EV_TO_KCAL_MOL

    logger.info(f"  Homolytic BDE = {bde_kcal_mol:.1f} kcal/mol ({bde_eV:.4f} eV)")

    # Save fragment structures
    _save_fragment(frag1_atoms, os.path.join(output_dir, f"frag_bond{bond_idx}_homo_1.xyz"))
    _save_fragment(frag2_atoms, os.path.join(output_dir, f"frag_bond{bond_idx}_homo_2.xyz"))

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
        "frag1_file": f"frag_bond{bond_idx}_homo_1.xyz",
        "frag2_file": f"frag_bond{bond_idx}_homo_2.xyz",
    }


# ---------------------------------------------------------------------------
# BDE computation: heterolytic
# ---------------------------------------------------------------------------

def compute_single_bde_heterolytic(
    mol: Chem.Mol,
    bond_info: Dict,
    wrapper: Any,
    intact_energy: float,
    fmax: float,
    output_dir: str,
    charge_key: str,
    spin_key: str,
) -> Dict:
    """
    Compute heterolytic BDE for a single bond (cation + anion).

    Two polarity variants are always evaluated:
        Variant A:  E(frag1+) + E(frag2-)   (frag1 loses electron)
        Variant B:  E(frag1-) + E(frag2+)   (frag2 loses electron)

    The reported heterolytic BDE is the minimum of the two.  Both raw variants
    are included in the output for transparency.

    Ionic fragments are treated as closed-shell singlets (spin_multiplicity=1).

    Args:
        mol: RDKit Mol of the intact molecule.
        bond_info: Dict with bond metadata from enumerate_bonds.
        wrapper: MLIP wrapper (must have supports_charge_spin == True).
        intact_energy: Energy of the relaxed intact molecule (eV).
        fmax: Force convergence for fragment relaxation.
        output_dir: Directory to save fragment structures.
        charge_key: atoms.info key for charge (model-dependent).
        spin_key: atoms.info key for spin multiplicity (model-dependent).

    Returns:
        Dict with heterolytic BDE results.
    """
    bond_idx = bond_info["bond_idx"]
    idx_i, idx_j = bond_info["atom_indices"]
    sym_i, sym_j = bond_info["atom_symbols"]
    bond_label = f"{sym_i}({idx_i})-{sym_j}({idx_j})"

    logger.info(f"\nBond {bond_idx}: {bond_label} — heterolytic")

    if bond_info["in_ring"]:
        logger.warning(
            f"  Skipping ring bond {bond_label} "
            "(ring-opening produces a single diradical)"
        )
        return {
            **bond_info,
            "skipped": True,
            "skip_reason": "ring_bond",
            "heterolytic_bde_eV": None,
            "heterolytic_bde_kJ_mol": None,
            "heterolytic_bde_kcal_mol": None,
            "heterolytic_variants": [],
        }

    # Obtain base fragment atoms (neutral geometry — good starting point for ionic relax)
    frag1_mol, frag2_mol = fragment_molecule(mol, bond_idx)
    frag1_base = fragment_to_atoms(frag1_mol)
    frag2_base = fragment_to_atoms(frag2_mol)

    frag1_formula = get_formula_from_atoms(frag1_base)
    frag2_formula = get_formula_from_atoms(frag2_base)

    logger.info(f"  Fragments: {frag1_formula} / {frag2_formula}")

    # FairChem UMA (and similar models) only have neutral single-atom energies in their
    # lookup table. A charged single-atom fragment (e.g. H⁻, H⁺) cannot be computed.
    # Skip heterolytic BDE for bonds that produce any single-atom fragment.
    if len(frag1_base) == 1 or len(frag2_base) == 1:
        logger.warning(
            f"  Skipping heterolytic BDE for bond {bond_label}: one fragment is a single atom "
            f"({frag1_formula}/{frag2_formula}). The model only stores neutral single-atom energies "
            "and cannot compute ionic single-atom fragments."
        )
        return {
            **bond_info,
            "skipped_heterolytic": True,
            "skip_reason_heterolytic": "single_atom_fragment",
            "frag1_formula": frag1_formula,
            "frag2_formula": frag2_formula,
            "heterolytic_bde_eV": None,
            "heterolytic_bde_kJ_mol": None,
            "heterolytic_bde_kcal_mol": None,
            "heterolytic_best_variant": None,
            "heterolytic_variants": [],
        }

    variants = []

    for variant_label, c1, c2 in [
        ("frag1+ / frag2-", +1, -1),
        ("frag1- / frag2+", -1, +1),
    ]:
        logger.info(f"  Variant: {variant_label}")

        # Annotate charge/spin on fresh copies
        f1 = set_charge_spin(frag1_base, charge=c1, spin_multiplicity=1,
                             charge_key=charge_key, spin_key=spin_key)
        f2 = set_charge_spin(frag2_base, charge=c2, spin_multiplicity=1,
                             charge_key=charge_key, spin_key=spin_key)

        f1_lbl = f"Frag1 ({frag1_formula}, q={c1:+d})"
        f2_lbl = f"Frag2 ({frag2_formula}, q={c2:+d})"

        f1, e1 = relax_atoms(f1, wrapper, fmax=fmax, label=f1_lbl)
        f2, e2 = relax_atoms(f2, wrapper, fmax=fmax, label=f2_lbl)

        bde_eV = e1 + e2 - intact_energy
        bde_kcal_mol = bde_eV * EV_TO_KCAL_MOL

        logger.info(f"    BDE ({variant_label}) = {bde_kcal_mol:.1f} kcal/mol")

        # Save fragment structures
        polarity = "pos_neg" if c1 == +1 else "neg_pos"
        _save_fragment(f1, os.path.join(output_dir, f"frag_bond{bond_idx}_hetero_{polarity}_1.xyz"))
        _save_fragment(f2, os.path.join(output_dir, f"frag_bond{bond_idx}_hetero_{polarity}_2.xyz"))

        variants.append({
            "variant": variant_label,
            "frag1_charge": c1,
            "frag2_charge": c2,
            "frag1_energy_eV": float(e1),
            "frag2_energy_eV": float(e2),
            "bde_eV": float(bde_eV),
            "bde_kJ_mol": float(bde_eV * EV_TO_KJ_MOL),
            "bde_kcal_mol": float(bde_kcal_mol),
            "frag1_file": f"frag_bond{bond_idx}_hetero_{polarity}_1.xyz",
            "frag2_file": f"frag_bond{bond_idx}_hetero_{polarity}_2.xyz",
        })

    # Best (lowest) heterolytic BDE
    best = min(variants, key=lambda v: v["bde_eV"])

    logger.info(
        f"  Best heterolytic BDE = {best['bde_kcal_mol']:.1f} kcal/mol "
        f"({best['variant']})"
    )

    return {
        **bond_info,
        "skipped": False,
        "frag1_formula": frag1_formula,
        "frag2_formula": frag2_formula,
        "heterolytic_bde_eV": best["bde_eV"],
        "heterolytic_bde_kJ_mol": best["bde_kJ_mol"],
        "heterolytic_bde_kcal_mol": best["bde_kcal_mol"],
        "heterolytic_best_variant": best["variant"],
        "heterolytic_variants": variants,
    }


# ---------------------------------------------------------------------------
# Unified dispatcher
# ---------------------------------------------------------------------------

def compute_bond_bde(
    mol: Chem.Mol,
    bond_info: Dict,
    wrapper: Any,
    intact_energy: float,
    fmax: float,
    output_dir: str,
    cleavage: str,
    charge_key: Optional[str],
    spin_key: Optional[str],
) -> Dict:
    """
    Dispatch homolytic and/or heterolytic BDE calculation for one bond.

    Args:
        mol: RDKit Mol of the intact molecule.
        bond_info: Bond metadata dict.
        wrapper: Loaded MLIP wrapper.
        intact_energy: Relaxed intact molecule energy (eV).
        fmax: Force convergence (eV/Å).
        output_dir: Output directory for fragment files.
        cleavage: One of "homolytic", "heterolytic", "both".
        charge_key: atoms.info key for charge (required for heterolytic/both).
        spin_key: atoms.info key for spin (required for heterolytic/both).

    Returns:
        Merged result dict with all computed BDE data.
    """
    result: Dict = {}

    if cleavage in ("homolytic", "both"):
        homo = compute_single_bde_homolytic(
            mol, bond_info, wrapper, intact_energy, fmax, output_dir,
            charge_key=charge_key,
            spin_key=spin_key,
        )
        result.update(homo)

    if cleavage in ("heterolytic", "both"):
        hetero = compute_single_bde_heterolytic(
            mol, bond_info, wrapper, intact_energy, fmax, output_dir,
            charge_key=charge_key,
            spin_key=spin_key,
        )
        # Merge heterolytic-specific keys; avoid clobbering base keys already set
        for k, v in hetero.items():
            if k not in result:
                result[k] = v
            elif k.startswith("heterolytic"):
                result[k] = v

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate homolytic and/or heterolytic bond dissociation energies (BDEs) "
            "using MLIPs.  Heterolytic BDE requires a model with charge/spin support "
            "(e.g. MACE-OMOL-extra-large or FairChem UMA with --task_name omol)."
        )
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--smiles", help="SMILES string of the molecule")
    input_group.add_argument("--structure", help="Path to a structure file (.xyz, .sdf, .mol2)")

    parser.add_argument("--bond", help="Specific bond as atom indices, e.g. 0-1 (0-indexed, includes H)")
    parser.add_argument("--all_bonds", action="store_true", default=True,
                        help="Compute BDE for all single bonds (default: True)")
    parser.add_argument("--include_h_bonds", action="store_true", default=False,
                        help="Include X-H bonds (by default only heavy-atom bonds)")

    parser.add_argument(
        "--cleavage",
        default="homolytic",
        choices=["homolytic", "heterolytic", "both"],
        help=(
            "Cleavage mode to compute. "
            "'homolytic' (default): radical fragments. "
            "'heterolytic': cation+anion pairs (requires charge/spin-aware MLIP). "
            "'both': compute and report both modes."
        ),
    )

    parser.add_argument("--model_type", default="mace", choices=["mace", "matgl", "fairchem"],
                        help="MLIP backend (default: mace)")
    parser.add_argument("--model_name", default=None,
                        help="Specific model name (default: MACE-OFF23-small for homolytic, "
                             "MACE-OMOL-extra-large for heterolytic/both)")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")
    parser.add_argument("--task_name", default=None,
                        help="Task head for multi-task models (e.g. omol for FairChem UMA)")

    parser.add_argument("--fmax", type=float, default=0.01,
                        help="Force convergence for relaxation (eV/Å, default: 0.01)")
    parser.add_argument("--output_dir", required=True, help="Output directory")

    args = parser.parse_args()

    # Setup output
    os.makedirs(args.output_dir, exist_ok=True)

    # Default model selection
    needs_charge_spin = args.cleavage in ("heterolytic", "both")
    if args.model_type == "mace" and args.model_name is None:
        if needs_charge_spin:
            args.model_name = "MACE-OMOL-extra-large"
            logger.info(f"Using default charge/spin-aware model: {args.model_name}")
        else:
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
        if args.structure.endswith(".sdf") or args.structure.endswith(".mol"):
            mol = Chem.MolFromMolFile(args.structure, removeHs=False)
        elif args.structure.endswith(".mol2"):
            mol = Chem.MolFromMol2File(args.structure, removeHs=False)
        else:
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

    # ── Step 2b: Validate charge/spin capability ──
    if needs_charge_spin and not wrapper.supports_charge_spin:
        if args.cleavage == "heterolytic":
            raise RuntimeError(
                f"Model '{wrapper.model_name}' (type={args.model_type!r}) does not support "
                "charge and spin multiplicity (wrapper.supports_charge_spin == False). "
                "Heterolytic BDE requires a charge/spin-aware model such as "
                "MACE-OMOL-extra-large or FairChem UMA with --task_name omol."
            )
        else:  # cleavage == "both"
            logger.warning(
                f"Model '{wrapper.model_name}' does not support charge/spin "
                "(wrapper.supports_charge_spin == False). "
                "Heterolytic BDE will be skipped; only homolytic BDE will be computed."
            )
            args.cleavage = "homolytic"
            needs_charge_spin = False

    # Determine info keys for charge/spin (only needed if actually computing heterolytic)
    charge_key: Optional[str] = None
    spin_key: Optional[str] = None
    if needs_charge_spin:
        charge_key, spin_key = _get_info_keys(args.model_type, wrapper.model_name)
        logger.info(
            f"Charge/spin keys: atoms.info['{charge_key}'] / atoms.info['{spin_key}']"
        )

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
        logger.info(
            f"  Bond {b['bond_idx']}: {b['atom_symbols'][0]}({b['atom_indices'][0]})"
            f"-{b['atom_symbols'][1]}({b['atom_indices'][1]}){ring_tag}"
        )

    # ── Step 5: Compute BDEs ──
    logger.info("=" * 60)
    logger.info(f"Step 5: Computing BDEs (cleavage={args.cleavage})")
    logger.info("=" * 60)

    results = []
    for bond_info in bonds:
        result = compute_bond_bde(
            mol=mol,
            bond_info=bond_info,
            wrapper=wrapper,
            intact_energy=intact_energy,
            fmax=args.fmax,
            output_dir=args.output_dir,
            cleavage=args.cleavage,
            charge_key=charge_key,
            spin_key=spin_key,
        )
        results.append(result)

    # ── Step 6: Rank and save ──
    logger.info("=" * 60)
    logger.info("Step 6: Results summary")
    logger.info("=" * 60)

    computed = [r for r in results if not r.get("skipped", False)]

    # --- Homolytic ranking ---
    weakest_homo = None
    if args.cleavage in ("homolytic", "both"):
        homo_results = [r for r in computed if "bde_kcal_mol" in r]
        homo_results.sort(key=lambda x: x["bde_kcal_mol"])
        weakest_homo = homo_results[0] if homo_results else None

        logger.info(f"\n{'Bond':<20} {'Homolytic BDE (kcal/mol)':>24}")
        logger.info("-" * 46)
        for r in homo_results:
            sym_i, sym_j = r["atom_symbols"]
            idx_i, idx_j = r["atom_indices"]
            label = f"{sym_i}({idx_i})-{sym_j}({idx_j})"
            marker = " ← weakest" if r is weakest_homo else ""
            logger.info(f"{label:<20} {r['bde_kcal_mol']:>24.1f}{marker}")

    # --- Heterolytic ranking ---
    weakest_hetero = None
    if args.cleavage in ("heterolytic", "both"):
        hetero_results = [r for r in computed if r.get("heterolytic_bde_kcal_mol") is not None]
        hetero_results.sort(key=lambda x: x["heterolytic_bde_kcal_mol"])
        weakest_hetero = hetero_results[0] if hetero_results else None

        logger.info(f"\n{'Bond':<20} {'Heterolytic BDE (kcal/mol)':>26}")
        logger.info("-" * 48)
        for r in hetero_results:
            sym_i, sym_j = r["atom_symbols"]
            idx_i, idx_j = r["atom_indices"]
            label = f"{sym_i}({idx_i})-{sym_j}({idx_j})"
            marker = " ← weakest" if r is weakest_hetero else ""
            logger.info(f"{label:<20} {r['heterolytic_bde_kcal_mol']:>26.1f}{marker}")

    # Save JSON
    output = {
        "metadata": {
            "smiles": args.smiles,
            "structure_file": args.structure if not args.smiles else None,
            "formula": formula,
            "n_atoms": n_atoms,
            "model_type": args.model_type,
            "model_name": wrapper.model_name,
            "supports_charge_spin": wrapper.supports_charge_spin,
            "fmax": args.fmax,
            "include_h_bonds": args.include_h_bonds,
            "cleavage": args.cleavage,
        },
        "intact_energy_eV": float(intact_energy),
        "bonds": results,
    }

    # Homolytic ranking table
    if args.cleavage in ("homolytic", "both"):
        output["bonds_ranked_by_homolytic_bde"] = [
            {
                "bond_label": f"{r['atom_symbols'][0]}({r['atom_indices'][0]})"
                              f"-{r['atom_symbols'][1]}({r['atom_indices'][1]})",
                "bde_kcal_mol": r["bde_kcal_mol"],
                "bde_kJ_mol": r["bde_kJ_mol"],
                "bde_eV": r["bde_eV"],
            }
            for r in (homo_results if weakest_homo else [])
        ]
        output["weakest_bond_homolytic"] = {
            "bond_label": (
                f"{weakest_homo['atom_symbols'][0]}({weakest_homo['atom_indices'][0]})"
                f"-{weakest_homo['atom_symbols'][1]}({weakest_homo['atom_indices'][1]})"
            ),
            "bde_kcal_mol": weakest_homo["bde_kcal_mol"],
        } if weakest_homo else None

    # Heterolytic ranking table
    if args.cleavage in ("heterolytic", "both"):
        output["bonds_ranked_by_heterolytic_bde"] = [
            {
                "bond_label": f"{r['atom_symbols'][0]}({r['atom_indices'][0]})"
                              f"-{r['atom_symbols'][1]}({r['atom_indices'][1]})",
                "heterolytic_bde_kcal_mol": r["heterolytic_bde_kcal_mol"],
                "heterolytic_bde_kJ_mol": r["heterolytic_bde_kJ_mol"],
                "heterolytic_bde_eV": r["heterolytic_bde_eV"],
                "best_variant": r.get("heterolytic_best_variant"),
            }
            for r in (hetero_results if weakest_hetero else [])
        ]
        output["weakest_bond_heterolytic"] = {
            "bond_label": (
                f"{weakest_hetero['atom_symbols'][0]}({weakest_hetero['atom_indices'][0]})"
                f"-{weakest_hetero['atom_symbols'][1]}({weakest_hetero['atom_indices'][1]})"
            ),
            "heterolytic_bde_kcal_mol": weakest_hetero["heterolytic_bde_kcal_mol"],
            "best_variant": weakest_hetero.get("heterolytic_best_variant"),
        } if weakest_hetero else None

    # Backward-compat alias used by the homolytic-only API
    if args.cleavage == "homolytic":
        output["weakest_bond"] = output.get("weakest_bond_homolytic")
        output["bonds_ranked_by_bde"] = output.get("bonds_ranked_by_homolytic_bde", [])

    json_path = os.path.join(args.output_dir, "bde_results.json")
    with open(json_path, "w") as f:
        json.dump(output, f, indent=4)

    logger.info(f"\nResults saved to: {json_path}")
    if weakest_homo:
        logger.info(
            f"Weakest bond (homolytic): "
            f"{weakest_homo['atom_symbols'][0]}({weakest_homo['atom_indices'][0]})"
            f"-{weakest_homo['atom_symbols'][1]}({weakest_homo['atom_indices'][1]}) "
            f"= {weakest_homo['bde_kcal_mol']:.1f} kcal/mol"
        )
    if weakest_hetero:
        logger.info(
            f"Weakest bond (heterolytic): "
            f"{weakest_hetero['atom_symbols'][0]}({weakest_hetero['atom_indices'][0]})"
            f"-{weakest_hetero['atom_symbols'][1]}({weakest_hetero['atom_indices'][1]}) "
            f"= {weakest_hetero['heterolytic_bde_kcal_mol']:.1f} kcal/mol "
            f"({weakest_hetero.get('heterolytic_best_variant', '')})"
        )


if __name__ == "__main__":
    main()
