"""
Build a solvated, ion-neutralized protein-ligand complex for OpenMM simulation.

Takes a prepared receptor PDB and a ligand SDF, parameterizes both using
Amber ff14SB (protein) and OpenFF Sage or GAFF (ligand), merges them,
solvates with explicit water, adds counterions, and writes a ready-to-simulate
OpenMM system bundle.

Usage:
    python build_complex.py --receptor protein.pdb --ligand ligand.sdf --output_dir system/

Requirements:
    - Conda environment: drugmd-agent
    - Required packages: openmm, openmmforcefields, openff-toolkit, rdkit, parmed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import openmm
import openmm.app as app
import openmm.unit as unit


def load_ligand_molecule(sdf_path: Path, pose_index: int = 0):
    """Load a ligand from SDF and assign AM1-BCC partial charges."""
    from openff.toolkit import Molecule

    molecules = Molecule.from_file(str(sdf_path), allow_undefined_stereo=True)
    if isinstance(molecules, list):
        if pose_index >= len(molecules):
            raise ValueError(
                f"Requested pose_index={pose_index} but SDF has only {len(molecules)} molecules"
            )
        mol = molecules[pose_index]
    else:
        mol = molecules

    mol.assign_partial_charges("am1bcc")
    return mol


def create_template_generator(ligand_mol, ligand_ff: str):
    """Create a ForceField template generator for the ligand."""
    from openmmforcefields.generators import (
        GAFFTemplateGenerator,
        SMIRNOFFTemplateGenerator,
    )

    if ligand_ff.startswith("openff"):
        generator = SMIRNOFFTemplateGenerator(
            molecules=[ligand_mol],
            forcefield=ligand_ff,
        )
    elif ligand_ff.startswith("gaff"):
        generator = GAFFTemplateGenerator(
            molecules=[ligand_mol],
            forcefield=ligand_ff,
        )
    else:
        raise ValueError(f"Unsupported ligand force field: {ligand_ff}")

    return generator


def check_clashes(
    receptor_positions,
    ligand_positions,
    clash_threshold: float = 1.5,
) -> None:
    """Warn if any protein-ligand heavy-atom pair is closer than clash_threshold (A)."""
    prot = np.array(receptor_positions.value_in_unit(unit.angstrom))
    lig = np.array(ligand_positions.value_in_unit(unit.angstrom))

    diff = prot[:, np.newaxis, :] - lig[np.newaxis, :, :]
    dists = np.sqrt((diff ** 2).sum(axis=2))
    min_dist = float(dists.min())

    if min_dist < clash_threshold:
        n_clashes = int((dists < clash_threshold).sum())
        print(
            f"WARNING: {n_clashes} protein-ligand atom pairs closer than "
            f"{clash_threshold} A (min distance: {min_dist:.2f} A). "
            f"Energy minimization may struggle with severe clashes."
        )


def build_complex(
    receptor_path: Path,
    ligand_path: Path,
    ligand_ff: str = "openff-2.2.0",
    protein_ff: str = "amber/ff14SB",
    water_model: str = "tip3p",
    box_padding: float = 12.0,
    ionic_strength: float = 0.15,
    pose_index: int = 0,
    hydrogen_mass: float = 4.0,
    box_shape: str = "cube",
    output_dir: Path = Path("system"),
) -> dict:
    """Build a solvated protein-ligand complex."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Water model to XML mapping
    water_ff_map = {
        "tip3p": "amber/tip3p_standard.xml",
        "tip3pfb": "amber/tip3pfb_standard.xml",
        "tip4pew": "amber/tip4pew_standard.xml",
        "opc": "amber/opc_standard.xml",
        "spce": "amber/spce_standard.xml",
    }
    water_ff = water_ff_map.get(water_model)
    if water_ff is None:
        raise ValueError(
            f"Unsupported water model: {water_model}. "
            f"Supported: {', '.join(water_ff_map.keys())}"
        )

    # Load ligand (assigns AM1-BCC charges)
    print(f"Loading ligand from {ligand_path} (pose {pose_index})...")
    ligand_mol = load_ligand_molecule(ligand_path, pose_index)

    # Create template generator for ligand
    print(f"Parameterizing ligand with {ligand_ff}...")
    template_generator = create_template_generator(ligand_mol, ligand_ff)

    # Set up force field with protein + water + ligand template generator
    ff = app.ForceField(f"{protein_ff}.xml", water_ff)
    ff.registerTemplateGenerator(template_generator.generator)

    # Load receptor
    print(f"Loading receptor from {receptor_path}...")
    receptor_pdb = app.PDBFile(str(receptor_path))

    # Create ligand topology and positions from the OpenFF Molecule
    ligand_topology = ligand_mol.to_topology().to_openmm()
    ligand_positions = ligand_mol.conformers[0].to_openmm()

    # Check for steric clashes before merging
    check_clashes(receptor_pdb.positions, ligand_positions)

    # Merge protein and ligand into a single Modeller
    modeller = app.Modeller(receptor_pdb.topology, receptor_pdb.positions)
    modeller.add(ligand_topology, ligand_positions)

    n_protein_atoms = receptor_pdb.topology.getNumAtoms()
    n_ligand_atoms = ligand_topology.getNumAtoms()
    print(f"Complex: {n_protein_atoms} protein atoms + {n_ligand_atoms} ligand atoms")

    # Solvate
    padding = box_padding * unit.angstrom
    print(f"Solvating with {water_model} (padding={box_padding} A, box={box_shape})...")
    modeller.addSolvent(
        ff,
        model=water_model,
        padding=padding,
        boxShape=box_shape,
        ionicStrength=ionic_strength * unit.molar,
        neutralize=True,
    )

    n_total = modeller.topology.getNumAtoms()
    n_solvent = n_total - n_protein_atoms - n_ligand_atoms
    print(f"Solvated system: {n_total} atoms ({n_solvent} solvent/ion atoms)")

    # Create system
    hmr_enabled = hydrogen_mass is not None and hydrogen_mass > 1.1
    if hmr_enabled:
        constraints = app.AllBonds
        print(
            f"Creating OpenMM system (HMR: {hydrogen_mass} amu, AllBonds constraints, "
            f"use 4-5 fs timestep)..."
        )
    else:
        constraints = app.HBonds
        print("Creating OpenMM system (no HMR: HBonds constraints, use 2 fs timestep)...")

    create_kwargs = {
        "nonbondedMethod": app.PME,
        "nonbondedCutoff": 10.0 * unit.angstrom,
        "constraints": constraints,
    }
    if hmr_enabled:
        create_kwargs["hydrogenMass"] = hydrogen_mass * unit.amu
    system = ff.createSystem(modeller.topology, **create_kwargs)

    # Get box vectors
    box_vectors = modeller.topology.getPeriodicBoxVectors()
    box_a = box_vectors[0][0].value_in_unit(unit.angstrom)
    box_b = box_vectors[1][1].value_in_unit(unit.angstrom)
    box_c = box_vectors[2][2].value_in_unit(unit.angstrom)

    # Write solvated PDB (for visualization; truncated to 0.001 A precision)
    pdb_path = output_dir / "complex_solvated.pdb"
    with open(pdb_path, "w") as f:
        app.PDBFile.writeFile(modeller.topology, modeller.positions, f)
    print(f"Wrote solvated PDB: {pdb_path}")

    # Serialize and write system XML
    system_xml_path = output_dir / "system.xml"
    with open(system_xml_path, "w") as f:
        f.write(openmm.XmlSerializer.serialize(system))
    print(f"Wrote system XML: {system_xml_path}")

    # Write full-precision state (positions + box vectors) for simulation restart
    state_xml_path = output_dir / "state_initial.xml"
    integrator = openmm.LangevinMiddleIntegrator(300 * unit.kelvin, 1.0 / unit.picosecond, 0.004 * unit.picosecond)
    context = openmm.Context(system, integrator)
    context.setPositions(modeller.positions)
    context.setPeriodicBoxVectors(*box_vectors)
    state = context.getState(getPositions=True)
    with open(state_xml_path, "w") as f:
        f.write(openmm.XmlSerializer.serialize(state))
    del context, integrator
    print(f"Wrote initial state: {state_xml_path}")

    # Write provenance
    provenance = {
        "receptor": str(receptor_path),
        "ligand": str(ligand_path),
        "pose_index": pose_index,
        "ligand_ff": ligand_ff,
        "protein_ff": protein_ff,
        "water_model": water_model,
        "box_padding_angstrom": box_padding,
        "box_shape": box_shape,
        "ionic_strength_mol_per_L": ionic_strength,
        "n_protein_atoms": n_protein_atoms,
        "n_ligand_atoms": n_ligand_atoms,
        "n_total_atoms": n_total,
        "n_solvent_ion_atoms": n_solvent,
        "box_dimensions_angstrom": [round(box_a, 2), round(box_b, 2), round(box_c, 2)],
        "nonbonded_method": "PME",
        "nonbonded_cutoff_angstrom": 10.0,
        "constraints": "AllBonds" if hmr_enabled else "HBonds",
        "hydrogen_mass_amu": hydrogen_mass if hmr_enabled else 1.008,
        "hmr_enabled": hmr_enabled,
        "output_pdb": str(pdb_path),
        "output_system_xml": str(system_xml_path),
        "output_state_xml": str(state_xml_path),
    }

    provenance_path = output_dir / "build_provenance.json"
    with open(provenance_path, "w") as f:
        json.dump(provenance, f, indent=4)
    print(f"Wrote provenance: {provenance_path}")

    return provenance


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a solvated protein-ligand complex for OpenMM MD."
    )
    parser.add_argument("--receptor", required=True, help="Prepared receptor PDB file.")
    parser.add_argument("--ligand", required=True, help="Ligand SDF file with 3D pose(s).")
    parser.add_argument(
        "--ligand_ff",
        default="openff-2.2.0",
        help="Ligand force field (default: openff-2.2.0). Options: openff-2.2.0, gaff-2.11.",
    )
    parser.add_argument(
        "--protein_ff",
        default="amber/ff14SB",
        help="Protein force field (default: amber/ff14SB).",
    )
    parser.add_argument(
        "--water_model",
        default="tip3p",
        help="Water model (default: tip3p). Options: tip3p, tip3pfb, tip4pew, opc, spce.",
    )
    parser.add_argument(
        "--box_padding",
        type=float,
        default=12.0,
        help="Padding from solute to box edge in Angstroms (default: 12.0).",
    )
    parser.add_argument(
        "--ionic_strength",
        type=float,
        default=0.15,
        help="NaCl concentration in mol/L (default: 0.15).",
    )
    parser.add_argument(
        "--pose_index",
        type=int,
        default=0,
        help="Which pose from the SDF to use (default: 0).",
    )
    parser.add_argument(
        "--box_shape",
        default="cube",
        choices=["cube", "dodecahedron", "octahedron"],
        help=(
            "Simulation box shape (default: cube). "
            "Dodecahedron and octahedron use ~30%% less water."
        ),
    )
    parser.add_argument(
        "--hydrogen_mass",
        type=float,
        default=4.0,
        help=(
            "Hydrogen mass in amu for hydrogen mass repartitioning (default: 4.0). "
            "With HMR (3-4 amu), AllBonds constraints are used, enabling 4 fs timesteps. "
            "Set to 1.008 to disable HMR (uses HBonds constraints, requires 2 fs timestep)."
        ),
    )
    parser.add_argument("--output_dir", required=True, help="Output directory for system files.")
    args = parser.parse_args()

    receptor_path = Path(args.receptor)
    ligand_path = Path(args.ligand)

    if not receptor_path.exists():
        print(f"ERROR: Receptor not found: {receptor_path}", file=sys.stderr)
        sys.exit(1)
    if not ligand_path.exists():
        print(f"ERROR: Ligand not found: {ligand_path}", file=sys.stderr)
        sys.exit(1)

    build_complex(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        ligand_ff=args.ligand_ff,
        protein_ff=args.protein_ff,
        water_model=args.water_model,
        box_padding=args.box_padding,
        ionic_strength=args.ionic_strength,
        pose_index=args.pose_index,
        hydrogen_mass=args.hydrogen_mass,
        box_shape=args.box_shape,
        output_dir=Path(args.output_dir),
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
