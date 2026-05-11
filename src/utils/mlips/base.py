"""
Base MLIP model interface for MLIP MCP Wrappers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Union
import logging
import json
import os
import sys
import time
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # Must be set before importing pyplot
import matplotlib.pyplot as plt
import numpy as np

# MD related imports will be done inside methods to avoid hard dependencies if not used
# But we can add some common ones here
try:
    from ase import Atoms, units
except ImportError:
    pass

logger = logging.getLogger(__name__)

from .md_utils import MDStopIteration, get_md_callback


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
            'loss_train': [],
            'loss_val': [],
            'energy_mae_train': [],
            'energy_mae_val': [],
            'force_mae_train': [],
            'force_mae_val': [],
            'stress_mae_train': [],
            'stress_mae_val': [],
            'epoch': []
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
            if not hasattr(structure, 'get_atomic_numbers'):
                return False
            if not hasattr(structure, 'get_positions'):
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
        import os

        # Check for file path string
        # Check for file path string
        if isinstance(structure_data, str):
            if str(structure_data).endswith(".traj"):
                from ase.io import read
                try:
                    return read(structure_data, index=-1)
                except Exception as e:
                    return {"error": f"Failed to load trajectory from file: {structure_data}, error: {e}"}
            else:
                from ..structure_utils import load_structure_from_file
                struct = load_structure_from_file(structure_data)
                if struct is not None:
                    from pymatgen.io.ase import AseAtomsAdaptor
                    return AseAtomsAdaptor.get_atoms(struct)
                else:
                    return {"error": f"Failed to load structure from file: {structure_data}"}
        
        # Check for pymatgen Structure object
        if hasattr(structure_data, "as_dict") and hasattr(structure_data, "lattice"):
             try:
                 from pymatgen.io.ase import AseAtomsAdaptor
                 return AseAtomsAdaptor.get_atoms(structure_data)
             except ImportError:
                 return {"error": "pymatgen not installed, cannot convert Structure object."}
        
        # Check for ASE Atoms object
        if isinstance(structure_data, Atoms):
             return structure_data
             
        # Check for dict format
        if isinstance(structure_data, dict):
            # Check for pymatgen dict
            if "@module" in structure_data or ("sites" in structure_data and "lattice" in structure_data):
                try:
                    from pymatgen.core import Structure
                    from pymatgen.io.ase import AseAtomsAdaptor
                    struct = Structure.from_dict(structure_data)
                    return AseAtomsAdaptor.get_atoms(struct)
                except Exception as e:
                    return {"error": f"Failed to convert pymatgen dict: {str(e)}"}
            
            # Check for simple ASE dict
            if 'symbols' in structure_data and 'positions' in structure_data:
                return Atoms(
                    symbols=structure_data['symbols'],
                    positions=structure_data['positions'],
                    cell=structure_data.get('cell'),
                    pbc=structure_data.get('pbc', True)
                )
        
            return {"error": "Invalid structure format. Must be file path, pymatgen Structure, ASE Atoms, or dict with 'symbols' and 'positions'."}

            return {"error": f"Relaxation failed: {str(e)}"}
    
    def relax_structure(
        self,
        structure_data: Union[Any, str, List[Union[Dict[str, Any], str]]],
        fmax: float = 0.01,
        steps: int = 500,
        optimizer: str = "FIRE",
        relax_cell: bool = True,
        output_dir: Optional[str] = None,
        fixed_atoms: Optional[List[int]] = None
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
            
        Returns:
            For single structure: Dict with energy, trajectory_path, cif_path, json_path
            For batch mode: Dict with mode="batch", total_structures, successful, failed, results list
        """
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load_model first."}
        
        # Auto-detect batch mode
        from pathlib import Path
        is_batch = isinstance(structure_data, list) or (isinstance(structure_data, str) and Path(structure_data).is_dir())
        
        if is_batch:
            # BATCH MODE
            return self._batch_relax(structure_data, fmax, steps, optimizer, relax_cell, output_dir)
        else:
            # SINGLE STRUCTURE MODE
            return self._single_relax(structure_data, fmax, steps, optimizer, relax_cell, output_dir, fixed_atoms)
    
    def _single_relax(
        self,
        structure_data: Any,
        fmax: float,
        steps: int,
        optimizer: str,
        relax_cell: bool,
        output_dir: Optional[str],
        fixed_atoms: Optional[List[int]]
    ) -> Dict[str, Any]:
        """Internal method for single structure relaxation."""
        try:
            from ase.constraints import FixAtoms
            from ase.filters import FrechetCellFilter
            from pymatgen.io.ase import AseAtomsAdaptor
            import os
            import json
            import sys
            import contextlib
            from ..structure_utils import save_structure
            from ..research_utils import get_current_research_dir
            import ase.optimize
            from ase import Atoms

            # Check structure data
            atoms = self.check_structure_data(structure_data)
            if isinstance(atoms, dict) and "error" in atoms:
                return atoms

            # Ensure we have a standard ASE Atoms object (fix MSONAtoms issue)
            if atoms.__class__.__name__ == "MSONAtoms" or not hasattr(atoms, "set_constraint"):
                atoms = Atoms(atoms)
                
            if fixed_atoms:
                atoms.set_constraint(FixAtoms(indices=fixed_atoms))

            if not output_dir:
                try:
                    output_dir = str(get_current_research_dir() / self.__class__.__name__.lower().replace("wrapper", "") / "relaxation")
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
            opt.run(fmax=fmax, steps=steps)
            
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
                with open(energy_file, 'w') as f:
                    f.write(str(energy_val))

            return {
                "energy": energy_val,
                "trajectory_path": traj_file,
                "log_path": log_file,
                "cif_path": cif_path,
                "output_dir": output_dir
            }
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            return {"error": f"Relaxation failed: {str(e)}"}
    
    def _batch_relax(
        self,
        structure_data: Union[str, List[Union[Dict[str, Any], str]]],
        fmax: float,
        steps: int,
        optimizer: str,
        relax_cell: bool,
        output_dir: Optional[str]
    ) -> Dict[str, Any]:
        """Internal method for batch relaxation."""
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
                    return {"error": f"No structure files found in directory: {structure_data}"}
                    
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
                return {"error": "structure_data must be a directory path or a list of structures/paths"}
            
            # Set up output directory
            if not output_dir:
                try:
                    output_dir = str(get_current_research_dir() / self.__class__.__name__.lower().replace("wrapper", "") / "batch_relaxation")
                except Exception:
                    output_dir = "batch_relaxation"
            
            os.makedirs(output_dir, exist_ok=True)
            
            # Process each structure
            results = []
            logger.info(f"Batch relaxing {len(structure_list)} structures...")
            
            for idx, (struct_data, struct_name) in enumerate(zip(structure_list, structure_names)):
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
                        fixed_atoms=None
                    )
                    
                    if "error" in relax_result:
                        results.append({
                            "structure_name": struct_name,
                            "status": "failed",
                            "error": relax_result["error"]
                        })
                        logger.warning(f"Failed to relax {struct_name}: {relax_result['error']}")
                    else:
                        results.append({
                            "structure_name": struct_name,
                            "status": "success",
                            "energy": relax_result.get("energy"),
                            "output_dir": struct_output,
                            **{k: v for k, v in relax_result.items() if k not in ["energy", "final_structure"]}
                        })
                        logger.info(f"Successfully relaxed {struct_name} ({idx+1}/{len(structure_list)})")
                        
                except Exception as e:
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    results.append({
                        "structure_name": struct_name,
                        "status": "failed",
                        "error": str(e)
                    })
                    logger.error(f"Error relaxing {struct_name}: {e}")
            
            # Summary
            n_success = sum(1 for r in results if r["status"] == "success")
            n_failed = len(results) - n_success
            
            logger.info(f"Batch relaxation complete: {n_success} successful, {n_failed} failed")
            
            return {
                "mode": "batch",
                "total_structures": len(results),
                "successful": n_success,
                "failed": n_failed,
                "output_dir": output_dir,
                "results": results
            }
                
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            return {"error": f"Batch relaxation failed: {str(e)}"}
        

    def static_calculation(self, structure_data: Any) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Run static calculation (predict energy, forces, stress) for a structure.
        """
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load_model first."}
            
        from pathlib import Path
        import os
        is_batch = isinstance(structure_data, list) or (isinstance(structure_data, str) and Path(structure_data).is_dir())
        
        if is_batch:
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
            return {"mode": "batch", "total_structures": len(results), "results": results}
        else:
            return self._single_static_calculation(structure_data)

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
            
            result = {
                "energy": energy,
                "forces": forces
            }
            
            # Try to get stress
            try:
                stress = atoms.get_stress()
                # ASE units: stress is in eV/A^3
                # We standardize to eV/A^3 across the project for simulation compatibility
                result["stress"] = [float(x) for x in stress.tolist()] if hasattr(stress, "tolist") else [float(x) for x in stress]
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
        supercell_min_length: Optional[float] = None
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
        import os
        
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
                logger.info(f"Expanded structure to supercell {repeats.tolist()} to meet minimum length {supercell_min_length}Å")

        if not output_dir:
            try:
                output_dir = str(get_current_research_dir() / self.__class__.__name__.lower().replace("wrapper", "") / "md")
            except Exception:
                output_dir = "md_results"
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save MD inputs
        import json
        # Extract model info
        m_name = getattr(self, "model_name", None) or getattr(self.model, "model_name", None)
        
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
            "supercell_min_length": supercell_min_length
        }
        with open(os.path.join(output_dir, "md_inputs.json"), "w") as f:
            json.dump(md_inputs, f, indent=4)
        
        # Formulate filenames
        if hasattr(atoms, "get_chemical_formula"):
            formula = atoms.get_CHEMICAL_FORMULA() if hasattr(atoms, "get_CHEMICAL_FORMULA") else atoms.get_chemical_formula()
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
                    **(monitor_params or {})
                )
                if callback_instance:
                    additional_callbacks.append((callback_instance, log_interval))

        # Prepare Calculator
        calc = self.create_calculator()
        
        # Convert pressure from bar to eV/A^3 for MatCalc
        pressure_ev_ang3 = pressure * units.bar if pressure is not None else 0.0

        has_velocities = hasattr(atoms, "get_velocities") and atoms.get_velocities() is not None

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
            additional_callbacks=additional_callbacks if additional_callbacks else None
        )
        
        # Run simulation
        try:
            from src.utils.mlips.md_utils import MDStopIteration
            md_calc.calc(atoms)
        except MDStopIteration as e:
            logger.info(f"MD terminated early by monitor: {e}")
            
        # Normal Final struct update
        final_structure = AseAtomsAdaptor.get_structure(atoms)
        cif_path = os.path.join(output_dir, "final_structure.cif")
        final_structure.to(filename=cif_path)
        
        return {
            "status": "success",
            "trajectory_path": traj_path,
            "log_path": log_path,
            "cif_path": cif_path,
            "final_structure": final_structure.as_dict()
        }

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
        supercell_min_length: Optional[float] = None
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
            
        Returns:
            Dictionary with MD results (or batch summary).
        """
        # Check if structure_data is batch
        from pathlib import Path
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
                supercell_min_length=supercell_min_length
            )

        # Batch Mode Initialization
        if not output_dir:
            from src.utils.research_utils import get_current_research_dir
            try:
                output_dir = str(get_current_research_dir() / self.__class__.__name__.lower().replace("wrapper", "") / "batch_md" / f"{temperature}K")
            except Exception:
                output_dir = f"batch_md_{temperature}K"
        
        os.makedirs(output_dir, exist_ok=True)
        results = []
        logger.info(f"Batch MD on {len(structure_list)} structures at {temperature}K...")

        for idx, (struct_data, struct_name) in enumerate(zip(structure_list, structure_names)):
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
                    supercell_min_length=supercell_min_length
                )
                
                if "error" in md_res:
                    results.append({
                        "structure_name": struct_name,
                        "status": "failed",
                        "error": md_res["error"]
                    })
                else:
                    results.append({
                        "structure_name": struct_name,
                        "status": md_res.get("status", "success"),
                        "trajectory_path": md_res.get("trajectory_path"),
                        "log_path": md_res.get("log_path"),
                        "output_dir": struct_output_dir
                    })
            except Exception as e:
                results.append({
                    "structure_name": struct_name,
                    "status": "failed",
                    "error": str(e)
                })
                    
        n_success = sum(1 for r in results if r["status"] in ["success", "stopped_early"])
        n_failed = len(results) - n_success
        
        logger.info(f"Batch MD complete: {n_success} successful, {n_failed} failed")
        
        return {
            "mode": "batch",
            "total_jobs": len(results),
            "successful": n_success,
            "failed": n_failed,
            "output_dir": output_dir,
            "results": results
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
    


