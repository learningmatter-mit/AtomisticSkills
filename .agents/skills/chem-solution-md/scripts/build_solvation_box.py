"""
Build a solvation box for solution-phase MD using Packmol.

Generates 3D geometries from SMILES (via RDKit), packs them into a periodic
box using Packmol (via pymatgen's PackmolBoxGen), and writes the result as
both XYZ and CIF files.

Usage:
    python build_solvation_box.py --solvent water --num_solvent 64 --output_dir my_box
    python build_solvation_box.py --solute_smiles "[Na+].[Cl-]" --solvent water --num_solvent 64 --output_dir my_box
    python build_solvation_box.py --solute_file solute.xyz --solvent_smiles "O" --num_solvent 100 --output_dir my_box

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, rdkit, ase, pyyaml
    - External binary: packmol (must be on PATH)
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import yaml
from ase import Atoms
from ase.io import write as ase_write
from pymatgen.core import Lattice, Molecule, Structure
from pymatgen.io.packmol import PackmolBoxGen
from rdkit import Chem
from rdkit.Chem import AllChem

# Path to the solvent library
RESOURCES_DIR = Path(__file__).parent.parent / "resources"
SOLVENTS_YAML = RESOURCES_DIR / "common_solvents.yaml"


def smiles_to_molecule(smiles: str, name: str = "molecule") -> Molecule:
    """
    Convert a SMILES string to a pymatgen Molecule via RDKit 3D embedding.

    Args:
        smiles: SMILES string (may contain '.' for multi-fragment like '[Na+].[Cl-]').
        name: Name for logging purposes.

    Returns:
        pymatgen Molecule object with 3D coordinates.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit could not parse SMILES: {smiles}")

    mol = Chem.AddHs(mol)
    result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if result == -1:
        # Retry with random coordinates
        result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        if result == -1:
            raise ValueError(f"RDKit failed to generate 3D coordinates for: {smiles}")

    AllChem.MMFFOptimizeMolecule(mol, maxIters=500)

    # Extract coordinates and species
    conf = mol.GetConformer()
    species = []
    coords = []
    for i, atom in enumerate(mol.GetAtoms()):
        species.append(atom.GetSymbol())
        pos = conf.GetAtomPosition(i)
        coords.append([pos.x, pos.y, pos.z])

    pmg_mol = Molecule(species, coords)
    print(f"  Generated 3D geometry for {name}: {pmg_mol.formula} ({len(pmg_mol)} atoms)")
    return pmg_mol


def load_solvent_library() -> dict:
    """
    Load the common solvents library from YAML.

    Returns:
        Dictionary mapping solvent names to their properties.
    """
    if not SOLVENTS_YAML.exists():
        raise FileNotFoundError(f"Solvent library not found: {SOLVENTS_YAML}")
    with open(SOLVENTS_YAML, "r") as f:
        return yaml.safe_load(f)


def calculate_box_size(
    solvent_mol: Molecule,
    num_solvent: int,
    density_g_cm3: float,
    molecular_weight: float,
    solute_mol: Optional[Molecule] = None,
) -> float:
    """
    Calculate the cubic box side length from target density.

    Uses the formula: L = (N * M / (rho * N_A))^(1/3)
    where N is total number of molecules, M is molecular weight,
    rho is density, and N_A is Avogadro's number.

    Args:
        solvent_mol: Pymatgen Molecule for the solvent.
        num_solvent: Number of solvent molecules.
        density_g_cm3: Target density in g/cm³.
        molecular_weight: Solvent molecular weight in g/mol.
        solute_mol: Optional solute molecule.

    Returns:
        Box side length in Angstroms.
    """
    avogadro = 6.02214076e23

    # Total mass in grams
    total_mass_g = num_solvent * molecular_weight / avogadro
    if solute_mol is not None:
        solute_mass_g = sum(el.atomic_mass for el in solute_mol.species) / avogadro
        total_mass_g += solute_mass_g

    # Volume in cm³ then convert to ų (1 cm = 1e8 Å)
    volume_cm3 = total_mass_g / density_g_cm3
    volume_angstrom3 = volume_cm3 * (1e8) ** 3

    box_length = volume_angstrom3 ** (1.0 / 3.0)
    return box_length


def build_solvation_box(
    solvent_name: Optional[str] = None,
    solvent_smiles: Optional[str] = None,
    solvent_file: Optional[str] = None,
    solute_smiles: Optional[str] = None,
    solute_file: Optional[str] = None,
    num_solvent: int = 64,
    box_size: Optional[float] = None,
    tolerance: float = 2.0,
    seed: int = 1,
    output_dir: str = "solvation_box",
) -> dict:
    """
    Build a solvation box using Packmol.

    Args:
        solvent_name: Name of a pre-defined solvent (e.g., 'water', 'methanol').
        solvent_smiles: SMILES string for the solvent (alternative to solvent_name).
        solvent_file: Path to a solvent structure file (alternative to above).
        solute_smiles: SMILES string for the solute molecule.
        solute_file: Path to a solute structure file.
        num_solvent: Number of solvent molecules.
        box_size: Cubic box side length in Å. Auto-calculated if None.
        tolerance: Minimum distance between molecules in Å (Packmol parameter).
        seed: Random seed for Packmol.
        output_dir: Output directory for results.

    Returns:
        Dictionary with box info, file paths, and metadata.
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- Load solvent ---
    solvent_library = load_solvent_library()
    solvent_density = None
    solvent_mw = None

    if solvent_name is not None:
        if solvent_name not in solvent_library:
            available = ", ".join(sorted(solvent_library.keys()))
            raise ValueError(f"Unknown solvent: {solvent_name}. Available: {available}")
        solvent_info = solvent_library[solvent_name]
        solvent_mol = smiles_to_molecule(solvent_info["smiles"], name=solvent_name)
        solvent_density = solvent_info["density_g_cm3"]
        solvent_mw = solvent_info["molecular_weight"]
    elif solvent_smiles is not None:
        solvent_mol = smiles_to_molecule(solvent_smiles, name="solvent")
        # Estimate density as 1.0 g/cm³ if not provided
        solvent_density = 1.0
        solvent_mw = float(sum(el.atomic_mass for el in solvent_mol.species))
    elif solvent_file is not None:
        solvent_mol = Molecule.from_file(solvent_file)
        solvent_density = 1.0
        solvent_mw = float(sum(el.atomic_mass for el in solvent_mol.species))
    else:
        raise ValueError("Must provide one of: --solvent, --solvent_smiles, or --solvent_file")

    # --- Load solute (optional) ---
    solute_mol = None
    if solute_smiles is not None:
        solute_mol = smiles_to_molecule(solute_smiles, name="solute")
    elif solute_file is not None:
        solute_mol = Molecule.from_file(solute_file)
        print(f"  Loaded solute from file: {solute_mol.formula} ({len(solute_mol)} atoms)")

    # --- Calculate box size ---
    if box_size is None:
        box_size = calculate_box_size(
            solvent_mol, num_solvent, solvent_density, solvent_mw, solute_mol
        )
        print(f"  Auto-calculated box size: {box_size:.2f} Å")
    else:
        print(f"  Using specified box size: {box_size:.2f} Å")

    # --- Build Packmol input ---
    molecules = []

    if solute_mol is not None:
        molecules.append({
            "name": "solute",
            "number": 1,
            "coords": solute_mol,
        })

    molecules.append({
        "name": "solvent",
        "number": num_solvent,
        "coords": solvent_mol,
    })

    box = [0.0, 0.0, 0.0, box_size, box_size, box_size]

    packmol_gen = PackmolBoxGen(
        tolerance=tolerance,
        seed=seed,
        outputfile="packmol_out.xyz",
    )
    packmol_set = packmol_gen.get_input_set(molecules=molecules, box=box)

    # --- Run Packmol ---
    print(f"  Running Packmol (tolerance={tolerance} Å, seed={seed})...")
    packmol_set.write_input(output_dir)
    packmol_set.run(output_dir, timeout=120)
    print("  Packmol finished successfully.")

    # --- Read output and create periodic structure ---
    output_xyz = Path(output_dir) / "packmol_out.xyz"
    if not output_xyz.exists():
        raise FileNotFoundError(f"Packmol output not found: {output_xyz}")

    # Read as pymatgen Molecule
    packed_mol = Molecule.from_file(str(output_xyz))
    total_atoms = len(packed_mol)

    # Convert to periodic Structure with cubic cell
    lattice = Lattice.cubic(box_size)
    structure = Structure(
        lattice,
        packed_mol.species,
        packed_mol.cart_coords,
        coords_are_cartesian=True,
    )

    # Save as CIF (periodic, for MD)
    cif_path = Path(output_dir) / "solvated_box.cif"
    structure.to(filename=str(cif_path))
    print(f"  Saved periodic structure: {cif_path} ({total_atoms} atoms)")

    # Save as XYZ (non-periodic, for visualization)
    xyz_path = Path(output_dir) / "solvated_box.xyz"
    ase_atoms = Atoms(
        symbols=[str(s) for s in packed_mol.species],
        positions=packed_mol.cart_coords,
        cell=[box_size, box_size, box_size],
        pbc=True,
    )
    ase_write(str(xyz_path), ase_atoms)
    print(f"  Saved XYZ structure: {xyz_path}")

    # --- Identify solute atom indices (for later analysis) ---
    solute_indices = []
    if solute_mol is not None:
        num_solute_atoms = len(solute_mol)
        solute_indices = list(range(num_solute_atoms))

    # --- Save metadata ---
    metadata = {
        "box_size_angstrom": round(box_size, 4),
        "total_atoms": total_atoms,
        "num_solvent_molecules": num_solvent,
        "solvent_name": solvent_name or "custom",
        "solvent_density_g_cm3": solvent_density,
        "has_solute": solute_mol is not None,
        "solute_num_atoms": len(solute_mol) if solute_mol is not None else 0,
        "solute_indices": solute_indices,
        "tolerance_angstrom": tolerance,
        "seed": seed,
        "cif_path": str(cif_path),
        "xyz_path": str(xyz_path),
    }
    metadata_path = Path(output_dir) / "box_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved metadata: {metadata_path}")

    return metadata


def main() -> None:
    """Main entry point for building solvation boxes."""
    parser = argparse.ArgumentParser(
        description="Build a solvation box for solution-phase MD using Packmol."
    )

    # Solvent specification (mutually exclusive)
    solvent_group = parser.add_mutually_exclusive_group(required=True)
    solvent_group.add_argument(
        "--solvent", type=str, default=None,
        help="Pre-defined solvent name (e.g., water, methanol, acetonitrile)"
    )
    solvent_group.add_argument(
        "--solvent_smiles", type=str, default=None,
        help="SMILES string for the solvent molecule"
    )
    solvent_group.add_argument(
        "--solvent_file", type=str, default=None,
        help="Path to a solvent structure file (XYZ, CIF, etc.)"
    )

    # Solute specification (optional, mutually exclusive)
    solute_group = parser.add_mutually_exclusive_group()
    solute_group.add_argument(
        "--solute_smiles", type=str, default=None,
        help="SMILES string for the solute molecule"
    )
    solute_group.add_argument(
        "--solute_file", type=str, default=None,
        help="Path to a solute structure file (XYZ, CIF, etc.)"
    )

    # Box parameters
    parser.add_argument(
        "--num_solvent", type=int, default=64,
        help="Number of solvent molecules (default: 64)"
    )
    parser.add_argument(
        "--box_size", type=float, default=None,
        help="Cubic box side length in Å (auto-calculated from density if not set)"
    )
    parser.add_argument(
        "--tolerance", type=float, default=2.0,
        help="Minimum inter-molecular distance in Å (default: 2.0)"
    )
    parser.add_argument(
        "--seed", type=int, default=1,
        help="Random seed for Packmol (default: 1, use -1 for random)"
    )
    parser.add_argument(
        "--output_dir", type=str, required=True,
        help="Output directory for solvation box files"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Building Solvation Box")
    print("=" * 60)

    result = build_solvation_box(
        solvent_name=args.solvent,
        solvent_smiles=args.solvent_smiles,
        solvent_file=args.solvent_file,
        solute_smiles=args.solute_smiles,
        solute_file=args.solute_file,
        num_solvent=args.num_solvent,
        box_size=args.box_size,
        tolerance=args.tolerance,
        seed=args.seed,
        output_dir=args.output_dir,
    )

    print("=" * 60)
    print(f"Box size: {result['box_size_angstrom']} Å")
    print(f"Total atoms: {result['total_atoms']}")
    print(f"CIF: {result['cif_path']}")
    print(f"XYZ: {result['xyz_path']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
