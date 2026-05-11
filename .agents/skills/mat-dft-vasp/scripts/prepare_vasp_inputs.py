"""
Prepare VASP input files (POSCAR, INCAR, KPOINTS, POTCAR).

Usage:
    python prepare_vasp_inputs.py input.cif output_dir --calculation_type relaxation --preset_type omat

Requirements:
    - Conda environment: base-agent
    - Required packages: ase, pymatgen
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.structure_utils import load_structure_from_file
from src.utils.dft.vasp_writer import write_vasp_input_files
from ase import Atoms

def main():
    parser = argparse.ArgumentParser(description="Prepare VASP input files.")
    parser.add_argument("structure_path", help="Path to structure file or directory.")
    parser.add_argument("output_dir", help="Output directory for VASP files.")
    parser.add_argument("--calculation_type", default="relaxation", choices=["relaxation", "static", "md"], help="Type of calculation")
    parser.add_argument("--preset_type", default="omat", choices=["omat", "mp", "matpes-pbe", "matpes-r2scan"], help="VASP preset type")
    parser.add_argument("--config", default="{}", help="Custom INCAR tags to override preset as JSON string")
    
    args = parser.parse_args()
    
    input_path = Path(args.structure_path)
    out_path = Path(args.output_dir)
    config = json.loads(args.config)
    
    if input_path.is_dir():
        structure_files = list(input_path.rglob("*.cif")) + \
                          list(input_path.rglob("*.xyz")) + \
                          list(input_path.rglob("POSCAR"))
        
        if not structure_files:
            print(f"Error: No structure files found in directory {args.structure_path}")
            sys.exit(1)
            
        summary = []
        for i, struct_file in enumerate(sorted(structure_files)):
            # Create subdirectory for each structure
            sub_name = struct_file.stem
            if sub_name == "POSCAR":
                sub_name = struct_file.parent.name
                
            sub_dir = out_path / sub_name
            sub_dir.mkdir(parents=True, exist_ok=True)
            
            structure_loaded = load_structure_from_file(str(struct_file))
            if structure_loaded:
                from pymatgen.io.ase import AseAtomsAdaptor
                if not isinstance(structure_loaded, Atoms):
                    structure_loaded = AseAtomsAdaptor.get_atoms(structure_loaded)
                write_vasp_input_files(
                    atoms=structure_loaded,
                    output_dir=str(sub_dir),
                    preset_type=args.preset_type,
                    calculation_type=args.calculation_type,
                    config=config
                )
                summary.append(sub_name)
                
        print(f"Successfully prepared VASP inputs for {len(summary)} structures in {args.output_dir}.")
    else:
        # Single file processing
        structure_loaded = load_structure_from_file(args.structure_path)
        if structure_loaded is None:
            print(f"Error: Could not load structure from {args.structure_path}")
            sys.exit(1)
            
        from pymatgen.io.ase import AseAtomsAdaptor
        if not isinstance(structure_loaded, Atoms):
            structure_loaded = AseAtomsAdaptor.get_atoms(structure_loaded)
        
        # Write files
        files = write_vasp_input_files(
            atoms=structure_loaded,
            output_dir=args.output_dir,
            preset_type=args.preset_type,
            calculation_type=args.calculation_type,
            config=config
        )
        
        print(f"Successfully wrote VASP input files to {args.output_dir}. Files saved: {list(files.keys())}")

if __name__ == "__main__":
    main()
