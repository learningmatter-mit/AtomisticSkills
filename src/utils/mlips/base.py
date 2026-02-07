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
    
    @abstractmethod
    def fine_tune(
        self,
        training_data: List[Dict[str, Any]],
        validation_data: Optional[List[Dict[str, Any]]] = None,
        training_config: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        wandb_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fine-tune the model on provided training data.
        
        Args:
            training_data: List of training samples, each containing structure and properties
            validation_data: Optional validation data for monitoring training
            training_config: Training configuration parameters
            output_dir: Directory to save the fine-tuned model
            wandb_config: Optional wandb configuration dictionary with keys:
                - project: wandb project name
                - entity: wandb entity (username/team)
                - name: run name
                - tags: list of tags
                - mode: "online", "offline", or "disabled"
        
        Returns:
            Dictionary containing training history and metrics.
        
        Raises:
            RuntimeError: If fine-tuning fails.
        """
        pass
    
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
            "model_type": self.__class__.__name__
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
        

    def static_calculation(self, structure_data: Any) -> Dict[str, Any]:
        """
        Run static calculation (predict energy, forces, stress) for a structure.
        
        Args:
            structure_data: Structure data compatible with check_structure_data.
            
        Returns:
            Dictionary containing 'energy' (eV), 'forces' (eV/A), and 'stress' (eV/Å³) if available.
        """
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load_model first."}
            
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

    def run_md(
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
        monitor_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run molecular dynamics simulation using MatCalc.
        
        Args:
            structure_data: Structure data compatible with check_structure_data.
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
            
        Returns:
            Dictionary with MD results.
        """
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load_model first."}

        try:
            from matcalc import MDCalc
            from ase import units
            from pymatgen.io.ase import AseAtomsAdaptor
            from src.utils.research_utils import get_current_research_dir
            from src.utils.serialization_utils import recursive_tolist

            # Check structure data
            atoms = self.check_structure_data(structure_data)
            if isinstance(atoms, dict) and "error" in atoms:
                return atoms

            if not output_dir:
                try:
                    output_dir = str(get_current_research_dir() / self.__class__.__name__.lower().replace("wrapper", "") / "md")
                except Exception:
                    output_dir = "md_results"
            
            os.makedirs(output_dir, exist_ok=True)
            
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
                    callback_info = get_md_callback(
                        m_type, 
                        atoms, 
                        timestep_fs=timestep, 
                        log_interval=log_interval,
                        temperature=temperature,
                        **(monitor_params or {})
                    )
                    if callback_info:
                        additional_callbacks.append(callback_info)

            # Prepare Calculator
            calc = self.create_calculator()
            
            # Convert pressure from bar to eV/A^3 for MatCalc
            pressure_ev_ang3 = pressure * units.bar if pressure is not None else 0.0

            from src.utils.mlips.md_runner import CustomMDCalc

            # Initialize MDCalc with the calculator and parameters
            # Note: We use CustomMDCalc to ensure additional_callbacks are supported and passed correctly.
            md_runner = CustomMDCalc(
                calculator=calc,
                ensemble=ensemble.lower(), # Keep .lower() for consistency with matcalc
                temperature=temperature,
                timestep=timestep,
                steps=steps,
                trajfile=traj_path,
                logfile=log_path,
                loginterval=log_interval,
                pressure=pressure_ev_ang3,
                mask=pressure_mask, # Re-added mask
                set_zero_rotation=True, # Good practice for MD
                set_com_stationary=True,
                additional_callbacks=additional_callbacks if additional_callbacks else None
            )
            
            # Run MD - Catch the StopIteration
            try:
                result = md_runner.calc(atoms)
            except MDStopIteration as e:
                logger.info(f"MD stopped by monitor: {e}")
                # We return a result manually since MDCalc.calc was interrupted
                # Save final structure
                final_struct = AseAtomsAdaptor.get_structure(atoms)
                final_struct_path = os.path.join(output_dir, f"{filename_base}_final.cif")
                try:
                    final_struct.to(filename=final_struct_path)
                except Exception as save_err:
                    logger.warning(f"Failed to save final structure in stopped run: {save_err}")
                    final_struct_path = None

                return {
                    "status": "stopped",
                    "stop_reason": str(e),
                    "final_structure_path": final_struct_path,
                    "trajectory_path": traj_path,
                    "log_path": log_path,
                    "energy": float(atoms.get_potential_energy()),
                    "final_energy": float(atoms.get_potential_energy()),
                    "final_temperature": float(atoms.get_temperature())
                }

            # Clean up result for return (remove heavy objects)
            safe_result = {
                "trajectory_path": traj_path,
                "log_path": log_path,
                "potential_energy": result.get("potential_energy"),
                "kinetic_energy": result.get("kinetic_energy"),
                "total_energy": result.get("total_energy"),
                "status": "success"
            }
            
            # Save final structure if present
            if "final_structure" in result:
                final_struct = result["final_structure"]
                final_struct_path = os.path.join(output_dir, f"{filename_base}_final.cif")
                
                try:
                    # Pymatgen Structure
                    if hasattr(final_struct, "to"):
                        final_struct.to(filename=final_struct_path)
                    # ASE Atoms
                    elif hasattr(final_struct, "write"):
                        final_struct.write(final_struct_path)
                        
                    safe_result["final_structure_path"] = final_struct_path
                except Exception as e:
                    logger.warning(f"Failed to save final structure: {e}")
            
            return recursive_tolist(safe_result)

        except Exception as e:
            import traceback
            logger.error(f"MD failed: {str(e)}\n{traceback.format_exc()}")
            return {"error": f"MD failed: {str(e)}"}
            



    
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
    
    def plot_training_history(self, save_path: Optional[str] = None, show: bool = True) -> None:
        """
        Plot training history with multiple subplots showing training progress.
        
        Args:
            save_path: Optional path to save the plot. If None, plot is not saved.
            show: Whether to display the plot.
        
        Raises:
            RuntimeError: If fine-tuning has not been performed.
        """
        if not self.is_fine_tuned:
            raise RuntimeError("Model must be fine-tuned before plotting training history")
        
        # Get training history from the model
        training_history = getattr(self, '_training_history', None)
        if training_history is None:
            raise RuntimeError("Training history not available. Please ensure fine-tuning was completed successfully.")
        
        # Create figure with subplots: 2 rows x 3 cols for distributions and MAEs, plus loss
        # Layout: [Energy Dist, Force Dist, Stress Dist]
        #         [Energy MAE, Force MAE, Stress MAE]
        #         [Loss (separate row)]
        fig = plt.figure(figsize=(18, 16)) # Increased height
        gs = fig.add_gridspec(3, 3, hspace=0.4, wspace=0.3) # Increased hspace
        fig.suptitle(f'Training History - {self.model_name}', fontsize=16, fontweight='bold')
        
        # Create axes for distributions and MAEs (rows 0-1)
        ax1 = fig.add_subplot(gs[0, 0])  # Energy distribution
        ax2 = fig.add_subplot(gs[0, 1])  # Force distribution
        ax3 = fig.add_subplot(gs[0, 2])  # Stress distribution
        ax4 = fig.add_subplot(gs[1, 0])  # Energy MAE
        ax5 = fig.add_subplot(gs[1, 1])  # Force MAE
        ax6 = fig.add_subplot(gs[1, 2])  # Stress MAE
        # Place Loss in the center of the bottom row (2, 1) to avoid overlap and use 3x3 grid properly
        ax_loss = fig.add_subplot(gs[2, 1]) 
        
        # Create axes array for compatibility with existing code
        axes = np.array([
            [ax1, ax2, ax3],
            [ax4, ax5, ax6]
        ])
        
        # 1. Distribution of energy, force, and stress label values
        ax1 = axes[0, 0]
        if 'energy_distribution' in training_history and len(training_history['energy_distribution']) > 0:
            energies = training_history['energy_distribution']
            ax1.hist(energies, bins=50, alpha=0.7, color='blue', edgecolor='black')
            ax1.set_xlabel('Energy (eV/atom)')
            ax1.set_ylabel('Count')
            ax1.set_title('Energy Distribution')
            ax1.grid(True, alpha=0.3)
        else:
            ax1.text(0.5, 0.5, 'No energy data', ha='center', va='center', transform=ax1.transAxes)
            ax1.set_title('Energy Distribution')
        
        ax2 = axes[0, 1]
        if 'force_distribution' in training_history and len(training_history['force_distribution']) > 0:
            forces = training_history['force_distribution']
            ax2.hist(forces, bins=50, alpha=0.7, color='green', edgecolor='black')
            ax2.set_xlabel('Force (eV/Å)')
            ax2.set_ylabel('Count')
            ax2.set_title('Force Distribution')
            ax2.grid(True, alpha=0.3)
        else:
            ax2.text(0.5, 0.5, 'No force data', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Force Distribution')
        
        ax3 = axes[0, 2]
        if 'stress_distribution' in training_history and len(training_history['stress_distribution']) > 0:
            stresses = training_history['stress_distribution']
            ax3.hist(stresses, bins=50, alpha=0.7, color='red', edgecolor='black')
            ax3.set_xlabel('Stress (eV/Å³)')
            ax3.set_ylabel('Count')
            ax3.set_title('Stress Distribution')
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, 'No stress data', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Stress Distribution')
        
        # 2. Training and validation MAEs for energy (meV/atom)
        ax4 = axes[1, 0]
        energy_mae_train = [x for x in training_history.get('energy_mae_train', []) if x is not None]
        energy_mae_val = [x for x in training_history.get('energy_mae_val', []) if x is not None]
        if len(energy_mae_train) > 0 or len(energy_mae_val) > 0:
            if len(energy_mae_train) > 0:
                epochs_train = range(1, len(energy_mae_train) + 1)
                # Energy MAE is already in meV/atom from MACE, but may be in eV/atom from others
                train_vals = np.array(energy_mae_train)
                if train_vals.max() < 10.0:  # Likely in eV/atom
                    train_vals = train_vals * 1000  # Convert to meV/atom
                ax4.plot(epochs_train, train_vals, 'b-', label='Train', linewidth=2, marker='o')
            if len(energy_mae_val) > 0:
                epochs_val = range(1, len(energy_mae_val) + 1)
                val_vals = np.array(energy_mae_val)
                if val_vals.max() < 10.0:  # Likely in eV/atom
                    val_vals = val_vals * 1000  # Convert to meV/atom
                ax4.plot(epochs_val, val_vals, 'r-', label='Validation', linewidth=2, marker='s')
            ax4.set_xlabel('Epoch')
            ax4.set_ylabel('Energy MAE (meV/atom)')
            ax4.set_title('Energy MAE')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, 'No energy MAE data', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Energy MAE')
        
        # 3. Training and validation MAEs for forces (meV/Å)
        ax5 = axes[1, 1]
        force_mae_train = [x for x in training_history.get('force_mae_train', []) if x is not None]
        force_mae_val = [x for x in training_history.get('force_mae_val', []) if x is not None]
        if len(force_mae_train) > 0 or len(force_mae_val) > 0:
            if len(force_mae_train) > 0:
                epochs_train = range(1, len(force_mae_train) + 1)
                # Force MAE is already in meV/Å from MACE, but may be in eV/Å from others
                train_vals = np.array(force_mae_train)
                if train_vals.max() < 1.0:  # Likely in eV/Å
                    train_vals = train_vals * 1000  # Convert to meV/Å
                ax5.plot(epochs_train, train_vals, 'b-', label='Train', linewidth=2, marker='o')
            if len(force_mae_val) > 0:
                epochs_val = range(1, len(force_mae_val) + 1)
                val_vals = np.array(force_mae_val)
                if val_vals.max() < 1.0:  # Likely in eV/Å
                    val_vals = val_vals * 1000  # Convert to meV/Å
                ax5.plot(epochs_val, val_vals, 'r-', label='Validation', linewidth=2, marker='s')
            ax5.set_xlabel('Epoch')
            ax5.set_ylabel('Force MAE (meV/Å)')
            ax5.set_title('Force MAE')
            ax5.legend()
            ax5.grid(True, alpha=0.3)
        else:
            ax5.text(0.5, 0.5, 'No force MAE data', ha='center', va='center', transform=ax5.transAxes)
            ax5.set_title('Force MAE')
        
        # 4. Training and validation MAEs for stress (eV/Å³)
        ax6 = axes[1, 2]
        stress_mae_train = [x for x in training_history.get('stress_mae_train', []) if x is not None]
        stress_mae_val = [x for x in training_history.get('stress_mae_val', []) if x is not None]
        if len(stress_mae_train) > 0 or len(stress_mae_val) > 0:
            if len(stress_mae_train) > 0:
                epochs_train = range(1, len(stress_mae_train) + 1)
                ax6.plot(epochs_train, np.array(stress_mae_train), 'b-', label='Train', linewidth=2, marker='o')
            if len(stress_mae_val) > 0:
                epochs_val = range(1, len(stress_mae_val) + 1)
                ax6.plot(epochs_val, np.array(stress_mae_val), 'r-', label='Validation', linewidth=2, marker='s')
            ax6.set_xlabel('Epoch')
            ax6.set_ylabel('Stress MAE (eV/Å³)')
            ax6.set_title('Stress MAE')
            ax6.legend()
            ax6.grid(True, alpha=0.3)
        else:
            ax6.text(0.5, 0.5, 'No stress MAE data', ha='center', va='center', transform=ax6.transAxes)
            ax6.set_title('Stress MAE')
        
        # 5. Loss plot - separate subplot spanning full width
        # ax_loss is already created above
        loss_train = [x for x in training_history.get('loss_train', []) if x is not None]
        loss_val = [x for x in training_history.get('loss_val', []) if x is not None]
        if len(loss_train) > 0 or len(loss_val) > 0:
            if len(loss_train) > 0:
                epochs_train = range(1, len(loss_train) + 1)
                ax_loss.plot(epochs_train, loss_train, 'b-', label='Train', linewidth=2, marker='o')
            if len(loss_val) > 0:
                epochs_val = range(1, len(loss_val) + 1)
                ax_loss.plot(epochs_val, loss_val, 'r-', label='Validation', linewidth=2, marker='s')
            ax_loss.set_xlabel('Epoch', fontsize=12)
            ax_loss.set_ylabel('Loss', fontsize=12)
            ax_loss.set_title('Training Loss', fontsize=14, fontweight='bold')
            ax_loss.legend(fontsize=12)
            ax_loss.grid(True, alpha=0.3)
        else:
            ax_loss.text(0.5, 0.5, 'No loss data', ha='center', va='center', transform=ax_loss.transAxes)
            ax_loss.set_title('Training Loss')
        
        # Use tight_layout with rect to leave space for suptitle and ensuring good spacing
        plt.tight_layout(rect=[0, 0, 1, 0.96], h_pad=3.0, w_pad=2.0)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Training history plot saved to {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
        
        # Also save loss plot separately
        if save_path and (len(loss_train) > 0 or len(loss_val) > 0):
            fig2, ax_loss2 = plt.subplots(1, 1, figsize=(10, 6))
            if len(loss_train) > 0:
                epochs_train = range(1, len(loss_train) + 1)
                ax_loss2.plot(epochs_train, loss_train, 'b-', label='Train', linewidth=2, marker='o')
            if len(loss_val) > 0:
                epochs_val = range(1, len(loss_val) + 1)
                ax_loss2.plot(epochs_val, loss_val, 'r-', label='Validation', linewidth=2, marker='s')
            ax_loss2.set_xlabel('Epoch', fontsize=12)
            ax_loss2.set_ylabel('Loss', fontsize=12)
            ax_loss2.set_title('Training Loss', fontsize=14, fontweight='bold')
            ax_loss2.legend(fontsize=12)
            ax_loss2.grid(True, alpha=0.3)
            plt.tight_layout()
            loss_plot_path = str(Path(save_path).parent / 'training_loss.png')
            plt.savefig(loss_plot_path, dpi=300, bbox_inches='tight')
            logger.info(f"Training loss plot saved to {loss_plot_path}")
            if not show:
                plt.close()
    
    def _collect_label_distributions(self, training_data: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        """
        Collect distributions of energy, force, and stress labels from training data.
        
        This is a shared method used by all MLIP frameworks to ensure consistent
        training history plots. It extracts energy (per-atom), force, and stress
        values from the training data.
        
        Args:
            training_data: List of training samples, each containing:
                - 'structure': ASE Atoms or pymatgen Structure
                - 'energy': Total energy (eV)
                - 'forces': Forces array (eV/Å)
                - 'stress': Stress tensor (eV/Å³)
        
        Returns:
            Dictionary with keys:
                - 'energy_distribution': List of per-atom energies (eV/atom)
                - 'force_distribution': List of all force components (eV/Å)
                - 'stress_distribution': List of all stress components (eV/Å³)
        """
        import numpy as np
        from ase import Atoms
        from pymatgen.core import Structure
        
        energies = []
        forces = []
        stresses = []
        
        for data in training_data:
            # Extract structure to get number of atoms
            structure = data.get('structure')
            if structure is None:
                continue
            
            # Convert to ASE Atoms if needed
            if isinstance(structure, dict):
                # Try to convert from dict representation
                if '@module' in structure and '@class' in structure:
                    # pymatgen Structure dict
                    from pymatgen.core import Structure as PymatgenStructure
                    from pymatgen.io.ase import AseAtomsAdaptor
                    struct = PymatgenStructure.from_dict(structure)
                    atoms = AseAtomsAdaptor.get_atoms(struct)
                else:
                    # Assume it's already an ASE Atoms dict or skip
                    continue
            elif isinstance(structure, Structure):
                from pymatgen.io.ase import AseAtomsAdaptor
                atoms = AseAtomsAdaptor.get_atoms(structure)
            elif isinstance(structure, Atoms):
                atoms = structure
            else:
                continue
            
            num_atoms = len(atoms)
            
            # Extract energy and convert to per-atom
            if 'energy' in data and data['energy'] is not None:
                energy = float(data['energy'])
                energy_per_atom = energy / num_atoms if num_atoms > 0 else energy
                energies.append(energy_per_atom)
            
            # Extract forces and flatten
            if 'forces' in data and data['forces'] is not None:
                forces_array = np.array(data['forces'])
                if forces_array.size > 0:
                    forces.extend(forces_array.flatten().tolist())
            
            # Extract stress and flatten
            if 'stress' in data and data['stress'] is not None:
                stress_array = np.array(data['stress'])
                if stress_array.size > 0:
                    # we standardize to eV/Å³ (ASE standard)
                    stress_flat = stress_array.flatten()
                    stresses.extend(stress_flat.tolist())
        
        return {
            'energy_distribution': energies,
            'force_distribution': forces,
            'stress_distribution': stresses
        }

    def save_training_history(self, save_path: str) -> None:
        """
        Save the training history to a JSON file.
        
        Args:
            save_path: Path where to save the JSON file.
        """
        training_history = getattr(self, '_training_history', None)
        if training_history is None:
            logger.warning("No training history available to save.")
            return

        # Prepare for JSON serializing (convert numpy arrays to lists)
        serializable_history = {}
        for key, value in training_history.items():
            if isinstance(value, np.ndarray):
                serializable_history[key] = value.tolist()
            elif isinstance(value, list):
                processed_list = []
                for item in value:
                    if isinstance(item, np.ndarray):
                        processed_list.append(item.tolist())
                    elif hasattr(item, 'item'): # Handle torch scalars or numpy scalars
                        processed_list.append(item.item())
                    else:
                        processed_list.append(item)
                serializable_history[key] = processed_list
            else:
                if hasattr(value, 'item'):
                    serializable_history[key] = value.item()
                else:
                    serializable_history[key] = value

        try:
            with open(save_path, 'w') as f:
                json.dump(serializable_history, f, indent=4)
            logger.info(f"Training history saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save training history to {save_path}: {e}")
