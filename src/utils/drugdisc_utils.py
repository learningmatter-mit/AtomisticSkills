"""
Drug Discovery Utilities

Core cheminformatics operations for drug discovery workflows.
Provides standalone functions for SMILES parsing, molecule standardization,
3D conformer generation, descriptor calculation, and fingerprinting.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, Lipinski, QED

logger = logging.getLogger(__name__)


# ==================== SMILES Parsing ====================

def parse_smiles_from_string(smiles: str, name: Optional[str] = None) -> List[Tuple[str, Optional[str]]]:
    """Parse a single SMILES string into [(smiles, name)] format."""
    return [(smiles, name)]


def parse_smiles_from_file(filepath: str) -> List[Tuple[str, Optional[str]]]:
    """
    Parse SMILES from file. Supports multiple formats:
    - SMILES (no name)
    - SMILES\\tNAME (tab-separated)
    - SMILES NAME (space-separated)
    
    Lines starting with # are ignored.
    """
    records = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Try tab-separated first, then space-separated
            if '\t' in line:
                parts = line.split('\t', 1)
            else:
                parts = line.split(None, 1)
            
            smiles = parts[0]
            name = parts[1].strip() if len(parts) > 1 else None
            records.append((smiles, name))
    
    return records


# ==================== Molecule Operations ====================

def mol_from_smiles(smiles: str) -> Optional[Chem.Mol]:
    """Convert SMILES string to RDKit molecule."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        return mol
    except Exception as e:
        logger.error(f"Failed to parse SMILES '{smiles}': {e}")
        return None


def standardize_mol(mol: Chem.Mol, mode: str = "cleanup") -> Optional[Chem.Mol]:
    """
    Apply RDKit MolStandardize transformations.
    
    Args:
        mol: RDKit molecule
        mode: Standardization mode
            - "none": No standardization
            - "cleanup": Basic cleanup (sanitization, charge parent)
            - "parent": Largest fragment + cleanup
            - "uncharged": Parent + neutralize
            - "tautomer": Parent + canonical tautomer
            
    Returns:
        Standardized molecule
    """
    if mode == "none":
        return mol
    
    try:
        from rdkit.Chem.MolStandardize import rdMolStandardize
        
        if mode in ["cleanup", "parent", "uncharged", "tautomer"]:
            # Always start with cleanup
            mol = rdMolStandardize.Cleanup(mol)
        
        if mode in ["parent", "uncharged", "tautomer"]:
            # Get largest fragment  
            mol = rdMolStandardize.FragmentParent(mol)
        
        if mode == "uncharged":
            # Neutralize charges
            uncharger = rdMolStandardize.Uncharger()
            mol = uncharger.uncharge(mol)
        
        if mode == "tautomer":
            # Get canonical tautomer
            te = rdMolStandardize.TautomerEnumerator()
            mol = te.Canonicalize(mol)
        
        return mol
        
    except ImportError:
        logger.warning("rdkit.Chem.MolStandardize not available, returning original molecule")
        return mol
    except Exception as e:
        logger.error(f"Standardization failed: {e}")
        return None


def enumerate_protomers(
    smiles: str,
    ph_min: float = 6.4,
    ph_max: float = 8.4,
    max_variants: int = 10
) -> List[str]:
    """
    Enumerate pH-dependent protonation states using Dimorphite-DL.
    
    Returns:
        List of SMILES strings for different protomers
    """
    try:
        from dimorphite_dl import DimorphiteDL
        dimorphite = DimorphiteDL(
            min_ph=ph_min,
            max_ph=ph_max,
            max_variants=max_variants,
            silent=True
        )
        protomers = dimorphite.protonate(smiles)
        return protomers if protomers else [smiles]
    except ImportError:
        logger.warning("dimorphite_dl not available, returning original SMILES")
        return [smiles]
    except Exception as e:
        logger.error(f"Protomer enumeration failed: {e}")
        return [smiles]


# ==================== 3D Conformer Generation ====================

def embed_conformers(mol: Chem.Mol, num_confs: int = 10) -> List[int]:
    """
    Generate 3D conformers using ETKDG.
    
    Returns:
        List of conformer IDs
    """
    from rdkit.Chem import AllChem
    try:
        conf_ids = AllChem.EmbedMultipleConfs(
            mol,
            numConfs=num_confs,
            params=AllChem.ETKDGv3()
        )
        return list(conf_ids)
    except Exception as e:
        logger.error(f"Conformer embedding failed: {e}")
        return []


def optimize_conformers(
    mol: Chem.Mol,
    max_iters: int = 500,
    force_field: str = "MMFF94"
) -> List[Tuple[int, float, bool]]:
    """
    Optimize all conformers with specified force field.
    
    Returns:
        List of (conformer_id, energy, converged) tuples
    """
    from rdkit.Chem import AllChem
    results = []
    
    for conf_id in range(mol.GetNumConformers()):
        try:
            if force_field.upper().startswith("MMFF"):
                props = AllChem.MMFFGetMoleculeProperties(mol)
                ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=conf_id)
                converged = ff.Minimize(maxIts=max_iters) == 0
                energy = ff.CalcEnergy()
            else:  # UFF
                ff = AllChem.UFFGetMoleculeForceField(mol, confId=conf_id)
                converged = ff.Minimize(maxIts=max_iters) == 0
                energy = ff.CalcEnergy()
            
            results.append((conf_id, energy, converged))
        except Exception as e:
            logger.error(f"Optimization failed for conformer {conf_id}: {e}")
            results.append((conf_id, float('inf'), False))
    
    return results


def select_best_conformer(opt_results: List[Tuple[int, float, bool]]) -> Tuple[int, float, bool]:
    """Select conformer with lowest energy."""
    if not opt_results:
        return (-1, float('inf'), False)
    return min(opt_results, key=lambda x: x[1])


# ==================== PDBQT Conversion ====================

def mol_to_pdbqt(mol: Chem.Mol, output_path: str, conf_id: int = -1) -> None:
    """Convert RDKit molecule to PDBQT format using Meeko."""
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    
    preparator = MoleculePreparation()
    mol_setups = preparator.prepare(mol)
    
    for setup in mol_setups:
        pdbqt_string = PDBQTWriterLegacy.write_string(setup)[0]
        with open(output_path, 'w') as f:
            f.write(pdbqt_string)
        break  # Only write first setup


# ==================== Molecular Descriptors ====================

def compute_descriptors(
    smiles: str,
    name: Optional[str] = None,
    include_sandp_tpsa: bool = False
) -> Dict[str, Any]:
    """
    Compute molecular descriptors and drug-likeness heuristics.
    
    Returns:
        Dictionary with descriptors and validity flags
    """
    mol = mol_from_smiles(smiles)
    if mol is None:
        return {
            "smiles": smiles,
            "name": name or smiles,
            "valid": False,
            "error": "Invalid SMILES"
        }
    
    try:
        # Descriptors
        mw = round(Descriptors.MolWt(mol), 2)
        logp = round(Crippen.MolLogP(mol), 2)
        tpsa = round(Descriptors.TPSA(mol, includeSandP=include_sandp_tpsa), 2)
        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        rotatable = Lipinski.NumRotatableBonds(mol)
        num_atoms = mol.GetNumAtoms()
        num_heavy = mol.GetNumHeavyAtoms()
        formal_charge = Chem.GetFormalCharge(mol)
        qed = round(QED.qed(mol), 2)
        
        # Lipinski Ro5
        lipinski_violations = sum([
            mw > 500,
            logp > 5,
            hbd > 5,
            hba > 10
        ])
        
        # Veber
        veber_pass = rotatable <= 10 and tpsa <= 140
        
        return {
            "smiles": Chem.MolToSmiles(mol),
            "name": name or Chem.MolToSmiles(mol),
            "valid": True,
            "molecular_weight": mw,
            "logp": logp,
            "tpsa": tpsa,
            "hbd": hbd,
            "hba": hba,
            "rotatable_bonds": rotatable,
            "num_atoms": num_atoms,
            "num_heavy_atoms": num_heavy,
            "formal_charge": formal_charge,
            "qed": qed,
            "lipinski_violations": lipinski_violations,
            "lipinski_ro5_pass": lipinski_violations <= 1,
            "veber_pass": veber_pass
        }
    except Exception as e:
        return {
            "smiles": smiles,
            "name": name or smiles,
            "valid": False,
            "error": str(e)
        }


# ==================== Fingerprints ====================

def compute_fingerprints(
    records: List[Tuple[str, Optional[str]]],
    radius: int = 2,
    fp_size: int = 2048,
    use_chirality: bool = False,
    use_features: bool = False,
    compute_similarity: bool = True
) -> Dict[str, Any]:
    """
    Compute Morgan fingerprints and optional similarity matrix.
    
    Returns:
        Dictionary with fingerprints, compounds info, and optional similarity matrix
    """
    from rdkit.Chem import rdFingerprintGenerator
    from rdkit import DataStructs
    
    # Create fingerprint generator
    if use_features:
        invgen = rdFingerprintGenerator.GetMorganFeatureAtomInvGen()
        fpgen = rdFingerprintGenerator.GetMorganGenerator(
            radius=radius,
            fpSize=fp_size,
            includeChirality=use_chirality,
            atomInvariantsGenerator=invgen
        )
    else:
        fpgen = rdFingerprintGenerator.GetMorganGenerator(
            radius=radius,
            fpSize=fp_size,
            includeChirality=use_chirality
        )
    
    # Compute fingerprints
    compounds = []
    fps = []
    
    for smiles, name in records:
        mol = mol_from_smiles(smiles)
        if mol is None:
            compounds.append({
                "smiles": smiles,
                "name": name or smiles,
                "valid": False
            })
            fps.append(None)
            continue
        
        try:
            fp = fpgen.GetFingerprint(mol)
            canonical_smiles = Chem.MolToSmiles(mol)
            
            compounds.append({
                "smiles": canonical_smiles,
                "name": name or canonical_smiles,
                "valid": True,
                "fingerprint": fp.ToBitString()
            })
            fps.append(fp)
        except Exception as e:
            compounds.append({
                "smiles": smiles,
                "name": name or smiles,
                "valid": False,
                "error": str(e)
            })
            fps.append(None)
    
    result = {
        "n_compounds": len(compounds),
        "n_valid": sum(1 for c in compounds if c.get("valid")),
        "compounds": compounds
    }
    
    # Compute similarity matrix if requested
    if compute_similarity:
        n = len(fps)
        matrix = [[None] * n for _ in range(n)]
        
        valid_indices = [i for i, fp in enumerate(fps) if fp is not None]
        valid_fps = [fps[i] for i in valid_indices]
        
        for i, idx_i in enumerate(valid_indices):
            for j, idx_j in enumerate(valid_indices):
                if idx_i <= idx_j:
                    sim = DataStructs.TanimotoSimilarity(valid_fps[i], valid_fps[j])
                    matrix[idx_i][idx_j] = round(float(sim), 4)
                    matrix[idx_j][idx_i] = matrix[idx_i][idx_j]
        
        result["similarity_matrix"] = matrix
    
    return result
