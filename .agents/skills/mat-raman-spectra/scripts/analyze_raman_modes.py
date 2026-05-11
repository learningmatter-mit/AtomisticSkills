"""
Analyse Raman-active phonon modes from a phonopy calculation and simulate Raman spectrum.

Workflow
--------
1. Load phonon.yaml produced by mat-phonon skill (phonopy output).
2. Extract Γ-point eigenvectors and frequencies.
3. Determine Raman-active modes via phonopy irreducible representations (IrReps)
   and point-group selection rules.
4. Simulate spectrum using Lorentzian broadening.
5. Optionally compute Raman intensities from VASP Born effective charges (DFT tier).

Usage
-----
    # MLIP tier (equal intensities)
    python analyze_raman_modes.py \
        --phonon-yaml phonon/phonon.yaml \
        --structure relax/relaxed_structure.cif \
        --output-dir raman/

    # DFT tier (computed intensities)
    python analyze_raman_modes.py \
        --phonon-yaml phonon/phonon.yaml \
        --structure relax/relaxed_structure.cif \
        --born-charges vasp_dfpt/OUTCAR \
        --output-dir raman_dft/

Requirements
------------
    - Conda environment: base-agent
    - Required packages: phonopy, pymatgen, numpy, matplotlib
"""

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.research_utils import get_current_research_dir

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("RamanAnalysis")

# ---------------------------------------------------------------------------
# Raman/IR activity selection rules by point group
# ---------------------------------------------------------------------------
# For centrosymmetric point groups the mutual exclusion rule applies:
#   modes with 'g' suffix → Raman active; 'u' suffix → IR active.
# For non-centrosymmetric groups nearly all modes can be both.

CENTROSYMMETRIC_POINT_GROUPS = {
    "Ci", "C2h", "D2h", "C4h", "D4h", "S6", "D3d",
    "C6h", "D6h", "Th", "Oh", "S10",
    # Hermann-Mauguin equivalents
    "-1", "2/m", "mmm", "4/m", "4/mmm", "-3", "-3m",
    "6/m", "6/mmm", "m-3", "m-3m",
}


def _is_raman_active(label: str, point_group: str) -> bool:
    """Return True if a mode with the given symmetry label is Raman active.

    Uses the mutual exclusion rule for centrosymmetric groups (g → Raman),
    and conservatively marks all non-acoustic modes as Raman active for
    non-centrosymmetric groups (where the selection rules depend on specific
    irreducible representations that require the full character table).
    """
    # Strip trailing characters like ',' or digits used for degeneracy
    clean = label.strip().rstrip(",")

    # Acoustic-like labels
    if clean in {"Au", "A1u", "B1u", "B2u", "Eu", "T1u", "A2u"}:
        # These are common acoustic representations — handled separately
        pass

    if point_group in CENTROSYMMETRIC_POINT_GROUPS:
        # Raman active ↔ gerade (ends with 'g'), BUT excluding A2g (rotation, Raman inactive)
        if clean in {"A2g"}:
            return False
        return clean.endswith("g") or clean.endswith("g'") or clean.endswith("g\"")

    # Non-centrosymmetric: all modes are potentially Raman active.
    # (A full determination requires the character table of the specific point group.)
    return True


def load_phonopy_result(phonon_yaml: str):
    """Load a phonopy Phonopy object from phonon.yaml."""
    import phonopy
    phonon = phonopy.load(phonopy_yaml=phonon_yaml)
    return phonon


def get_gamma_frequencies_and_eigenvectors(
    phonon,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract Γ-point frequencies (cm⁻¹) and eigenvectors from a Phonopy object."""
    phonon.run_band_structure(
        paths=[[np.array([0.0, 0.0, 0.0])]],
        with_eigenvectors=True,
    )
    band_dict = phonon.get_band_structure_dict()
    # band_dict['frequencies'] shape: (n_paths, n_qpoints, n_bands)
    freqs_thz = band_dict["frequencies"][0][0]  # THz
    eigvecs = band_dict["eigenvectors"][0][0]   # (n_atoms*3, n_bands)

    # Convert THz → cm⁻¹  (1 THz = 33.3564 cm⁻¹)
    freqs_cm = freqs_thz * 33.3564
    return freqs_cm, eigvecs


def get_point_group(structure_path: str) -> str:
    """Return the point group symbol of the crystal from its space group."""
    from pymatgen.core import Structure
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    struct = Structure.from_file(structure_path)
    sga = SpacegroupAnalyzer(struct, symprec=0.1)
    pg = sga.get_point_group_symbol()
    logger.info(f"Point group: {pg}")
    return pg


def run_irreps(phonon, freq_tolerance_cm: float = 0.5) -> Optional[dict]:
    """Run phonopy IrReps analysis at Γ and return a dict of {band_index: label}.

    Supports phonopy 3.x (set_irreps / phonon.irreps) and legacy 2.x (run_irreps).
    Returns None if IrReps fails (e.g., non-symmorphic space groups not supported).
    """
    try:
        # phonopy 3.x API: set_irreps populates phonon.irreps
        if hasattr(phonon, "set_irreps"):
            phonon.set_irreps(q=[0.0, 0.0, 0.0])
            irreps_obj = phonon.irreps
            ir_labels = irreps_obj._ir_labels        # list, may contain None
            ir_freqs_thz = list(irreps_obj.frequencies)
        else:
            # Legacy phonopy 2.x
            phonon.run_irreps(q_point=np.array([0.0, 0.0, 0.0]))
            irreps_obj = phonon.get_irreps()
            ir_labels = irreps_obj.get_ir_labels()
            ir_freqs_thz = list(irreps_obj.get_ir_frequencies())

        result = {}
        for i, (label, freq_thz) in enumerate(zip(ir_labels, ir_freqs_thz)):
            result[i] = {
                "label": label if label else "Unknown",
                "freq_cm": float(freq_thz * 33.3564),
            }
        return result
    except Exception as exc:
        logger.warning(f"IrReps analysis failed: {exc}. Will use 'Unknown' labels.")
        return None



def compute_raman_intensities_from_born(
    phonon,
    outcar_path: str,
    laser_wavelength_nm: float = 532.0,
    temperature_K: float = 300.0,
) -> Optional[np.ndarray]:
    """Compute non-resonant Raman intensities from Born charges and dielectric tensor.

    Uses the bond-polarizability model:
        α_ν = Σ_k (Z*_k · e_ν,k) / sqrt(m_k)
    Intensity ∝ |α_ν|² · (ω_laser - ω_ν)⁴ / ω_ν · Bose-Einstein factor.

    Args:
        phonon       : loaded Phonopy object with force constants
        outcar_path  : path to VASP OUTCAR containing Born charges and ε_∞
        laser_wavelength_nm : laser wavelength in nm (default 532 = green)
        temperature_K       : temperature for Bose-Einstein factor

    Returns:
        Array of Raman intensities (arbitrary units), length = n_modes.
        Returns None if parsing fails.
    """
    try:
        from pymatgen.io.vasp.outputs import Outcar
        outcar = Outcar(outcar_path)
        born_charges = np.array(outcar.born)     # shape (n_atoms, 3, 3)
        epsilon_inf = np.array(outcar.dielectric_tensor)  # shape (3, 3)
    except Exception as exc:
        logger.warning(f"Failed to parse Born charges from {outcar_path}: {exc}")
        return None

    phonon.run_band_structure(
        paths=[[np.array([0.0, 0.0, 0.0])]],
        with_eigenvectors=True,
    )
    band_dict = phonon.get_band_structure_dict()
    freqs_thz = band_dict["frequencies"][0][0]
    eigvecs = band_dict["eigenvectors"][0][0]  # (n_dof, n_modes), complex

    masses = np.array([site.mass for site in phonon.primitive.sites])  # amu

    n_modes = len(freqs_thz)
    intensities = np.zeros(n_modes)

    omega_laser = 2 * np.pi * 3e14 / (laser_wavelength_nm * 1e-9)  # rad/s

    for nu in range(n_modes):
        freq_thz = freqs_thz[nu]
        if abs(freq_thz) < 0.1:
            continue

        omega_nu = 2 * np.pi * freq_thz * 1e12  # rad/s

        # Compute Raman tensor α_ν (sum over atoms)
        alpha_nu = np.zeros((3, 3))
        for k, (Z_k, m_k) in enumerate(zip(born_charges, masses)):
            # Normalised mass-weighted displacement for atom k in mode nu
            e_nu_k = eigvecs[3 * k: 3 * k + 3, nu].real / np.sqrt(m_k)
            # Raman tensor contribution: Z*_k contracted with mode displacement
            alpha_nu += np.outer(Z_k @ e_nu_k, np.ones(3))

        # Rotationally averaged intensity (isotropic powder)
        alpha_avg = np.trace(alpha_nu) / 3.0
        beta2 = 0.0
        for i in range(3):
            for j in range(3):
                beta2 += (alpha_nu[i, j] - (alpha_avg if i == j else 0)) ** 2
        beta2 /= 2.0
        I_classical = (10 * alpha_avg ** 2 + 7 * beta2)

        # Bose-Einstein correction
        hbar_omega = 1.0546e-34 * omega_nu
        kBT = 1.381e-23 * temperature_K
        bose_factor = 1.0
        if hbar_omega / kBT < 50:
            bose_factor = (1 + 1 / (np.exp(hbar_omega / kBT) - 1 + 1e-30))

        # Pre-factor: (ω_laser - ω_ν)⁴ / ω_ν
        pre = (omega_laser - omega_nu) ** 4 / (omega_nu + 1e-30) if freq_thz > 0.1 else 0.0

        intensities[nu] = max(0.0, pre * bose_factor * I_classical)

    # Normalise to maximum
    if intensities.max() > 0:
        intensities /= intensities.max()

    return intensities


def simulate_spectrum(
    freqs_cm: np.ndarray,
    intensities: np.ndarray,
    freq_min: float = 0.0,
    freq_max: float = 1000.0,
    n_points: int = 2000,
    broadening: float = 5.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Simulate Raman spectrum as a sum of Lorentzian peaks."""
    x = np.linspace(freq_min, freq_max, n_points)
    y = np.zeros_like(x)
    for freq, intensity in zip(freqs_cm, intensities):
        if freq < freq_min or freq > freq_max:
            continue
        gamma = broadening
        y += intensity * (gamma / 2) ** 2 / ((x - freq) ** 2 + (gamma / 2) ** 2)
    if y.max() > 0:
        y /= y.max()
    return x, y


def plot_spectrum(
    x: np.ndarray,
    y: np.ndarray,
    raman_freqs: list,
    output_path: str,
    title: str = "Raman Spectrum",
    intensity_type: str = "equal",
) -> None:
    """Plot simulated Raman spectrum and save to file."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 14})
    fig, ax = plt.subplots(figsize=(6, 5))

    ax.plot(x, y, linewidth=2.5, color="#2874A6", label="Simulated spectrum")

    # Mark mode positions
    for freq in raman_freqs:
        ax.axvline(freq, color="#E74C3C", linewidth=0.8, alpha=0.6, linestyle="--")

    intensity_note = (
        "equal intensities (MLIP tier)" if intensity_type == "equal"
        else "DFT Raman intensities"
    )
    ax.set_xlabel("Raman shift (cm⁻¹)", fontweight="bold")
    ax.set_ylabel("Intensity (arb. units)", fontweight="bold")
    ax.set_title(f"{title}\n({intensity_note})")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(frameon=False)
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.savefig(output_path.replace(".png", ".svg"), bbox_inches="tight")
    plt.close()
    logger.info(f"Saved Raman spectrum plot to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyse Raman-active phonon modes and simulate Raman spectrum."
    )
    parser.add_argument(
        "--phonon-yaml",
        required=True,
        help="Path to phonon.yaml produced by mat-phonon / phonopy.",
    )
    parser.add_argument(
        "--structure",
        required=True,
        help="Path to relaxed structure file (CIF, POSCAR, etc.).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to <research_dir>/raman.",
    )
    parser.add_argument(
        "--born-charges",
        default=None,
        help="Path to VASP OUTCAR with Born charges for DFT-tier intensities.",
    )
    parser.add_argument(
        "--broadening",
        type=float,
        default=5.0,
        help="Lorentzian HWHM in cm⁻¹ (default: 5.0).",
    )
    parser.add_argument(
        "--freq-max",
        type=float,
        default=1000.0,
        help="Maximum frequency for spectrum in cm⁻¹ (default: 1000).",
    )
    parser.add_argument(
        "--laser-wavelength",
        type=float,
        default=532.0,
        help="Laser wavelength in nm, used for Born-charge intensity pre-factor (default: 532).",
    )
    args = parser.parse_args()

    if args.output_dir is None:
        research_dir = get_current_research_dir()
        args.output_dir = str(research_dir / "raman")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading phonopy result from {args.phonon_yaml}")
    phonon = load_phonopy_result(args.phonon_yaml)

    logger.info("Extracting Γ-point frequencies and eigenvectors")
    freqs_cm, eigvecs = get_gamma_frequencies_and_eigenvectors(phonon)
    n_modes = len(freqs_cm)
    logger.info(f"Found {n_modes} modes at Γ-point")

    logger.info("Determining crystal point group")
    point_group = get_point_group(args.structure)

    logger.info("Running IrReps symmetry analysis")
    irreps_dict = run_irreps(phonon)

    # Determine Raman activity for each mode
    mode_records = []
    raman_freqs = []

    for i, freq in enumerate(freqs_cm):
        is_acoustic = abs(freq) < 5.0  # ≈ acoustic at Γ

        if irreps_dict and i in irreps_dict:
            label = irreps_dict[i]["label"]
        else:
            label = "Unknown"

        raman = False if is_acoustic else _is_raman_active(label, point_group)

        record = {
            "mode_index": int(i),
            "frequency_cm": round(float(freq), 2),
            "symmetry_label": str(label),
            "is_acoustic": bool(is_acoustic),
            "raman_active": bool(raman),
        }
        mode_records.append(record)

        if raman and not is_acoustic:
            raman_freqs.append(float(freq))

    n_raman = len(raman_freqs)
    logger.info(f"Identified {n_raman} Raman-active modes")

    # Intensities — DFT tier or equal weights
    intensity_type = "equal"
    intensities = np.zeros(n_modes)
    if args.born_charges:
        logger.info(f"Computing Raman intensities from Born charges: {args.born_charges}")
        dft_intensities = compute_raman_intensities_from_born(
            phonon, args.born_charges, laser_wavelength_nm=args.laser_wavelength
        )
        if dft_intensities is not None:
            intensities = dft_intensities
            intensity_type = "dft"
            logger.info("Using DFT-computed Raman intensities")
        else:
            logger.warning("DFT intensity computation failed; falling back to equal intensities")

    if intensity_type == "equal":
        for rec in mode_records:
            if rec["raman_active"] and not rec["is_acoustic"]:
                intensities[rec["mode_index"]] = 1.0
        for rec in mode_records:
            rec["raman_intensity"] = float(
                intensities[rec["mode_index"]] if rec["raman_active"] else 0.0
            )
    else:
        for rec in mode_records:
            rec["raman_intensity"] = round(float(intensities[rec["mode_index"]]), 6)

    # Simulate spectrum
    x, y = simulate_spectrum(
        freqs_cm=freqs_cm,
        intensities=intensities,
        freq_min=5.0,
        freq_max=args.freq_max,
        broadening=args.broadening,
    )

    # Save mode table (JSON)
    summary = {
        "structure": args.structure,
        "phonon_yaml": args.phonon_yaml,
        "point_group": point_group,
        "n_modes_total": n_modes,
        "n_raman_active": n_raman,
        "intensity_type": intensity_type,
        "broadening_cm": args.broadening,
        "modes": mode_records,
    }
    json_path = output_dir / "raman_modes.json"
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Saved mode table to {json_path}")

    # Save CSV
    csv_path = output_dir / "raman_modes_table.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["mode_index", "frequency_cm", "symmetry_label",
                        "is_acoustic", "raman_active", "raman_intensity"],
        )
        writer.writeheader()
        writer.writerows(mode_records)
    logger.info(f"Saved CSV table to {csv_path}")

    # Plot
    from pymatgen.core import Structure
    struct = Structure.from_file(args.structure)
    formula = struct.composition.reduced_formula
    plot_path = str(output_dir / "raman_spectrum.png")
    plot_spectrum(x, y, raman_freqs, plot_path, title=f"Raman Spectrum — {formula}", intensity_type=intensity_type)

    # Print summary
    print("\n" + "=" * 60)
    print("RAMAN ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"  Formula        : {formula}")
    print(f"  Point group    : {point_group}")
    print(f"  Total modes    : {n_modes}")
    print(f"  Raman active   : {n_raman}")
    print(f"  Intensity type : {intensity_type}")
    print(f"  Output dir     : {output_dir}")
    print("\n  Raman-active mode frequencies (cm⁻¹):")
    for rec in mode_records:
        if rec["raman_active"] and not rec["is_acoustic"]:
            print(f"    {rec['symmetry_label']:12s}  {rec['frequency_cm']:8.1f} cm⁻¹")
    print("=" * 60)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
