"""
Single-trajectory MM-GBSA rescoring using OpenMM implicit solvent (GBn2).

Extracts complex, receptor, and ligand subsystems from a solvated MD
trajectory, evaluates potential energy with GBn2 implicit solvent for
each component, and computes per-frame binding free energy estimates:

    dG = E_complex - E_receptor - E_ligand

The entropy term (-TdS) is omitted, which is standard practice when
the goal is relative ranking rather than absolute binding affinity.

Usage:
    python compute_mmgbsa.py \
        --topology system/complex_solvated.pdb \
        --trajectory run/production.dcd \
        --ligand_sdf ligand.sdf \
        --ligand_resname UNL \
        --skip_ns 0.5 \
        --output_dir mmgbsa/

Requirements:
    - Conda environment: drugmd-agent
    - Required packages: openmm, openmmforcefields, openff-toolkit, rdkit, MDAnalysis
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

import openmm
import openmm.app as app
import openmm.unit as unit

import MDAnalysis as mda


def _apply_minimum_image_ligand(universe: mda.Universe, ligand_sel: str) -> None:
    """Shift ligand atoms to minimum-image positions relative to the protein.

    Each frame, translate every ligand atom by the box vector that puts it
    closest to the protein center of mass. Without this, a ligand that wraps
    across a periodic boundary appears spatially separated from the protein
    in subsequent energy evaluations, yielding spurious near-zero interaction
    energies. Avoids `trans.unwrap()` which requires bond topology that
    OpenMM-written DCDs typically lack.
    """
    protein_ca = universe.select_atoms("protein and name CA")
    ligand = universe.select_atoms(ligand_sel)

    class _MinImageLigand:
        def __init__(self, protein_ca, ligand):
            self.protein_ca = protein_ca
            self.ligand = ligand

        def __call__(self, ts):
            box = ts.dimensions[:3] if ts.dimensions is not None else None
            if box is None or np.any(box == 0):
                return ts
            prot_com = self.protein_ca.center_of_mass()
            lig_pos = self.ligand.positions.copy()
            for i in range(3):
                diff = lig_pos[:, i] - prot_com[i]
                lig_pos[:, i] -= box[i] * np.round(diff / box[i])
            self.ligand.positions = lig_pos
            return ts

    universe.trajectory.add_transformations(_MinImageLigand(protein_ca, ligand))


def load_openff_molecule(sdf_path: Path):
    """Load an OpenFF Molecule from SDF and assign AM1-BCC charges."""
    from openff.toolkit import Molecule

    mol = Molecule.from_file(str(sdf_path), allow_undefined_stereo=True)
    if isinstance(mol, list):
        mol = mol[0]
    mol.assign_partial_charges("am1bcc")
    return mol


def strip_and_write_pdbs(
    topology_path: Path,
    trajectory_path: Path,
    ligand_sel_str: str,
    receptor_sel_str: str,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """Strip water/ions and write PDBs for complex, receptor, and ligand subsystems."""
    u = mda.Universe(str(topology_path), str(trajectory_path))
    u.trajectory[0]

    solute_sel = "not (resname HOH WAT TIP3 SOL NA CL Na+ Cl- K K+ NA+ CL-)"
    ligand_sel = ligand_sel_str
    receptor_sel = receptor_sel_str

    complex_atoms = u.select_atoms(solute_sel)
    receptor_atoms = u.select_atoms(receptor_sel)
    ligand_atoms = u.select_atoms(ligand_sel)

    print(f"Complex: {len(complex_atoms)} atoms")
    print(f"Receptor: {len(receptor_atoms)} atoms")
    print(f"Ligand: {len(ligand_atoms)} atoms")

    complex_pdb = output_dir / "complex_stripped.pdb"
    receptor_pdb = output_dir / "receptor_stripped.pdb"
    ligand_pdb = output_dir / "ligand_stripped.pdb"

    complex_atoms.write(str(complex_pdb))
    receptor_atoms.write(str(receptor_pdb))
    ligand_atoms.write(str(ligand_pdb))

    return complex_pdb, receptor_pdb, ligand_pdb


def build_implicit_system(
    pdb_path: Path,
    small_molecules: list,
    protein_ff: str = "amber/ff14SB",
    solute_dielectric: float = 1.0,
    solvent_dielectric: float = 78.5,
) -> tuple[openmm.System, app.Topology, list]:
    """Build an OpenMM System with GBn2 implicit solvent for a subsystem."""
    from openmmforcefields.generators import SMIRNOFFTemplateGenerator

    ff = app.ForceField(f"{protein_ff}.xml", "implicit/gbn2.xml")

    if small_molecules:
        generator = SMIRNOFFTemplateGenerator(
            molecules=small_molecules,
            forcefield="openff-2.2.0",
        )
        ff.registerTemplateGenerator(generator.generator)

    pdb = app.PDBFile(str(pdb_path))

    system = ff.createSystem(
        pdb.topology,
        nonbondedMethod=app.NoCutoff,
        constraints=app.HBonds,
        soluteDielectric=solute_dielectric,
        solventDielectric=solvent_dielectric,
    )

    return system, pdb.topology, pdb.positions


def compute_mmgbsa(
    topology_path: Path,
    trajectory_path: Path,
    ligand_sdf: Path,
    cofactor_sdf: Path | None,
    ligand_sel_str: str,
    receptor_sel_str: str,
    skip_ns: float = 0.5,
    stride: int = 5,
    protein_ff: str = "amber/ff14SB",
    solute_dielectric: float = 1.0,
    solvent_dielectric: float = 78.5,
    output_dir: Path = Path("mmgbsa"),
) -> dict:
    """Run single-trajectory MM-GBSA calculation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    wall_start = time.time()

    print(f"Ligand selection: {ligand_sel_str}")
    print(f"Receptor selection: {receptor_sel_str}")

    # Step 1: Strip solvent and write subsystem PDBs
    print("--- Stripping solvent and writing subsystem PDBs ---")
    complex_pdb, receptor_pdb, ligand_pdb = strip_and_write_pdbs(
        topology_path, trajectory_path,
        ligand_sel_str, receptor_sel_str, output_dir,
    )

    # Step 2: Load small molecules for template generator
    print("\n--- Loading small molecules for parameterization ---")
    ligand_mol = load_openff_molecule(ligand_sdf)
    small_molecules = [ligand_mol]

    cofactor_mol = None
    if cofactor_sdf:
        cofactor_mol = load_openff_molecule(cofactor_sdf)
        small_molecules.append(cofactor_mol)

    # Step 3: Build three implicit-solvent systems
    print("\n--- Building implicit-solvent systems ---")
    print(
        f"Dielectrics: solute={solute_dielectric}, solvent={solvent_dielectric}"
    )
    print("Building complex system...")
    complex_system, complex_top, _ = build_implicit_system(
        complex_pdb, small_molecules, protein_ff,
        solute_dielectric=solute_dielectric,
        solvent_dielectric=solvent_dielectric,
    )

    print("Building receptor system...")
    receptor_molecules = [cofactor_mol] if cofactor_mol else []
    receptor_system, receptor_top, _ = build_implicit_system(
        receptor_pdb, receptor_molecules, protein_ff,
        solute_dielectric=solute_dielectric,
        solvent_dielectric=solvent_dielectric,
    )

    print("Building ligand system...")
    ligand_system, ligand_top, _ = build_implicit_system(
        ligand_pdb, [ligand_mol], protein_ff,
        solute_dielectric=solute_dielectric,
        solvent_dielectric=solvent_dielectric,
    )

    # Step 4: Create Contexts
    print("\n--- Creating OpenMM Contexts ---")
    platform = openmm.Platform.getPlatformByName("CPU")

    def make_context(system):
        integrator = openmm.VerletIntegrator(0.001 * unit.picosecond)
        return openmm.Context(system, integrator, platform)

    ctx_complex = make_context(complex_system)
    ctx_receptor = make_context(receptor_system)
    ctx_ligand = make_context(ligand_system)

    # Step 5: Load trajectory and determine frame range
    print("\n--- Loading trajectory for energy evaluation ---")
    u = mda.Universe(str(topology_path), str(trajectory_path))

    # PBC correction: shift ligand to its minimum-image position relative to
    # the protein each frame. Without this, ligand atoms that wrap to a
    # different periodic image appear far from the protein and produce
    # spurious zero (non-interacting) per-frame energies.
    _apply_minimum_image_ligand(u, ligand_sel_str)

    # Determine timestep from trajectory
    if len(u.trajectory) > 1:
        u.trajectory[0]
        t0 = u.trajectory[0].time
        u.trajectory[1]
        t1 = u.trajectory[1].time
        dt_ps = t1 - t0
    else:
        dt_ps = 20.0  # default 20 ps

    skip_frames = int(skip_ns * 1000.0 / dt_ps) if dt_ps > 0 else 0
    total_frames = len(u.trajectory)
    start_frame = min(skip_frames, total_frames - 1)

    frames_to_use = list(range(start_frame, total_frames, stride))
    n_eval = len(frames_to_use)
    print(
        f"Trajectory: {total_frames} frames, dt={dt_ps:.1f} ps, "
        f"skipping first {skip_ns} ns ({skip_frames} frames)"
    )
    print(f"Evaluating {n_eval} frames (stride={stride})")

    # Define atom selections (matching stripped PDBs)
    solute_sel = "not (resname HOH WAT TIP3 SOL NA CL Na+ Cl- K K+ NA+ CL-)"

    complex_atoms = u.select_atoms(solute_sel)
    receptor_atoms = u.select_atoms(receptor_sel_str)
    ligand_atoms = u.select_atoms(ligand_sel_str)

    # Step 6: Evaluate energies per frame
    print("\n--- Evaluating MM-GBSA energies ---")
    frame_results = []

    for i, fi in enumerate(frames_to_use):
        u.trajectory[fi]
        time_ns = u.trajectory[fi].time / 1000.0

        # Extract positions (MDAnalysis uses Angstrom, OpenMM uses nanometer)
        complex_pos = complex_atoms.positions * 0.1  # A -> nm
        receptor_pos = receptor_atoms.positions * 0.1
        ligand_pos = ligand_atoms.positions * 0.1

        # Convert to OpenMM Quantity
        complex_pos_omm = [openmm.Vec3(*p) for p in complex_pos] * unit.nanometer
        receptor_pos_omm = [openmm.Vec3(*p) for p in receptor_pos] * unit.nanometer
        ligand_pos_omm = [openmm.Vec3(*p) for p in ligand_pos] * unit.nanometer

        # Evaluate energies
        ctx_complex.setPositions(complex_pos_omm)
        e_complex = ctx_complex.getState(getEnergy=True).getPotentialEnergy()

        ctx_receptor.setPositions(receptor_pos_omm)
        e_receptor = ctx_receptor.getState(getEnergy=True).getPotentialEnergy()

        ctx_ligand.setPositions(ligand_pos_omm)
        e_ligand = ctx_ligand.getState(getEnergy=True).getPotentialEnergy()

        dg = (e_complex - e_receptor - e_ligand).value_in_unit(unit.kilocalorie_per_mole)

        frame_results.append({
            "frame": fi,
            "time_ns": round(time_ns, 4),
            "E_complex_kcal": round(e_complex.value_in_unit(unit.kilocalorie_per_mole), 2),
            "E_receptor_kcal": round(e_receptor.value_in_unit(unit.kilocalorie_per_mole), 2),
            "E_ligand_kcal": round(e_ligand.value_in_unit(unit.kilocalorie_per_mole), 2),
            "dG_kcal": round(dg, 2),
        })

        if (i + 1) % 10 == 0 or i == 0:
            print(f"  Frame {fi} ({time_ns:.2f} ns): dG = {dg:.2f} kcal/mol")

    # Step 7: Compute statistics and write results
    dg_values = np.array([r["dG_kcal"] for r in frame_results])
    dg_mean = float(np.mean(dg_values))
    dg_std = float(np.std(dg_values))
    dg_sem = float(dg_std / np.sqrt(len(dg_values)))

    wall_time = time.time() - wall_start

    # Write per-frame CSV
    csv_path = output_dir / "mmgbsa_frames.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=frame_results[0].keys())
        writer.writeheader()
        writer.writerows(frame_results)
    print(f"\nWrote per-frame results: {csv_path}")

    # Write summary
    summary = {
        "dG_mean_kcal_mol": round(dg_mean, 2),
        "dG_std_kcal_mol": round(dg_std, 2),
        "dG_sem_kcal_mol": round(dg_sem, 2),
        "sem_note": (
            "SEM assumes frames are independent samples. Because frames come "
            "from a single correlated trajectory, this underestimates the "
            "true statistical error. For honest uncertainties, run replicate "
            "trajectories or compute a block-averaged error."
        ),
        "n_frames_evaluated": len(frame_results),
        "skip_ns": skip_ns,
        "stride": stride,
        "start_frame": start_frame,
        "ligand_sdf": str(ligand_sdf),
        "cofactor_sdf": str(cofactor_sdf) if cofactor_sdf else None,
        "ligand_sel": ligand_sel_str,
        "receptor_sel": receptor_sel_str,
        "protein_ff": protein_ff,
        "implicit_solvent": "GBn2",
        "solute_dielectric": solute_dielectric,
        "solvent_dielectric": solvent_dielectric,
        "wall_time_seconds": round(wall_time, 1),
    }

    summary_path = output_dir / "mmgbsa_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=4)
    print(f"Wrote summary: {summary_path}")

    print(f"\n--- MM-GBSA Results ---")
    print(f"dG = {dg_mean:.2f} +/- {dg_std:.2f} kcal/mol (SEM: {dg_sem:.2f})")
    print(f"Frames evaluated: {len(frame_results)}")
    print(f"Wall time: {wall_time:.1f} s")

    # Clean up
    del ctx_complex, ctx_receptor, ctx_ligand

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single-trajectory MM-GBSA rescoring with OpenMM GBn2."
    )
    parser.add_argument("--topology", required=True, help="Solvated complex PDB (topology).")
    parser.add_argument("--trajectory", required=True, help="Production trajectory (DCD).")
    parser.add_argument("--ligand_sdf", required=True, help="Ligand SDF (for parameterization).")
    parser.add_argument("--cofactor_sdf", default=None, help="Cofactor SDF (e.g., NADPH).")
    parser.add_argument("--ligand_resname", default="UNL", help="Ligand residue name (default: UNL).")
    parser.add_argument("--ligand_sel", default=None, help="Full MDAnalysis selection for ligand (overrides --ligand_resname).")
    parser.add_argument("--cofactor_resname", default=None, help="Cofactor residue name (e.g., NDP).")
    parser.add_argument("--cofactor_sel", default=None, help="Full MDAnalysis selection for cofactor (overrides --cofactor_resname).")
    parser.add_argument("--skip_ns", type=float, default=0.5,
                        help="Skip first N ns of trajectory as equilibration (default: 0.5). "
                             "For longer production MD (>10 ns), increase proportionally (e.g., "
                             "1-5 ns).")
    parser.add_argument("--stride", type=int, default=5, help="Frame stride for evaluation (default: 5).")
    parser.add_argument("--protein_ff", default="amber/ff14SB", help="Protein force field (default: amber/ff14SB).")
    parser.add_argument("--solute_dielectric", type=float, default=1.0,
                        help="Interior dielectric constant of the solute (default: 1.0). Raise to "
                             "2-4 for polar or highly charged binding sites; see SKILL.md for "
                             "guidance. This parameter is a major knob for MM-GBSA rankings.")
    parser.add_argument("--solvent_dielectric", type=float, default=78.5,
                        help="Solvent dielectric constant (default: 78.5, bulk water). Rarely "
                             "needs to be changed.")
    parser.add_argument("--output_dir", required=True, help="Output directory for MM-GBSA results.")
    args = parser.parse_args()

    topology_path = Path(args.topology)
    trajectory_path = Path(args.trajectory)
    ligand_sdf = Path(args.ligand_sdf)
    cofactor_sdf = Path(args.cofactor_sdf) if args.cofactor_sdf else None

    for label, path in [("Topology", topology_path), ("Trajectory", trajectory_path), ("Ligand SDF", ligand_sdf)]:
        if not path.exists():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            sys.exit(1)
    if cofactor_sdf and not cofactor_sdf.exists():
        print(f"ERROR: Cofactor SDF not found: {cofactor_sdf}", file=sys.stderr)
        sys.exit(1)

    # Build selection strings
    if args.ligand_sel:
        ligand_sel_str = args.ligand_sel
    else:
        ligand_sel_str = f"resname {args.ligand_resname}"

    if args.cofactor_sel:
        receptor_sel_str = f"protein or ({args.cofactor_sel})"
    elif args.cofactor_resname:
        receptor_sel_str = f"protein or resname {args.cofactor_resname}"
    else:
        receptor_sel_str = "protein"

    compute_mmgbsa(
        topology_path=topology_path,
        trajectory_path=trajectory_path,
        ligand_sdf=ligand_sdf,
        cofactor_sdf=cofactor_sdf,
        ligand_sel_str=ligand_sel_str,
        receptor_sel_str=receptor_sel_str,
        skip_ns=args.skip_ns,
        stride=args.stride,
        protein_ff=args.protein_ff,
        solute_dielectric=args.solute_dielectric,
        solvent_dielectric=args.solvent_dielectric,
        output_dir=Path(args.output_dir),
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
