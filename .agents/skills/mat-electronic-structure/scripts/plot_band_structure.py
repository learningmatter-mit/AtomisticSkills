"""
Post-process and plot band structure from atomate2 VASP calculations.

This script parses vasprun.xml output from atomate2's BandStructureMaker workflow
and generates a band structure plot.

Usage:
    python plot_band_structure.py <results_dir> [--output output.png]

    where <results_dir> is the atomate2 output directory containing:
        results/structure_0/job_*/vasprun.xml.gz

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, matplotlib
"""
import argparse
from pathlib import Path
from pymatgen.io.vasp import BSVasprun
from pymatgen.electronic_structure.plotter import BSPlotter
import matplotlib.pyplot as plt


def plot_band_structure(results_dir: str, output_path: str = "band_structure.png") -> None:
    """
    Parse and plot band structure from atomate2 output.
    
    Args:
        results_dir: Path to atomate2 output directory (contains results/structure_0/)
        output_path: Output path for the band structure plot
    """
    results_path = Path(results_dir)
    
    # Find structure directories
    structure_dirs = sorted((results_path / "results").glob("structure_*"))
    
    if not structure_dirs:
        raise FileNotFoundError(f"No structure directories found in {results_path}/results/")
    
    # Use the first structure
    structure_dir = structure_dirs[0]
    print(f"Processing: {structure_dir.name}")
    
    # Find job directories (should have 2: static + band structure)
    job_dirs = sorted(structure_dir.glob("job_*"))
    
    if len(job_dirs) < 2:
        raise ValueError(f"Expected at least 2 jobs (static + band structure), found {len(job_dirs)}")
    
    print(f"Found {len(job_dirs)} job directories")
    
    # The second job is the non-SCF band structure calculation
    bs_job = job_dirs[1]
    vasprun_path = bs_job / "vasprun.xml.gz"
    
    if not vasprun_path.exists():
        raise FileNotFoundError(f"vasprun.xml.gz not found in {bs_job}")
    
    print(f"Reading band structure from: {vasprun_path}")
    
    # Parse band structure
    vasprun = BSVasprun(str(vasprun_path), parse_projected_eigen=False)
    bs = vasprun.get_band_structure(line_mode=True)
    
    # Print band structure info
    print(f"\nBand structure info:")
    print(f"  - Spin-polarized: {bs.is_spin_polarized}")
    print(f"  - Metal: {bs.is_metal()}")
    
    if not bs.is_metal():
        bg = bs.get_band_gap()
        print(f"  - Band gap: {bg['energy']:.3f} eV")
        print(f"  - Direct: {bg['direct']}")
        print(f"  - Transition: {bg['transition']}")
    
    # Plot band structure
    plotter = BSPlotter(bs)
    ax = plotter.get_plot(ylim=(-10, 10))
    
    # Save plot
    output = Path(output_path)
    fig = ax.get_figure()
    fig.savefig(output, dpi=300, bbox_inches='tight')
    print(f"\n✓ Band structure plot saved to: {output}")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot band structure from atomate2 VASP calculation results"
    )
    parser.add_argument(
        "results_dir",
        help="Path to atomate2 output directory containing results/structure_0/"
    )
    parser.add_argument(
        "--output",
        default="band_structure.png",
        help="Output path for the band structure plot (default: band_structure.png)"
    )
    
    args = parser.parse_args()

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(_json.dumps(_config, indent=2, default=str))
    plot_band_structure(args.results_dir, args.output)
