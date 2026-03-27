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
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

# Suppress all warnings to prevent protocol pollution
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

# Silence RDKit and related libraries
logging.getLogger("rdkit").setLevel(logging.ERROR)

from rdkit import Chem
import src.utils.drugdisc_utils as drugdisc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DrugDiscServer")

# Create MCP server
mcp = FastMCP("drugdisc")


@mcp.tool()
def parse_smiles_input(
    smiles: Optional[str] = None,
    smiles_file: Optional[str] = None,
    name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parse SMILES from string or file.
    
    Args:
        smiles: Single SMILES string
        smiles_file: Path to SMILES file (formats: "SMILES", "SMILES\\tNAME", "SMILES NAME")
        name: Optional molecule name (only used with smiles string)
        
    Returns:
        Dictionary with parsed SMILES and names
    """
    try:
        if smiles_file:
            records = drugdisc.parse_smiles_from_file(smiles_file)
        elif smiles:
            records = drugdisc.parse_smiles_from_string(smiles, name)
        else:
            return {
                "success": False,
                "error": "Must provide either 'smiles' or 'smiles_file'"
            }
        
        return {
            "success": True,
            "n_molecules": len(records),
            "molecules": [
                {"smiles": smi, "name": n}
                for smi, n in records
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def standardize_molecule(
    smiles: str,
    mode: str = "cleanup",
    enumerate_protomers: bool = False,
    ph_min: float = 6.4,
    ph_max: float = 8.4,
    max_protomers: int = 10
) -> Dict[str, Any]:
    """
    Standardize a molecule using RDKit MolStandardize.
    
    Args:
        smiles: Input SMILES string
        mode: Standardization mode
            - "none": No standardization
            - "cleanup": Basic cleanup
            - "parent": Largest fragment + cleanup
            - "uncharged": Parent + neutralize
            - "tautomer": Parent + canonical tautomer
        enumerate_protomers: Generate pH-dependent protonation states
        ph_min: Minimum pH for protomer enumeration
        ph_max: Maximum pH for protomer enumeration
        max_protomers: Maximum number of protomers to generate
        
    Returns:
        Dictionary with standardized SMILES or list of protomers
    """
    try:
        mol = drugdisc.mol_from_smiles(smiles)
        if mol is None:
            return {
                "success": False,
                "error": f"Invalid SMILES: {smiles}"
            }
        
        # Standardize
        if mode != "none":
            mol = drugdisc.standardize_mol(mol, mode=mode)
            if mol is None:
                return {
                    "success": False,
                    "error": "Standardization failed"
                }
        
        standardized_smiles = Chem.MolToSmiles(mol)
        
        result = {
            "success": True,
            "input_smiles": smiles,
            "standardized_smiles": standardized_smiles,
            "mode": mode
        }
        
        # Enumerate protomers if requested
        if enumerate_protomers:
            protomers = drugdisc.enumerate_protomers(
                standardized_smiles,
                ph_min=ph_min,
                ph_max=ph_max,
                max_variants=max_protomers
            )
            result["protomers"] = protomers
            result["n_protomers"] = len(protomers)
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def convert_to_pdbqt(
    input_data: Union[str, Dict[str, Any]],
    output_path: str,
    input_type: str = "smiles",
    num_confs: int = 10,
    force_field: str = "MMFF94",
    max_iters: int = 500
) -> Dict[str, Any]:
    """
    Convert molecule or protein to PDBQT format using Meeko.
    
    Args:
        input_data: Can be:
            - SMILES string (if input_type="smiles")
            - Path to SDF file (if input_type="sdf")
            - Path to PDB file (if input_type="pdb")
        output_path: Output PDBQT file path
        input_type: Type of input ("smiles", "sdf", "pdb")
        num_confs: Number of conformers to generate (for SMILES/SDF)
        force_field: Force field for optimization ("MMFF94", "MMFF94s", "UFF")
        max_iters: Maximum optimization iterations
        
    Returns:
        Dictionary with conversion results
    """
    try:
        from rdkit import Chem
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        import subprocess
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Handle different input types
        if input_type == "smiles":
            # Parse and generate 3D
            mol = drugdisc.mol_from_smiles(input_data)
            if mol is None:
                return {"success": False, "error": "Invalid SMILES"}
            
            # Add hydrogens
            mol = Chem.AddHs(mol)
            
            # Embed conformers
            conf_ids = drugdisc.embed_conformers(mol, num_confs=num_confs)
            if not conf_ids:
                return {"success": False, "error": "Failed to embed conformers"}
            
            # Optimize
            opt_results = drugdisc.optimize_conformers(mol, max_iters=max_iters, force_field=force_field)
            best_id, best_energy, converged = drugdisc.select_best_conformer(opt_results)
            
            # Convert to PDBQT
            drugdisc.mol_to_pdbqt(mol, str(output_path), conf_id=best_id)
            
            return {
                "success": True,
                "output_path": str(output_path.absolute()),
                "input_type": input_type,
                "n_conformers": len(conf_ids),
                "best_conformer_id": best_id,
                "best_energy": round(best_energy, 3),
                "converged": converged
            }
            
        elif input_type == "sdf":
            # Read SDF
            suppl = Chem.SDMolSupplier(input_data, removeHs=False)
            mol = next(suppl)
            if mol is None:
                return {"success": False, "error": "Failed to read SDF file"}
            
            # Add hydrogens if needed
            if mol.GetNumConformers() == 0:
                mol = Chem.AddHs(mol)
                conf_ids = drugdisc.embed_conformers(mol, num_confs=num_confs)
                opt_results = drugdisc.optimize_conformers(mol, max_iters=max_iters, force_field=force_field)
                best_id, best_energy, _ = drugdisc.select_best_conformer(opt_results)
            else:
                best_id = 0
                best_energy = 0.0
            
            # Convert
            drugdisc.mol_to_pdbqt(mol, str(output_path), conf_id=best_id)
            
            return {
                "success": True,
                "output_path": str(output_path.absolute()),
                "input_type": input_type
            }
            
        if input_type == "pdb":
            # Use Meeko's command-line tool for proteins
            import shutil
            
            exe = shutil.which("mk_prepare_receptor.py")
            if exe is None:
                # Try finding it in the same environment as the python interpreter
                candidate = Path(sys.prefix) / "bin" / "mk_prepare_receptor.py"
                if candidate.exists():
                    exe = str(candidate)
                    
            if exe is None:
                return {
                    "success": False,
                    "error": "mk_prepare_receptor.py not found using shutil.which or in sys.prefix/bin"
                }

            cmd = [
                exe,
                "--read_pdb", input_data,
                "--write_pdbqt", str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Receptor preparation failed: {result.stderr}"
                }
            
            return {
                "success": True,
                "output_path": str(output_path.absolute()),
                "input_type": input_type
            }
        else:
            return {
                "success": False,
                "error": f"Unknown input_type: {input_type}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def compute_molecular_descriptors(
    smiles: Optional[str] = None,
    smiles_file: Optional[str] = None,
    include_sandp_tpsa: bool = False,
    output_file: str = None
) -> Dict[str, Any]:
    """
    Compute molecular descriptors and drug-likeness heuristics.
    
    Args:
        smiles: Single SMILES string
        smiles_file: Path to SMILES file
        include_sandp_tpsa: Use S,P-inclusive TPSA calculation
        output_file: Path to save results as JSON (REQUIRED)
        
    Returns:
        Dictionary with summary statistics and path to full results
    """
    try:
        if not output_file:
            return {
                "success": False,
                "error": "output_file is required"
            }
        
        # Parse input
        if smiles_file:
            records = drugdisc.parse_smiles_from_file(smiles_file)
        elif smiles:
            records = drugdisc.parse_smiles_from_string(smiles)
        else:
            return {
                "success": False,
                "error": "Must provide either 'smiles' or 'smiles_file'"
            }
        
        # Compute descriptors for each molecule
        results = []
        for smi, name in records:
            descriptors = drugdisc.compute_descriptors(
                smi,
                name=name,
                include_sandp_tpsa=include_sandp_tpsa
            )
            results.append(descriptors)
        
        # Summary statistics
        n_valid = sum(1 for r in results if r.get("valid", False))
        n_ro5_pass = sum(1 for r in results if r.get("lipinski_ro5_pass", False))
        n_veber_pass = sum(1 for r in results if r.get("veber_pass", False))
        
        # Full output saved to disk
        full_output = {
            "n_molecules": len(results),
            "n_valid": n_valid,
            "n_ro5_pass": n_ro5_pass,
            "n_veber_pass": n_veber_pass,
            "descriptors": results
        }
        
        # Save full results
        with open(output_file, 'w') as f:
            json.dump(full_output, f, indent=2)
        
        # Return minimal summary only
        return {
            "success": True,
            "n_molecules": len(results),
            "n_valid": n_valid,
            "n_ro5_pass": n_ro5_pass,
            "n_veber_pass": n_veber_pass,
            "output_file": output_file
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def compute_molecular_fingerprints(
    smiles_file: str,
    radius: int = 2,
    fp_size: int = 2048,
    use_chirality: bool = False,
    use_features: bool = False,
    compute_similarity: bool = True,
    cluster: bool = False,
    cluster_cutoff: float = 0.5,
    save_heatmap: Optional[str] = None,
    output_file: str = None
) -> Dict[str, Any]:
    """
    Compute Morgan fingerprints and chemical similarity.
    
    Args:
        smiles_file: Path to SMILES file
        radius: Morgan radius (default 2 for ECFP4)
        fp_size: Fingerprint bit vector size
        use_chirality: Include stereochemistry
        use_features: Use pharmacophore features (FCFP)
        compute_similarity: Calculate pairwise Tanimoto similarity
        cluster: Perform Butina clustering
        cluster_cutoff: Similarity cutoff for clustering
        save_heatmap: Optional path to save similarity heatmap
        output_file: Path to save results as JSON (REQUIRED)
        
    Returns:
        Dictionary with summary statistics and paths
    """
    try:
        if not output_file:
            return {
                "success": False,
                "error": "output_file is required"
            }
        
        # Parse SMILES
        records = drugdisc.parse_smiles_from_file(smiles_file)
        
        # Compute fingerprints
        fp_result = drugdisc.compute_fingerprints(
            records,
            radius=radius,
            fp_size=fp_size,
            use_chirality=use_chirality,
            use_features=use_features,
            compute_similarity=compute_similarity
        )
        
        # Clustering if requested
        if cluster and compute_similarity:
            from rdkit.ML.Cluster import Butina
            from rdkit import DataStructs, Chem
            
            # Rebuild fingerprints for clustering
            fps = []
            for smi, _ in records:
                mol = Chem.MolFromSmiles(smi)
                if mol:
                    from rdkit.Chem import rdFingerprintGenerator
                    fpgen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=fp_size)
                    fps.append(fpgen.GetFingerprint(mol))
                else:
                    fps.append(None)
            
            # Compute distance matrix
            dists = []
            for i in range(len(fps)):
                for j in range(i+1, len(fps)):
                    if fps[i] and fps[j]:
                        sim = DataStructs.TanimotoSimilarity(fps[i], fps[j])
                        dists.append(1.0 - sim)
                    else:
                        dists.append(1.0)
            
            # Cluster
            clusters = Butina.ClusterData(dists, len(fps), 1.0 - cluster_cutoff, isDistData=True)
            
            fp_result["clusters"] = [list(cluster) for cluster in clusters]
            fp_result["n_clusters"] = len(clusters)
        
        # Save heatmap if requested
        if save_heatmap and compute_similarity:
            import matplotlib.pyplot as plt
            import numpy as np
            
            sim_matrix = fp_result.get("similarity_matrix", [])
            labels = [c["name"] for c in fp_result["compounds"]]
            
            # Convert to numpy array and handle None values
            sim_array = np.array([[s if s is not None else 0.0 for s in row] for row in sim_matrix])
            
            fig, ax = plt.subplots(figsize=(10, 8))
            im = ax.imshow(sim_array, cmap='RdYlGn', vmin=0, vmax=1)
            ax.set_xticks(range(len(labels)))
            ax.set_yticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.set_yticklabels(labels)
            plt.colorbar(im, label='Tanimoto Similarity')
            plt.title('Molecular Similarity Heatmap')
            plt.tight_layout()
            plt.savefig(save_heatmap, dpi=300)
            plt.close()
            
            heatmap_path = save_heatmap
        
        # Save full results (remove bit strings to reduce file size)
        save_data = fp_result.copy()
        for comp in save_data["compounds"]:
            if "fingerprint" in comp:
                del comp["fingerprint"]
        
        with open(output_file, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        # Return minimal summary only
        return {
            "success": True,
            "n_compounds": fp_result["n_compounds"],
            "n_valid": fp_result["n_valid"],
            "n_clusters": fp_result.get("n_clusters"),
            "output_file": output_file,
            "heatmap_path": heatmap_path
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)
