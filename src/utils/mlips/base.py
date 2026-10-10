"""
Base MLIP model interface for MLIP MCP Wrappers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
import logging
import os
import sys
from pathlib import Path
import matplotlib

matplotlib.use("Agg")  # Must be set before importing pyplot

# MD related imports will be done inside methods to avoid hard dependencies if not used
# But we can add some common ones here
try:
    from ase import Atoms  # noqa: F401
except ImportError:
    pass

logger = logging.getLogger(__name__)


class MLIPModel(ABC):
    """
    Abstract base class for MLIP models.

    This class defines the interface that all MLIP model implementations
    must follow to ensure compatibility.
    """

    def __init__(self, model_name: str, model_version: str = "latest"):
        """
        Initialize the MLIP model.

        Args:
            model_name: Name of the model (e.g., "M3GNet", "CHGNet")
            model_version: Version of the model to use
        """
        self.model_name = model_name
        self.model_version = model_version
        self.model = None
        self.calculator = None
        self.is_loaded = False
        self.is_fine_tuned = False
        self._training_history = {
            "loss_train": [],
            "loss_val": [],
            "energy_mae_train": [],
            "energy_mae_val": [],
            "force_mae_train": [],
            "force_mae_val": [],
            "stress_mae_train": [],
            "stress_mae_val": [],
            "epoch": [],
        }

    @abstractmethod
    def load(self, model_path: Optional[str] = None) -> None:
        """
        Load a model.

        Args:
            model_path: Path to the model checkpoint. If None, loads default pretrained model.
                       If provided, loads checkpoint from the specified path.

        Raises:
            RuntimeError: If model loading fails.
        """
        pass

    @abstractmethod
    def create_calculator(self) -> Any:
        """
        Create an ASE calculator from the loaded model.

        Returns:
            ASE calculator object.

        Raises:
            RuntimeError: If calculator creation fails.
        """
        pass

    @property
    def supports_charge_spin(self) -> bool:
        """
        Whether this model accepts per-calculation charge and spin multiplicity.

        Models that return ``True`` read charge / spin from ``atoms.info`` during
        each ``calculate()`` call (e.g. MACE-OMOL, FairChem omol task), enabling
        reliable heterolytic BDE probing.  Models that return ``False`` are
        electron-agnostic and should only be used for homolytic BDE.

        Subclasses must override this property.  The default is ``False`` so that
        new wrappers are safe-by-default.

        Returns:
            bool: True when charge/spin are honoured by the model.
        """
        return False

    @abstractmethod
    def save_checkpoint(self, checkpoint_path: str) -> None:
        """
        Save the current model state to a checkpoint.

        Args:
            checkpoint_path: Path where to save the checkpoint.

        Raises:
            RuntimeError: If saving fails.
        """
        pass

    @abstractmethod
    def load_checkpoint(self, checkpoint_path: str) -> None:
        """
        Load a model from a checkpoint.

        Args:
            checkpoint_path: Path to the checkpoint file.

        Raises:
            RuntimeError: If loading fails.
        """
        pass

    @abstractmethod
    def predict_atomic_features(self, structure_data: Any) -> Dict[str, Any]:
        """
        Predict atomic latent features (descriptors) for a structure.

        Args:
            structure_data: Structure data compatible with check_structure_data.

        Returns:
            Dictionary containing 'atomic_features' (list of lists/arrays).

        Raises:
            RuntimeError: If prediction fails.
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary containing model information.
        """
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "is_loaded": self.is_loaded,
            "is_fine_tuned": self.is_fine_tuned,
            "model_type": self.__class__.__name__,
            "supports_charge_spin": self.supports_charge_spin,
        }

    def _get_nvalchemi_model(self) -> Optional[Any]:
        """Return a NValchemi-compatible model wrapper, or None.

        Subclasses override this to expose their inner model wrapped as a
        nvalchemi BaseModelMixin so that GPU-parallel batch operations can
        be dispatched through NValchemi dynamics (FIRE, NVTNoseHoover, etc.).

        The base implementation returns None, which causes all batch calls to
        fall back to the sequential Python loop.
        """
        return None

    def _get_enabled_nvalchemi_model(self, use_nvalchemi: bool) -> Optional[Any]:
        """Select the experimental batch backend only after explicit opt-in."""
        if not use_nvalchemi:
            return None

        from src.utils.mlips.nvalchemi.nvalchemi_utils import check_nvalchemi_available

        model = self._get_nvalchemi_model() if check_nvalchemi_available() else None
        if model is None:
            logger.warning(
                "NValchemi unavailable for this model; using sequential execution."
            )
        else:
            logger.warning(
                "Using experimental NValchemi batching. Toolkit 0.2.0 dynamics has "
                "known correctness limitations; read skills/ml-mlip-nvalchemi/SKILL.md."
            )
        return model

    def validate_structure(self, structure: Any) -> bool:
        """
        Validate that a structure is compatible with the model.

        Args:
            structure: Structure to validate.

        Returns:
            True if structure is valid, False otherwise.
        """
        # Basic validation - can be overridden by subclasses
        try:
            # Check if structure has required attributes
            if not hasattr(structure, "get_atomic_numbers"):
                return False
            if not hasattr(structure, "get_positions"):
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def check_structure_data(structure_data: Any) -> Any:
        """
        Check and convert structure data to ASE Atoms object.

        Args:
            structure_data: Input structure data (dict, pymatgen Structure, ASE Atoms, or file path string).

        Returns:
            ASE Atoms object if valid, or a dict with "error" key if invalid.
        """
        from ase import Atoms

        # Check for file path string
        # Check for file path string
        if isinstance(structure_data, str):
            if str(structure_data).endswith(".traj"):
                from ase.io import read

                try:
                    return read(structure_data, index=-1)
                except Exception as e:
                    return {
                        "error": f"Failed to load trajectory from file: {structure_data}, error: {e}"
                    }
            else:
                from ..structure_utils import load_structure_from_file

                struct = load_structure_from_file(structure_data)
                if struct is not None:
                    from pymatgen.io.ase import AseAtomsAdaptor

                    return AseAtomsAdaptor.get_atoms(struct)
                else:
                    return {
                        "error": f"Failed to load structure from file: {structure_data}"
                    }

        # Check for pymatgen Structure object
        if hasattr(structure_data, "as_dict") and hasattr(structure_data, "lattice"):
            try:
                from pymatgen.io.ase import AseAtomsAdaptor

                return AseAtomsAdaptor.get_atoms(structure_data)
            except ImportError:
                return {
                    "error": "pymatgen not installed, cannot convert Structure object."
                }

        # Check for ASE Atoms object
        if isinstance(structure_data, Atoms):
            return structure_data

        # Check for dict format
        if isinstance(structure_data, dict):
            # Check for pymatgen dict
            if "@module" in structure_data or (
                "sites" in structure_data and "lattice" in structure_data
            ):
                try:
                    from pymatgen.core import Structure
                    from pymatgen.io.ase import AseAtomsAdaptor

                    struct = Structure.from_dict(structure_data)
                    return AseAtomsAdaptor.get_atoms(struct)
                except Exception as e:
                    return {"error": f"Failed to convert pymatgen dict: {str(e)}"}

            # Check for simple ASE dict
            if "symbols" in structure_data and "positions" in structure_data:
                return Atoms(
                    symbols=structure_data["symbols"],
                    positions=structure_data["positions"],
                    cell=structure_data.get("cell"),
                    pbc=structure_data.get("pbc", True),
                )

            return {
                "error": "Invalid structure format. Must be file path, pymatgen Structure, ASE Atoms, or dict with 'symbols' and 'positions'."
            }

    def relax_structure(
        self,
        structure_data: Union[Any, str, List[Union[Dict[str, Any], str]]],
        fmax: float = 0.01,
        steps: int = 500,
        optimizer: str = "FIRE",
        relax_cell: bool = True,
        output_dir: Optional[str] = None,
        fixed_atoms: Optional[List[int]] = None,
        extract_batch_results: bool = True,
        max_batch_atoms: Optional[int] = None,
        use_nvalchemi: bool = False,
    ) -> Dict[str, Any]:
        """
        Relax one or multiple structures using the loaded model.

        Automatically detects batch mode from input and handles accordingly.

        Args:
            structure_data: Can be:
                - Single structure (dict, ASE Atoms, pymatgen Structure, or file path)
                - Directory path containing CIF/POSCAR files (batch mode)
                - List of file paths (batch mode)
                - List of structure dicts (batch mode)
            fmax: Force convergence criterion (eV/Ang).
            steps: Maximum number of optimization steps.
            optimizer: Optimizer to use ("FIRE", "BFGS", "LBFGS").
            relax_cell: Whether to relax the unit cell (True) or just atomic positions (False).
            output_dir: Directory to save results. For batch mode, each structure gets a subdirectory.
            fixed_atoms: List of indices of atoms to keep fixed during relaxation (single mode only).
            use_nvalchemi: Opt in to experimental NValchemi batching (default False).
            extract_batch_results: Whether to extract full trajectory / logs for all structures in batch mode.
            max_batch_atoms: Override the auto-detected atom budget for the NValchemi inflight live
                batch.  When None (default) the budget is estimated from free VRAM.  Set a smaller
                value (e.g. 500) on shared GPUs to avoid OOM.

        Returns:
            For single structure: Dict with energy, trajectory_path, cif_path, json_path
            For batch mode: Dict with mode="batch", total_structures, successful, failed, results list
        """
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load_model first."}

        # Auto-detect batch mode
        is_batch = isinstance(structure_data, list) or (
            isinstance(structure_data, str) and Path(structure_data).is_dir()
        )

        if is_batch:
            # BATCH MODE
            return self._batch_relax(
                structure_data,
                fmax,
                steps,
                optimizer,
                relax_cell,
                output_dir,
                extract_batch_results=extract_batch_results,
                max_batch_atoms=max_batch_atoms,
                use_nvalchemi=use_nvalchemi,
            )
        else:
            # SINGLE STRUCTURE MODE
            return self._single_relax(
                structure_data,
                fmax,
                steps,
                optimizer,
                relax_cell,
                output_dir,
                fixed_atoms,
            )

    def _single_relax(
        self,
        structure_data: Any,
        fmax: float,
        steps: int,
        optimizer: str,
        relax_cell: bool,
        output_dir: Optional[str],
        fixed_atoms: Optional[List[int]],
    ) -> Dict[str, Any]:
        """Internal method for single structure relaxation."""
        try:
            from ase.constraints import FixAtoms
            from ase.filters import FrechetCellFilter
            import os
            import sys
            from ..structure_utils import save_structure
            from ..research_utils import get_current_research_dir
            import ase.optimize
            from ase import Atoms

            # Check structure data
            atoms = self.check_structure_data(structure_data)
            if isinstance(atoms, dict) and "error" in atoms:
                return atoms

            # Ensure we have a standard ASE Atoms object (fix MSONAtoms issue)
            if atoms.__class__.__name__ == "MSONAtoms" or not hasattr(
                atoms, "set_constraint"
            ):
                atoms = Atoms(atoms)

            if fixed_atoms:
                atoms.set_constraint(FixAtoms(indices=fixed_atoms))

            if not output_dir:
                try:
                    output_dir = str(
                        get_current_research_dir()
                        / self.__class__.__name__.lower().replace("wrapper", "")
                        / "relaxation"
                    )
                except Exception:
                    output_dir = "relaxation"

            os.makedirs(output_dir, exist_ok=True)

            # Define paths
            filename_base = "relax"
            traj_file = os.path.join(output_dir, f"{filename_base}.traj")
            log_file = os.path.join(output_dir, f"{filename_base}.log")

            # Create and attach calculator
            calc = self.create_calculator()
            atoms.calc = calc

            # Use ASE optimizer
            if not hasattr(ase.optimize, optimizer):
                raise ValueError(f"Optimizer {optimizer} not found in ase.optimize")

            # Setup cell filter if relaxing cell
            if relax_cell:
                opt_atoms = FrechetCellFilter(atoms)
            else:
                opt_atoms = atoms

            OptClass = getattr(ase.optimize, optimizer)
            opt = OptClass(opt_atoms, logfile=log_file, trajectory=traj_file)
            converged = bool(opt.run(fmax=fmax, steps=steps))

            # Clear constraints before returning/saving
            final_struct = atoms
            if hasattr(final_struct, "set_constraint"):
                final_struct.set_constraint([])

            cif_path = os.path.join(output_dir, "relaxed_structure.cif")
            save_structure(final_struct, cif_path)

            # Get energy safely
            try:
                energy_val = float(atoms.get_potential_energy())
            except Exception:
                energy_val = None

            # Save energy to text file for compute_ehull.py
            if energy_val is not None:
                energy_file = os.path.join(output_dir, "relaxed_energy.txt")
                with open(energy_file, "w") as f:
                    f.write(str(energy_val))

            return {
                "status": "success" if converged else "not_converged",
                "converged": converged,
                "steps": opt.nsteps,
                "energy": energy_val,
                "trajectory_path": traj_file,
                "log_path": log_file,
                "cif_path": cif_path,
                "output_dir": output_dir,
            }
        except Exception as e:
            import traceback

            traceback.print_exc(file=sys.stderr)
            return {"error": f"Relaxation failed: {str(e)}"}

    def _parse_batch_input(
        self,
        structure_data: Union[str, List[Union[Dict[str, Any], str]]],
    ) -> tuple:
        """Parse batch structure input into (structure_list, structure_names).

        Returns an error dict if the input is invalid.
        """
        structure_list: List[Any] = []
        structure_names: List[str] = []

        if isinstance(structure_data, str) and Path(structure_data).is_dir():
            dir_path = Path(structure_data)
            patterns = ["*.cif", "*.CIF", "*POSCAR*", "*CONTCAR*", "*.vasp"]
            for pattern in patterns:
                for filepath in dir_path.glob(pattern):
                    structure_list.append(str(filepath))
                    structure_names.append(filepath.stem)
            if not structure_list:
                return (
                    {
                        "error": f"No structure files found in directory: {structure_data}"
                    },
                    [],
                )
        elif isinstance(structure_data, list):
            for i, struct in enumerate(structure_data):
                structure_list.append(struct)
                if isinstance(struct, str):
                    structure_names.append(Path(struct).stem)
                else:
                    structure_names.append(f"structure_{i}")
        else:
            return (
                {
                    "error": "structure_data must be a directory path or a list of structures/paths"
                },
                [],
            )
        return structure_list, structure_names

    def _batch_relax(
        self,
        structure_data: Union[str, List[Union[Dict[str, Any], str]]],
        fmax: float,
        steps: int,
        optimizer: str,
        relax_cell: bool,
        output_dir: Optional[str],
        extract_batch_results: bool = True,
        max_batch_atoms: Optional[int] = None,
        use_nvalchemi: bool = False,
    ) -> Dict[str, Any]:
        """Use sequential relaxation unless NValchemi is explicitly requested."""
        nv_model = self._get_enabled_nvalchemi_model(use_nvalchemi)
        if nv_model is not None:
            try:
                return self._batch_relax_nvalchemi(
                    nv_model=nv_model,
                    structure_data=structure_data,
                    fmax=fmax,
                    steps=steps,
                    relax_cell=relax_cell,
                    output_dir=output_dir,
                    extract_batch_results=extract_batch_results,
                    max_batch_atoms=max_batch_atoms,
                )
            except ValueError as exc:
                if "Per-system shift count" not in str(exc):
                    raise
                logger.warning(
                    "NValchemi neighbor-list overflow during batch relaxation; "
                    "falling back to sequential relaxation."
                )
        return self._batch_relax_sequential(
            structure_data, fmax, steps, optimizer, relax_cell, output_dir
        )

    def _batch_relax_nvalchemi(
        self,
        nv_model: Any,
        structure_data: Union[str, List[Union[Dict[str, Any], str]]],
        fmax: float,
        steps: int,
        relax_cell: bool,
        output_dir: Optional[str],
        extract_batch_results: bool = True,
        max_batch_atoms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """GPU-parallel batch relaxation via NValchemi FIRE optimizer."""
        import os
        import torch
        from src.utils.mlips.nvalchemi.nvalchemi_utils import (
            ForceStressClippingHook,
            PositionWrappingHook,
            RelaxStepCountHook,
            atoms_to_atomic_data,
            extract_batch_results as extract_batch_results_fn,
            relax_convergence_hook,
            warp_on_torch_stream,
        )

        try:
            from nvalchemi.data import Batch
            from nvalchemi.dynamics.base import DynamicsStage
            from nvalchemi.dynamics.optimizers.fire import FIRE
            from nvalchemi.dynamics.optimizers.fire2 import FIRE2VariableCell
            from src.utils.mlips.nvalchemi.neighbor_list import make_neighbor_list_hook
        except ImportError as e:
            logger.warning(f"NValchemi import failed: {e}; falling back to sequential.")
            return self._batch_relax_sequential(
                structure_data, fmax, steps, "FIRE", relax_cell, output_dir
            )

        parsed = self._parse_batch_input(structure_data)
        if isinstance(parsed[0], dict) and "error" in parsed[0]:
            return parsed[0]
        structure_list, structure_names = parsed

        if not output_dir:
            try:
                from src.utils.research_utils import get_current_research_dir

                output_dir = str(
                    get_current_research_dir()
                    / self.__class__.__name__.lower().replace("wrapper", "")
                    / "batch_relaxation"
                )
            except Exception:
                output_dir = "batch_relaxation"
        os.makedirs(output_dir, exist_ok=True)

        output_dirs = [os.path.join(output_dir, name) for name in structure_names]
        device = getattr(self, "device", "cpu")

        logger.info(f"NValchemi GPU batch relaxing {len(structure_list)} structures...")

        from nvalchemi.dynamics.hooks import SnapshotHook
        from nvalchemi.dynamics.sinks import HostMemory

        atoms_list = []
        for s in structure_list:
            atoms = self.check_structure_data(s)
            if hasattr(atoms, "cell") and atoms.cell and atoms.cell.volume > 1e-6:
                std_cell, Q = atoms.cell.standard_form()
                atoms.set_cell(std_cell, scale_atoms=False)
                atoms.positions = atoms.positions @ Q.T
                if atoms.get_velocities() is not None:
                    atoms.set_velocities(atoms.get_velocities() @ Q.T)
            atoms_list.append(atoms)

        # Switch to inflight mode when all structures would exceed GPU memory.
        # A model wrapper can opt out with _nvalchemi_supports_inflight=False.
        total_atoms = sum(len(a) for a in atoms_list)
        if max_batch_atoms is None:
            max_batch_atoms = self._estimate_max_batch_atoms(device, model=nv_model)
        supports_inflight = getattr(nv_model, "_nvalchemi_supports_inflight", True)
        if total_atoms > max_batch_atoms and not supports_inflight:
            logger.warning(
                f"Total atoms ({total_atoms}) exceeds batch limit ({max_batch_atoms}) "
                f"but inflight batching is not supported for {type(nv_model).__name__}. "
                f"Proceeding with fixed-batch (may OOM for very large structure sets)."
            )
        if total_atoms > max_batch_atoms and supports_inflight:
            logger.info(
                f"Total atoms ({total_atoms}) exceeds batch limit "
                f"({max_batch_atoms}); switching to inflight batching."
            )
            return self._batch_relax_nvalchemi_inflight(
                nv_model=nv_model,
                atoms_list=atoms_list,
                structure_names=structure_names,
                output_dirs=output_dirs,
                fmax=fmax,
                steps=steps,
                relax_cell=relax_cell,
                max_batch_atoms=max_batch_atoms,
            )

        data_list = [
            atoms_to_atomic_data(a, device=device, dtype=torch.float32)
            for a in atoms_list
        ]
        for data in data_list:
            data.add_system_property(
                "relax_steps", torch.zeros(1, 1, dtype=torch.long, device=device)
            )
        batch = Batch.from_data_list(data_list)
        batch.status = torch.zeros(batch.num_graphs, dtype=torch.int32, device=device)

        if relax_cell:
            optimizer_obj = FIRE2VariableCell(
                model=nv_model,
                dt=0.05,
                tmax=0.5,
                delaystep=5,
                maxstep=0.2,
                n_steps=steps,
                convergence_hook=relax_convergence_hook(fmax, relax_cell=True),
            )
            optimizer_obj._mutable_fields = ("positions", "velocities", "cell")
        else:
            optimizer_obj = FIRE(
                model=nv_model,
                dt=0.5,
                n_steps=steps,
                convergence_hook=relax_convergence_hook(fmax, relax_cell=False),
            )

        if optimizer_obj.convergence_hook is not None:
            optimizer_obj.register_hook(optimizer_obj.convergence_hook)
        optimizer_obj.register_hook(RelaxStepCountHook(DynamicsStage.BEFORE_STEP))
        optimizer_obj.register_hook(
            PositionWrappingHook(stage=DynamicsStage.BEFORE_COMPUTE)
        )
        if getattr(nv_model.model_config, "neighbor_config", None) is not None:
            nl_hook = make_neighbor_list_hook(
                nv_model.model_config.neighbor_config,
                stage=DynamicsStage.BEFORE_COMPUTE,
            )
            optimizer_obj.register_hook(nl_hook)
        optimizer_obj.register_hook(
            ForceStressClippingHook(
                stage=DynamicsStage.AFTER_COMPUTE, max_force=5.0, max_stress=5.0
            )
        )

        # Set up memory sink to record full history of relaxation steps if requested
        memory_sink = None
        if extract_batch_results:
            capacity = (steps + 1) * len(structure_list)
            memory_sink = HostMemory(capacity=capacity)
            snapshot_hook = SnapshotHook(sink=memory_sink, frequency=1)
            optimizer_obj.register_hook(snapshot_hook)

        # Write step 0 state
        neighbor_config = getattr(nv_model.model_config, "neighbor_config", None)
        if neighbor_config is not None:
            from nvalchemi.neighbors import compute_neighbors

            compute_neighbors(batch, config=neighbor_config)

        nv_model.eval()
        if hasattr(batch, "positions") and batch.positions is not None:
            batch.positions.requires_grad_(True)
        initial_out = nv_model(batch)
        f0 = (
            initial_out.get("forces")
            if isinstance(initial_out, dict)
            else getattr(initial_out, "forces", None)
        )
        if f0 is not None:
            batch["forces"] = f0.detach()
        e0 = (
            initial_out.get("energy")
            if isinstance(initial_out, dict)
            else getattr(initial_out, "energy", None)
        )
        if e0 is not None:
            batch["energy"] = e0.detach()
        if relax_cell:
            s0 = (
                initial_out.get("stress")
                if isinstance(initial_out, dict)
                else getattr(initial_out, "stress", None)
            )
            if s0 is not None:
                batch["stress"] = s0.detach()
        batch.positions.requires_grad_(False)

        if memory_sink is not None:
            memory_sink.write(batch)

        # Entering the optimizer switches PyTorch to a dedicated CUDA stream;
        # bind Warp to it second so the neighbor-list kernels follow.
        with optimizer_obj, warp_on_torch_stream(device):
            final_batch = optimizer_obj.run(batch)

        # Reconstruct trajectory and log for each structure using unified extraction helper
        results = extract_batch_results_fn(
            final_batch=final_batch,
            structure_names=structure_names,
            output_dirs=output_dirs,
            mode="relax",
            memory_sink=memory_sink,
        )

        n_success = sum(1 for r in results if r["status"] == "success")
        n_not_converged = sum(r["status"] == "not_converged" for r in results)
        n_failed = sum(r["status"] == "failed" for r in results)
        logger.info(
            f"NValchemi batch relaxation: {n_success} converged, "
            f"{n_not_converged} not converged, {n_failed} failed"
        )

        return {
            "mode": "batch",
            "backend": "nvalchemi",
            "total_structures": len(results),
            "successful": n_success,
            "not_converged": n_not_converged,
            "failed": n_failed,
            "output_dir": output_dir,
            "results": results,
        }

    @staticmethod
    def _estimate_max_batch_atoms(
        device: str = "cuda", model: Optional[Any] = None
    ) -> int:
        """Estimate the atom budget that fits in a single fixed GPU batch.

        Returns the threshold used to decide between fixed-batch and inflight
        modes: if the total atom count across all input structures exceeds
        this value, ``_batch_relax_nvalchemi_inflight`` is used instead.

        Passing ``model`` enables per-architecture calibration (bytes/param/atom
        look-up) instead of a fixed 5 MB/atom fallback.
        """
        from src.utils.mlips.nvalchemi.nvalchemi_utils import estimate_max_batch_atoms

        return estimate_max_batch_atoms(device=device, model=model)

    def _batch_relax_nvalchemi_inflight(
        self,
        nv_model: Any,
        atoms_list: List[Any],
        structure_names: List[str],
        output_dirs: List[str],
        fmax: float,
        steps: int,
        relax_cell: bool,
        max_batch_atoms: int,
    ) -> Dict[str, Any]:
        """GPU inflight-batched relaxation for large structure pools.

        Wraps FIRE in a FusedStage with a SizeAwareSampler so that only
        ``max_batch_atoms`` atoms occupy GPU memory at once.  As each
        structure converges (or exhausts its per-system step budget), it is
        evicted and a new structure takes its slot.  This allows relaxing
        pools larger than GPU memory in a single call.

        Trajectory capture is not available in inflight mode; only the final
        relaxed state is saved per structure.

        Parameters
        ----------
        nv_model : NValchemi model wrapper
        atoms_list : list[Atoms]
            Pre-loaded ASE Atoms objects (same order as structure_names).
        structure_names : list[str]
        output_dirs : list[str]
            Per-structure output directories.
        fmax : float
            Force convergence threshold (eV/Å).
        steps : int
            Per-structure maximum FIRE steps.
        relax_cell : bool
            Whether to relax the unit cell.
        max_batch_atoms : int
            Atom budget for the live batch (from ``_estimate_max_batch_atoms``).
        """
        import os
        import torch

        from nvalchemi.dynamics import SizeAwareSampler
        from nvalchemi.dynamics.base import DynamicsStage, FusedStage
        from nvalchemi.dynamics.optimizers.fire import FIRE
        from nvalchemi.dynamics.optimizers.fire2 import FIRE2VariableCell
        from src.utils.mlips.nvalchemi.nvalchemi_utils import (
            relax_convergence_hook,
            warp_on_torch_stream,
        )
        from src.utils.mlips.nvalchemi.neighbor_list import make_neighbor_list_hook
        from pymatgen.io.ase import AseAtomsAdaptor
        from src.utils.mlips.nvalchemi.nvalchemi_utils import (
            AtomsDataset,
            ForceStressClippingHook,
            HostMemoryWithSystemId,
            PositionWrappingHook,
            RelaxLogHook,
            RelaxStepCountHook,
            atomic_data_to_atoms,
        )

        device = getattr(self, "device", "cuda")
        n_structures = len(atoms_list)

        # Flush CUDA allocator cache before starting so the full memory budget is
        # available.  On DGX Spark's unified memory pool, cached-but-freed blocks
        # from model loading count against available memory if not released here.
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # --- Incremental disk-write callback ---
        # Structures are serialized to disk the moment they graduate from the live
        # batch, so partial results survive an OOM abort mid-run (analogous to how
        # ASE writes trajectory frames incrementally).
        saved_to_disk: Dict[int, Dict[str, Any]] = {}

        def on_graduate(orig_idx: int, data_cpu: Any) -> None:
            out_dir = output_dirs[orig_idx]
            struct_name = structure_names[orig_idx]
            os.makedirs(out_dir, exist_ok=True)
            try:
                atoms = atomic_data_to_atoms(data_cpu)
                structure = AseAtomsAdaptor.get_structure(atoms)
                cif_path = os.path.join(out_dir, "relaxed_structure.cif")
                structure.to(filename=cif_path)
                final_energy = atoms.get_potential_energy()
                with open(os.path.join(out_dir, "relaxed_energy.txt"), "w") as f:
                    f.write(f"{final_energy}\n")
                fmax_actual = float(data_cpu["forces"].norm(dim=-1).max().item())
                # FusedStage uses status=1 for both convergence and budget
                # exhaustion. Re-evaluate the same force AND cell criteria.
                from nvalchemi.data import Batch

                converged = (
                    relax_convergence_hook(fmax, relax_cell).evaluate(
                        Batch.from_data_list([data_cpu])
                    )
                    is not None
                )
                saved_to_disk[orig_idx] = {
                    "structure_name": struct_name,
                    "status": "success" if converged else "not_converged",
                    "energy": final_energy,
                    "cif_path": cif_path,
                    "output_dir": out_dir,
                    "converged": converged,
                    "steps": int(data_cpu.relax_steps.item()),
                }
                logger.debug(
                    f"Graduated [{orig_idx}] {struct_name}: "
                    f"E={final_energy:.4f} eV, fmax={fmax_actual:.4f} eV/Å"
                )
            except Exception as exc:
                logger.warning(
                    f"on_graduate failed for [{orig_idx}] {struct_name}: {exc}"
                )

        # AtomsDataset pre-allocates zero forces/energy/stress on every structure.
        # SegmentedLevelStorage.concatenate() only keeps keys common to both batches,
        # so refill replacements must carry the same keys as the live batch or
        # forces/energy will be silently dropped after each refill cycle.
        dataset = AtomsDataset(
            atoms_list, structure_names, device=device, relax_cell=relax_cell
        )
        sampler = SizeAwareSampler(
            dataset,
            max_atoms=max_batch_atoms,
            max_edges=None,  # edges computed dynamically by NeighborListHook
            max_batch_size=min(n_structures, 128),
        )

        results_sink = HostMemoryWithSystemId(
            capacity=n_structures, on_graduate=on_graduate
        )

        if relax_cell:
            fire_stage = FIRE2VariableCell(
                model=nv_model,
                dt=0.05,
                tmax=0.5,
                delaystep=5,
                maxstep=0.2,
                # Per-system step budget: structures graduate after `steps` FIRE
                # steps even if fmax never drops below threshold.
                n_steps=steps,
                convergence_hook=relax_convergence_hook(fmax, relax_cell=True),
            )
        else:
            fire_stage = FIRE(
                model=nv_model,
                dt=0.5,
                # Per-system step budget: structures graduate after `steps` FIRE
                # steps even if fmax never drops below threshold.
                n_steps=steps,
                convergence_hook=relax_convergence_hook(fmax, relax_cell=False),
            )

        neighbor_config = getattr(nv_model.model_config, "neighbor_config", None)

        # exit_status auto-set to len(sub_stages) = 1; structures with
        # status >= 1 are graduated and replaced by the sampler.
        # refill_frequency=1: check for graduates every step so that structures
        # with a short per-system budget (e.g. steps=2) are replaced immediately.
        # Higher values let graduated structures idle and can exhaust the global
        # step budget before all structures are processed.
        fused = FusedStage(
            sub_stages=[(0, fire_stage)],
            sampler=sampler,
            sinks=[results_sink],
            refill_frequency=1,
        )

        # In FusedStage, BEFORE_COMPUTE is fired on the fused stage itself
        # (not on sub-stages), so the NeighborListHook must be registered here.
        # This also covers the initial "prime forces" call in FusedStage.run().

        fused.register_hook(PositionWrappingHook(stage=DynamicsStage.BEFORE_COMPUTE))
        fused.register_hook(RelaxStepCountHook(DynamicsStage.BEFORE_STEP))
        if neighbor_config is not None:
            fused.register_hook(
                make_neighbor_list_hook(
                    neighbor_config, stage=DynamicsStage.BEFORE_COMPUTE
                )
            )
        fused.register_hook(
            ForceStressClippingHook(
                stage=DynamicsStage.AFTER_COMPUTE, max_force=5.0, max_stress=5.0
            )
        )

        # Write ASE-style relax.log per structure.  FusedStage calls __enter__/
        # __exit__ on registered hooks automatically, so file handles are closed
        # cleanly even if the run is aborted by OOM.
        fused.register_hook(
            RelaxLogHook(output_dirs=output_dirs, stage=DynamicsStage.AFTER_COMPUTE)
        )

        # Safety cap: absolute worst case is every structure processed serially.
        total_step_budget = steps * n_structures

        logger.info(
            f"NValchemi inflight relax: {n_structures} structures, "
            f"live batch ≤{max_batch_atoms} atoms, "
            f"≤{steps} steps/structure."
        )

        nv_model.eval()
        with fused, warp_on_torch_stream(device):
            remaining_batch = fused.run(batch=None, n_steps=total_step_budget)

        if remaining_batch is None:
            logger.info("Inflight relax: all structures processed (sampler exhausted).")
        else:
            logger.info(
                f"Inflight relax: step budget exhausted, "
                f"{remaining_batch.num_graphs} structure(s) still active."
            )

        # --- Collect remaining-batch results (not graduated — still active at budget exhaustion) ---
        # orig_idx is a system-level property stamped in AtomsDataset.__getitem__ that
        # survives refill_check unchanged: _bookkeeping_keys only overwrites "status" and
        # "system_id", so orig_idx is reliable even when n_remaining=0 resets system_ids.
        remaining_by_id: Dict[int, Any] = {}
        if remaining_batch is not None:
            for oidx, data in zip(
                remaining_batch["orig_idx"].squeeze(-1).tolist(),
                remaining_batch.to_data_list(),
            ):
                remaining_by_id[int(oidx)] = data

        # --- Serialize to disk ---
        # Structures already written by on_graduate are skipped; only remaining-batch
        # structures (not graduated before budget exhaustion) need post-run serialization.
        results: List[Dict[str, Any]] = []
        for i, struct_name in enumerate(structure_names):
            out_dir = output_dirs[i]

            if i in saved_to_disk:
                # Already written to disk by on_graduate during the run.
                results.append(saved_to_disk[i])
                continue

            os.makedirs(out_dir, exist_ok=True)

            if i not in remaining_by_id:
                results.append(
                    {
                        "structure_name": struct_name,
                        "status": "failed",
                        "error": "Structure missing from sink (lost during inflight batching)",
                        "output_dir": out_dir,
                    }
                )
                continue

            # Not-graduated: save best available state from remaining_batch.
            try:
                atoms = atomic_data_to_atoms(remaining_by_id[i])
                structure = AseAtomsAdaptor.get_structure(atoms)
                cif_path = os.path.join(out_dir, "relaxed_structure.cif")
                structure.to(filename=cif_path)
                final_energy = atoms.get_potential_energy()
                with open(os.path.join(out_dir, "relaxed_energy.txt"), "w") as f:
                    f.write(f"{final_energy}\n")
                results.append(
                    {
                        "structure_name": struct_name,
                        "status": "not_converged",
                        "energy": final_energy,
                        "cif_path": cif_path,
                        "output_dir": out_dir,
                        "converged": False,
                        "steps": int(remaining_by_id[i].relax_steps.item()),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "structure_name": struct_name,
                        "status": "failed",
                        "error": str(e),
                        "output_dir": out_dir,
                    }
                )

        n_success = sum(1 for r in results if r["status"] == "success")
        n_not_converged = sum(1 for r in results if r["status"] == "not_converged")
        n_failed = sum(1 for r in results if r["status"] == "failed")
        logger.info(
            f"NValchemi inflight relax: {n_success} converged, "
            f"{n_not_converged} not converged, {n_failed} failed."
        )

        output_dir_base = str(Path(output_dirs[0]).parent) if output_dirs else "."
        return {
            "mode": "batch",
            "backend": "nvalchemi_inflight",
            "total_structures": len(results),
            "successful": n_success,
            "not_converged": n_not_converged,
            "failed": n_failed,
            "output_dir": output_dir_base,
            "results": results,
        }

    def _batch_relax_sequential(
        self,
        structure_data: Union[str, List[Union[Dict[str, Any], str]]],
        fmax: float,
        steps: int,
        optimizer: str,
        relax_cell: bool,
        output_dir: Optional[str],
    ) -> Dict[str, Any]:
        """Internal method for batch relaxation (sequential loop)."""
        try:
            from pathlib import Path
            import os
            from ..research_utils import get_current_research_dir

            # Determine if this is directory mode or list mode
            structure_list = []
            structure_names = []

            if isinstance(structure_data, str) and Path(structure_data).is_dir():
                # Directory mode: find all structure files
                dir_path = Path(structure_data)

                # Find all CIF, POSCAR, CONTCAR files
                patterns = ["*.cif", "*.CIF", "*POSCAR*", "*CONTCAR*", "*.vasp"]
                for pattern in patterns:
                    for filepath in dir_path.glob(pattern):
                        structure_list.append(str(filepath))
                        structure_names.append(filepath.stem)

                if not structure_list:
                    return {
                        "error": f"No structure files found in directory: {structure_data}"
                    }

            elif isinstance(structure_data, list):
                # List mode
                for i, struct in enumerate(structure_data):
                    structure_list.append(struct)
                    # Generate names from file paths if available
                    if isinstance(struct, str):
                        structure_names.append(Path(struct).stem)
                    else:
                        structure_names.append(f"structure_{i}")
            else:
                return {
                    "error": "structure_data must be a directory path or a list of structures/paths"
                }

            # Set up output directory
            if not output_dir:
                try:
                    output_dir = str(
                        get_current_research_dir()
                        / self.__class__.__name__.lower().replace("wrapper", "")
                        / "batch_relaxation"
                    )
                except Exception:
                    output_dir = "batch_relaxation"

            os.makedirs(output_dir, exist_ok=True)

            # Process each structure
            results = []
            logger.info(f"Batch relaxing {len(structure_list)} structures...")

            for idx, (struct_data, struct_name) in enumerate(
                zip(structure_list, structure_names)
            ):
                try:
                    # Set up subdirectory for this structure
                    struct_output = os.path.join(output_dir, struct_name)
                    os.makedirs(struct_output, exist_ok=True)

                    # Call single structure relax method (recursive, but will NOT trigger batch mode)
                    relax_result = self._single_relax(
                        structure_data=struct_data,
                        fmax=fmax,
                        steps=steps,
                        optimizer=optimizer,
                        relax_cell=relax_cell,
                        output_dir=struct_output,
                        fixed_atoms=None,
                    )

                    if "error" in relax_result:
                        results.append(
                            {
                                "structure_name": struct_name,
                                "status": "failed",
                                "error": relax_result["error"],
                            }
                        )
                        logger.warning(
                            f"Failed to relax {struct_name}: {relax_result['error']}"
                        )
                    else:
                        results.append(
                            {
                                "structure_name": struct_name,
                                "status": relax_result["status"],
                                "energy": relax_result.get("energy"),
                                "output_dir": struct_output,
                                **{
                                    k: v
                                    for k, v in relax_result.items()
                                    if k not in ["energy", "final_structure"]
                                },
                            }
                        )
                        logger.info(
                            f"Relaxed {struct_name}: {relax_result['status']} "
                            f"({idx + 1}/{len(structure_list)})"
                        )

                except Exception as e:
                    import traceback

                    traceback.print_exc(file=sys.stderr)
                    results.append(
                        {
                            "structure_name": struct_name,
                            "status": "failed",
                            "error": str(e),
                        }
                    )
                    logger.error(f"Error relaxing {struct_name}: {e}")

            # Summary
            n_success = sum(1 for r in results if r["status"] == "success")
            n_not_converged = sum(r["status"] == "not_converged" for r in results)
            n_failed = sum(r["status"] == "failed" for r in results)

            logger.info(
                f"Batch relaxation complete: {n_success} converged, "
                f"{n_not_converged} not converged, {n_failed} failed"
            )

            return {
                "mode": "batch",
                "backend": "sequential",
                "total_structures": len(results),
                "successful": n_success,
                "not_converged": n_not_converged,
                "failed": n_failed,
                "output_dir": output_dir,
                "results": results,
            }

        except Exception as e:
            import traceback

            traceback.print_exc(file=sys.stderr)
            return {"error": f"Batch relaxation failed: {str(e)}"}

    def static_calculation(
        self, structure_data: Any, use_nvalchemi: bool = False
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Run static calculation (predict energy, forces, stress) for a structure.

        Batches use the native calculator sequentially by default. Set
        use_nvalchemi=True to opt in to experimental NValchemi batching.
        """
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load_model first."}

        import os

        is_batch = isinstance(structure_data, list) or (
            isinstance(structure_data, str) and Path(structure_data).is_dir()
        )

        if is_batch:
            # NValchemi is an experimental, explicitly selected batch backend.
            nv_model = self._get_enabled_nvalchemi_model(use_nvalchemi)
            if nv_model is not None:
                result = self._batch_static_nvalchemi(nv_model, structure_data)
                if "error" not in result:
                    return result

            # Sequential fallback
            structure_list = []
            structure_names = []
            if isinstance(structure_data, str) and Path(structure_data).is_dir():
                dir_path = Path(structure_data)
                patterns = ["*.cif", "*.CIF", "*POSCAR*", "*CONTCAR*", "*.vasp"]
                for pattern in patterns:
                    for filepath in dir_path.glob(pattern):
                        structure_list.append(str(filepath))
                        structure_names.append(filepath.stem)
            elif isinstance(structure_data, list):
                for i, struct in enumerate(structure_data):
                    structure_list.append(struct)
                    if isinstance(struct, str) and os.path.isfile(struct):
                        structure_names.append(Path(struct).stem)
                    else:
                        structure_names.append(f"structure_{i}")

            results = []
            for struct_data, struct_name in zip(structure_list, structure_names):
                res = self._single_static_calculation(struct_data)
                res["structure_name"] = struct_name
                results.append(res)
            return {
                "mode": "batch",
                "backend": "sequential",
                "total_structures": len(results),
                "results": results,
            }
        else:
            return self._single_static_calculation(structure_data)

    def _batch_static_nvalchemi(
        self,
        nv_model: Any,
        structure_data: Union[str, List[Union[Dict[str, Any], str]]],
    ) -> Dict[str, Any]:
        """GPU-parallel batch static calculation via a single NValchemi forward pass.

        Uses ``nvalchemi.neighbors.compute_neighbors`` to set up the neighbor
        list one-shot (outside a dynamics loop) for MACE/MatGL models.
        FairChem models (``neighbor_config=None``) build their own graph inside
        ``adapt_input``.
        """
        import torch
        from src.utils.mlips.nvalchemi.nvalchemi_utils import atoms_to_atomic_data

        try:
            from nvalchemi.data import Batch
            from nvalchemi.neighbors import compute_neighbors
        except ImportError as e:
            return {"error": f"NValchemi import failed: {e}"}

        parsed = self._parse_batch_input(structure_data)
        if isinstance(parsed[0], dict) and "error" in parsed[0]:
            return parsed[0]
        structure_list, structure_names = parsed

        device = getattr(self, "device", "cpu")

        try:
            atoms_list = [self.check_structure_data(s) for s in structure_list]
            data_list = [
                atoms_to_atomic_data(a, device=device, dtype=torch.float32)
                for a in atoms_list
            ]
            batch = Batch.from_data_list(data_list)

            # Populate neighbor list if the model requires one (MACE, MatGL).
            # FairChem has neighbor_config=None and builds its own graph.
            neighbor_config = getattr(nv_model.model_config, "neighbor_config", None)
            if neighbor_config is not None:
                compute_neighbors(batch, config=neighbor_config)

            # Do NOT use torch.no_grad() here: MACE/MatGL compute forces via
            # autograd and require gradient tracking through positions.
            # FairChemWrapper handles its own no_grad context internally.
            nv_model.eval()
            model_out = nv_model(batch)  # ModelOutputs (OrderedDict)

            energy_t = model_out.get("energy")  # [B, 1] or None
            forces_t = model_out.get("forces")  # [N_total, 3] or None
            stress_t = model_out.get("stress")  # [B, 3, 3] or None

            results = []
            for i, (atoms, struct_name) in enumerate(zip(atoms_list, structure_names)):
                res: Dict[str, Any] = {
                    "structure_name": struct_name,
                    "status": "success",
                }

                if energy_t is not None:
                    res["energy"] = float(energy_t[i].item())

                if forces_t is not None:
                    mask = batch.batch_idx == i
                    res["forces"] = forces_t[mask].detach().cpu().tolist()

                if stress_t is not None:
                    s = stress_t[i]
                    if s.dim() == 3:
                        s = s.squeeze(0)
                    res["stress"] = s.detach().cpu().tolist()

                results.append(res)

            return {
                "mode": "batch",
                "backend": "nvalchemi",
                "total_structures": len(results),
                "results": results,
            }

        except Exception as e:
            import traceback

            traceback.print_exc(file=sys.stderr)
            return {"error": f"NValchemi batch static failed: {e}"}

    def _batch_md_nvalchemi(
        self,
        nv_model: Any,
        structure_list: List[Any],
        structure_names: List[str],
        temperature: float,
        steps: int,
        timestep: float,
        ensemble: str,
        output_dir: str,
        log_interval: int = 10,
        extract_batch_results: bool = True,
    ) -> Dict[str, Any]:
        """GPU-parallel batch MD via NValchemi integrators.

        Supported ensembles: nve, nvt/nvt_nose_hoover, nvt_langevin, npt.
        All others fall back to sequential.
        """
        import os
        import torch
        from src.utils.mlips.nvalchemi.nvalchemi_utils import (
            atoms_to_atomic_data,
            extract_batch_results as extract_batch_results_fn,
            warp_on_torch_stream,
        )

        # Models that set _nvalchemi_supports_batch_md=False (e.g. FairChem,
        # where a batched step is slower than sequential) fall back to
        # sequential MD.
        if not getattr(nv_model, "_nvalchemi_supports_batch_md", True):
            return {
                "error": (
                    f"Batch MD not supported by NValchemi for "
                    f"{type(nv_model).__name__}; using sequential."
                )
            }

        # Map ensemble names → NValchemi integrator classes
        _SEQUENTIAL_ENSEMBLES = {
            "nvt_berendsen",
            "nvt_andersen",
            "nvt_bussi",
            "npt_berendsen",
            "npt_inhomogeneous",
        }
        if ensemble.lower() in _SEQUENTIAL_ENSEMBLES:
            return {"error": f"Ensemble '{ensemble}' not supported by NValchemi."}

        try:
            from nvalchemi.data import Batch
            from nvalchemi.dynamics.base import DynamicsStage
            from src.utils.mlips.nvalchemi.neighbor_list import make_neighbor_list_hook
            from nvalchemi.dynamics._ops.thermostat_utils import initialize_velocities
            from nvalchemi.dynamics.integrators.nve import NVE
            from nvalchemi.dynamics.integrators.nvt_nose_hoover import NVTNoseHoover
            from nvalchemi.dynamics.integrators.nvt_langevin import NVTLangevin
            from nvalchemi.dynamics.integrators.npt import NPT
        except ImportError as e:
            return {"error": f"NValchemi import failed: {e}"}

        device = getattr(self, "device", "cpu")
        os.makedirs(output_dir, exist_ok=True)
        output_dirs = [os.path.join(output_dir, name) for name in structure_names]

        try:
            from nvalchemi.dynamics.hooks import SnapshotHook
            from nvalchemi.dynamics.sinks import HostMemory

            atoms_list = [self.check_structure_data(s) for s in structure_list]
            data_list = [
                atoms_to_atomic_data(a, device=device, dtype=torch.float32)
                for a in atoms_list
            ]
            batch = Batch.from_data_list(data_list)

            # Pre-compute initial forces — Velocity Verlet integrators (NVTNoseHoover,
            # NVE, NPT) require forces at t=0 before the first half-step velocity update.
            # FIRE (relax) computes forces internally before touching positions, so it
            # does not need this, but it is safe to do for all dynamics.
            neighbor_config = getattr(nv_model.model_config, "neighbor_config", None)
            if neighbor_config is not None:
                from nvalchemi.neighbors import compute_neighbors

                compute_neighbors(batch, config=neighbor_config)

            nv_model.eval()
            if hasattr(batch, "positions") and batch.positions is not None:
                batch.positions.requires_grad_(True)
            initial_out = nv_model(batch)
            f0 = (
                initial_out.get("forces")
                if isinstance(initial_out, dict)
                else getattr(initial_out, "forces", None)
            )
            if f0 is not None:
                batch["forces"] = f0.detach()
            e0 = (
                initial_out.get("energy")
                if isinstance(initial_out, dict)
                else getattr(initial_out, "energy", None)
            )
            if e0 is not None:
                batch["energy"] = e0.detach()
            batch.positions.requires_grad_(False)

            # Initialize velocities from Maxwell-Boltzmann
            temp_tensor = torch.full(
                (batch.num_graphs,), temperature, dtype=torch.float32, device=device
            )
            if not hasattr(batch, "velocities") or batch.velocities is None:
                velocities = torch.zeros_like(batch.positions)
                batch["velocities"] = velocities
            initialize_velocities(
                velocities=batch.velocities,
                masses=batch.atomic_masses,
                temperature=temp_tensor,
                batch_idx=batch.batch_idx.int(),
            )

            ens = ensemble.lower()
            if ens == "nve":
                integrator = NVE(model=nv_model, dt=timestep, n_steps=steps)
            elif ens in ("nvt", "nvt_nose_hoover"):
                integrator = NVTNoseHoover(
                    model=nv_model,
                    dt=timestep,
                    temperature=temperature,
                    thermostat_time=100 * timestep,
                    n_steps=steps,
                )
            elif ens == "nvt_langevin":
                integrator = NVTLangevin(
                    model=nv_model,
                    dt=timestep,
                    temperature=temperature,
                    friction=0.01,
                    n_steps=steps,
                )
            elif ens in ("npt", "npt_nose_hoover", "npt_mtk", "npt_isotropic_mtk"):
                # pressure from bar → eV/Å³ (1 bar = 6.2415e-7 eV/Å³)
                pressure_ev_a3 = 0.0  # caller passes in bar; convert
                integrator = NPT(
                    model=nv_model,
                    dt=timestep,
                    temperature=temperature,
                    pressure=pressure_ev_a3,
                    barostat_time=1000 * timestep,
                    thermostat_time=100 * timestep,
                    pressure_coupling="isotropic",
                    n_steps=steps,
                )
            else:
                return {"error": f"Unknown ensemble '{ensemble}'."}

            if getattr(nv_model.model_config, "neighbor_config", None) is not None:
                nl_hook = make_neighbor_list_hook(
                    nv_model.model_config.neighbor_config,
                    stage=DynamicsStage.BEFORE_COMPUTE,
                )
                integrator.register_hook(nl_hook)

            # Setup memory sink to record MD snapshots if requested
            memory_sink = None
            if extract_batch_results:
                capacity = (steps // log_interval + 2) * len(structure_list)
                memory_sink = HostMemory(capacity=capacity)
                snapshot_hook = SnapshotHook(sink=memory_sink, frequency=log_interval)
                integrator.register_hook(snapshot_hook)

                # Write initial step 0 state
                memory_sink.write(batch)

            with integrator, warp_on_torch_stream(device):
                final_batch = integrator.run(batch)

            # Reconstruct trajectory and log for each structure using unified extraction helper
            results = extract_batch_results_fn(
                final_batch=final_batch,
                structure_names=structure_names,
                output_dirs=output_dirs,
                mode="md",
                memory_sink=memory_sink,
                log_interval=log_interval,
                timestep=timestep,
                temperature=temperature,
                ensemble=ensemble,
            )

        except Exception as e:
            import traceback
            import sys

            traceback.print_exc(file=sys.stderr)
            return {"error": f"NValchemi batch MD failed: {e}"}

        n_success = sum(1 for r in results if r["status"] == "success")
        n_failed = len(results) - n_success
        logger.info(f"NValchemi batch MD: {n_success} OK, {n_failed} failed")

        return {
            "mode": "batch",
            "backend": "nvalchemi",
            "total_jobs": len(results),
            "successful": n_success,
            "failed": n_failed,
            "output_dir": output_dir,
            "results": results,
        }

    def _single_static_calculation(self, structure_data: Any) -> Dict[str, Any]:
        """Internal single static calculation."""
        # Validate structure
        atoms = self.check_structure_data(structure_data)
        if isinstance(atoms, dict) and "error" in atoms:
            return atoms

        try:
            # Create and attach calculator
            calc = self.create_calculator()
            atoms.calc = calc

            # Predict
            energy = atoms.get_potential_energy()
            forces = atoms.get_forces().tolist()

            result = {"energy": energy, "forces": forces}

            # Try to get stress
            try:
                stress = atoms.get_stress()
                # ASE units: stress is in eV/A^3
                # We standardize to eV/A^3 across the project for simulation compatibility
                result["stress"] = (
                    [float(x) for x in stress.tolist()]
                    if hasattr(stress, "tolist")
                    else [float(x) for x in stress]
                )
            except Exception:
                pass
            return result
        except Exception as e:
            return {"error": f"Prediction failed: {str(e)}"}

    def _single_run_md(
        self,
        structure_data: Any,
        temperature: float = 300.0,
        steps: int = 1000,
        timestep: float = 1.0,
        ensemble: str = "nvt",
        log_interval: int = 10,
        pressure: float = 0.0,
        pressure_mask: Optional[List[int]] = None,
        output_dir: Optional[str] = None,
        monitor: bool = False,
        monitor_type: Optional[Union[str, List[str]]] = None,
        monitor_params: Optional[Dict[str, Any]] = None,
        supercell_min_length: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Run molecular dynamics simulation using MatCalc for a single structure/temperature.
        """
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load_model first."}

        from ase import units
        from pymatgen.io.ase import AseAtomsAdaptor
        from src.utils.research_utils import get_current_research_dir
        from src.utils.mlips.md_runner import CustomMDCalc

        # Check structure data
        atoms = self.check_structure_data(structure_data)
        if isinstance(atoms, dict) and "error" in atoms:
            return atoms

        # Perform supercell expansion if requested
        if supercell_min_length is not None and supercell_min_length > 0.0:
            import numpy as np

            cell_lengths = atoms.cell.lengths()
            # Calculate required repeats to meet min length
            repeats = np.ceil(supercell_min_length / cell_lengths).astype(int)
            # Ensure we don't have 0 repeats just in case
            repeats = np.maximum(repeats, 1)
            if any(r > 1 for r in repeats):
                atoms = atoms.repeat(repeats)
                logger.info(
                    f"Expanded structure to supercell {repeats.tolist()} to meet minimum length {supercell_min_length}Å"
                )

        if not output_dir:
            try:
                output_dir = str(
                    get_current_research_dir()
                    / self.__class__.__name__.lower().replace("wrapper", "")
                    / "md"
                )
            except Exception:
                output_dir = "md_results"

        os.makedirs(output_dir, exist_ok=True)

        # Save MD inputs
        import json

        # Extract model info
        m_name = getattr(self, "model_name", None) or getattr(
            self.model, "model_name", None
        )

        m_head = getattr(self, "head", None)
        if m_head is None:
            m_head = getattr(self, "task_name", None)
        if m_head is None and hasattr(self.model, "head"):
            m_head = getattr(self.model, "head", None)
        if m_head is None and hasattr(self.model, "task_name"):
            m_head = getattr(self.model, "task_name", None)

        md_inputs = {
            "model_name": m_name,
            "prediction_head": m_head,
            "temperature": temperature,
            "steps": steps,
            "timestep": timestep,
            "ensemble": ensemble,
            "log_interval": log_interval,
            "pressure": pressure,
            "pressure_mask": pressure_mask,
            "monitor": monitor,
            "monitor_type": monitor_type,
            "monitor_params": monitor_params,
            "supercell_min_length": supercell_min_length,
        }
        with open(os.path.join(output_dir, "md_inputs.json"), "w") as f:
            json.dump(md_inputs, f, indent=4)

        # Formulate filenames
        if hasattr(atoms, "get_chemical_formula"):
            formula = (
                atoms.get_CHEMICAL_FORMULA()
                if hasattr(atoms, "get_CHEMICAL_FORMULA")
                else atoms.get_chemical_formula()
            )
        else:
            formula = "unknown"

        filename_base = f"{formula}_{temperature}K_{ensemble}"
        traj_path = os.path.join(output_dir, f"{filename_base}.traj")
        log_path = os.path.join(output_dir, f"{filename_base}.log")

        # Setup Stability Monitoring callbacks
        additional_callbacks = []

        if monitor and monitor_type:
            # Support single string or list of monitor types
            monitors = [monitor_type] if isinstance(monitor_type, str) else monitor_type

            for m_type in monitors:
                # Delay import to avoid circular dependency
                from src.utils.mlips.md_utils import get_md_callback

                callback_instance = get_md_callback(
                    m_type,
                    atoms,
                    temperature=temperature,
                    output_dir=output_dir,
                    **(monitor_params or {}),
                )
                if callback_instance:
                    additional_callbacks.append((callback_instance, log_interval))

        # Prepare Calculator
        calc = self.create_calculator()

        # Convert pressure from bar to eV/A^3 for MatCalc
        pressure_ev_ang3 = pressure * units.bar if pressure is not None else 0.0

        # ASE returns zeros (never None) from get_velocities() when no momenta
        # are stored, so only a restart frame that carries momenta (e.g. a .traj
        # written by a previous MD run) keeps its velocities and skips relaxation.
        has_velocities = "momenta" in atoms.arrays and bool(atoms.get_momenta().any())

        md_calc = CustomMDCalc(
            calculator=calc,
            ensemble=ensemble.lower(),
            temperature=temperature,
            steps=steps,
            timestep=timestep,
            loginterval=log_interval,
            pressure=pressure_ev_ang3,
            mask=pressure_mask,
            trajfile=traj_path,
            logfile=log_path,
            set_zero_rotation=True,
            set_com_stationary=True,
            relax_structure=False if has_velocities else True,
            additional_callbacks=additional_callbacks if additional_callbacks else None,
        )

        # Run simulation
        status, stop_reason = "success", None
        try:
            from src.utils.mlips.md_utils import MDStopIteration

            md_calc.calc(atoms)
        except MDStopIteration as e:
            status, stop_reason = "stopped", str(e)
            logger.info(f"MD terminated early by monitor: {e}")

        # Final structure = last MD frame (the input when the MD never started)
        md_atoms = getattr(md_calc, "md_atoms", None)
        final_atoms = md_atoms.copy() if md_atoms is not None else atoms
        final_structure = AseAtomsAdaptor.get_structure(final_atoms)
        cif_path = os.path.join(output_dir, "final_structure.cif")
        final_structure.to(filename=cif_path)

        result = {
            "status": status,
            "trajectory_path": traj_path,
            "log_path": log_path,
            "cif_path": cif_path,
            "final_structure": final_structure.as_dict(),
        }
        if stop_reason is not None:
            result["stop_reason"] = stop_reason
        return result

    def run_md(
        self,
        structure_data: Union[Any, str, List[Union[Dict[str, Any], str]]],
        temperature: float = 300.0,
        steps: int = 1000,
        timestep: float = 1.0,
        ensemble: str = "nvt",
        log_interval: int = 10,
        pressure: float = 0.0,
        pressure_mask: Optional[List[int]] = None,
        output_dir: Optional[str] = None,
        monitor: bool = False,
        monitor_type: Optional[Union[str, List[str]]] = None,
        monitor_params: Optional[Dict[str, Any]] = None,
        supercell_min_length: Optional[float] = None,
        extract_batch_results: bool = True,
        use_nvalchemi: bool = False,
    ) -> Dict[str, Any]:
        """
        Run molecular dynamics simulation using MatCalc.
        Supports batch processing over multiple structures at a single temperature.

        Args:
            structure_data: Single structure, directory of structures, or list of structures.
            temperature: Temperature in Kelvin.
            steps: Number of steps.
            timestep: Timestep in fs.
            ensemble: Ensemble "nve", "nvt", "npt", etc.
            log_interval: Interval for logging.
            pressure: Target pressure in bar (converted to eV/A^3 for MatCalc if needed).
            pressure_mask: Mask for anisotropic NPT.
            output_dir: Directory to save results.
            monitor: Whether to monitor stability and stop early.
            monitor_type: Type of monitoring ("melting", "explosion", "overshoot", "volume") or list of types.
            monitor_params: Optional dictionary of parameters for the monitors (e.g., upper_limit_ratio).
            supercell_min_length: Minimum length (Å) for each lattice vector. Automatically expands supercell. Set None to disable.
            use_nvalchemi: Opt in to experimental NValchemi batching (default False).
            extract_batch_results: Whether to extract full trajectory / logs for all structures in batch mode.

        Returns:
            Dictionary with MD results (or batch summary).
        """
        # Check if structure_data is batch
        import os

        is_batch = False
        structure_list = []
        structure_names = []

        if isinstance(structure_data, str) and os.path.isdir(structure_data):
            is_batch = True
            dir_path = Path(structure_data)
            patterns = ["*.cif", "*.CIF", "*POSCAR*", "*CONTCAR*", "*.vasp"]
            for pattern in patterns:
                for filepath in dir_path.glob(pattern):
                    structure_list.append(str(filepath))
                    structure_names.append(filepath.stem)
        elif isinstance(structure_data, list):
            is_batch = True
            for i, struct in enumerate(structure_data):
                structure_list.append(struct)
                if isinstance(struct, str) and os.path.isfile(struct):
                    structure_names.append(Path(struct).stem)
                else:
                    structure_names.append(f"structure_{i}")
        else:
            structure_list = [structure_data]
            structure_names = ["structure"]

        # Special casing for single mode
        if not is_batch:
            return self._single_run_md(
                structure_data=structure_data,
                temperature=temperature,
                steps=steps,
                timestep=timestep,
                ensemble=ensemble,
                log_interval=log_interval,
                pressure=pressure,
                pressure_mask=pressure_mask,
                output_dir=output_dir,
                monitor=monitor,
                monitor_type=monitor_type,
                monitor_params=monitor_params,
                supercell_min_length=supercell_min_length,
            )

        # Batch Mode Initialization
        if not output_dir:
            from src.utils.research_utils import get_current_research_dir

            try:
                output_dir = str(
                    get_current_research_dir()
                    / self.__class__.__name__.lower().replace("wrapper", "")
                    / "batch_md"
                    / f"{temperature}K"
                )
            except Exception:
                output_dir = f"batch_md_{temperature}K"

        # Opt in to experimental NValchemi GPU-parallel MD.
        nv_model = self._get_enabled_nvalchemi_model(use_nvalchemi)
        if nv_model is not None:
            nv_result = self._batch_md_nvalchemi(
                nv_model=nv_model,
                structure_list=structure_list,
                structure_names=structure_names,
                temperature=temperature,
                steps=steps,
                timestep=timestep,
                ensemble=ensemble,
                output_dir=output_dir,
                log_interval=log_interval,
                extract_batch_results=extract_batch_results,
            )
            if "error" not in nv_result:
                return nv_result
            logger.warning(
                f"NValchemi MD failed ({nv_result.get('error')}); falling back to sequential."
            )

        os.makedirs(output_dir, exist_ok=True)
        results = []
        logger.info(
            f"Batch MD on {len(structure_list)} structures at {temperature}K..."
        )

        for idx, (struct_data, struct_name) in enumerate(
            zip(structure_list, structure_names)
        ):
            struct_output_dir = os.path.join(output_dir, struct_name)
            os.makedirs(struct_output_dir, exist_ok=True)

            try:
                logger.info(f"-> Batch MD: Running {struct_name}...")
                md_res = self._single_run_md(
                    structure_data=struct_data,
                    temperature=temperature,
                    steps=steps,
                    timestep=timestep,
                    ensemble=ensemble,
                    log_interval=log_interval,
                    pressure=pressure,
                    pressure_mask=pressure_mask,
                    output_dir=struct_output_dir,
                    monitor=monitor,
                    monitor_type=monitor_type,
                    monitor_params=monitor_params,
                    supercell_min_length=supercell_min_length,
                )

                if "error" in md_res:
                    results.append(
                        {
                            "structure_name": struct_name,
                            "status": "failed",
                            "error": md_res["error"],
                        }
                    )
                else:
                    results.append(
                        {
                            "structure_name": struct_name,
                            "status": md_res.get("status", "success"),
                            "stop_reason": md_res.get("stop_reason"),
                            "trajectory_path": md_res.get("trajectory_path"),
                            "log_path": md_res.get("log_path"),
                            "output_dir": struct_output_dir,
                        }
                    )
            except Exception as e:
                results.append(
                    {"structure_name": struct_name, "status": "failed", "error": str(e)}
                )

        n_success = sum(1 for r in results if r["status"] in ["success", "stopped"])
        n_failed = len(results) - n_success

        logger.info(f"Batch MD complete: {n_success} successful, {n_failed} failed")

        return {
            "mode": "batch",
            "backend": "sequential",
            "total_jobs": len(results),
            "successful": n_success,
            "failed": n_failed,
            "output_dir": output_dir,
            "results": results,
        }

    def get_supported_elements(self) -> List[str]:
        """
        Get list of chemical elements supported by the model.

        Returns:
            List of element symbols.
        """
        # Default implementation - should be overridden by subclasses
        return []

    def get_model_capabilities(self) -> Optional[Dict[str, bool]]:
        """
        Get model capabilities (energy, forces, stress, etc.).

        Returns:
            Dictionary indicating which properties the model can predict, or None if not implemented.
        """
        return None
