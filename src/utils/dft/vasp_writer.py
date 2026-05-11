"""
VASP input file writer using pymatgen for MLIP Agent
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from ase import Atoms

logger = logging.getLogger(__name__)

try:
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.io.vasp.sets import MPStaticSet, MatPESStaticSet, MPRelaxSet
    PYMATGEN_AVAILABLE = True
except ImportError:
    PYMATGEN_AVAILABLE = False
    logger.warning("pymatgen not available. VASP functions will fail.")

PRESETS = {
    "omat": MPStaticSet,
    "mp": MPStaticSet,
    "matpes-pbe": MatPESStaticSet,
    "matpes-r2scan": MatPESStaticSet,
}


def write_vasp_input_files(
    atoms: Atoms,
    output_dir: str,
    preset_type: str = "omat",
    calculation_type: str = "static",
    config: Optional[Dict[str, Any]] = None,
    custom_settings: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Write VASP input files (POSCAR, INCAR, KPOINTS, POTCAR) for structure labeling.
    
    Args:
        atoms: ASE Atoms object
        output_dir: Output directory for VASP files
        preset_type: Preset type ("omat", "mp", "matpes-pbe", "matpes-r2scan")
        calculation_type: Type of calculation ("static", "relaxation")
        config: Persistent config for the writer
        custom_settings: Custom overrides for this specific call
    """
    if not PYMATGEN_AVAILABLE:
        raise ImportError("pymatgen is required for writing VASP entries.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Base INCAR settings
    incar_params = {"LCHARG": False, "LREAL": "Auto"}
    
    if calculation_type == "static":
        incar_params.update({"IBRION": -1, "NSW": 0})
    elif calculation_type == "relaxation":
        # Standard structural relaxation convergence
        incar_params.update({
            "EDIFF": 1e-5,
            "EDIFFG": -0.02,
            "IBRION": 2,
            "NSW": 200,
            "ISIF": 3,
            "POTIM": 0.5
        })
    else:
        raise NotImplementedError(f"Calculation type '{calculation_type}' is not supported.")
    
    preset_key = preset_type.lower()
    if preset_key not in PRESETS:
        logger.warning(f"Unknown preset_type '{preset_key}'. Defaulting to 'omat'.")
        preset_key = "omat"

    # Preset-specific ALGO defaults
    if preset_key == "omat":
        incar_params["ALGO"] = "Normal"
    elif preset_key == "mp":
        incar_params["ALGO"] = "Fast"

    # Merge configurations: base < config < custom_settings
    if config:
        incar_params.update(config)
    if custom_settings:
        incar_params.update(custom_settings)
        
    # Select VaspInputSet
    set_class = PRESETS.get(preset_key, MPStaticSet)
    
    set_kwargs = {}
    if preset_key == "matpes-r2scan":
        set_kwargs["xc_functional"] = "R2SCAN"
    elif preset_key == "matpes-pbe":
        set_kwargs["xc_functional"] = "PBE"
        
    pmg_structure = AseAtomsAdaptor.get_structure(atoms)
    vis = set_class(pmg_structure, user_incar_settings=incar_params, **set_kwargs)
    vis.write_input(str(output_path))
    
    files = {f: str(output_path / f.upper()) for f in ['poscar', 'incar', 'kpoints', 'potcar']}
    
    # Optional custom submit script
    if 'submit_script' in incar_params:
         submit_path = output_path / "submit.sh"
         with open(submit_path, 'w') as f:
             f.write(incar_params['submit_script'])
         files['submit'] = str(submit_path)
    
    logger.info(f"VASP inputs generated in {output_path} using {set_class.__name__} ({preset_key})")
    return files
