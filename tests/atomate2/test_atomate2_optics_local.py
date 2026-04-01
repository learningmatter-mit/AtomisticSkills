import shutil
import sys
from pathlib import Path

from pymatgen.core import Lattice, Structure

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.utils.dft.atomate2_utils import Atomate2Handler


def test_atomate2_local_si_optics():
    """
    Test a local Atomate2 optics workflow for silicon.

    This is a functional smoke test for the Atomate2 `OpticsMaker` pathway.
    The settings are intentionally light to keep the test practical; they are
    not intended to be production-quality optics parameters.
    """
    test_dir = Path("tests/tmp_atomate2_si_optics")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)

    try:
        lattice = Lattice.cubic(5.43)
        structure = Structure(
            lattice,
            ["Si", "Si"],
            [[0, 0, 0], [0.25, 0.25, 0.25]],
        )
        structure_path = test_dir / "Si.cif"
        structure.to(filename=str(structure_path))

        handler = Atomate2Handler(str(test_dir))

        env = handler.check_environment()
        assert env["atomate2"] is True
        assert env["vasp"] is True
        assert env["potcar"] is True

        config = {
            "NBANDS": 32,
            "NEDOS": 400,
            "CSHIFT": 0.1,
            "EDIFF": 1e-4,
        }

        maker = handler.get_flow_maker(
            preset_type="mp",
            calculation_type="optics",
            config=config,
        )

        from jobflow import run_locally

        flow = maker.make(structure)
        responses = run_locally(
            flow,
            create_folders=True,
            ensure_success=False,
            root_dir=str(test_dir / "run"),
        )

        vasprun_files = list((test_dir / "run").rglob("vasprun.xml"))
        vasprun_files += list((test_dir / "run").rglob("vasprun.xml.gz"))
        assert len(vasprun_files) > 0, "Optics workflow should create vasprun.xml output"

        outcar_files = list((test_dir / "run").rglob("OUTCAR"))
        assert len(outcar_files) > 0, "Optics workflow should create OUTCAR output"

        dielectric_vaspruns = []
        for vasprun_file in vasprun_files:
            try:
                from pymatgen.io.vasp import Vasprun

                vasprun = Vasprun(str(vasprun_file), parse_projected_eigen=False)
                energies, real, imag = vasprun.dielectric
                if len(energies) > 0:
                    dielectric_vaspruns.append(vasprun_file)
            except Exception:
                continue

        assert dielectric_vaspruns, "At least one vasprun.xml should contain dielectric data"

        job_id = "test_si_optics_job"
        all_responses = {
            "test_flow_uuid": {
                "responses": responses,
                "dir": str(test_dir / "run"),
            }
        }

        import pickle

        with open(test_dir / f"{job_id}_responses.pkl", "wb") as f:
            pickle.dump(all_responses, f)

        results = handler.extract_results(job_id)
        assert "results" in results
        assert len(results["results"]) > 0

    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    test_atomate2_local_si_optics()
