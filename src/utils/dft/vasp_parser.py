"""
VASP output parser using pymatgen for MLIP Agent
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import numpy as np
import json
import h5py
from ase import Atoms

logger = logging.getLogger(__name__)

# Pymatgen imports - soft dependency check if needed, but assuming available in relevant env
try:
    from pymatgen.io.vasp import Vasprun, Outcar
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor
    PYMATGEN_AVAILABLE = True
except ImportError:
    PYMATGEN_AVAILABLE = False
    logger.warning("pymatgen not available. VASPParser will fail if initialized.")


class VASPParser:
    """
    VASP output parser using pymatgen for extracting DFT results.
    """
    
    def __init__(self, output_dir: str):
        """
        Initialize VASP parser.
        
        Args:
            output_dir: Directory containing VASP output files
        """
        self.output_dir = Path(output_dir)
        self.vasprun_path = self.output_dir / "vasprun.xml"
        self.outcar_path = self.output_dir / "OUTCAR"
        
    
    def parse_vasprun(self) -> Dict[str, Any]:
        """
        Parse vasprun.xml file using pymatgen.
        
        Returns:
            Dictionary containing parsed VASP results.
        """
        if not self.vasprun_path.exists():
            raise FileNotFoundError(f"vasprun.xml not found in {self.output_dir}")
        
        # Use pymatgen's Vasprun class
        vasprun = Vasprun(str(self.vasprun_path))
        
        # Extract basic information
        results = {
            'final_structure': vasprun.final_structure,
            'final_energy': vasprun.final_energy,
            'is_completed': vasprun.converged_electronic,
            'is_ionic_converged': vasprun.converged_ionic,
            'calculation_type': self._get_calculation_type(vasprun),
            'incar': dict(vasprun.incar),
            'kpoints': vasprun.kpoints,
            'potcar': vasprun.potcar,
        }
        
        # Extract forces if available
        if hasattr(vasprun, 'forces') and vasprun.forces is not None:
            results['forces'] = vasprun.forces[-1]  # Final forces
        else:
            results['forces'] = None
        
        # Extract stress if available
        if hasattr(vasprun, 'stress') and vasprun.stress is not None:
            # VASP stress is in kB. Convert to eV/A^3 (ASE standard).
            # 1 kB = 0.1 GPa. 1 GPa = ase.units.GPa eV/A^3.
            import ase.units
            results['stress'] = (np.array(vasprun.stress[-1]) * 0.1 * ase.units.GPa).tolist()
        else:
            results['stress'] = None
        
        # Extract ionic steps if available
        if hasattr(vasprun, 'ionic_steps'):
            results['ionic_steps'] = len(vasprun.ionic_steps)
            results['energy_history'] = [step['e_wo_entrp'] for step in vasprun.ionic_steps]
        else:
            results['ionic_steps'] = 0
            results['energy_history'] = []
        
        # Extract electronic convergence
        if hasattr(vasprun, 'electronic_steps'):
            results['electronic_steps'] = len(vasprun.electronic_steps)
        else:
            results['electronic_steps'] = 0
        
        logger.info(f"Successfully parsed vasprun.xml: {results['final_energy']:.6f} eV")
        return results
    
    def parse_outcar(self) -> Dict[str, Any]:
        """
        Parse OUTCAR file using pymatgen for additional information.
        
        Returns:
            Dictionary containing OUTCAR results.
        """
        if not self.outcar_path.exists():
            logger.warning(f"OUTCAR not found in {self.output_dir}")
            return {}
        
        # Use pymatgen's Outcar class
        outcar = Outcar(str(self.outcar_path))
        
        results = {
            'magnetization': outcar.magnetization,
            'total_magnetization': outcar.total_magnetization,
            'run_stats': outcar.run_stats,
            'elastic_modulus': outcar.elastic_modulus,
            'piezoelectric_tensor': outcar.piezoelectric_tensor,
            'born_charges': outcar.born_charges,
        }
        
        # Extract forces from OUTCAR if not available in vasprun
        if hasattr(outcar, 'forces') and outcar.forces:
            results['forces'] = outcar.forces[-1]
        
        # Extract stress from OUTCAR if not available in vasprun
        if hasattr(outcar, 'stress') and outcar.stress:
            results['stress'] = outcar.stress[-1]
        
        logger.info("Successfully parsed OUTCAR")
        return results
    

    
    def parse_all(self) -> List[Dict[str, Any]]:
        """
        Parse all available VASP results.
        
        Returns:
            List of dictionaries containing parsed results (one per structure directory).
        """
        all_results = []
        
        # Check if this is a directory with multiple structure subdirectories
        structure_dirs = [d for d in self.output_dir.iterdir() if d.is_dir() and d.name.startswith('structure_')]
        
        if structure_dirs:
            # Multiple structures - parse each one
            for struct_dir in sorted(structure_dirs):
                parser = VASPParser(str(struct_dir))
                try:
                    # Parse VASP format
                    if (struct_dir / "vasprun.xml").exists():
                        result = parser.parse_vasprun()
                        outcar_result = parser.parse_outcar()
                        result.update(outcar_result)
                    else:
                        logger.warning(f"No VASP results found in {struct_dir}")
                        continue
                    
                    result['structure_id'] = struct_dir.name
                    all_results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to parse {struct_dir}: {e}")
                    continue
        else:
            # Single structure directory - parse it
            try:
                # Parse VASP format
                if self.vasprun_path.exists():
                    result = self.parse_vasprun()
                    outcar_result = self.parse_outcar()
                    result.update(outcar_result)
                else:
                    raise FileNotFoundError(f"No VASP result files found in {self.output_dir}")
                
                all_results.append(result)
            except Exception as e:
                logger.error(f"Failed to parse {self.output_dir}: {e}")
                raise
        
        logger.info(f"Parsed {len(all_results)} structure results")
        return all_results
    
    def convert_to_matgl_format(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert VASP or UMA results to MatGL training format.
        
        Args:
            results: Parsed VASP or UMA results (single structure)
        
        Returns:
            List of training data in MatGL format (typically one entry per structure).
        """
        training_data = []
        
        # Convert pymatgen Structure to ASE Atoms
        structure = results.get('final_structure')
        if structure is None:
            logger.error("No structure found in results")
            return []
        
        # Convert to ASE Atoms
        atoms = AseAtomsAdaptor.get_atoms(structure)
        
        # Convert forces and stress to numpy arrays if they're lists
        forces = results.get('forces')
        if forces is not None:
            if isinstance(forces, list):
                forces = np.array(forces)
            elif not isinstance(forces, np.ndarray):
                forces = np.array(forces)
        
        stress = results.get('stress')
        if stress is not None:
            if isinstance(stress, list):
                stress = np.array(stress)
            elif not isinstance(stress, np.ndarray):
                stress = np.array(stress)
        
        # Create training data entry
        data_entry = {
            'structure': atoms,
            'energy': float(results.get('final_energy', 0.0)),
            'forces': forces,
            'stress': stress,
            'metadata': {
                'calculation_type': results.get('calculation_type', 'unknown'),
                'is_converged': results.get('is_completed', False),
                'ionic_steps': results.get('ionic_steps', 0),
                'electronic_steps': results.get('electronic_steps', 0),
                'source': results.get('source', 'vasp'),
                'structure_id': results.get('structure_id', 'unknown')
            }
        }
        
        training_data.append(data_entry)
        
        # Add intermediate steps if available (only for VASP with history)
        if 'energy_history' in results and len(results['energy_history']) > 1:
            # Add intermediate structures (simplified)
            for i, energy in enumerate(results['energy_history'][:-1]):
                intermediate_data = {
                    'structure': atoms,  # Simplified - would need actual intermediate structures
                    'energy': float(energy),
                    'forces': None,
                    'stress': None,
                    'metadata': {
                        'calculation_type': 'intermediate',
                        'step': i,
                        'is_converged': False,
                        'source': results.get('source', 'vasp')
                    }
                }
                training_data.append(intermediate_data)
        
        logger.info(f"Converted 1 structure to MatGL format (energy: {data_entry['energy']:.6f} eV)")
        return training_data
    
    def save_results(self, results: Dict[str, Any], output_path: str, format: str = 'json') -> None:
        """
        Save parsed results to file.
        
        Args:
            results: Parsed results dictionary
            output_path: Output file path
            format: Output format ('json' or 'hdf5')
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == 'json':
            # Convert numpy arrays to lists for JSON serialization
            json_results = self._prepare_for_json(results)
            
            with open(output_path, 'w') as f:
                json.dump(json_results, f, indent=2, default=str)
            
            logger.info(f"Results saved to {output_path}")
            
        elif format.lower() == 'hdf5':
            with h5py.File(output_path, 'w') as f:
                self._save_to_hdf5(f, results)
            
            logger.info(f"Results saved to {output_path}")
            
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _get_calculation_type(self, vasprun) -> str:
        """
        Determine the type of VASP calculation.
        
        Args:
            vasprun: Pymatgen Vasprun object
        
        Returns:
            Calculation type string.
        """
        incar = vasprun.incar
        
        if incar.get('IBRION', 0) == -1:
            return 'static'
        elif incar.get('IBRION', 0) == 0:
            return 'md'
        elif incar.get('IBRION', 0) in [1, 2, 3]:
            return 'relaxation'
        else:
            return 'unknown'
    
    def _prepare_for_json(self, data: Any) -> Any:
        """
        Prepare data for JSON serialization.
        
        Args:
            data: Data to prepare
        
        Returns:
            JSON-serializable data.
        """
        if isinstance(data, dict):
            return {key: self._prepare_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._prepare_for_json(item) for item in data]
        elif isinstance(data, np.ndarray):
            return data.tolist()
        elif isinstance(data, (np.integer, np.floating)):
            return data.item()
        elif hasattr(data, 'as_dict'):
            return data.as_dict()
        else:
            return data
    
    def _save_to_hdf5(self, f: h5py.File, results: Dict[str, Any]) -> None:
        """
        Save results to HDF5 file.
        
        Args:
            f: HDF5 file object
            results: Results dictionary.
        """
        # Save basic information
        f.attrs['final_energy'] = results.get('final_energy', 0.0)
        f.attrs['is_completed'] = results.get('is_completed', False)
        f.attrs['calculation_type'] = results.get('calculation_type', 'unknown')
        
        # Save structure information
        structure = results.get('final_structure')
        if structure is not None:
            # Save lattice parameters
            lattice = structure.lattice
            f.create_dataset('lattice_a', data=lattice.a)
            f.create_dataset('lattice_b', data=lattice.b)
            f.create_dataset('lattice_c', data=lattice.c)
            f.create_dataset('lattice_alpha', data=lattice.alpha)
            f.create_dataset('lattice_beta', data=lattice.beta)
            f.create_dataset('lattice_gamma', data=lattice.gamma)
            
            # Save atomic positions and species
            f.create_dataset('positions', data=structure.cart_coords)
            f.create_dataset('atomic_numbers', data=[site.specie.Z for site in structure])
        
        # Save forces if available
        forces = results.get('forces')
        if forces is not None:
            f.create_dataset('forces', data=forces)
        
        # Save stress if available
        stress = results.get('stress')
        if stress is not None:
            f.create_dataset('stress', data=stress)
        
        # Save energy history if available
        energy_history = results.get('energy_history', [])
        if energy_history:
            f.create_dataset('energy_history', data=energy_history)
    
    def validate_results(self, results: Dict[str, Any]) -> bool:
        """
        Validate parsed VASP results.
        
        Args:
            results: Parsed results dictionary
        
        Returns:
            True if results are valid, False otherwise.
        """
        # Check required fields
        required_fields = ['final_structure', 'final_energy']
        for field in required_fields:
            if field not in results:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Check energy is reasonable
        energy = results.get('final_energy', 0.0)
        if abs(energy) > 1e6:  # Unreasonably large energy
            logger.warning(f"Suspicious energy value: {energy}")
            return False
        
        # Check structure is valid
        structure = results.get('final_structure')
        if structure is None or len(structure) == 0:
            logger.error("Invalid structure")
            return False
        
        logger.info("VASP results validation passed")
        return True
