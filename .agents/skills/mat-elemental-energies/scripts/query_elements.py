"""
Query Materials Project for the most stable phase of each element.

Usage:
    python query_elements.py --elements H Li Fe O Si --output_dir ../resources/structures

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, mp_api
"""

import argparse
import os
import logging
from mp_api.client import MPRester
from pymatgen.io.cif import CifWriter
from pymatgen.core import Element

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def query_element_structure(element: str, api_key: str = None) -> str:
    """
    Query MP for the ground state structure of an element.
    Returns the pymatgen Structure object.
    """
    try:
        with MPRester(api_key=api_key) as mpr:
            docs = mpr.materials.summary.search(
                formula=element,
                is_stable=True,
                fields=["material_id", "structure", "energy_above_hull"]
            )
            
            if not docs:
                logger.warning(f"No stable phase found for element {element} in Materials Project summary.")
                # Try searching without is_stable=True and pick lowest E_hull
                docs = mpr.materials.summary.search(
                    formula=element,
                    fields=["material_id", "structure", "energy_above_hull"]
                )
                if not docs:
                    return None
                
            # Sort by energy_above_hull and pick the best one
            docs.sort(key=lambda x: x.energy_above_hull if x.energy_above_hull is not None else 1e9)
            best_doc = docs[0]
            
            logger.info(f"Selected phase for {element}: {best_doc.material_id} (E_hull={best_doc.energy_above_hull})")
            return best_doc.structure
    except Exception as e:
        logger.error(f"Error querying {element}: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Query ground state element structures from Materials Project.")
    parser.add_argument("--elements", nargs="+", help="List of elements to query (e.g., Li Fe O). If empty, queries all elements H-Lr.")
    parser.add_argument("--output_dir", default="../resources/structures", help="Directory to save CIF files")
    args = parser.parse_args()

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(_json.dumps(_config, indent=2, default=str))

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    elements = args.elements
    if not elements:
        # Generate all elements from H (1) to Lr (103)
        elements = [Element.from_Z(z).symbol for z in range(1, 104)]

    for element in elements:
        output_path = os.path.join(args.output_dir, f"{element}.cif")
        if os.path.exists(output_path):
            logger.info(f"Structure for {element} already exists at {output_path}. Skipping.")
            continue

        logger.info(f"Querying element: {element}")
        structure = query_element_structure(element)
        if structure:
            CifWriter(structure).write_file(output_path)
            logger.info(f"Saved {element} structure to {output_path}")
        else:
            logger.warning(f"Could not retrieve structure for {element}")


if __name__ == "__main__":
    main()
