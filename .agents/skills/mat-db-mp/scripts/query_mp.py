#!/usr/bin/env python3
"""
Materials Project Database Query Tool (MP API)

Query Materials Project for inorganic crystal structures with computed properties.
Supports retrieval of:
  - Structures (CIF format)
  - Thermodynamic properties (energy_above_hull, formation_energy_per_atom, energy_per_atom)
  - Electronic properties (band_gap, is_metal)
  - Structural properties (density, volume, nsites)
  - Magnetic properties (total_magnetization)
  - Training data for MLIP fine-tuning (structure + total DFT energy)

Query options:
  - Chemical system (e.g., "Li-S", "Li-Fe-P-O")
  - Chemical formula (e.g., "LiFePO4")
  - List of elements (e.g., Li Fe P O)
  - Property filtering (e.g., energy_above_hull < 0.1 eV/atom for stable materials)

Output formats:
  - JSON: Full structure + property data (compatible with MatterGen training pipeline)
  - CSV: Tabular format for quick inspection (properties only, no structures)
  - Training data JSON: MLIP fine-tuning format (structure dict + total energy)

Usage:
    # Query Li-S structures with stability data
    python query_mp.py --chemsys "Li-S" --properties energy_above_hull formation_energy_per_atom --limit 50 --output li_s.json
    
    # Query stable Li-O materials (e_hull < 0.05 eV/atom)
    python query_mp.py --chemsys "Li-O" --properties energy_above_hull --e_above_hull_max 0.05 --limit 20 --output li_o_stable.json
    
    # Query by formula
    python query_mp.py --formula "LiFePO4" --properties energy_above_hull band_gap --output lifepo4.json
    
    # Export to CSV for inspection
    python query_mp.py --chemsys "Li-S" --properties energy_above_hull --limit 10 --output li_s.csv
    
    # Export MLIP training data with PBE energies
    python query_mp.py --chemsys "Si-O" --training_data --output si_o_training.json
    
    # Export MLIP training data with r2SCAN energies (thermo endpoint)
    python query_mp.py --chemsys "Si-O" --training_data --thermo_type r2SCAN --output si_o_r2scan_training.json

Requirements:
    - Conda environment: base-agent
    - Required packages: mp-api, pymatgen
    - MP_API_KEY environment variable must be set
"""

import argparse
import json
import csv
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional


def query_materials_project(
    chemsys: Optional[str] = None,
    formula: Optional[str] = None,
    elements: Optional[List[str]] = None,
    properties: Optional[List[str]] = None,
    e_above_hull_max: Optional[float] = None,
    formation_energy_max: Optional[float] = None,
    limit: int = 100,
    endpoint: str = "summary",
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query Materials Project for structures with properties.
    
    Args:
        chemsys: Chemical system (e.g., "Li-S", "Li-O-P")
        formula: Chemical formula (e.g., "LiFePO4")
        elements: List of elements to include
        properties: List of properties to retrieve (default: ["energy_above_hull", "formation_energy_per_atom"])
        e_above_hull_max: Maximum energy above hull (eV/atom) for filtering
        formation_energy_max: Maximum formation energy (eV/atom) for filtering
        limit: Maximum number of results
        endpoint: API endpoint to use ("summary" or "thermo", default: "summary")
        api_key: MP API key (defaults to environment)
        
    Returns:
        List of dictionaries with structure and property data
    """
    from mp_api.client import MPRester
    from pymatgen.io.cif import CifWriter
    import io
    
    # Get API key
    mp_key = api_key or os.environ.get('MP_API_KEY')
    if not mp_key:
        raise ValueError("Materials Project API key not found. Set MP_API_KEY environment variable.")
    
    # Default properties if not specified
    if properties is None:
        properties = ["energy_above_hull", "formation_energy_per_atom"]
    
    # Build query fields (thermo endpoint doesn't support structure field)
    if endpoint == "thermo":
        fields = ["material_id", "formula_pretty"] + properties
    else:
        fields = ["material_id", "formula_pretty", "structure"] + properties
    
    print(f"Querying Materials Project...")
    print(f"  Endpoint: {endpoint}")
    print(f"  Chemical system: {chemsys if chemsys else 'N/A'}")
    print(f"  Formula: {formula if formula else 'N/A'}")
    print(f"  Elements: {elements if elements else 'N/A'}")
    print(f"  Properties: {properties}")
    print(f"  Limit: {limit}")
    
    with MPRester(mp_key) as mpr:
        # Build query criteria
        criteria = {}
        
        if chemsys:
            criteria["chemsys"] = chemsys
        if formula:
            criteria["formula"] = formula
        if elements:
            criteria["elements"] = elements
        if e_above_hull_max is not None:
            criteria["energy_above_hull"] = (None, e_above_hull_max)
        if formation_energy_max is not None:
            criteria["formation_energy_per_atom"] = (None, formation_energy_max)
        
        # Query materials using specified endpoint
        if endpoint == "thermo":
            docs = mpr.materials.thermo.search(
                **criteria,
                fields=fields,
                num_chunks=1,
                chunk_size=limit
            )
        else:  # summary endpoint (default)
            docs = mpr.materials.summary.search(
                **criteria,
                fields=fields,
                num_chunks=1,
                chunk_size=limit
            )
    
    print(f"Found {len(docs)} materials")
    
    # Process results
    results = []
    for doc in docs:
        # Build result dict
        result = {
            "material_id": str(doc.material_id),
            "formula": doc.formula_pretty,
        }
        
        # Convert structure to CIF string (only available from summary endpoint)
        if hasattr(doc, 'structure') and doc.structure:
            structure = doc.structure
            cif_writer = CifWriter(structure)
            cif_string = str(cif_writer)
            result["cif"] = cif_string
            result["structure"] = structure.as_dict()  # For programmatic use
        
        # Add requested properties
        for prop in properties:
            if hasattr(doc, prop):
                value = getattr(doc, prop)
                result[prop] = float(value) if value is not None else None
            else:
                result[prop] = None
        
        results.append(result)
    
    return results


def query_training_data(
    chemsys: Optional[str] = None,
    formula: Optional[str] = None,
    e_above_hull_max: Optional[float] = None,
    thermo_type: str = "GGA_GGA+U",
    limit: int = 100,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query Materials Project for MLIP fine-tuning training data.
    
    Returns structures with total DFT energies, forces, and stresses.
    Forces and stresses are extracted from the trajectory endpoint.
    
    Args:
        chemsys: Chemical system (e.g., "Si-O")
        formula: Chemical formula (e.g., "SiO2")
        e_above_hull_max: Max energy above hull filter (eV/atom)
        thermo_type: DFT functional type for energies.
                     "GGA_GGA+U" (default, PBE) or "R2SCAN"
        limit: Maximum number of results
        api_key: MP API key (defaults to environment)
        
    Returns:
        List of dicts with:
          - 'structure': pymatgen Structure dict
          - 'energy': total DFT energy (eV)
          - 'forces': per-atom forces (eV/Å), shape [natoms, 3]
          - 'stress': Voigt stress (eV/Å³), shape [6] (xx,yy,zz,yz,xz,xy)
          - 'material_id', 'formula', 'energy_per_atom', 'nsites'
    """
    import numpy as np
    from mp_api.client import MPRester
    
    # kbar -> eV/Å³ conversion factor
    KBAR_TO_EV_A3 = 1.0 / 160.21766208
    
    mp_key = api_key or os.environ.get('MP_API_KEY')
    if not mp_key:
        raise ValueError("Materials Project API key not found. Set MP_API_KEY environment variable.")
    
    print(f"Querying training data from Materials Project...")
    print(f"  Functional: {thermo_type}")
    print(f"  Chemical system: {chemsys if chemsys else 'N/A'}")
    print(f"  Formula: {formula if formula else 'N/A'}")
    print(f"  E_hull filter: {e_above_hull_max if e_above_hull_max is not None else 'None'}")
    
    with MPRester(mp_key) as mpr:
        # Build query criteria
        criteria = {}
        if chemsys:
            criteria["chemsys"] = chemsys
        if formula:
            criteria["formula"] = formula
        if e_above_hull_max is not None:
            criteria["energy_above_hull"] = (None, e_above_hull_max)
        
        # Use summary endpoint: has structure + energy_per_atom + nsites
        fields = ["material_id", "formula_pretty", "structure",
                  "energy_per_atom", "uncorrected_energy_per_atom",
                  "nsites", "energy_above_hull"]
        
        docs = mpr.materials.summary.search(
            **criteria,
            fields=fields,
            num_chunks=1,
            chunk_size=limit
        )
        
        print(f"Found {len(docs)} materials")
        
        # Build training data with forces/stress from trajectory endpoint
        training_data = []
        failed_count = 0
        for i, doc in enumerate(docs):
            if doc.structure is None or doc.energy_per_atom is None:
                continue
            
            mid = str(doc.material_id)
            
            # Get forces, stress, and energy from trajectory endpoint
            # IMPORTANT: Use trajectory e_wo_entrp (raw VASP energy) instead of
            # summary energy_per_atom which includes MP2020 corrections
            forces = None
            stress_voigt = None
            traj_energy = None
            traj = mpr.materials.tasks.get_trajectory(mid)
            
            if traj:
                # Use the last frame (final calculation)
                frame = traj[-1]
                
                # Energy: use e_wo_entrp (energy without entropy) from last ionic step
                e_wo_entrp = frame.get("e_wo_entrp", [])
                if e_wo_entrp:
                    if isinstance(e_wo_entrp, list):
                        traj_energy = e_wo_entrp[-1]
                    else:
                        traj_energy = e_wo_entrp
                
                # Forces: last ionic step, shape [natoms, 3] in eV/Å
                forces_data = frame.get("forces", [])
                if forces_data:
                    forces = forces_data
                    if isinstance(forces[0][0], list):
                        forces = forces[-1]
                
                # Stress: last ionic step, 3x3 matrix in kbar
                stress_data = frame.get("stress", [])
                if stress_data:
                    stress_3x3 = stress_data
                    if isinstance(stress_3x3[0][0], list):
                        stress_3x3 = stress_3x3[-1]
                    
                    # Convert kbar -> eV/Å³ and to Voigt notation [xx,yy,zz,yz,xz,xy]
                    s = np.array(stress_3x3) * KBAR_TO_EV_A3
                    stress_voigt = [
                        float(s[0][0]), float(s[1][1]), float(s[2][2]),
                        float(s[1][2]), float(s[0][2]), float(s[0][1])
                    ]
            
            if forces is None or traj_energy is None:
                failed_count += 1
                print(f"  [{i+1}/{len(docs)}] {mid} {doc.formula_pretty}: "
                      f"SKIPPED (no trajectory data)")
                continue
            
            # Validate forces match structure (trajectory may be from supercell)
            if len(forces) != doc.nsites:
                failed_count += 1
                print(f"  [{i+1}/{len(docs)}] {mid} {doc.formula_pretty}: "
                      f"SKIPPED (forces={len(forces)} != sites={doc.nsites})")
                continue
            
            sample = {
                "structure": doc.structure.as_dict(),
                "energy": traj_energy,
                "forces": forces,
                "stress": stress_voigt,
                "material_id": mid,
                "formula": doc.formula_pretty,
                "energy_per_atom": traj_energy / doc.nsites,
                "nsites": doc.nsites,
                "energy_above_hull": doc.energy_above_hull,
            }
            training_data.append(sample)
            
            max_f = max(max(abs(f) for f in atom) for atom in forces) if forces else 0
            print(f"  [{i+1}/{len(docs)}] {mid} {doc.formula_pretty}: "
                  f"E={traj_energy:.4f} eV ({traj_energy/doc.nsites:.4f} eV/atom), "
                  f"F_max={max_f:.4f} eV/Å, nsites={doc.nsites}")
    
    print(f"\nTotal training samples: {len(training_data)} "
          f"({failed_count} skipped)")
    
    return training_data


def save_to_json(data: List[Dict], output_path: str) -> None:
    """Save data to JSON file."""
    output_path = Path(output_path)
    
    # Remove 'structure' field for cleaner JSON (keep CIF)
    clean_data = []
    for item in data:
        clean_item = {k: v for k, v in item.items() if k != "structure"}
        clean_data.append(clean_item)
    
    with open(output_path, 'w') as f:
        json.dump(clean_data, f, indent=2)
    
    print(f"Saved {len(data)} materials to {output_path}")


def save_to_csv(data: List[Dict], output_path: str, properties: List[str]) -> None:
    """Save data to CSV file."""
    output_path = Path(output_path)
    
    # Get all unique keys except structure and CIF (too large for CSV)
    fieldnames = ["material_id", "formula"] + properties
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in data:
            row = {k: item.get(k) for k in fieldnames}
            writer.writerow(row)
    
    print(f"Saved {len(data)} materials to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Query Materials Project for structures with properties"
    )
    
    # Query options
    parser.add_argument("--chemsys", type=str, help="Chemical system (e.g., 'Li-S', 'Li-O-P')")
    parser.add_argument("--formula", type=str, help="Chemical formula (e.g., 'LiFePO4')")
    parser.add_argument("--elements", nargs="+", help="Elements to include (e.g., Li S O)")
    
    # Property options
    parser.add_argument(
        "--properties", 
        nargs="+", 
        default=["energy_above_hull", "formation_energy_per_atom"],
        help="Properties to retrieve (default: energy_above_hull formation_energy_per_atom)"
    )
    
    # Filters
    parser.add_argument("--endpoint", type=str, choices=["summary", "thermo"], default="summary",
                        help="API endpoint to use (default: summary, use 'thermo' for more detailed thermodynamic data)")
    parser.add_argument("--e_above_hull_max", type=float, help="Maximum energy above hull (eV/atom)")
    parser.add_argument("--formation_energy_max", type=float, help="Maximum formation energy (eV/atom)")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of results (default: 100)")
    
    # Training data mode
    parser.add_argument("--training_data", action="store_true",
                        help="Export MLIP training data format (structure + total DFT energy)")
    parser.add_argument("--thermo_type", type=str, default="GGA_GGA+U",
                        choices=["GGA_GGA+U", "R2SCAN"],
                        help="DFT functional for energies (default: GGA_GGA+U i.e. PBE)")
    
    # Output
    parser.add_argument("--output", type=str, required=True, help="Output file path (.json or .csv)")
    parser.add_argument("--api_key", type=str, help="Materials Project API key (defaults to MP_API_KEY env var)")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not any([args.chemsys, args.formula, args.elements]):
        parser.error("Must specify at least one of: --chemsys, --formula, --elements")
    
    # Training data mode
    if args.training_data:
        results = query_training_data(
            chemsys=args.chemsys,
            formula=args.formula,
            e_above_hull_max=args.e_above_hull_max,
            thermo_type=args.thermo_type,
            limit=args.limit,
            api_key=args.api_key
        )
        
        if not results:
            print("No training data found matching criteria")
            sys.exit(1)
        
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n\u2713 Saved {len(results)} training samples to {output_path}")
        return
    
    # Standard query mode
    results = query_materials_project(
        chemsys=args.chemsys,
        formula=args.formula,
        elements=args.elements,
        properties=args.properties,
        e_above_hull_max=args.e_above_hull_max,
        formation_energy_max=args.formation_energy_max,
        limit=args.limit,
        endpoint=args.endpoint,
        api_key=args.api_key
    )
    
    if not results:
        print("No materials found matching criteria")
        sys.exit(1)
    
    # Save results
    output_path = Path(args.output)
    if output_path.suffix == ".csv":
        save_to_csv(results, args.output, args.properties)
    else:
        save_to_json(results, args.output)
    
    print(f"\n\u2713 Successfully retrieved {len(results)} materials")


if __name__ == "__main__":
    main()
