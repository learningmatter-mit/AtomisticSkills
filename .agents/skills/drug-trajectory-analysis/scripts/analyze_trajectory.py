"""
Analyze a protein-ligand MD trajectory for binding-mode stability.

Computes ligand RMSD, COM drift, pocket RMSF, hydrogen bonds, contacts,
and (optionally) protein-ligand interaction fingerprints via ProLIF.

Usage:
    python analyze_trajectory.py --topology complex.pdb --trajectory prod.dcd --output_dir analysis/

Requirements:
    - Conda environment: drugmd-agent
    - Required packages: MDAnalysis, matplotlib, (optional) prolif
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import warnings
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import MDAnalysis as mda
from MDAnalysis.analysis import align, rms


def make_ligand_whole_minimum_image(universe: mda.Universe, ligand_sel: str) -> None:
    """On-the-fly transformation: place ligand near protein using minimum image.

    For each frame, shifts each ligand atom by the box vector that puts it
    closest to the protein center of mass. This fixes PBC wrapping without
    needing bond topology (which trans.unwrap requires).
    """
    protein_ca = universe.select_atoms("protein and name CA")
    ligand = universe.select_atoms(ligand_sel)

    class MinImageLigand(object):
        def __init__(self, protein_ca, ligand):
            self.protein_ca = protein_ca
            self.ligand = ligand

        def __call__(self, ts):
            box = ts.dimensions[:3]
            if box is None or np.any(box == 0):
                return ts
            prot_com = self.protein_ca.center_of_mass()
            lig_pos = self.ligand.positions.copy()
            for i in range(3):
                diff = lig_pos[:, i] - prot_com[i]
                lig_pos[:, i] -= box[i] * np.round(diff / box[i])
            self.ligand.positions = lig_pos
            return ts

    universe.trajectory.add_transformations(MinImageLigand(protein_ca, ligand))


def compute_ligand_rmsd(
    universe: mda.Universe,
    ligand_sel: str,
    skip: int = 0,
) -> List[Dict]:
    """Compute ligand heavy-atom RMSD relative to the first frame.

    Aligns each frame on protein CA atoms, then measures ligand
    heavy-atom RMSD without additional superposition.
    """
    ligand_heavy = universe.select_atoms(ligand_sel + " and not name H*")
    if len(ligand_heavy) == 0:
        raise ValueError(f"No atoms found for ligand selection: {ligand_sel}")

    R = rms.RMSD(
        universe,
        universe,
        select="protein and name CA",
        groupselections=[ligand_sel + " and not name H*"],
        ref_frame=skip,
    )
    R.run(start=skip)

    results = []
    for row in R.results.rmsd:
        results.append({
            "frame": int(row[0]),
            "time_ps": round(float(row[1]), 4),
            "rmsd_angstrom": round(float(row[3]), 4),
        })

    return results


def compute_ligand_com(
    universe: mda.Universe,
    ligand_sel: str,
    skip: int = 0,
) -> List[Dict]:
    """Compute ligand COM displacement relative to protein backbone COM.

    Uses minimum-image convention so PBC wrapping does not produce
    spurious large distances.
    """
    ligand = universe.select_atoms(ligand_sel)
    protein_bb = universe.select_atoms("protein and backbone")
    results = []
    for i, ts in enumerate(universe.trajectory[skip:]):
        box = ts.dimensions[:3]
        lig_com = ligand.center_of_mass()
        prot_com = protein_bb.center_of_mass()
        rel = lig_com - prot_com
        if box is not None and np.all(box > 0):
            rel -= box * np.round(rel / box)
        results.append({
            "frame": i + skip,
            "time_ps": ts.time,
            "rel_com_x": round(float(rel[0]), 4),
            "rel_com_y": round(float(rel[1]), 4),
            "rel_com_z": round(float(rel[2]), 4),
            "distance_to_protein_com": round(float(np.linalg.norm(rel)), 4),
        })
    return results


def compute_pocket_rmsf(
    universe: mda.Universe,
    ligand_sel: str,
    pocket_cutoff: float = 5.0,
    skip: int = 0,
) -> List[Dict]:
    """Compute per-residue RMSF of pocket residues (CA atoms).

    Uses the MDAnalysis-recommended pattern: compute an average structure,
    align the trajectory to that average, then calculate RMSF.
    """
    # Identify pocket residues from first frame
    universe.trajectory[0]
    pocket_sel = f"protein and name CA and around {pocket_cutoff} ({ligand_sel})"
    pocket_atoms = universe.select_atoms(pocket_sel)

    if len(pocket_atoms) == 0:
        print("WARNING: No pocket residues found. Check ligand selection and cutoff.")
        return []

    # Get residue IDs for a stable selection
    resids = list(set(a.resid for a in pocket_atoms))
    resid_str = " ".join(str(r) for r in sorted(resids))
    stable_sel = f"protein and name CA and resid {resid_str}"
    pocket_ca = universe.select_atoms(stable_sel)

    protein_sel = "protein and name CA"

    # Step 1: compute average structure
    avg = align.AverageStructure(
        universe, universe, select=protein_sel, ref_frame=skip,
    ).run(start=skip)
    ref = avg.results.universe

    # Step 2: align trajectory to the average structure
    align.AlignTraj(universe, ref, select=protein_sel, in_memory=True).run(start=skip)

    # Step 3: compute RMSF
    rmsf_analysis = rms.RMSF(pocket_ca).run(start=skip)
    rmsf_values = rmsf_analysis.results.rmsf

    results = []
    for atom, rmsf_val in zip(pocket_ca.atoms, rmsf_values):
        results.append({
            "resname": atom.resname,
            "resid": int(atom.resid),
            "chain": atom.segid if hasattr(atom, "segid") else "",
            "rmsf_angstrom": round(float(rmsf_val), 4),
        })

    return results


def compute_hbonds(
    universe: mda.Universe,
    ligand_sel: str,
    skip: int = 0,
) -> List[Dict]:
    """Compute protein-ligand hydrogen bonds and their occupancy.

    Uses the ``between`` parameter to restrict the search to
    inter-molecular H-bonds directly, avoiding post-filtering.
    """
    from MDAnalysis.analysis.hydrogenbonds.hbond_analysis import HydrogenBondAnalysis

    hbond_analysis = HydrogenBondAnalysis(
        universe,
        donors_sel=f"({ligand_sel}) or protein",
        hydrogens_sel=f"({ligand_sel} and name H*) or (protein and name H*)",
        acceptors_sel=f"({ligand_sel}) or protein",
        between=["protein", ligand_sel],
        d_a_cutoff=3.5,
        d_h_a_angle_cutoff=120,
    )

    hbond_analysis.run(start=skip, verbose=False)

    if len(hbond_analysis.results.hbonds) == 0:
        return []

    n_frames = len(universe.trajectory[skip:])
    hbond_counts: Dict[tuple, int] = {}

    for hb in hbond_analysis.results.hbonds:
        donor_idx = int(hb[1])
        acceptor_idx = int(hb[3])
        donor_atom = universe.atoms[donor_idx]
        acceptor_atom = universe.atoms[acceptor_idx]

        key = (
            f"{donor_atom.resname}{donor_atom.resid}:{donor_atom.name}",
            f"{acceptor_atom.resname}{acceptor_atom.resid}:{acceptor_atom.name}",
        )
        hbond_counts[key] = hbond_counts.get(key, 0) + 1

    results = []
    for (donor, acceptor), count in sorted(hbond_counts.items(), key=lambda x: -x[1]):
        occupancy = count / n_frames
        if occupancy >= 0.05:  # only report if >5% occupancy
            results.append({
                "donor": donor,
                "acceptor": acceptor,
                "occupancy": round(occupancy, 4),
                "count": count,
            })

    return results


def compute_contacts_occupancy(
    universe: mda.Universe,
    ligand_sel: str,
    pocket_cutoff: float = 5.0,
    skip: int = 0,
) -> List[Dict]:
    """Compute residue-level contact occupancy between protein and ligand.

    Uses ``capped_distance`` for sparse pair detection instead of the
    full N x M distance matrix, which scales much better for large systems.
    """
    ligand = universe.select_atoms(ligand_sel)
    protein = universe.select_atoms("protein")

    n_frames = 0
    residue_contacts: Dict[str, int] = {}

    for ts in universe.trajectory[skip:]:
        n_frames += 1
        pairs = mda.lib.distances.capped_distance(
            ligand.positions, protein.positions,
            max_cutoff=pocket_cutoff, box=ts.dimensions,
            return_distances=False,
        )
        # pairs is an (N_pairs, 2) array of [ligand_idx, protein_idx]
        frame_residues = set()
        for _, prot_idx in pairs:
            atom = protein.atoms[prot_idx]
            frame_residues.add(f"{atom.resname}{atom.resid}")
        for key in frame_residues:
            residue_contacts[key] = residue_contacts.get(key, 0) + 1

    results = []
    for reskey, count in sorted(residue_contacts.items(), key=lambda x: -x[1]):
        occupancy = count / n_frames if n_frames > 0 else 0
        if occupancy >= 0.1:  # report residues in contact >10% of the time
            results.append({
                "residue": reskey,
                "occupancy": round(occupancy, 4),
            })

    return results


def compute_interaction_fingerprints(
    topology_path: str,
    trajectory_path: str,
    ligand_resname: str,
    skip: int = 0,
    stride: int = 1,
) -> List[Dict] | None:
    """Compute per-frame interaction fingerprints using ProLIF."""
    try:
        import prolif
    except ImportError:
        print("WARNING: ProLIF not installed. Skipping interaction fingerprints.")
        return None

    u = mda.Universe(topology_path, trajectory_path)
    ligand_sel = u.select_atoms(f"resname {ligand_resname}")
    protein_sel = u.select_atoms("protein")

    fp = prolif.Fingerprint()
    fp.run(u.trajectory[skip::stride], ligand_sel, protein_sel)

    df = fp.to_dataframe()
    results = []
    for frame_idx, row in df.iterrows():
        frame_data = {"frame": int(frame_idx)}
        for col in df.columns:
            frame_data[str(col)] = bool(row[col])
        results.append(frame_data)

    return results


def write_csv(data: List[Dict], path: Path) -> None:
    """Write a list of dicts to CSV."""
    if not data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)


def plot_rmsd(rmsd_data: List[Dict], output_path: Path) -> None:
    """Plot ligand RMSD time series."""
    times = [d["time_ps"] / 1000.0 for d in rmsd_data]  # convert to ns
    rmsds = [d["rmsd_angstrom"] for d in rmsd_data]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(times, rmsds, linewidth=0.8)
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Ligand RMSD (A)")
    ax.set_title("Ligand Heavy-Atom RMSD")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_com(com_data: List[Dict], output_path: Path) -> None:
    """Plot ligand-protein COM distance over time."""
    if not com_data:
        return
    times = [d["time_ps"] / 1000.0 for d in com_data]
    dists = [d["distance_to_protein_com"] for d in com_data]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(times, dists, linewidth=0.8, color="darkorange")
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Ligand-Protein COM Distance (A)")
    ax.set_title("Ligand COM Drift (relative to protein)")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_rmsf(rmsf_data: List[Dict], output_path: Path) -> None:
    """Plot pocket residue RMSF bar chart."""
    if not rmsf_data:
        return
    labels = [f"{d['resname']}{d['resid']}" for d in rmsf_data]
    values = [d["rmsf_angstrom"] for d in rmsf_data]

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.4), 4))
    ax.bar(range(len(labels)), values, color="steelblue")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("RMSF (A)")
    ax.set_title("Pocket Residue RMSF")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_contacts(contacts_data: List[Dict], output_path: Path) -> None:
    """Plot contact occupancy bar chart."""
    if not contacts_data:
        return
    labels = [d["residue"] for d in contacts_data[:20]]  # top 20
    values = [d["occupancy"] for d in contacts_data[:20]]

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.4), 4))
    ax.barh(range(len(labels)), values, color="coral")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Contact Occupancy")
    ax.set_title("Protein-Ligand Contact Occupancy")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_binding_snapshots(
    universe: mda.Universe,
    ligand_sel: str,
    output_path: Path,
    skip: int = 0,
) -> None:
    """Render 4 PyMOL snapshots of the ligand in the binding pocket.

    Picks frames at the start, 1/3, 2/3, and end of the trajectory,
    renders each with PyMOL ray-tracing, and stitches them into a
    4-column figure with matplotlib.
    """
    import tempfile

    try:
        import pymol
        pymol.finish_launching(["pymol", "-cq"])
        from pymol import cmd
    except ImportError:
        print("WARNING: PyMOL not installed. Skipping binding snapshots.")
        return

    traj = universe.trajectory
    usable = list(range(skip, len(traj)))
    if len(usable) < 2:
        return
    n = len(usable)
    if n < 4:
        frame_indices = usable
    else:
        frame_indices = [usable[0], usable[n // 3], usable[2 * n // 3], usable[-1]]

    ligand_resname = ligand_sel.replace("resname ", "")
    sel_atoms = universe.select_atoms(f"protein or ({ligand_sel})")

    tmpdir = tempfile.mkdtemp()
    panel_paths = []

    # Render first frame to lock the camera orientation
    traj[frame_indices[0]]
    first_pdb = Path(tmpdir) / "frame_ref.pdb"
    sel_atoms.write(str(first_pdb))

    cmd.reinitialize()
    cmd.load(str(first_pdb), "ref")
    cmd.hide("all")
    cmd.show("cartoon", "polymer")
    cmd.show("sticks", f"resn {ligand_resname}")
    cmd.set_color("protein_blue", [0.275, 0.510, 0.706])
    cmd.set_color("ligand_orange", [1.0, 0.271, 0.0])
    cmd.color("protein_blue", "polymer")
    cmd.color("ligand_orange", f"resn {ligand_resname} and elem C")
    cmd.color("red", f"resn {ligand_resname} and elem O")
    cmd.color("tv_blue", f"resn {ligand_resname} and elem N")
    cmd.set("cartoon_fancy_helices", 1)
    cmd.set("stick_radius", 0.15)
    cmd.set("ray_opaque_background", 0)
    cmd.bg_color("white")
    cmd.zoom(f"resn {ligand_resname}", 10)
    view = cmd.get_view()
    cmd.delete("ref")

    for fi in frame_indices:
        traj[fi]
        time_ps = traj[fi].time

        frame_pdb = Path(tmpdir) / f"frame_{fi}.pdb"
        sel_atoms.write(str(frame_pdb))

        cmd.reinitialize()
        cmd.load(str(frame_pdb), "complex")
        cmd.hide("all")
        cmd.show("cartoon", "polymer")
        cmd.show("sticks", f"resn {ligand_resname}")
        cmd.set_color("protein_blue", [0.275, 0.510, 0.706])
        cmd.set_color("ligand_orange", [1.0, 0.271, 0.0])
        cmd.color("protein_blue", "polymer")
        cmd.color("ligand_orange", f"resn {ligand_resname} and elem C")
        cmd.color("red", f"resn {ligand_resname} and elem O")
        cmd.color("tv_blue", f"resn {ligand_resname} and elem N")
        cmd.set("cartoon_fancy_helices", 1)
        cmd.set("stick_radius", 0.15)
        cmd.set("ray_opaque_background", 0)
        cmd.bg_color("white")
        cmd.set_view(view)

        panel_png = Path(tmpdir) / f"panel_{fi}.png"
        cmd.ray(600, 600)
        cmd.png(str(panel_png), dpi=150)
        panel_paths.append((fi, time_ps, panel_png))
        cmd.delete("complex")

    # Stitch panels into a single figure
    n_panels = len(panel_paths)
    fig, axes = plt.subplots(1, n_panels, figsize=(4 * n_panels, 4))
    if n_panels == 1:
        axes = [axes]

    for ax, (fi, time_ps, png_path) in zip(axes, panel_paths):
        img = plt.imread(str(png_path))
        ax.imshow(img)
        ax.set_title(f"Frame {fi} ({time_ps:.1f} ps)", fontsize=10)
        ax.axis("off")

    fig.suptitle("Binding Pocket Snapshots", fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    # Clean up temp files
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze protein-ligand MD trajectory."
    )
    parser.add_argument("--topology", required=True, help="Topology PDB file.")
    parser.add_argument("--trajectory", required=True, help="Trajectory file (DCD, XTC, etc.).")
    parser.add_argument("--ligand_resname", default="UNL", help="Ligand residue name (default: UNL).")
    parser.add_argument("--pocket_cutoff", type=float, default=5.0, help="Pocket definition cutoff in A (default: 5.0).")
    parser.add_argument("--skip_frames", type=int, default=0, help="Skip first N frames (default: 0).")
    parser.add_argument("--stride", type=int, default=1, help="Frame stride for IFP (default: 1).")
    parser.add_argument("--rmsd_only", action="store_true", help="Only compute ligand RMSD.")
    parser.add_argument("--snapshots", action="store_true", help="Render PyMOL binding pocket snapshots (requires pymol-open-source).")
    parser.add_argument("--output_dir", required=True, help="Output directory.")
    args = parser.parse_args()

    topo_path = Path(args.topology)
    traj_path = Path(args.trajectory)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)

    if not topo_path.exists():
        print(f"ERROR: Topology not found: {topo_path}", file=sys.stderr)
        sys.exit(1)
    if not traj_path.exists():
        print(f"ERROR: Trajectory not found: {traj_path}", file=sys.stderr)
        sys.exit(1)

    ligand_sel = f"resname {args.ligand_resname}"

    # Load universe and unwrap PBC
    print(f"Loading trajectory: {traj_path}")
    u = mda.Universe(str(topo_path), str(traj_path))
    n_frames = len(u.trajectory)
    print(f"Trajectory: {n_frames} frames")

    # Fix PBC wrapping: place ligand near protein using minimum image convention.
    # trans.unwrap() requires bond topology which is often missing for ligands
    # from OpenMM DCD trajectories. The minimum-image approach is more robust.
    make_ligand_whole_minimum_image(u, ligand_sel)
    print("Applied minimum-image PBC correction for ligand.")

    # Ligand RMSD
    print("Computing ligand RMSD...")
    rmsd_data = compute_ligand_rmsd(u, ligand_sel, skip=args.skip_frames)
    write_csv(rmsd_data, output_dir / "ligand_rmsd.csv")
    plot_rmsd(rmsd_data, plots_dir / "ligand_rmsd.png")

    summary = {
        "n_frames": n_frames,
        "skip_frames": args.skip_frames,
        "ligand_resname": args.ligand_resname,
    }

    if rmsd_data:
        rmsds = [d["rmsd_angstrom"] for d in rmsd_data]
        summary["ligand_rmsd_mean_A"] = round(float(np.mean(rmsds)), 4)
        summary["ligand_rmsd_std_A"] = round(float(np.std(rmsds)), 4)
        summary["ligand_rmsd_max_A"] = round(float(np.max(rmsds)), 4)

    if args.rmsd_only:
        summary_path = output_dir / "analysis_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=4)
        print(f"RMSD-only analysis complete. Results in {output_dir}")
        return

    # COM drift
    print("Computing ligand COM...")
    com_data = compute_ligand_com(u, ligand_sel, skip=args.skip_frames)
    write_csv(com_data, output_dir / "ligand_com.csv")
    plot_com(com_data, plots_dir / "ligand_com.png")

    if com_data:
        first_rel = np.array([com_data[0]["rel_com_x"], com_data[0]["rel_com_y"], com_data[0]["rel_com_z"]])
        last_rel = np.array([com_data[-1]["rel_com_x"], com_data[-1]["rel_com_y"], com_data[-1]["rel_com_z"]])
        summary["ligand_com_drift_A"] = round(float(np.linalg.norm(last_rel - first_rel)), 4)

    # Pocket RMSF
    print("Computing pocket RMSF...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rmsf_data = compute_pocket_rmsf(u, ligand_sel, args.pocket_cutoff, skip=args.skip_frames)
    write_csv(rmsf_data, output_dir / "pocket_rmsf.csv")
    plot_rmsf(rmsf_data, plots_dir / "pocket_rmsf.png")
    summary["n_pocket_residues"] = len(rmsf_data)

    # Hydrogen bonds
    print("Computing hydrogen bonds...")
    hbond_data = compute_hbonds(u, ligand_sel, skip=args.skip_frames)
    write_csv(hbond_data, output_dir / "hbonds.csv")
    summary["n_hbonds_detected"] = len(hbond_data)

    # Contacts
    print("Computing contact occupancy...")
    contacts_data = compute_contacts_occupancy(u, ligand_sel, args.pocket_cutoff, skip=args.skip_frames)
    write_csv(contacts_data, output_dir / "contacts.csv")
    plot_contacts(contacts_data, plots_dir / "contacts.png")
    summary["n_contact_residues"] = len(contacts_data)

    # Interaction fingerprints (optional)
    print("Computing interaction fingerprints...")
    ifp_data = compute_interaction_fingerprints(
        str(topo_path), str(traj_path), args.ligand_resname,
        skip=args.skip_frames, stride=args.stride,
    )
    if ifp_data is not None:
        write_csv(ifp_data, output_dir / "interaction_fingerprints.csv")
        summary["ifp_computed"] = True
    else:
        summary["ifp_computed"] = False

    # Binding pocket snapshots (opt-in, requires PyMOL)
    # Run last because PyMOL initialization can interfere with
    # multiprocessing-based analyses like ProLIF.
    if args.snapshots:
        print("Rendering binding pocket snapshots...")
        plot_binding_snapshots(u, ligand_sel, plots_dir / "binding_snapshots.png", skip=args.skip_frames)

    summary_path = output_dir / "analysis_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=4)

    print(f"\nAnalysis complete. Results in {output_dir}")
    print(f"  RMSD mean: {summary.get('ligand_rmsd_mean_A', 'N/A')} A")
    print(f"  COM drift: {summary.get('ligand_com_drift_A', 'N/A')} A")
    print(f"  Pocket residues: {summary.get('n_pocket_residues', 0)}")
    print(f"  H-bonds: {summary.get('n_hbonds_detected', 0)}")
    print(f"  Contact residues: {summary.get('n_contact_residues', 0)}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
