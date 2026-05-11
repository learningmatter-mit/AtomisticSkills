"""
Post-process and plot dielectric-response data from VASP.

This script is designed around the VASP dielectric tutorials and can overlay:
    - the independent-particle optical response from `LOPTICS`
    - the independent-particle response from `ALGO = CHI`
    - the local-field-corrected response from `ALGO = CHI`

The default output matches the tutorial-style comparison plot:
    - Re(epsilon) plotted above zero
    - -Im(epsilon) plotted below zero
    - IPA curves in black
    - RPA/DFT-local-field curves in red
    - `LOPTICS` curves in blue

Usage:
    python plot_dielectric.py <input_path> [--output output.png]

    where <input_path> is one of:
        - an `optics/` directory containing `vasprun.xml` or `vasprun.xml.gz`
        - a direct path to `vasprun.xml` or `vasprun.xml.gz`
        - a parent directory containing sibling `optics/` and `chi/` folders
        - an atomate2/jobflow directory containing `job_*/vasprun.xml(.gz)`
        - a wrapper output directory containing `results/structure_*/job_*/vasprun.xml(.gz)`

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, matplotlib, numpy
"""

import argparse
import gzip
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pymatgen.io.vasp import Vasprun


STATIC_DIELECTRIC_HEADER = (
    "HEAD OF MICROSCOPIC STATIC DIELECTRIC TENSOR "
    "(independent particle, excluding Hartree and local field effects)"
)


def find_vasprun(input_path: str) -> Path:
    """
    Resolve a VASP vasprun file from a direct file path or a calculation directory.

    Args:
        input_path: Path to a vasprun file or directory containing one.

    Returns:
        Path to `vasprun.xml` or `vasprun.xml.gz`.
    """
    path = Path(input_path)

    if path.is_file():
        return path

    if not path.exists():
        raise FileNotFoundError(f"Input path does not exist: {path}")

    direct_candidates = [
        path / "vasprun.xml",
        path / "vasprun.xml.gz",
    ]
    for candidate in direct_candidates:
        if candidate.exists():
            return candidate

    atomate2_candidates = sorted(path.glob("job_*/vasprun.xml.gz"))
    if atomate2_candidates:
        return atomate2_candidates[-1]

    atomate2_candidates = sorted(path.glob("job_*/vasprun.xml"))
    if atomate2_candidates:
        return atomate2_candidates[-1]

    wrapper_candidates = sorted(path.glob("results/structure_*/job_*/vasprun.xml.gz"))
    if wrapper_candidates:
        return wrapper_candidates[-1]

    wrapper_candidates = sorted(path.glob("results/structure_*/job_*/vasprun.xml"))
    if wrapper_candidates:
        return wrapper_candidates[-1]

    raise FileNotFoundError(
        f"Could not find vasprun.xml or vasprun.xml.gz under {path}"
    )


def find_chi_outcar(input_path: str, chi_outcar: str | None = None) -> Path | None:
    """
    Resolve an OUTCAR from an `ALGO = CHI` calculation when present.

    Args:
        input_path: Path to a vasprun file or calculation directory.
        chi_outcar: Optional explicit path to the CHI OUTCAR.

    Returns:
        Path to `OUTCAR` when found, otherwise `None`.
    """
    if chi_outcar is not None:
        path = Path(chi_outcar)
        if not path.exists():
            raise FileNotFoundError(f"CHI OUTCAR not found: {path}")
        return path

    path = Path(input_path)

    candidate_dirs: list[Path] = []
    if path.is_dir():
        candidate_dirs.append(path)
        candidate_dirs.append(path / "chi")
        if path.name == "optics":
            candidate_dirs.append(path.parent / "chi")
        candidate_dirs.extend(sorted(path.glob("job_*")))
        for structure_dir in sorted(path.glob("results/structure_*")):
            candidate_dirs.extend(sorted(structure_dir.glob("job_*")))
    elif path.is_file():
        candidate_dirs.append(path.parent)
        if path.parent.name == "optics":
            candidate_dirs.append(path.parent.parent / "chi")

    for candidate_dir in candidate_dirs:
        for candidate in (candidate_dir / "OUTCAR", candidate_dir / "OUTCAR.gz"):
            if candidate.exists():
                return candidate

    return None


def read_text_maybe_gz(path: Path) -> str:
    """
    Read plain-text content from a regular or gzipped file.

    Args:
        path: File path to read.

    Returns:
        Decoded file content.
    """
    if path.suffix == ".gz":
        with gzip.open(path, "rt", errors="ignore") as handle:
            return handle.read()
    return path.read_text(errors="ignore")


def find_primary_outcar(vasprun_path: Path) -> Path | None:
    """
    Resolve the OUTCAR associated with the main vasprun file being plotted.

    Args:
        vasprun_path: Path to the resolved vasprun file.

    Returns:
        Matching OUTCAR path when present, otherwise `None`.
    """
    for candidate in (vasprun_path.parent / "OUTCAR", vasprun_path.parent / "OUTCAR.gz"):
        if candidate.exists():
            return candidate
    return None


def ensure_frequency_dependent_calculation(vasprun_path: Path) -> None:
    """
    Fail fast when the selected output corresponds to a static dielectric run.

    Args:
        vasprun_path: Path to the resolved vasprun file.
    """
    outcar_path = find_primary_outcar(vasprun_path)
    if outcar_path is None:
        return

    outcar_text = read_text_maybe_gz(outcar_path)
    if STATIC_DIELECTRIC_HEADER in outcar_text:
        raise ValueError(
            "Detected a static dielectric calculation in OUTCAR. "
            "This calculation was a static calculation, not a frequency-dependent calculation."
        )


def parse_dielectric_section(outcar_path: Path, header: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse a dielectric data block from OUTCAR.

    The relevant tutorial blocks contain rows with energy, Re(epsilon), and
    Im(epsilon). Additional trailing text is ignored.

    Args:
        outcar_path: Path to OUTCAR from an `ALGO = CHI` calculation.
        header: Header line identifying the section to extract.

    Returns:
        Tuple of energies, real part, and imaginary part.
    """
    text = read_text_maybe_gz(outcar_path)
    lines = text.splitlines()

    start_idx = None
    for idx, line in enumerate(lines):
        if header in line:
            start_idx = idx + 1
            break

    if start_idx is None:
        raise ValueError(f"Could not find section '{header}' in {outcar_path}")

    number_pattern = re.compile(
        r"^\s*([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)"
    )

    energies: list[float] = []
    real: list[float] = []
    imag: list[float] = []
    saw_data = False

    for line in lines[start_idx:]:
        match = number_pattern.match(line)
        if match:
            energies.append(float(match.group(1)))
            real.append(float(match.group(2)))
            imag.append(float(match.group(3)))
            saw_data = True
            continue

        if saw_data and line.strip():
            break

    if not energies:
        raise ValueError(f"No dielectric data found after section '{header}' in {outcar_path}")

    return np.array(energies), np.array(real), np.array(imag)


def summarize_dielectric(energies: np.ndarray, real: np.ndarray, imag: np.ndarray) -> None:
    """
    Print a compact summary of the dielectric spectrum.

    Args:
        energies: Photon energies in eV.
        real: Real dielectric tensor components.
        imag: Imaginary dielectric tensor components.
    """
    eps1_avg = real[:, :3].mean(axis=1)
    eps2_avg = imag[:, :3].mean(axis=1)

    print("\nDielectric response summary:")
    print(f"  - Energy range: {energies.min():.3f} to {energies.max():.3f} eV")
    print(f"  - Number of points: {len(energies)}")
    print(f"  - Average Re(epsilon) at lowest energy: {eps1_avg[0]:.3f}")
    print(f"  - Maximum average Im(epsilon): {eps2_avg.max():.3f}")

    threshold = 0.05
    above_threshold = np.where(eps2_avg > threshold)[0]
    if len(above_threshold) > 0:
        onset_energy = energies[above_threshold[0]]
        print(f"  - Approximate absorption onset (Im > {threshold}): {onset_energy:.3f} eV")


def plot_dielectric(
    input_path: str,
    output_path: str = "dielectric_function.png",
    mode: str = "average",
    xmax: float = 15.0,
    ymin: float = -50.0,
    ymax: float = 40.0,
    chi_outcar: str | None = None,
) -> None:
    """
    Parse and plot the dielectric function from VASP output.

    Args:
        input_path: Path to a vasprun file or calculation directory.
        output_path: Output path for the dielectric-function plot.
        mode: Plot mode. `average` plots diagonal averages for Re/Im.
              `diagonal` plots xx/yy/zz components separately.
        xmax: Upper x-axis bound in eV.
        ymin: Lower y-axis bound.
        ymax: Upper y-axis bound.
        chi_outcar: Optional explicit path to OUTCAR from an `ALGO = CHI` run.
    """
    vasprun_path = find_vasprun(input_path)
    print(f"Reading dielectric data from: {vasprun_path}")
    ensure_frequency_dependent_calculation(vasprun_path)

    vasprun = Vasprun(str(vasprun_path), parse_projected_eigen=False)
    energies, real, imag = vasprun.dielectric

    energies = np.array(energies)
    real = np.array(real)
    imag = np.array(imag)

    if real.shape[1] < 3 or imag.shape[1] < 3:
        raise ValueError("Unexpected dielectric tensor shape in vasprun.xml")

    summarize_dielectric(energies, real, imag)

    outcar_path = find_chi_outcar(input_path, chi_outcar=chi_outcar)
    if outcar_path is not None:
        print(f"Reading CHI data from: {outcar_path}")

    fig, ax = plt.subplots(figsize=(8.0, 5.2))

    if mode == "average":
        eps1_avg = real[:, :3].mean(axis=1)
        eps2_avg = imag[:, :3].mean(axis=1)
        if outcar_path is not None:
            ipa_energy, ipa_real, ipa_imag = parse_dielectric_section(
                outcar_path,
                "HEAD OF MICROSCOPIC DIELECTRIC TENSOR (INDEPENDENT PARTICLE)",
            )
            rpa_energy, rpa_real, rpa_imag = parse_dielectric_section(
                outcar_path,
                "INVERSE MACROSCOPIC DIELECTRIC TENSOR",
            )

            ax.plot(
                ipa_energy,
                ipa_real,
                color="black",
                lw=1.7,
                marker="s",
                markevery=max(1, len(ipa_energy) // 14),
                ms=5,
                mfc="white",
                label="IPA real",
            )
            ax.plot(
                ipa_energy,
                -ipa_imag,
                color="black",
                lw=1.4,
                ls=":",
                marker="s",
                markevery=max(1, len(ipa_energy) // 14),
                ms=5,
                mfc="white",
                label="IPA imag",
            )
            ax.plot(
                rpa_energy,
                rpa_real,
                color="red",
                lw=1.4,
                marker="x",
                markevery=max(1, len(rpa_energy) // 14),
                ms=7,
                mew=1.2,
                label="RPA real",
            )
            ax.plot(
                rpa_energy,
                -rpa_imag,
                color="red",
                lw=1.4,
                ls=":",
                marker="x",
                markevery=max(1, len(rpa_energy) // 14),
                ms=7,
                mew=1.2,
                label="RPA imag",
            )

        ax.plot(energies, eps1_avg, color="blue", lw=1.4, label="LOPTICS real")
        ax.plot(energies, -eps2_avg, color="blue", lw=1.4, ls=":", label="LOPTICS imag")
    elif mode == "diagonal":
        labels = ["xx", "yy", "zz"]
        colors = ["tab:blue", "tab:orange", "tab:green"]
        for idx, (label, color) in enumerate(zip(labels, colors)):
            ax.plot(energies, real[:, idx], color=color, lw=2, label=f"Re(epsilon_{label})")
            ax.plot(
                energies,
                -imag[:, idx],
                color=color,
                lw=2,
                ls="--",
                label=f"-Im(epsilon_{label})",
            )
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    ax.set_xlabel("Energy (eV)")
    ax.set_ylabel("Dielectric function")
    ax.set_xlim(0, xmax)
    ax.set_ylim(ymin, ymax)
    ax.tick_params(direction="in", top=True, right=True, length=6, width=1.0, pad=8)
    ax.legend(loc="upper right", frameon=False, handlelength=2.6)

    fig.tight_layout()

    output = Path(output_path)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    print(f"\nSaved dielectric plot to: {output}")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot the dielectric function from a VASP optics calculation"
    )
    parser.add_argument(
        "input_path",
        help="Path to vasprun.xml(.gz) or a directory containing it"
    )
    parser.add_argument(
        "--output",
        default="dielectric_function.png",
        help="Output path for the dielectric plot (default: dielectric_function.png)"
    )
    parser.add_argument(
        "--mode",
        choices=["average", "diagonal"],
        default="average",
        help="Plot diagonal average or separate xx/yy/zz components (default: average)"
    )
    parser.add_argument(
        "--xmax",
        type=float,
        default=15.0,
        help="Upper x-axis limit in eV (default: 15)"
    )
    parser.add_argument(
        "--ymin",
        type=float,
        default=-50.0,
        help="Lower y-axis limit (default: -50)"
    )
    parser.add_argument(
        "--ymax",
        type=float,
        default=40.0,
        help="Upper y-axis limit (default: 40)"
    )
    parser.add_argument(
        "--chi-outcar",
        default=None,
        help="Optional path to OUTCAR from an `ALGO = CHI` calculation"
    )

    args = parser.parse_args()

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(_json.dumps(_config, indent=2, default=str))
    plot_dielectric(
        input_path=args.input_path,
        output_path=args.output,
        mode=args.mode,
        xmax=args.xmax,
        ymin=args.ymin,
        ymax=args.ymax,
        chi_outcar=args.chi_outcar,
    )
