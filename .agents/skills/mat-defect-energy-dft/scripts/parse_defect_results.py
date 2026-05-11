"""
Parse DFT results for defect calculations and compute formation energy diagrams.

Applies Freysoldt (FNV) finite-size corrections for charged defects and
produces formation energy vs. Fermi energy plots.

Usage:
    python parse_defect_results.py --bulk_dir dft_bulk/ --defect_dir dft_defect_calcs/ \
        --defect_index dft_defects/defect_index.json --dielectric 9.8 \
        --output formation_energies.json --plot formation_energy_diagram.png

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, pymatgen-analysis-defects, matplotlib
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


def parse_vasp_energy(calc_dir: Path) -> Optional[float]:
    """
    Parse total energy from VASP output files.

    Looks for vasprun.xml(.gz), OSZICAR, or relaxation result JSON files.

    Args:
        calc_dir: Directory containing VASP outputs.

    Returns:
        Total energy in eV, or None if not found.
    """
    # Try vasprun.xml first
    for vr_name in ["vasprun.xml", "vasprun.xml.gz"]:
        vr_path = calc_dir / vr_name
        if vr_path.exists():
            from pymatgen.io.vasp import Vasprun
            vr = Vasprun(str(vr_path), parse_dos=False, parse_eigen=False)
            return vr.final_energy

    # Try OSZICAR
    oszicar_path = calc_dir / "OSZICAR"
    if oszicar_path.exists():
        from pymatgen.io.vasp import Oszicar
        osz = Oszicar(str(oszicar_path))
        return osz.final_energy

    # Try MCP-style result files
    for fname in ["relaxation_results.json", "result.json"]:
        fpath = calc_dir / fname
        if fpath.exists():
            with open(fpath) as f:
                data = json.load(f)
            energy = data.get("relaxed_energy") or data.get("energy") or data.get("final_energy")
            if energy is not None:
                return float(energy)

    # Try relaxed_energy.txt
    txt_path = calc_dir / "relaxed_energy.txt"
    if txt_path.exists():
        with open(txt_path) as f:
            return float(f.read().strip())

    return None


def parse_vasp_vbm_bandgap(calc_dir: Path) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse VBM and band gap from VASP bulk calculation.

    Args:
        calc_dir: Directory containing bulk VASP outputs.

    Returns:
        Tuple of (VBM in eV, band gap in eV), or (None, None).
    """
    for vr_name in ["vasprun.xml", "vasprun.xml.gz"]:
        vr_path = calc_dir / vr_name
        if vr_path.exists():
            from pymatgen.io.vasp import Vasprun
            vr = Vasprun(str(vr_path), parse_dos=True, parse_eigen=True)
            bs = vr.get_band_structure()
            vbm = bs.get_vbm()["energy"]
            if bs.is_metal():
                return vbm, 0.0
            bg = bs.get_band_gap()["energy"]
            return vbm, bg

    return None, None


def compute_freysoldt_correction(
    charge: int,
    dielectric: float,
    lattice_volume: float,
    lattice_length: float,
) -> float:
    """
    Simplified Madelung-based point-charge correction for charged defects.

    This is a first-order approximation. For full Freysoldt corrections,
    use pymatgen.analysis.defects.corrections.FreysoldtCorrection with
    the potential alignment term.

    E_corr ≈ -alpha_M * q^2 / (2 * epsilon * L)

    where alpha_M ≈ 2.8373 (Madelung constant for sc), L = V^(1/3).

    Args:
        charge: Defect charge state.
        dielectric: Static dielectric constant.
        lattice_volume: Supercell volume in Å³.
        lattice_length: Characteristic length V^(1/3) in Å.

    Returns:
        Correction energy in eV.
    """
    if charge == 0:
        return 0.0

    # Madelung constant for simple cubic
    ALPHA_MADELUNG = 2.8373
    # Conversion: e^2/(4*pi*eps0) in eV·Å
    COULOMB_CONST = 14.3996

    e_corr = -ALPHA_MADELUNG * charge**2 * COULOMB_CONST / (2.0 * dielectric * lattice_length)
    return e_corr


def compute_formation_energies(
    bulk_energy: float,
    bulk_num_atoms: int,
    defect_entries: List[dict],
    vbm: float,
    band_gap: float,
    dielectric: float,
    elemental_energies: Dict[str, float],
    lattice_volume: float,
) -> List[dict]:
    """
    Compute formation energies for all defect entries.

    Args:
        bulk_energy: Total energy of pristine supercell.
        bulk_num_atoms: Number of atoms in pristine supercell.
        defect_entries: List of defect dicts with 'energy', 'charge', etc.
        vbm: Valence band maximum energy.
        band_gap: Band gap in eV.
        dielectric: Static dielectric constant.
        elemental_energies: Dict of element -> energy_per_atom.
        lattice_volume: Supercell volume in Å³.

    Returns:
        List of formation energy results.
    """
    e_bulk_per_atom = bulk_energy / bulk_num_atoms
    lattice_length = lattice_volume ** (1.0 / 3.0)

    results = []
    # Sample Fermi energies across the band gap
    fermi_energies = np.linspace(0, band_gap, 50).tolist()

    for entry in defect_entries:
        q = entry["charge"]
        e_defect = entry["energy"]
        n_defect = entry["num_atoms"]

        # Chemical potential correction
        delta_n = entry.get("delta_n", {})
        mu_correction = sum(dn * elemental_energies.get(el, 0.0) for el, dn in delta_n.items())

        # Finite-size correction
        e_corr = compute_freysoldt_correction(q, dielectric, lattice_volume, lattice_length)

        # Formation energy at each Fermi level
        # E_f = E_defect - (n_defect/n_bulk)*E_bulk + sum(Dn_i*mu_i) + q*(VBM + E_F) + E_corr
        e_f_at_vbm = (
            e_defect
            - (n_defect / bulk_num_atoms) * bulk_energy
            + mu_correction
            + q * vbm
            + e_corr
        )

        formation_vs_fermi = []
        for ef in fermi_energies:
            e_f = e_f_at_vbm + q * ef
            formation_vs_fermi.append({"fermi_eV": ef, "formation_eV": e_f})

        results.append({
            "name": entry["name"],
            "base_name": entry.get("base_name", entry["name"]),
            "charge": q,
            "defect_energy_eV": e_defect,
            "correction_eV": e_corr,
            "mu_correction_eV": mu_correction,
            "formation_at_vbm_eV": e_f_at_vbm,
            "formation_vs_fermi": formation_vs_fermi,
        })

    return results


def plot_formation_energy_diagram(
    results: List[dict],
    band_gap: float,
    output_path: str,
) -> None:
    """
    Plot formation energy vs. Fermi energy diagram.

    Args:
        results: List of formation energy result dicts.
        band_gap: Band gap in eV (x-axis range).
        output_path: Path to save the plot.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6))

    # Group by base defect name
    grouped = {}
    for r in results:
        base = r["base_name"]
        if base not in grouped:
            grouped[base] = []
        grouped[base].append(r)

    colors = plt.cm.tab10(np.linspace(0, 1, len(grouped)))

    for (base_name, entries), color in zip(grouped.items(), colors):
        # For each Fermi energy, find the lowest formation energy across charge states
        fermi_vals = [p["fermi_eV"] for p in entries[0]["formation_vs_fermi"]]
        min_ef = []
        for j in range(len(fermi_vals)):
            min_val = min(e["formation_vs_fermi"][j]["formation_eV"] for e in entries)
            min_ef.append(min_val)

        ax.plot(fermi_vals, min_ef, "-", color=color, linewidth=2, label=base_name)

        # Also plot individual charge states as dashed lines
        for entry in entries:
            ef_vals = [p["formation_eV"] for p in entry["formation_vs_fermi"]]
            ax.plot(fermi_vals, ef_vals, "--", color=color, alpha=0.3, linewidth=1)

    ax.set_xlabel("Fermi Energy (eV)", fontsize=14)
    ax.set_ylabel("Formation Energy (eV)", fontsize=14)
    ax.set_title("Defect Formation Energy Diagram", fontsize=16)
    ax.set_xlim(0, band_gap)
    ax.legend(fontsize=10)
    ax.axhline(y=0, color="gray", linestyle=":", alpha=0.5)
    ax.tick_params(labelsize=12)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    print(f"✓ Saved formation energy diagram to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Parse DFT defect results and compute formation energy diagrams."
    )
    parser.add_argument("--bulk_dir", required=True, help="Directory with bulk DFT results")
    parser.add_argument("--defect_dir", required=True, help="Directory with defect DFT results")
    parser.add_argument(
        "--defect_index", required=True,
        help="JSON file with defect index (from generate_defect_structures.py)"
    )
    parser.add_argument(
        "--dielectric", type=float, required=True,
        help="Static dielectric constant of the host material"
    )
    parser.add_argument(
        "--elemental_energies", default=None,
        help="JSON file mapping element -> energy_per_atom (eV/atom)"
    )
    parser.add_argument("--output", default="formation_energies.json", help="Output JSON")
    parser.add_argument("--plot", default=None, help="Output plot path (png)")
    args = parser.parse_args()

    # Load defect index
    with open(args.defect_index) as f:
        defect_index = json.load(f)

    bulk_num_atoms = defect_index["pristine_num_atoms"]
    print(f"✓ Defect index: {len(defect_index['defects'])} entries, "
          f"pristine = {bulk_num_atoms} atoms")

    # Parse bulk energy
    bulk_dir = Path(args.bulk_dir)
    bulk_energy = parse_vasp_energy(bulk_dir)
    if bulk_energy is None:
        raise FileNotFoundError(f"No energy found in bulk directory: {bulk_dir}")
    print(f"✓ Bulk energy: {bulk_energy:.4f} eV ({bulk_energy/bulk_num_atoms:.4f} eV/atom)")

    # Try to get VBM and band gap
    vbm, band_gap = parse_vasp_vbm_bandgap(bulk_dir)
    if vbm is None:
        print("⚠️  Could not parse VBM/band gap from bulk calculation.")
        print("   Using VBM=0.0 and band_gap=5.0 as defaults. Update manually.")
        vbm = 0.0
        band_gap = 5.0
    else:
        print(f"✓ VBM = {vbm:.4f} eV, Band gap = {band_gap:.4f} eV")

    # Load elemental energies
    elem_energies = {}
    if args.elemental_energies and Path(args.elemental_energies).exists():
        with open(args.elemental_energies) as f:
            elem_energies = json.load(f)

    # Parse defect energies
    defect_dir = Path(args.defect_dir)
    defect_entries = []

    for defect_info in defect_index["defects"]:
        name = defect_info["name"]
        # Look for subdirectory matching defect name
        subdir = defect_dir / name
        if not subdir.is_dir():
            print(f"⚠️  No results directory for {name}, skipping")
            continue

        energy = parse_vasp_energy(subdir)
        if energy is None:
            print(f"⚠️  No energy for {name}, skipping")
            continue

        # Compute delta_n (pristine - defect composition)
        from pymatgen.core import Structure
        defect_struct = Structure.from_file(defect_info["file"])
        pristine_path = Path(args.defect_index).parent / "pristine_supercell.cif"
        pristine_struct = Structure.from_file(str(pristine_path))

        pristine_comp = {str(el): int(amt) for el, amt in pristine_struct.composition.element_composition.items()}
        defect_comp = {str(el): int(amt) for el, amt in defect_struct.composition.element_composition.items()}

        delta_n = {}
        for el in set(list(pristine_comp.keys()) + list(defect_comp.keys())):
            dn = pristine_comp.get(el, 0) - defect_comp.get(el, 0)
            if dn != 0:
                delta_n[el] = dn

        entry = {
            "name": name,
            "base_name": defect_info.get("base_name", name),
            "charge": defect_info["charge"],
            "energy": energy,
            "num_atoms": defect_info["num_atoms"],
            "delta_n": delta_n,
        }
        defect_entries.append(entry)
        print(f"  ✓ {name}: E = {energy:.4f} eV, q = {defect_info['charge']:+d}")

    if not defect_entries:
        print("⚠️  No defect energies parsed. Ensure DFT calculations have completed.")
        return

    # Get lattice volume from pristine
    lattice_volume = pristine_struct.volume

    # Compute formation energies
    results = compute_formation_energies(
        bulk_energy=bulk_energy,
        bulk_num_atoms=bulk_num_atoms,
        defect_entries=defect_entries,
        vbm=vbm,
        band_gap=band_gap,
        dielectric=args.dielectric,
        elemental_energies=elem_energies,
        lattice_volume=lattice_volume,
    )

    # Save results
    output_data = {
        "bulk_energy_eV": bulk_energy,
        "bulk_energy_per_atom_eV": bulk_energy / bulk_num_atoms,
        "vbm_eV": vbm,
        "band_gap_eV": band_gap,
        "dielectric_constant": args.dielectric,
        "defects": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize, converting numpy types
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else o)

    print(f"\n✓ Saved {len(results)} formation energies to {output_path}")

    # Plot if requested
    if args.plot:
        plot_formation_energy_diagram(results, band_gap, args.plot)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
