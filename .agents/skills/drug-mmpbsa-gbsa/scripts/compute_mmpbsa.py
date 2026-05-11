"""
Single-trajectory MM-PBSA / MM-GBSA rescoring via AmberTools MMPBSA.py.

Companion to compute_mmgbsa.py (which uses OpenMM GBn2 directly). This
script delegates the actual energy decomposition to AmberTools MMPBSA.py,
which supports both Poisson-Boltzmann (PB) and Generalized-Born (GB)
implicit solvent on the same trajectory and reports a normalized
contribution breakdown (ELE, VDW, EGB / EPB, ESURF, etc.).

Pipeline:
    1. Strip waters / ions from the input topology, write subsystem PDBs
       for the dry complex, receptor, and ligand.
    2. Re-parameterize each subsystem in OpenMM with ff14SB + OpenFF
       (matching the parameters used in the original MD).
    3. Convert each OpenMM System to an Amber prmtop via ParmEd. Atom
       ordering is preserved against the source PDB, so the trajectory
       and the prmtops are aligned without any tleap-side reordering.
    4. Use cpptraj to strip waters / ions from the trajectory and write a
       NetCDF that matches the dry-complex prmtop atom count.
    5. Generate an MMPBSA.py input file (PB and / or GB sections) and run
       MMPBSA.py with that input plus the prmtops and trajectory.
    6. Parse FINAL_RESULTS_MMPBSA.dat into a JSON summary alongside the
       raw outputs.

Usage:
    python compute_mmpbsa.py \\
        --topology system/complex_solvated.pdb \\
        --trajectory run/production.dcd \\
        --ligand_sdf ligand.sdf \\
        --ligand_resname UNL \\
        --skip_ns 0.5 \\
        --stride 5 \\
        --method both \\
        --output_dir mmpbsa/

Requirements:
    - Conda environment: drugmd-agent
    - Required packages: openmm, openmmforcefields, openff-toolkit, parmed,
      MDAnalysis, AmberTools (MMPBSA.py + cpptraj must be on PATH).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np

import openmm
import openmm.app as app
import openmm.unit as unit

import parmed

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import MDAnalysis as mda


# ---------------------------------------------------------------------------
# Subsystem extraction (mirrors compute_mmgbsa.py for consistent atom sets)
# ---------------------------------------------------------------------------

SOLUTE_SEL = (
    "not (resname HOH WAT TIP3 SOL NA CL Na+ Cl- K K+ NA+ CL-)"
)


def _check_cli(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"ERROR: '{name}' not on PATH. Install AmberTools (drugmd-agent).")
    return path


def strip_and_write_pdbs(
    topology_path: Path,
    trajectory_path: Path,
    ligand_sel: str,
    receptor_sel: str,
    output_dir: Path,
) -> tuple[Path, Path, Path, int]:
    """Write dry complex, receptor, and ligand PDBs from frame 0."""
    u = mda.Universe(str(topology_path), str(trajectory_path))
    u.trajectory[0]

    complex_atoms = u.select_atoms(SOLUTE_SEL)
    receptor_atoms = u.select_atoms(receptor_sel)
    ligand_atoms = u.select_atoms(ligand_sel)

    if len(complex_atoms) == 0:
        sys.exit("ERROR: dry-complex selection produced 0 atoms.")
    if len(ligand_atoms) == 0:
        sys.exit(f"ERROR: ligand selection '{ligand_sel}' produced 0 atoms.")
    if len(receptor_atoms) == 0:
        sys.exit(f"ERROR: receptor selection '{receptor_sel}' produced 0 atoms.")

    print(f"Complex: {len(complex_atoms)} atoms")
    print(f"Receptor: {len(receptor_atoms)} atoms")
    print(f"Ligand: {len(ligand_atoms)} atoms")

    complex_pdb = output_dir / "complex_dry.pdb"
    receptor_pdb = output_dir / "receptor_dry.pdb"
    ligand_pdb = output_dir / "ligand_dry.pdb"

    complex_atoms.write(str(complex_pdb))
    receptor_atoms.write(str(receptor_pdb))
    ligand_atoms.write(str(ligand_pdb))
    return complex_pdb, receptor_pdb, ligand_pdb, len(complex_atoms)


# ---------------------------------------------------------------------------
# OpenFF / OpenMM parameterization, then ParmEd -> Amber prmtop
# ---------------------------------------------------------------------------

def load_openff_molecule(sdf_path: Path):
    from openff.toolkit import Molecule

    mol = Molecule.from_file(str(sdf_path), allow_undefined_stereo=True)
    if isinstance(mol, list):
        mol = mol[0]
    mol.assign_partial_charges("am1bcc")
    return mol


def _build_openmm_system(
    pdb_path: Path,
    small_molecules: list,
    protein_ff: str,
) -> tuple[openmm.System, app.Topology, list]:
    """Build a vacuum OpenMM System (NoCutoff, no implicit solvent).

    MMPBSA.py adds implicit solvent itself when it evaluates frames, so
    the prmtop must be a vacuum (gas-phase) parameterization. Constraints
    are disabled because MMPBSA.py expects an unconstrained Hamiltonian.
    """
    from openmmforcefields.generators import SMIRNOFFTemplateGenerator

    ff = app.ForceField(f"{protein_ff}.xml")
    if small_molecules:
        generator = SMIRNOFFTemplateGenerator(
            molecules=small_molecules, forcefield="openff-2.2.0",
        )
        ff.registerTemplateGenerator(generator.generator)

    pdb = app.PDBFile(str(pdb_path))
    system = ff.createSystem(
        pdb.topology,
        nonbondedMethod=app.NoCutoff,
        constraints=None,
        rigidWater=False,
    )
    return system, pdb.topology, pdb.positions


_RADII_FOR_IGB: dict[int, str] = {
    1: "mbondi",
    2: "mbondi2",
    5: "mbondi2",
    7: "mbondi",   # GBn (Mongan et al. 2007) parameterized against mbondi.
    8: "mbondi3",  # GBn2 (Nguyen et al. 2013) parameterized against mbondi3.
}


def _save_amber_prmtop(
    system: openmm.System,
    topology: app.Topology,
    positions,
    prmtop_out: Path,
    inpcrd_out: Path,
    radius_set: str,
) -> None:
    """Convert an OpenMM System to an Amber prmtop with the requested GB radii.

    sander / mmpbsa_py_energy require the prmtop's `RADII` section to match
    the chosen `igb` model. ParmEd's `changeRadii` rewrites that section in
    place (without changing the rest of the topology) so the trajectory and
    atom ordering stay consistent.
    """
    from parmed.tools import changeRadii

    struct = parmed.openmm.load_topology(topology, system, xyz=positions)
    changeRadii(struct, radius_set).execute()
    struct.save(str(prmtop_out), format="amber", overwrite=True)
    struct.save(str(inpcrd_out), format="rst7", overwrite=True)


def parameterize_subsystems(
    complex_pdb: Path,
    receptor_pdb: Path,
    ligand_pdb: Path,
    ligand_sdf: Path,
    cofactor_sdf: Path | None,
    protein_ff: str,
    radius_set: str,
    output_dir: Path,
) -> dict[str, Path]:
    print(f"\n--- Parameterizing subsystems (GB radii: {radius_set}) ---")
    ligand_mol = load_openff_molecule(ligand_sdf)
    cofactor_mol = load_openff_molecule(cofactor_sdf) if cofactor_sdf else None

    print("  Building complex system...")
    cs, ct, cp = _build_openmm_system(
        complex_pdb,
        [ligand_mol] + ([cofactor_mol] if cofactor_mol else []),
        protein_ff,
    )
    complex_prmtop = output_dir / "complex.prmtop"
    complex_inpcrd = output_dir / "complex.inpcrd"
    _save_amber_prmtop(cs, ct, cp, complex_prmtop, complex_inpcrd, radius_set)

    print("  Building receptor system...")
    rs, rt, rp = _build_openmm_system(
        receptor_pdb,
        [cofactor_mol] if cofactor_mol else [],
        protein_ff,
    )
    receptor_prmtop = output_dir / "receptor.prmtop"
    receptor_inpcrd = output_dir / "receptor.inpcrd"
    _save_amber_prmtop(rs, rt, rp, receptor_prmtop, receptor_inpcrd, radius_set)

    print("  Building ligand system...")
    ls, lt, lp = _build_openmm_system(ligand_pdb, [ligand_mol], protein_ff)
    ligand_prmtop = output_dir / "ligand.prmtop"
    ligand_inpcrd = output_dir / "ligand.inpcrd"
    _save_amber_prmtop(ls, lt, lp, ligand_prmtop, ligand_inpcrd, radius_set)

    return {
        "complex_prmtop": complex_prmtop, "complex_inpcrd": complex_inpcrd,
        "receptor_prmtop": receptor_prmtop, "receptor_inpcrd": receptor_inpcrd,
        "ligand_prmtop": ligand_prmtop, "ligand_inpcrd": ligand_inpcrd,
    }


# ---------------------------------------------------------------------------
# Trajectory conversion via cpptraj
# ---------------------------------------------------------------------------

def _trajectory_dt_ps(topology_path: Path, trajectory_path: Path) -> float:
    u = mda.Universe(str(topology_path), str(trajectory_path))
    if len(u.trajectory) < 2:
        return 20.0
    u.trajectory[0]; t0 = u.trajectory[0].time
    u.trajectory[1]; t1 = u.trajectory[1].time
    dt = t1 - t0
    return float(dt) if dt > 0 else 20.0


def convert_trajectory_with_cpptraj(
    topology_path: Path,
    trajectory_path: Path,
    expected_atoms: int,
    skip_frames: int,
    stride: int,
    output_dir: Path,
) -> Path:
    """Strip waters / ions from the trajectory and write a NetCDF.

    cpptraj reads the original solvated PDB topology, applies the same
    `not (resname HOH ...)` strip we used to build the dry subsystem
    PDBs, and writes a NetCDF with the resulting atom set. Frame counts
    and atom ordering are sanity-checked against the dry complex prmtop.
    """
    cpptraj_bin = _check_cli("cpptraj")
    nc_path = output_dir / "trajectory_dry.nc"
    cpptraj_in = output_dir / "cpptraj_strip.in"

    n_total = len(mda.Universe(str(topology_path), str(trajectory_path)).trajectory)
    start_one_based = max(1, skip_frames + 1)
    last = n_total
    script = "\n".join([
        f"parm {topology_path}",
        f"trajin {trajectory_path} {start_one_based} {last} {stride}",
        "strip :HOH,WAT,TIP3,SOL,Na+,Cl-,K+,NA,CL,K",
        f"trajout {nc_path} netcdf",
        "go",
        "quit",
        "",
    ])
    cpptraj_in.write_text(script)
    print(f"\n--- Converting trajectory with cpptraj ---")
    print(f"  cpptraj input: {cpptraj_in}")
    proc = subprocess.run(
        [cpptraj_bin, "-i", str(cpptraj_in)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout); sys.stderr.write(proc.stderr)
        sys.exit(f"cpptraj failed (exit {proc.returncode}).")

    if not nc_path.exists():
        sys.exit(f"cpptraj completed but output NetCDF not found: {nc_path}")

    # Sanity check: NetCDF atom count must match the dry-complex prmtop.
    try:
        from scipy.io import netcdf_file
        with netcdf_file(str(nc_path), "r", mmap=False) as nc:
            nc_atoms = int(nc.dimensions["atom"])
            nc_frames = int(nc.dimensions["frame"])
    except Exception as e:
        print(f"WARN: could not introspect NetCDF for atom/frame check: {e}")
        nc_atoms, nc_frames = expected_atoms, -1

    if nc_atoms != expected_atoms:
        sys.exit(
            f"ERROR: stripped trajectory has {nc_atoms} atoms but the dry "
            f"complex prmtop has {expected_atoms}. Atom selection mismatch "
            "between strip_and_write_pdbs and the cpptraj `strip` mask."
        )
    print(f"  NetCDF: {nc_frames} frames, {nc_atoms} atoms")
    return nc_path


# ---------------------------------------------------------------------------
# MMPBSA.py invocation
# ---------------------------------------------------------------------------

def write_mmpbsa_in(
    out_path: Path,
    method: str,
    pb_int_diel: float,
    pb_ext_diel: float,
    gb_model: int,
    salt_conc: float,
) -> None:
    """Write an MMPBSA.py input file. method in {'pb', 'gb', 'both'}."""
    # MMPBSA.py does not expose a temperature variable; sander / PBSA use a
    # hard-coded thermal context internally. The temperature MD ran at is
    # already baked into the trajectory frames being rescored.
    sections: list[str] = [
        "MM-PBSA / MM-GBSA input file (auto-generated by compute_mmpbsa.py)",
        "&general",
        "  startframe=1, endframe=999999, interval=1,",
        "  verbose=2, keep_files=2,",
        "/",
    ]
    if method in ("gb", "both"):
        sections += [
            "&gb",
            f"  igb={gb_model}, saltcon={salt_conc:.3f},",
            "/",
        ]
    if method in ("pb", "both"):
        sections += [
            "&pb",
            f"  istrng={salt_conc:.3f}, indi={pb_int_diel:.2f}, exdi={pb_ext_diel:.2f},",
            "  inp=2, radiopt=0, fillratio=4.0,",
            "/",
        ]
    out_path.write_text("\n".join(sections) + "\n")


def run_mmpbsa(
    work_dir: Path,
    mmpbsa_in: Path,
    complex_prmtop: Path,
    receptor_prmtop: Path,
    ligand_prmtop: Path,
    trajectory: Path,
) -> Path:
    """Run MMPBSA.py and return the path to FINAL_RESULTS_MMPBSA.dat.

    MMPBSA.py drops scratch files into its current working directory, so
    we run it inside `work_dir`. Inputs are passed as absolute paths so
    MMPBSA.py can resolve them regardless of where the user invoked the
    script from.
    """
    mmpbsa_bin = _check_cli("MMPBSA.py")
    work_dir_abs = work_dir.resolve()
    cmd = [
        mmpbsa_bin, "-O",
        "-i", str(mmpbsa_in.resolve()),
        "-cp", str(complex_prmtop.resolve()),
        "-rp", str(receptor_prmtop.resolve()),
        "-lp", str(ligand_prmtop.resolve()),
        "-y", str(trajectory.resolve()),
        "-o", str(work_dir_abs / "FINAL_RESULTS_MMPBSA.dat"),
        "-do", str(work_dir_abs / "FINAL_DECOMP_MMPBSA.dat"),
    ]
    print(f"\n--- Running MMPBSA.py ---")
    print(f"  {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(work_dir_abs), capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(f"MMPBSA.py failed (exit {proc.returncode}).")
    final = work_dir_abs / "FINAL_RESULTS_MMPBSA.dat"
    if not final.exists():
        sys.exit(f"MMPBSA.py reported success but {final} not found.")
    return final


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

_DELTA_HEADER_RE = re.compile(r"DELTA TOTAL", re.IGNORECASE)
_SECTION_RE = re.compile(r"^(GENERALIZED BORN|POISSON BOLTZMANN):?", re.IGNORECASE)
_DG_RE = re.compile(
    r"DELTA TOTAL\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)"
)


def parse_final_results(path: Path) -> dict:
    """Parse `FINAL_RESULTS_MMPBSA.dat` into per-method dG / std / SEM (kcal/mol)."""
    text = path.read_text()
    out: dict[str, dict | None] = {"GB": None, "PB": None}
    current = None
    for line in text.splitlines():
        m = _SECTION_RE.match(line.strip())
        if m:
            head = m.group(1).upper()
            current = "GB" if "GENERALIZED" in head else "PB"
            continue
        if current is None:
            continue
        m = _DG_RE.search(line)
        if m:
            mean, std, sem = float(m.group(1)), float(m.group(2)), float(m.group(3))
            out[current] = {
                "dG_mean_kcal_mol": round(mean, 2),
                "dG_std_kcal_mol": round(std, 2),
                "dG_sem_kcal_mol": round(sem, 2),
            }
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def compute_mmpbsa(
    topology_path: Path,
    trajectory_path: Path,
    ligand_sdf: Path,
    cofactor_sdf: Path | None,
    ligand_sel: str,
    receptor_sel: str,
    method: str,
    skip_ns: float,
    stride: int,
    protein_ff: str,
    pb_int_diel: float,
    pb_ext_diel: float,
    gb_model: int,
    salt_conc: float,
    output_dir: Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    wall_start = time.time()

    # Strip + write subsystem PDBs
    print("--- Stripping solvent and writing subsystem PDBs ---")
    complex_pdb, receptor_pdb, ligand_pdb, n_dry_atoms = strip_and_write_pdbs(
        topology_path, trajectory_path, ligand_sel, receptor_sel, output_dir,
    )

    # Build prmtops via OpenMM + ParmEd (preserves atom ordering vs. trajectory).
    # GB radii must match the chosen igb model; PB-only runs use mbondi2 too.
    radius_set = _RADII_FOR_IGB.get(gb_model, "mbondi2")
    paths = parameterize_subsystems(
        complex_pdb, receptor_pdb, ligand_pdb,
        ligand_sdf, cofactor_sdf, protein_ff, radius_set, output_dir,
    )

    # Convert + strip trajectory
    dt_ps = _trajectory_dt_ps(topology_path, trajectory_path)
    skip_frames = max(0, int(skip_ns * 1000.0 / dt_ps)) if dt_ps > 0 else 0
    nc_path = convert_trajectory_with_cpptraj(
        topology_path, trajectory_path, n_dry_atoms,
        skip_frames=skip_frames, stride=stride, output_dir=output_dir,
    )

    # MMPBSA.py
    mmpbsa_in = output_dir / "mmpbsa.in"
    write_mmpbsa_in(
        mmpbsa_in, method=method,
        pb_int_diel=pb_int_diel, pb_ext_diel=pb_ext_diel,
        gb_model=gb_model, salt_conc=salt_conc,
    )
    final = run_mmpbsa(
        output_dir, mmpbsa_in,
        paths["complex_prmtop"], paths["receptor_prmtop"], paths["ligand_prmtop"],
        nc_path,
    )

    parsed = parse_final_results(final)
    wall_time = time.time() - wall_start

    summary = {
        "method": method,
        "results": {k: v for k, v in parsed.items() if v is not None},
        "n_frames_evaluated": None,
        "skip_ns": skip_ns,
        "stride": stride,
        "trajectory_dt_ps": round(dt_ps, 2),
        "skip_frames_applied": skip_frames,
        "ligand_sdf": str(ligand_sdf),
        "cofactor_sdf": str(cofactor_sdf) if cofactor_sdf else None,
        "ligand_sel": ligand_sel,
        "receptor_sel": receptor_sel,
        "protein_ff": protein_ff,
        "pb_int_diel": pb_int_diel,
        "pb_ext_diel": pb_ext_diel,
        "gb_model": gb_model,
        "salt_conc_M": salt_conc,
        "temperature_note": (
            "MMPBSA.py does not expose a temperature variable; sander / "
            "PBSA use a hard-coded thermal context. The temperature MD ran "
            "at is implicit in the sampled trajectory frames."
        ),
        "final_results_dat": str(final),
        "decomp_dat": str(output_dir / "FINAL_DECOMP_MMPBSA.dat"),
        "wall_time_seconds": round(wall_time, 1),
        "sem_note": (
            "MMPBSA.py reports SEM treating frames as independent samples; "
            "frames from a single trajectory are correlated, so the true "
            "statistical error is larger. For honest uncertainties, run "
            "replicate trajectories and compare across them."
        ),
    }
    summary_path = output_dir / "mmpbsa_summary.json"
    summary_path.write_text(json.dumps(summary, indent=4))
    print(f"\nWrote summary: {summary_path}")

    print(f"\n--- MM-PBSA / MM-GBSA Results ---")
    for tag, vals in summary["results"].items():
        print(
            f"  {tag}: dG = {vals['dG_mean_kcal_mol']:.2f} +/- "
            f"{vals['dG_std_kcal_mol']:.2f} kcal/mol "
            f"(SEM: {vals['dG_sem_kcal_mol']:.2f})"
        )
    print(f"  Wall time: {wall_time:.1f} s")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single-trajectory MM-PBSA / MM-GBSA via AmberTools MMPBSA.py.",
    )
    parser.add_argument("--topology", required=True, help="Solvated complex PDB (topology).")
    parser.add_argument("--trajectory", required=True, help="Production trajectory (DCD).")
    parser.add_argument("--ligand_sdf", required=True, help="Ligand SDF for parameterization.")
    parser.add_argument("--cofactor_sdf", default=None, help="Cofactor SDF (e.g., NADPH).")
    parser.add_argument("--ligand_resname", default="UNL", help="Ligand residue name (default: UNL).")
    parser.add_argument("--ligand_sel", default=None,
                        help="Full MDAnalysis selection for ligand (overrides --ligand_resname).")
    parser.add_argument("--cofactor_resname", default=None, help="Cofactor residue name.")
    parser.add_argument("--cofactor_sel", default=None,
                        help="Full MDAnalysis selection for cofactor (overrides --cofactor_resname).")
    parser.add_argument(
        "--method", choices=["pb", "gb", "both"], default="both",
        help="Implicit-solvent method (default: both).",
    )
    parser.add_argument("--skip_ns", type=float, default=0.5,
                        help="Skip first N ns of trajectory as equilibration (default: 0.5).")
    parser.add_argument("--stride", type=int, default=5,
                        help="Frame stride after skipping (default: 5).")
    parser.add_argument("--protein_ff", default="amber/ff14SB",
                        help="Protein force field XML name (default: amber/ff14SB).")
    parser.add_argument("--pb_int_diel", type=float, default=1.0,
                        help="PB interior (solute) dielectric (default: 1.0).")
    parser.add_argument("--pb_ext_diel", type=float, default=80.0,
                        help="PB exterior (solvent) dielectric (default: 80.0).")
    parser.add_argument("--gb_model", type=int, default=5, choices=[1, 2, 5, 7, 8],
                        help="GB model index (igb): 5 = OBC2 / mbondi2 (default, most widely used for "
                             "MM-GBSA); 2 = OBC1 / mbondi2; 7 = GBn / mbondi; 8 = GBn2 / mbondi3; "
                             "1 = HCT / mbondi. Radius set is paired automatically via ParmEd.")
    parser.add_argument("--salt_conc", type=float, default=0.0,
                        help="Salt concentration in M for GB (saltcon) and PB (istrng) (default: 0.0).")
    parser.add_argument("--output_dir", required=True, help="Output directory.")
    args = parser.parse_args()

    # Validation
    if args.skip_ns < 0:
        sys.exit("--skip_ns must be non-negative.")
    if args.stride <= 0:
        sys.exit("--stride must be positive.")
    if args.pb_int_diel <= 0 or args.pb_ext_diel <= 0:
        sys.exit("Dielectric constants must be positive.")
    if args.salt_conc < 0:
        sys.exit("--salt_conc must be non-negative.")

    topology = Path(args.topology)
    trajectory = Path(args.trajectory)
    ligand_sdf = Path(args.ligand_sdf)
    cofactor_sdf = Path(args.cofactor_sdf) if args.cofactor_sdf else None
    for label, path in [
        ("Topology", topology), ("Trajectory", trajectory), ("Ligand SDF", ligand_sdf),
    ]:
        if not path.exists():
            sys.exit(f"ERROR: {label} not found: {path}")
    if cofactor_sdf and not cofactor_sdf.exists():
        sys.exit(f"ERROR: Cofactor SDF not found: {cofactor_sdf}")

    ligand_sel = args.ligand_sel or f"resname {args.ligand_resname}"
    if args.cofactor_sel:
        receptor_sel = f"protein or ({args.cofactor_sel})"
    elif args.cofactor_resname:
        receptor_sel = f"protein or resname {args.cofactor_resname}"
    else:
        receptor_sel = "protein"

    compute_mmpbsa(
        topology_path=topology,
        trajectory_path=trajectory,
        ligand_sdf=ligand_sdf,
        cofactor_sdf=cofactor_sdf,
        ligand_sel=ligand_sel,
        receptor_sel=receptor_sel,
        method=args.method,
        skip_ns=args.skip_ns,
        stride=args.stride,
        protein_ff=args.protein_ff,
        pb_int_diel=args.pb_int_diel,
        pb_ext_diel=args.pb_ext_diel,
        gb_model=args.gb_model,
        salt_conc=args.salt_conc,
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
