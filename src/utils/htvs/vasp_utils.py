"""
VASP Input Generation and Conversion Utilities.

This module provides utilities for generating VASP inputs and converting
VASP parameters to HTVS details format.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import pymatgen
try:
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.io.vasp.sets import MPStaticSet, MatPESStaticSet, MPRelaxSet
    PYMATGEN_AVAILABLE = True
except ImportError:
    PYMATGEN_AVAILABLE = False


class HTVSVaspHandler:
    """
    Handler for generating VASP inputs and converting to HTVS details format.
    
    Centralizes VASP parameter generation, Pymatgen preset handling, and
    VASP→HTVS format conversion for consistency across HTVS utilities.
    
    Example:
        >>> handler = HTVSVaspHandler()
        >>> details = handler.convert_to_details({"ENCUT": 500, "ISPIN": 2})
    """
    
    # VASP INCAR tags to HTVS details key mapping
    VASP_TO_HTVS_MAPPING = {
        "ENCUT": "encut",
        "ISMEAR": "ismear",
        "SIGMA": "sigma",
        "ISPIN": "ispin",
        "LORBIT": "lorbit",
        "LREAL": "lreal",
        "NSW": "nsteps",
        "IBRION": "ibrion",
        "ISIF": "isif",
        "EDIFF": "ediff",
        "EDIFFG": "ediffg",
        "POTIM": "timestep",
        "TEBEG": "temperature",
        "ALGO": "algo",
        "PREC": "prec",
        "KPOINT_DENSITY": "kppa",
        "KPOINTS": "kpoints",
    }
    
    # Pymatgen preset mappings
    PRESETS = {
        "omat": MPStaticSet if PYMATGEN_AVAILABLE else None,
        "mp": MPStaticSet if PYMATGEN_AVAILABLE else None,
        "matpes-pbe": MatPESStaticSet if PYMATGEN_AVAILABLE else None,
        "matpes-r2scan": MatPESStaticSet if PYMATGEN_AVAILABLE else None,
    }
    
    def __init__(self):
        """Initialize with HTVS VASP configuration."""
        self.vasp_mapping = self.VASP_TO_HTVS_MAPPING
        self.presets = self.PRESETS
        self.pymatgen_available = PYMATGEN_AVAILABLE
    
    def _map_to_htvs(self, vasp_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert VASP tags to HTVS keys (centralized mapping).
        
        Args:
            vasp_params: Dictionary of VASP INCAR tags
            
        Returns:
            Dictionary with HTVS-formatted keys
        """
        return {
            self.vasp_mapping.get(tag, tag.lower()): value
            for tag, value in vasp_params.items()
        }
    
    def generate_inputs(
        self,
        atoms: Any,  # ASE Atoms object
        preset_type: str = "omat",
        calculation_type: str = "static",
        config: Optional[Dict[str, Any]] = None,
        custom_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate VASP input settings (INCAR parameters) from structure.
        
        Args:
            atoms: ASE Atoms object
            preset_type: Preset type ('omat', 'mp', 'matpes-pbe', 'matpes-r2scan')
            calculation_type: 'static' or 'relaxation'
            config: Base configuration dict to merge
            custom_settings: Custom settings to override defaults
        
        Returns:
            Dictionary of VASP INCAR parameters
        """
        if not self.pymatgen_available:
            logger.warning("pymatgen not available, cannot generate VASP inputs from structure.")
            return {}
        
        # Base INCAR settings
        incar_params = {"LCHARG": False, "LREAL": "Auto"}
        
        if calculation_type == "static":
            incar_params.update({"IBRION": -1, "NSW": 0})
        elif calculation_type == "relaxation":
            incar_params.update({
                "EDIFF": 1e-4,
                "EDIFFG": -0.02,
                "IBRION": 2,
                "NSW": 200,
                "ISIF": 2,  # Safer default for HTVS (prevents vacuum collapse in slabs)
                "POTIM": 0.5
            })
        
        preset_key = preset_type.lower()
        if preset_key not in self.presets:
            logger.warning(f"Unknown preset_type '{preset_key}'. Defaulting to 'omat'.")
            preset_key = "omat"
        
        # Preset-specific ALGO defaults
        if preset_key == "omat":
            incar_params["ALGO"] = "Normal"
        elif preset_key == "mp":
            incar_params["ALGO"] = "Fast"
        
        # Merge configurations
        if config:
            incar_params.update(config)
        if custom_settings:
            incar_params.update(custom_settings)
        
        return incar_params
    
    def convert_to_details(
        self,
        vasp_input: Optional[Dict[str, Any]] = None,
        additional_details: Optional[Dict[str, Any]] = None,
        structure_file: Optional[str] = None,
        preset_type: str = "omat",
        calculation_type: str = "static",
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convert VASP input parameters to HTVS 'details' dictionary.
        
        Can optionally generate VASP inputs from a structure file.
        
        Args:
            vasp_input: Dictionary of VASP INCAR tags
            additional_details: Additional HTVS-specific details
            structure_file: Optional path to structure file for generation
            preset_type: Preset for structure-based generation
            calculation_type: Calculation type for structure-based generation
            config: Base config for structure-based generation
        
        Returns:
            Dictionary in HTVS details format
        """
        details = {}
        
        # Generate VASP inputs from structure if provided
        if structure_file:
            if self.pymatgen_available:
                try:
                    from ase.io import read
                    atoms = read(structure_file)
                    generated_vasp_input = self.generate_inputs(
                        atoms=atoms,
                        preset_type=preset_type,
                        calculation_type=calculation_type,
                        config=config
                    )
                    # Merge: structure-generated < explicit vasp_input
                    if vasp_input:
                        generated_vasp_input.update(vasp_input)
                    vasp_input = generated_vasp_input
                except Exception as e:
                    logger.error(f"Failed to generate VASP inputs from structure: {e}")
            else:
                logger.warning("Pymatgen not available, skipping structure-based VASP generation.")
        
        if not vasp_input:
            vasp_input = {}
        
        # Map VASP tags to HTVS keys using centralized method
        details = self._map_to_htvs(vasp_input)
        
        # Merge additional details
        if additional_details:
            details.update(additional_details)
        
        return details
    
    def generate_details(
        self,
        structure_file: str,
        preset_type: str = "mp",
        calculation_type: str = "static",
        custom_settings: Optional[Dict[str, Any]] = None,
        magnetism: bool = True,
        magnetism_scheme: str = "fm",
    ) -> str:
        """
        Generate VASP details dictionary (INCAR parameters) using Pymatgen presets.
        
        This method provides a comprehensive way to generate HTVS-compatible
        DFT calculation parameters from a structure file using Pymatgen's preset
        input sets. It returns a JSON string for easy consumption by HTVS tools.
        
        Args:
            structure_file: Path to the structure file (readable by ASE/Pymatgen)
            preset_type: Pymatgen preset to use ("mp", "omat", "matpes-pbe", "matpes-r2scan")
            calculation_type: "static" or "relaxation"
            custom_settings: Dictionary of custom settings to override defaults
            magnetism: Whether to apply default magnetic moments
            magnetism_scheme: "fm" (ferromagnetic), "afm" (antiferromagnetic), or "nm" (non-magnetic)
        
        Returns:
            JSON string of the 'details' dictionary ready for HTVS submission
        """
        import json
        import os
        
        if not self.pymatgen_available:
            return json.dumps({"error": "Pymatgen not installed/available in this environment."})
        
        if not os.path.exists(structure_file):
            return json.dumps({"error": f"Structure file not found: {structure_file}"})
        
        try:
            from ase import io
            from pymatgen.io.ase import AseAtomsAdaptor
            from pymatgen.io.vasp.sets import MPStaticSet, MatPESStaticSet, MPRelaxSet
            
            # Load structure
            atoms = io.read(structure_file)
            pmg_structure = AseAtomsAdaptor.get_structure(atoms)
            
            # Select Preset
            presets = {
                "omat": MPStaticSet,
                "mp": MPStaticSet,
                "matpes-pbe": MatPESStaticSet,
                "matpes-r2scan": MatPESStaticSet,
            }
            
            set_class = presets.get(preset_type, MPStaticSet)
            
            # Handle Relaxation Logic
            use_mp_relax = (calculation_type == "relaxation" and "matpes" not in preset_type)
            if use_mp_relax:
                set_class = MPRelaxSet
                
            set_kwargs = {}
            if preset_type == "matpes-r2scan":
                set_kwargs["xc_functional"] = "R2SCAN"
            elif preset_type == "matpes-pbe":
                set_kwargs["xc_functional"] = "PBE"
                
            # Inject custom settings into Pymatgen so it automatically handles element-wise tags (like LDAUU for Fe, O, H)
            if custom_settings:
                set_kwargs["user_incar_settings"] = custom_settings
                
            # Generate Input
            vis = set_class(pmg_structure, **set_kwargs)
            
            # Map to HTVS Details using centralized method
            job_details = self._map_to_htvs(dict(vis.incar.items()))
                
            # 2. KPOINTS/KPPA
            if hasattr(vis, 'kppa') and vis.kppa:
                job_details['kppa'] = vis.kppa
            elif hasattr(vis, 'kpoints') and vis.kpoints:
                pass  # Explicit kpoints grid - let HTVS handle it
            
            if 'kppa' not in job_details and 'kpoints_density' not in job_details:
                job_details['kpoints_density'] = 3000

            # 3. Magnetism
            if magnetism and magnetism_scheme != "nm":
                # Basic magnetic moment mapping
                mag_map = {
                    "Cr": 5.0, "Mn": 5.0, "Fe": 4.0, "Co": 1.6, "Ni": 0.6,
                    "V": 3.0, "Ti": 2.0, "Cu": 0.6, "Mo": 4.0, "W": 4.0
                }
                
                symbols = atoms.get_chemical_symbols()
                magmoms = []
                
                for i, s in enumerate(symbols):
                    base_moment = mag_map.get(s, 0.0)
                    if magnetism_scheme == "afm" and i % 2 == 1:
                        magmoms.append(-base_moment)
                    else:
                        magmoms.append(base_moment)
                
                if any(abs(m) > 0 for m in magmoms):
                    job_details["magmom"] = magmoms
                    job_details["ispin"] = 2
                else:
                    job_details["ispin"] = 1
            else:
                job_details["ispin"] = 1

            # 4. MatPES Relaxation Overrides (Applied as defaults)
            if calculation_type == "relaxation" and "matpes" in preset_type:
                job_details["nsteps"] = 200
                job_details["ibrion"] = 2
                job_details["isif"] = 2

            return json.dumps(job_details, indent=2)

        except Exception as e:
            import traceback
            return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

    def validate_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that the details dictionary contains all mandatory HTVS/VASP fields.
        
        Args:
            details: Dictionary of HTVS parameters
            
        Returns:
            Dictionary with 'valid' boolean and list of 'errors'
        """
        mandatory_fields = ["encut", "ismear", "sigma", "kppa"]
        errors = []
        
        for field in mandatory_fields:
            if field not in details and f"{field}s" not in details: # handles kpoints vs kppa
                if field == "kppa" and "kpoints" in details:
                    continue
                errors.append(f"Missing mandatory field: {field}")
        
        # Check for consistency
        if details.get("ispin") == 2 and "magmom" not in details:
            errors.append("ISPIN=2 requested but no MAGMOM provided.")
            
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
