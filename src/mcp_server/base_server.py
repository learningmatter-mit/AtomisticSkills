import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.mcp_utils import setup_mcp_stdout, run_fastmcp_server

# Setup stdout redirection for MCP
mcp_pipe_binary = setup_mcp_stdout()

import logging
import warnings
import json
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional, List
from pathlib import Path

# Suppress all warnings to prevent protocol pollution
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

# Silence common blabbermouth libraries
logging.getLogger("mp-api").setLevel(logging.ERROR)
logging.getLogger("pymatgen").setLevel(logging.ERROR)

from src.utils.dft.vasp_writer import write_vasp_input_files
from src.utils.dft.vasp_parser import VASPParser
from src.utils.structure_utils import (
    load_structure_from_file, 
    get_structure_by_formula, 
    get_structure_by_chemsys,
    save_structure
)

from src.utils.research_utils import create_new_research_dir

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BaseServer")

# Create MCP server
mcp = FastMCP("base_tools")

# Import literature utils
from src.utils.literature_utils import query_openalex, reconstruct_abstract
import subprocess
import json

@mcp.tool()
def create_research_dir(research_topic: str) -> str:
    """Create research directory and set as active for MCP tools.
    
    Args:
        research_topic: Short description (e.g. "LiFePO4_stability"), prefixed with date.
        
    Returns:
        Path to the newly created directory.
    """
    try:
        new_dir = create_new_research_dir(research_topic)
        return f"Successfully created and set research directory: {new_dir}"
    except Exception as e:
        return f"Error creating research directory: {str(e)}"

@mcp.tool()
def search_materials_project_by_formula(

    formula: str,
    api_key: Optional[str] = None,
    save_to_file: Optional[str] = None,
    return_all: bool = False
) -> str:
    """Search Materials Project by formula. Supports wildcards.
    
    Args:
        formula: Chemical formula (e.g., "Si", "Fe2O3", "Si*").
        api_key: Optional MP API key (defaults to environment).
        save_to_file: Optional save path (or directory if return_all=True).
        return_all: If True, returns all matching structures instead of just the ground state.
        
    Returns:
        Path to saved CIF file(s).
    """
    mp_key = api_key or os.getenv("MP_API_KEY")
    if not mp_key:
        return "Error: Materials Project API key not found. Please provide api_key or set MP_API_KEY environment variable."
        
    try:
        from mp_api.client import MPRester
        with MPRester(mp_key) as mprester:
            result = get_structure_by_formula(formula, mprester, return_all=return_all)
                
        if result is None or (isinstance(result, list) and len(result) == 0):
            return f"Error: No structure found for formula {formula} in Materials Project."
            
        if return_all:
            # Result is a list of atoms
            if save_to_file:
                save_dir = Path(save_to_file)
            else:
                safe_name = formula.replace("-", "").replace(" ", "").replace("*", "_star")
                save_dir = Path(f"{safe_name}_structures")
                
            save_dir.mkdir(parents=True, exist_ok=True)
            
            saved_paths = []
            for atoms in result:
                mp_id = atoms.info.get('material_id', 'unknown')
                form = atoms.info.get('formula', formula)
                theoretical = atoms.info.get('theoretical', True)
                
                # Create filename
                filename = f"{mp_id}_{form}.cif"
                filepath = save_dir / filename
                
                save_structure(atoms, filepath)
                saved_paths.append(f"{mp_id} (theoretical={theoretical})")
                
            summary = f"Found {len(result)} structures for {formula}\n"
            summary += f"Saved to directory: {save_dir.absolute()}\n\n"
            summary += "Structures:\n"
            for path_info in saved_paths:
                summary += f"  - {path_info}\n"
            return summary
        else:
            return _save_atoms(result, formula, save_to_file)
    except Exception as e:
        return f"Error executing search_materials_project_by_formula: {str(e)}"

@mcp.tool()
def search_materials_project_by_chemsys(
    chemsys: str,
    api_key: Optional[str] = None,
    save_to_file: Optional[str] = None
) -> str:
    """Search Materials Project by chemical system. Returns all stable structures on convex hull.
    
    Args:
        chemsys: Chemical system (e.g., "Li-O", "Si-Fe-O").
        api_key: Optional MP API key (defaults to environment).
        save_to_file: Optional directory path to save structures. If not provided, creates a directory named {chemsys}_structures.
        
    Returns:
        Summary of saved structures with paths.
    """
    mp_key = api_key or os.getenv("MP_API_KEY")
    if not mp_key:
        return "Error: Materials Project API key not found. Please provide api_key or set MP_API_KEY environment variable."
        
    try:
        from mp_api.client import MPRester
        with MPRester(mp_key) as mprester:
            atoms_list = get_structure_by_chemsys(chemsys, mprester)
                
        if not atoms_list:
            return f"Error: No structures found on convex hull for chemical system {chemsys} in Materials Project."
        
        # Determine save directory
        if save_to_file:
            save_dir = Path(save_to_file)
        else:
            safe_name = chemsys.replace("-", "").replace(" ", "")
            save_dir = Path(f"{safe_name}_structures")
        
        # Create directory
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save all structures
        saved_paths = []
        for atoms in atoms_list:
            mp_id = atoms.info.get('material_id', 'unknown')
            formula = atoms.info.get('formula', 'unknown')
            e_hull = atoms.info.get('energy_above_hull', 0.0)
            
            # Create filename: {mp-id}_{formula}.cif
            filename = f"{mp_id}_{formula}.cif"
            filepath = save_dir / filename
            
            save_structure(atoms, filepath)
            saved_paths.append(f"{mp_id} ({formula}, E_hull={e_hull:.6f} eV/atom)")
        
        summary = f"Found {len(atoms_list)} structures on convex hull for {chemsys}\n"
        summary += f"Saved to directory: {save_dir.absolute()}\n\n"
        summary += "Structures:\n"
        for path_info in saved_paths:
            summary += f"  - {path_info}\n"
        
        return summary
    except Exception as e:
        return f"Error executing search_materials_project_by_chemsys: {str(e)}"

def _save_atoms(atoms: Any, name_hint: str, save_to_file: Optional[str] = None) -> str:
    """Helper to save ASE atoms to file."""
    # Determine save path
    if save_to_file:
        save_path = Path(save_to_file)
    else:
        # Create a safe filename
        safe_name = name_hint.replace(" ", "").replace("*", "_star")
        save_path = Path(f"{safe_name}_structure.cif")
        
    # Save structure
    save_structure(atoms, save_path)
    
    return f"Structure for {name_hint} saved to {save_path.absolute()}"

@mcp.tool()
def visualize_structure(
    structure_path: str,
    output_path: Optional[str] = None,
    width: int = 1200,
    height: int = 800,
    scale: float = 2.0,
) -> str:
    """Visualize structure(s) as high-quality image(s).
    
    Args:
        structure_path: Can be:
            - Path to a single structure file (CIF, POSCAR, XYZ, etc.)
            - Path to a directory containing multiple structures (generates one image per structure)
            - Path to a trajectory file (visualizes the last frame)
        output_path: Save path for single file, or directory for batch mode (auto: research_dir or cwd). 
                     Formats: png, jpg, svg, pdf.
        width: Image width in pixels (default: 1200).
        height: Image height in pixels (default: 800).
        scale: Resolution scale factor (default: 2.0).
        
    Returns:
        Summary of saved image(s).
    """
    try:
        import os
        from pathlib import Path
        import plotly.io as pio
        from ase.io import read
        from ase import Atoms
        from pymatgen.io.ase import AseAtomsAdaptor

        input_path = Path(structure_path)
        from src.utils.research_utils import get_current_research_dir
        current_research_dir = str(get_current_research_dir())
        
        # Check if input is a directory
        if input_path.is_dir():
            # Batch mode: find all structure files
            structure_files = []
            for ext in ["cif", "CIF", "poscar", "POSCAR", "vasp", "xyz", "json"]:
                structure_files.extend(input_path.rglob(f"*.{ext}"))
            
            # Also check for POSCAR files without extension
            for poscar in input_path.rglob("POSCAR"):
                if poscar not in structure_files:
                    structure_files.append(poscar)
            
            structure_files = sorted(structure_files)
            
            if not structure_files:
                return f"Error: No structure files found in directory {structure_path}"
            
            # Determine output directory
            if output_path:
                out_dir = Path(output_path)
            elif current_research_dir:
                out_dir = Path(current_research_dir) / "structure_visualizations"
            else:
                out_dir = Path.cwd() / "structure_visualizations"
            
            out_dir.mkdir(parents=True, exist_ok=True)
            
            # Process each structure
            saved_images = []
            for struct_file in structure_files:
                try:
                    structure = load_structure_from_file(str(struct_file))
                    if structure is None:
                        continue
                    
                    # Convert to pymatgen if needed
                    if isinstance(structure, Atoms):
                        structure = AseAtomsAdaptor.get_structure(structure)
                    
                    # Generate output filename
                    struct_name = struct_file.stem
                    if struct_name == "POSCAR":
                        struct_name = struct_file.parent.name
                    
                    img_path = out_dir / f"{struct_name}_structure.png"
                    
                    # Import visualization function
                    from src.utils.structure_viz import structure_3d_custom
                    
                    # Generate and save figure
                    fig = structure_3d_custom(structure, scale=scale)
                    pio.write_image(fig, img_path, width=width, height=height, scale=scale)
                    saved_images.append(str(img_path))
                    
                except Exception as e:
                    print(f"Warning: Failed to visualize {struct_file}: {e}")
                    continue
            
            if not saved_images:
                return f"Error: Failed to visualize any structures in {structure_path}"
            
            return f"Successfully visualized {len(saved_images)} structures. Images saved to {out_dir}. Files: {[Path(p).name for p in saved_images[:5]]}{'...' if len(saved_images) > 5 else ''}"
        
        # Check if input is a trajectory file
        trajectory_extensions = [".traj", ".extxyz"]
        is_trajectory = any(str(input_path).endswith(ext) for ext in trajectory_extensions)
        
        if is_trajectory:
            # Load trajectory and get the last frame
            atoms_list = read(str(input_path), index=":")
            if not atoms_list:
                return f"Error: Trajectory file {structure_path} is empty"
            
            # Get last frame
            structure = atoms_list[-1]
            
            # Convert to pymatgen
            if isinstance(structure, Atoms):
                structure = AseAtomsAdaptor.get_structure(structure)
            
            struct_name = f"{input_path.stem}_last_frame"
        else:
            # Single structure file
            structure = load_structure_from_file(structure_path)
            if structure is None:
                return f"Error: Could not load structure from {structure_path}"
            
            # Convert ASE Atoms to pymatgen Structure if needed
            if isinstance(structure, Atoms):
                structure = AseAtomsAdaptor.get_structure(structure)
                
            # Get structure name for default filename
            struct_name = input_path.stem
        
        # Determine output path with research dir support
        if output_path:
            out_p = Path(output_path)
            # If output_path is relative and research dir is set, save there
            if not out_p.is_absolute() and len(out_p.parts) == 1 and current_research_dir:
                output_path = Path(current_research_dir) / out_p
            else:
                output_path = out_p
        else:
            filename = f"{struct_name}_structure.png"
            if current_research_dir:
                output_path = Path(current_research_dir) / filename
            else:
                output_path = Path.cwd() / filename
                
        # Ensure parent directory exists
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use custom implementation for better style control (Vesta colors, 3D lighting)
        from src.utils.structure_viz import structure_3d_custom
            
        # Generate the figure with custom settings
        fig = structure_3d_custom(
            structure,
            scale=scale,
        )
        
        # Save the image
        pio.write_image(fig, output_path, width=width, height=height, scale=scale)
        
        return f"Structure visualization saved to {output_path.absolute()}"
        
    except Exception as e:
        return f"Error visualizing structure: {str(e)}"

@mcp.tool()
def prepare_vasp_inputs(
    structure_path: str,
    output_dir: str,
    calculation_type: str = "relaxation",
    preset_type: str = "omat",
    config: Optional[Dict[str, Any]] = None,
    vasp_settings: Optional[Dict[str, Any]] = None
) -> str:
    """Prepare VASP input files (POSCAR, INCAR, KPOINTS, POTCAR).
    
    Args:
        structure_path: Path to structure file or directory.
        output_dir: Output directory for VASP files.
        calculation_type: "relaxation", "static", or "md".
        preset_type: "omat", "mp", "matpes-pbe", or "matpes-r2scan" (default: "omat").
        config: Custom INCAR tags to override preset.
        vasp_settings: Deprecated, use config instead.
                        
    Returns:
        Summary message.
    """
    input_path = Path(structure_path)
    out_path = Path(output_dir)
    
    # Prepare VASP inputs
    
    # Check if input is a directory (Batch processing)
    if input_path.is_dir():
        structure_files = list(input_path.rglob("*.cif")) + \
                          list(input_path.rglob("*.xyz")) + \
                          list(input_path.rglob("POSCAR"))
        
        if not structure_files:
            return f"Error: No structure files found in directory {structure_path}"
            
        summary = []
        for i, struct_file in enumerate(sorted(structure_files)):
            # Create subdirectory for each structure
            # Use filename stem or index if generic
            sub_name = struct_file.stem
            if sub_name == "POSCAR":
                sub_name = struct_file.parent.name
                
            # If names are generic like "structure_0", preserve them
            # Otherwise ensure uniqueness
            sub_dir = out_path / sub_name
            sub_dir.mkdir(parents=True, exist_ok=True)
            
            structure_loaded = load_structure_from_file(str(struct_file))
            if structure_loaded:
                from ase import Atoms
                from pymatgen.io.ase import AseAtomsAdaptor
                if not isinstance(structure_loaded, Atoms):
                    structure_loaded = AseAtomsAdaptor.get_atoms(structure_loaded)
                write_vasp_input_files(
                    atoms=structure_loaded,
                    output_dir=str(sub_dir),
                    preset_type=preset_type,
                    calculation_type=calculation_type,
                    config=config or vasp_settings
                )
                summary.append(sub_name)
                
        return f"Successfully prepared VASP inputs for {len(summary)} structures in {output_dir}. Subdirectories: {summary[:5]}..."
        
    else:
        # Single file processing
        structure_loaded = load_structure_from_file(structure_path)
        if structure_loaded is None:
            return f"Error: Could not load structure from {structure_path}"
            
        from ase import Atoms
        from pymatgen.io.ase import AseAtomsAdaptor
        if not isinstance(structure_loaded, Atoms):
            structure_loaded = AseAtomsAdaptor.get_atoms(structure_loaded)
        
        # Write files
        files = write_vasp_input_files(
            atoms=structure_loaded,
            output_dir=output_dir,
            preset_type=preset_type,
            calculation_type=calculation_type,
            config=config or vasp_settings
        )
        
        return f"Successfully wrote VASP input files to {output_dir}. Files: {list(files.keys())}"

@mcp.tool()
def parse_vasp_results(output_dir: str, save_to_file: Optional[str] = None) -> Dict[str, Any]:
    """Parse VASP outputs (vasprun.xml, OUTCAR).
    
    Args:
        output_dir: Directory with VASP outputs.
        save_to_file: Optional JSON save path.
        
    Returns:
        Dict with energy, forces, stress, structure (single calc) or list of results (batch).
    """
    parser = VASPParser(output_dir)
    
    # Check if this is a single calculation directory
    has_vasprun = (parser.output_dir / "vasprun.xml").exists()
    
    if has_vasprun:
        # Parse single VASP calculation
        result = parser.parse_vasprun()
        outcar_result = parser.parse_outcar()
        result.update(outcar_result)
        
        # Serialize for JSON
        results = parser._prepare_for_json(result)
        
        if save_to_file:
            with open(save_to_file, 'w') as f:
                json.dump(results, f, indent=2)
                
        return results
    
    # Otherwise, parse all subdirectories
    try:
        all_results = parser.parse_all()
    except Exception as e:
        return {"error": str(e)}
        
    if not all_results:
        return {"error": f"No valid VASP results found in {output_dir}"}
        
    # Return serialized list
    results = {"results": parser._prepare_for_json(all_results)}
    
    if save_to_file:
        with open(save_to_file, 'w') as f:
            json.dump(results, f, indent=2)
            
    return results

@mcp.tool()
def search_literature(query: str, limit: int = 10, download: bool = True, save_to_file: Optional[str] = None) -> str:
    """Search the OpenAlex database for scientific literature and optionally download full-text.
    
    Args:
        query: The search term (e.g., "solid state battery LGPS").
        limit: Maximum number of results to return (default 10, max 50).
        download: Whether to automatically attempt downloading the full text of discovered papers.
        save_to_file: Optional path to save the full JSON results.
        
    Returns:
        Formatted markdown summary of the top papers found, downloading status, and paywall warnings.
    """
    try:
        import json
        import os
        from pathlib import Path
        from src.utils.literature_utils import query_openalex, reconstruct_abstract
        
        limit = min(limit, 50) # Cap at 50 to avoid massive responses
        results = query_openalex(query, limit)
        
        if not results:
            return f"No results found on OpenAlex for query: '{query}'"
            
        # Optional: Save raw JSON data
        if save_to_file:
            save_path = Path(save_to_file)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w') as f:
                json.dump(results, f, indent=2)
                
        # Format the output summary
        summary = f"Found {len(results)} papers on OpenAlex for query '{query}':\\n\\n"
        
        # Determine download directory early
        output_dir = None
        if download:
            from src.utils.paper_downloader import download_paper_by_publisher
            from src.utils.research_utils import get_current_research_dir
            working_dir = get_current_research_dir()
            output_dir = Path(working_dir) / "papers"
            output_dir.mkdir(parents=True, exist_ok=True)
            
        paywalled_notifications = []
        
        for i, work in enumerate(results, 1):
            title = work.get('title', 'Unknown Title')
            year = work.get('publication_year', 'Unknown Year')
            authors = ", ".join(work.get('authors', [])[:3])
            if len(work.get('authors', [])) > 3:
                authors += " et al."
            
            doi = work.get('doi', 'No DOI')
            citations = work.get('cited_by_count', 0)
            is_oa = "Yes" if work.get('is_oa') else "No"
            
            summary += f"### {i}. {title}\\n"
            summary += f"- **Authors:** {authors}\\n"
            summary += f"- **Year:** {year} | **Citations:** {citations} | **Open Access:** {is_oa}\\n"
            summary += f"- **DOI:** https://doi.org/{doi}\\n"
            
            if download and doi and doi != 'No DOI':
                # Determine "publisher" intuitively. Try elsevier/springer, fallback to unpaywall.
                publisher_hint = "unpaywall"
                # Naive check, could be expanded if raw OpenAlex host metadata is passed
                if "elsevier" in (work.get("primary_location") or {}).get("landing_page_url", "").lower():
                    publisher_hint = "elsevier"
                elif "springer" in (work.get("primary_location") or {}).get("landing_page_url", "").lower():
                    publisher_hint = "springer"
                    
                downloaded_path = download_paper_by_publisher(doi, publisher_hint, output_dir)
                if downloaded_path:
                    summary += f"- **Downloaded Full-Text:** {downloaded_path}\\n"
                else:
                    summary += f"- **Download Failed:** Hit paywall or access restriction.\\n"
                    paywalled_notifications.append(f"[{i}] {title} (DOI: {doi})")
            
            # Reconstruct abstract
            abstract_idx = work.get('abstract_inverted_index')
            abstract_text = reconstruct_abstract(abstract_idx)
            if len(abstract_text) > 500:
                abstract_text = abstract_text[:497] + "..."
            summary += f"- **Abstract:** {abstract_text}\\n\\n"
            
        if download and paywalled_notifications:
            summary += "\\n### ⚠️ Paywall Notice\\n"
            summary += "The following papers could not be automatically downloaded due to publisher paywalls or lack of Open Access availability:\\n"
            for note in paywalled_notifications:
                summary += f"- {note}\\n"
            summary += "\\nPlease download these PDFs manually via your institutional proxy and upload them to the workspace if you need their full text.\\n"
            
        if save_to_file:
            summary += f"\\nFull results saved to {save_to_file}"
            
        return summary
        
    except Exception as e:
        return f"Error executing search_literature: {str(e)}"


if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)


