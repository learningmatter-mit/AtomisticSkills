"""Exercise QHA scale selection with synthetic inputs and no force calculations."""

from importlib.util import module_from_spec, spec_from_file_location
import inspect
import json
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.emt import EMT
from ase.io import write
from pymatgen.core import Lattice, Structure


pytestmark = pytest.mark.base

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/mat-qha-thermal-expansion/scripts/calculate_qha.py"
)


@pytest.fixture
def qha_runtime(tmp_path, monkeypatch):
    """Use native MatCalc initialization while replacing only expensive work."""
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl-cache"))
    import matcalc

    native_qha = matcalc.QHACalc
    calls = SimpleNamespace(kwargs=[], calculations=[], loads=[])

    def calculate(self, atoms):
        calls.calculations.append((self, atoms))
        return {"temperatures": np.array([0.0, 25.0, 50.0])}

    def create_qha(**kwargs):
        calls.kwargs.append(kwargs)
        return native_qha(**kwargs)

    wrapper = SimpleNamespace(create_calculator=EMT)

    def load_wrapper(model_type, model_name=None, device="auto"):
        calls.loads.append((model_type, model_name, device))
        return wrapper

    loader = ModuleType("src.utils.mlips.loader")
    loader.load_wrapper = load_wrapper
    research = ModuleType("src.utils.research_utils")
    research.get_current_research_dir = lambda: tmp_path / "research"
    monkeypatch.setitem(sys.modules, loader.__name__, loader)
    monkeypatch.setitem(sys.modules, research.__name__, research)
    monkeypatch.setattr(native_qha, "calc", calculate)
    monkeypatch.setattr(matcalc, "QHACalc", create_qha)
    return SimpleNamespace(native=native_qha, calls=calls, wrapper=wrapper)


@pytest.mark.parametrize("entrypoint", ["function", "cli"])
@pytest.mark.parametrize("window,n_volumes", [(None, None), (None, 17), (0.10, 7)])
def test_qha_scale_selection(tmp_path, monkeypatch, qha_runtime, entrypoint, window, n_volumes):
    """Omission preserves native defaults; explicit controls describe volumes."""
    output = tmp_path / "qha"
    atoms = Atoms("Al", cell=[3.0, 3.0, 3.0], pbc=True)
    if entrypoint == "function":
        spec = spec_from_file_location("synthetic_qha", SCRIPT)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        args = SimpleNamespace(
            output_dir=str(output), t_min=0.0, t_max=50.0, t_step=25.0,
            eos="vinet", fmax=1e-3, max_steps=10,
            volume_window=window, n_volumes=n_volumes or 11,
        )
        module.run_qha(args, qha_runtime.wrapper, atoms)
        assert not qha_runtime.calls.loads
    else:
        structure_file = tmp_path / "synthetic.extxyz"
        write(structure_file, atoms)
        argv = [
            str(SCRIPT), "--structure", str(structure_file),
            "--model_type", "matgl", "--model_name", "synthetic-model",
            "--device", "cpu", "--t_max", "50", "--t_step", "25",
            "--max_steps", "10", "--output_dir", str(output),
        ]
        if window is not None:
            argv.extend(["--volume_window", str(window)])
        if n_volumes is not None:
            argv.extend(["--n_volumes", str(n_volumes)])
        monkeypatch.setattr(sys, "argv", argv)
        runpy.run_path(str(SCRIPT), run_name="__main__")
        assert qha_runtime.calls.loads == [("matgl", "synthetic-model", "cpu")]
        assert (output / "input_configs.yaml").is_file()

    assert len(qha_runtime.calls.calculations) == 1
    qha, calculated_atoms = qha_runtime.calls.calculations[0]
    assert calculated_atoms.get_chemical_symbols() == ["Al"]
    if window is None:
        assert "scale_factors" not in qha_runtime.calls.kwargs[0]
        native_default = inspect.signature(qha_runtime.native).parameters["scale_factors"].default
        assert qha.scale_factors == tuple(sorted(native_default))
    else:
        assert len(qha.scale_factors) == n_volumes
        reference = Structure(Lattice.cubic(3.0), ["Al"], [[0.0, 0.0, 0.0]])
        volume_ratios = [
            qha._scale_structure(reference, scale).volume / reference.volume
            for scale in qha.scale_factors
        ]
        assert volume_ratios == pytest.approx(np.linspace(1.0 - window, 1.0 + window, n_volumes))
    summary = json.loads((output / "qha_results.json").read_text())
    assert summary["summary"]["num_points"] == 3
