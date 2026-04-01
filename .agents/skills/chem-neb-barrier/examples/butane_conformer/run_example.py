"""
NEB example: Butane gauche-to-anti conformational change.

A textbook NEB example — rotation around the central C-C bond in n-butane.
No bonds are broken/formed, just a dihedral rotation through an eclipsed TS.

    gauche (60°) --> eclipsed TS (~0°/120°) --> anti (180°)

Literature barrier: ~0.15 eV (3.4 kcal/mol) for gauche-to-anti via eclipsed TS

Usage (from project root):
    conda activate mace-agent
    python .agents/skills/chem-neb-barrier/examples/butane_conformer/run_example.py
"""
import os
import sys
import json
import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.insert(0, project_root)

from ase.io import read, write
from ase.optimize import FIRE
from ase.mep import NEB, NEBTools
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.utils.mlips.mace.mace_wrapper import MACEWrapper

EXAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(EXAMPLE_DIR, "output")

MODEL_NAME = "MACE-OFF23-small"
N_IMAGES = 7
FMAX_RELAX = 0.005
FMAX_NEB = 0.02
MAX_STEPS = 300


def compute_dihedral(pos: np.ndarray, idx: list) -> float:
    """Compute dihedral angle for 4 atom indices, in degrees."""
    b1 = pos[idx[1]] - pos[idx[0]]
    b2 = pos[idx[2]] - pos[idx[1]]
    b3 = pos[idx[3]] - pos[idx[2]]
    n1 = np.cross(b1, b2)
    n2 = np.cross(b2, b3)
    norm1 = np.linalg.norm(n1)
    norm2 = np.linalg.norm(n2)
    if norm1 < 1e-10 or norm2 < 1e-10:
        return 0.0
    n1 = n1 / norm1
    n2 = n2 / norm2
    m1 = np.cross(n1, b2 / np.linalg.norm(b2))
    x = np.dot(n1, n2)
    y = np.dot(m1, n2)
    return np.degrees(np.arctan2(y, x))


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading {MODEL_NAME}...")
    wrapper = MACEWrapper(model_name=MODEL_NAME)
    wrapper.load()

    # Load RDKit-generated structures
    gauche = read(os.path.join(EXAMPLE_DIR, "gauche_butane.xyz"))
    anti = read(os.path.join(EXAMPLE_DIR, "anti_butane.xyz"))
    gauche.pbc = False
    anti.pbc = False

    # Carbon indices for dihedral (first 4 atoms from RDKit SMILES "CCCC")
    c_idx = [0, 1, 2, 3]
    print(f"Initial dihedrals (C0-C1-C2-C3):")
    print(f"  Gauche: {compute_dihedral(gauche.positions, c_idx):.1f} deg")
    print(f"  Anti: {compute_dihedral(anti.positions, c_idx):.1f} deg")

    # Step 1: Relax endpoints
    print("\nRelaxing gauche-butane...")
    gauche.calc = wrapper.create_calculator()
    opt_g = FIRE(gauche)
    opt_g.run(fmax=FMAX_RELAX, steps=500)
    e_gauche = gauche.get_potential_energy()
    d_gauche = compute_dihedral(gauche.positions, c_idx)
    print(f"  Gauche energy: {e_gauche:.6f} eV, dihedral: {d_gauche:.1f} deg")

    print("Relaxing anti-butane...")
    anti.calc = wrapper.create_calculator()
    opt_a = FIRE(anti)
    opt_a.run(fmax=FMAX_RELAX, steps=500)
    e_anti = anti.get_potential_energy()
    d_anti = compute_dihedral(anti.positions, c_idx)
    print(f"  Anti energy: {e_anti:.6f} eV, dihedral: {d_anti:.1f} deg")

    energy_diff = e_gauche - e_anti
    print(f"  Energy diff (gauche - anti): {energy_diff:.4f} eV ({energy_diff * 23.0609:.2f} kcal/mol)")

    write(os.path.join(OUTPUT_DIR, "gauche_relaxed.xyz"), gauche)
    write(os.path.join(OUTPUT_DIR, "anti_relaxed.xyz"), anti)

    # Step 2: Build NEB band (gauche -> anti)
    print(f"\nBuilding NEB band with {N_IMAGES} intermediate images (gauche -> anti)...")
    images = [gauche.copy()]
    for _ in range(N_IMAGES):
        images.append(gauche.copy())
    images.append(anti.copy())

    for image in images:
        image.calc = wrapper.create_calculator()

    neb = NEB(images, climb=True, allow_shared_calculator=False)
    neb.interpolate(method="idpp", mic=False)

    # Print initial dihedrals along path
    print("  Initial path dihedrals:")
    for i, img in enumerate(images):
        d = compute_dihedral(img.positions, c_idx)
        print(f"    Image {i}: {d:.1f} deg")

    # Step 3: Run NEB
    print(f"\nRunning CI-NEB (fmax={FMAX_NEB}, max_steps={MAX_STEPS})...")
    opt = FIRE(neb, trajectory=os.path.join(OUTPUT_DIR, "neb.traj"))
    converged = opt.run(fmax=FMAX_NEB, steps=MAX_STEPS)

    # Step 4: Analysis
    neb_tools = NEBTools(images)
    barrier_fwd = neb_tools.get_barrier()[0]
    barrier_rev = neb_tools.get_barrier()[1]

    energies = [img.get_potential_energy() for img in images]
    ts_idx = np.argmax(energies)
    ts_structure = images[ts_idx]

    print(f"\n=== NEB Results ===")
    print(f"Forward barrier (gauche -> anti): {barrier_fwd:.4f} eV ({barrier_fwd * 23.0609:.2f} kcal/mol)")
    print(f"Reverse barrier (anti -> gauche): {barrier_rev:.4f} eV ({barrier_rev * 23.0609:.2f} kcal/mol)")
    print(f"Converged: {converged}")
    print(f"TS image index: {ts_idx}")
    print(f"Literature: ~0.15 eV (3.4 kcal/mol) gauche->anti")

    # Final dihedral path
    print(f"\nFinal path dihedrals:")
    dihedrals = []
    for i, img in enumerate(images):
        d = compute_dihedral(img.positions, c_idx)
        dihedrals.append(d)
        e_rel = (img.get_potential_energy() - e_gauche) * 1000
        print(f"  Image {i}: dihedral = {d:.1f} deg, E_rel = {e_rel:.1f} meV")

    # Save outputs
    write(os.path.join(OUTPUT_DIR, "ts_neb.xyz"), ts_structure)
    write(os.path.join(OUTPUT_DIR, "neb_path.xyz"), images, format="extxyz")

    # Plot
    fig = neb_tools.plot_band()
    fig.savefig(os.path.join(OUTPUT_DIR, "neb_barrier_plot.png"), dpi=300)
    plt.close(fig)
    print(f"\nSaved barrier plot to {os.path.join(OUTPUT_DIR, 'neb_barrier_plot.png')}")

    # Save JSON
    results = {
        "model": MODEL_NAME,
        "reaction": "butane_gauche_to_anti",
        "formula": "C4H10",
        "n_atoms": 14,
        "n_images": N_IMAGES,
        "fmax_relax": FMAX_RELAX,
        "fmax_neb": FMAX_NEB,
        "max_steps": MAX_STEPS,
        "periodic": False,
        "converged": bool(converged),
        "gauche_energy_eV": float(e_gauche),
        "anti_energy_eV": float(e_anti),
        "energy_diff_eV": float(energy_diff),
        "energy_diff_kcal_mol": float(energy_diff * 23.0609),
        "forward_barrier_eV": float(barrier_fwd),
        "reverse_barrier_eV": float(barrier_rev),
        "forward_barrier_kcal_mol": float(barrier_fwd * 23.0609),
        "reverse_barrier_kcal_mol": float(barrier_rev * 23.0609),
        "ts_dihedral_deg": float(compute_dihedral(ts_structure.positions, c_idx)),
        "dihedrals_deg": [float(d) for d in dihedrals],
        "energies_eV": [float(e) for e in energies],
    }

    with open(os.path.join(OUTPUT_DIR, "neb_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
