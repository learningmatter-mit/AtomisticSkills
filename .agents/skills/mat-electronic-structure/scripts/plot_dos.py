"""
Post-process and plot density of states (DOS) from atomate2 VASP calculations.

This script parses vasprun.xml output from atomate2's BandStructureMaker workflow
with uniform k-mesh and generates a DOS plot.

Usage:
    python plot_dos.py <results_dir> [--output output.png]

    where <results_dir> is the atomate2 output directory containing:
        results/structure_0/job_*/vasprun.xml.gz

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, matplotlib
"""
import argparse
from pathlib import Path
from pymatgen.io.vasp import Vasprun
from pymatgen.electronic_structure.plotter import DosPlotter
import matplotlib.pyplot as plt


def plot_dos(results_dir: str, output_path: str = "dos.png") -> None:
    """
    Parse and plot density of states from atomate2 output.
    
    Args:
        results_dir: Path to atomate2 output directory (contains results/structure_0/)
        output_path: Output path for the DOS plot
    """
    results_path = Path(results_dir)
    
    # Find structure directories
    structure_dirs = sorted((results_path / "results").glob("structure_*"))
    
    if not structure_dirs:
        raise FileNotFoundError(f"No structure directories found in {results_path}/results/")
    
    # Use the first structure
    structure_dir = structure_dirs[0]
    print(f"Processing: {structure_dir.name}")
    
    # Find job directories (should have 2: static + uniform)
    job_dirs = sorted(structure_dir.glob("job_*"))
    
    if len(job_dirs) < 2:
        raise ValueError(f"Expected at least 2 jobs (static + uniform), found {len(job_dirs)}")
    
    print(f"Found {len(job_dirs)} job directories")
    
    # The second job is the uniform k-mesh calculation
    dos_job = job_dirs[1]
    vasprun_path = dos_job / "vasprun.xml.gz"
    
    if not vasprun_path.exists():
        raise FileNotFoundError(f"vasprun.xml.gz not found in {dos_job}")
    
    print(f"Reading DOS from: {vasprun_path}")
    
    # Parse DOS
    vasprun = Vasprun(str(vasprun_path), parse_projected_eigen=False)
    dos = vasprun.complete_dos
    
    # Print DOS info
    print(f"\nDOS info:")
    print(f"  - Spin-polarized: {dos.spin_polarization is not None}")
    print(f"  - Fermi level: {dos.efermi:.3f} eV")
    if hasattr(dos, 'get_gap'):
        gap = dos.get_gap()
        print(f"  - Band gap: {gap:.3f} eV")
    
    # Plot DOS
    plotter = DosPlotter()
    plotter.add_dos("Total DOS", dos)
    
    # Get the plot
    plt_obj = plotter.get_plot(xlim=(-10, 10))
    
    # Save plot - get figure from the returned object
    output = Path(output_path)
    if hasattr(plt_obj, 'savefig'):
        # It's a figure
        plt_obj.savefig(output, dpi=300, bbox_inches='tight')
    else:
        # It's an axes, get the figure
        fig = plt_obj.get_figure() if hasattr(plt_obj, 'get_figure') else plt.gcf()
        fig.savefig(output, dpi=300, bbox_inches='tight')
    
    print(f"\n✓ DOS plot saved to: {output}")
    plt.close('all')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot density of states from atomate2 VASP calculation results"
    )
    parser.add_argument(
        "results_dir",
        help="Path to atomate2 output directory containing results/structure_0/"
    )
    parser.add_argument(
        "--output",
        default="dos.png",
        help="Output path for the DOS plot (default: dos.png)"
    )
    
    args = parser.parse_args()
    plot_dos(args.results_dir, args.output)
