"""
Match target structure(s) against candidate structures or the Materials Project database.

Usage:
    python match_structure.py <target_structure_or_dir> <candidates_or_MP> [--ltol 0.2] [--stol 0.3] [--angle_tol 5]

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, ase, argparse, mp_api (if using 'MP')
"""
import argparse
import sys
import json
import os
from pathlib import Path
import inspect

from pymatgen.core import Structure
from pymatgen.analysis.structure_matcher import StructureMatcher

# Add project root to sys.path robustly
script_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
project_root = os.path.abspath(os.path.join(script_dir, "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.structure_utils import load_structures

def get_identifier(struct, default="unknown"):
    if hasattr(struct, "properties") and struct.properties:
        if "material_id" in struct.properties:
            return struct.properties["material_id"]
        if "filename" in struct.properties:
            return struct.properties["filename"]
        if "filepath" in struct.properties:
            return struct.properties["filepath"]
    return default

def main():
    parser = argparse.ArgumentParser(description="Match target structure(s) against candidates.")
    parser.add_argument("target", help="Path to target structure file or directory.")
    parser.add_argument("candidates", nargs="?", default="MP", help="Path to candidate structure file/dir, or 'MP' to automatically query Materials Project.")
    parser.add_argument("--ltol", type=float, default=0.2, help="Fractional length tolerance.")
    parser.add_argument("--stol", type=float, default=0.3, help="Site tolerance.")
    parser.add_argument("--angle_tol", type=float, default=5.0, help="Angle tolerance.")
    parser.add_argument("--output", type=str, default="match_results.json", help="Output JSON file.")
    
    args = parser.parse_args()
    
    # 1. Load targets
    print(f"Loading target structure(s) from {args.target}...")
    target_path = Path(args.target)
    target_structs = []
    
    if target_path.is_dir():
        for f in target_path.rglob("*"):
            if f.is_file() and f.suffix.lower() in [".cif", ".xyz", ".poscar", ".vasp"]:
                try:
                    stm = Structure.from_file(str(f))
                    stm.properties = stm.properties or {}
                    stm.properties["filename"] = f.name
                    stm.properties["filepath"] = str(f)
                    target_structs.append(stm)
                except:
                    pass
    else:
        try:
            targets = load_structures(str(target_path))
            if targets:
                for stm in targets:
                    stm.properties = stm.properties or {}
                    stm.properties["filename"] = target_path.name
                    stm.properties["filepath"] = str(target_path)
                    target_structs.append(stm)
        except Exception as e:
            print(f"Error reading target: {e}")
            sys.exit(1)
            
    if not target_structs:
        print(f"Error: No valid target structures found in {args.target}")
        sys.exit(1)
        
    print(f"Loaded {len(target_structs)} target structure(s).")
    
    # 2. Load candidates
    candidate_dict = {}  # formula -> list of structures
    num_candidates = 0
    
    if args.candidates.upper() == "MP":
        from mp_api.client import MPRester
        unique_formulas = set(stm.composition.reduced_formula for stm in target_structs)
        print(f"Querying Materials Project for {len(unique_formulas)} unique formulas...")
        with MPRester() as mpr:
            for formula in unique_formulas:
                try:
                    docs = mpr.materials.summary.search(formula=formula, fields=["structure", "material_id"])
                    structs = []
                    for doc in docs:
                        s = doc.structure
                        s.properties = s.properties or {}
                        s.properties["material_id"] = str(doc.material_id)
                        structs.append(s)
                    candidate_dict[formula] = structs
                    num_candidates += len(structs)
                    print(f"  -> Found {len(structs)} known MP polymorphs for {formula}.")
                except Exception as e:
                    print(f"  -> Error querying {formula}: {e}")
                    candidate_dict[formula] = []
    else:
        print(f"Loading candidate structure(s) from {args.candidates}...")
        cand_path = Path(args.candidates)
        cand_list = []
        if cand_path.is_dir():
            for f in cand_path.rglob("*"):
                if f.is_file() and f.suffix.lower() in [".cif", ".xyz", ".poscar", ".vasp"]:
                    try:
                        stm = Structure.from_file(str(f))
                        stm.properties = stm.properties or {}
                        stm.properties["filename"] = f.name
                        cand_list.append(stm)
                    except:
                        pass
        else:
            try:
                stm = Structure.from_file(str(cand_path))
                stm.properties = stm.properties or {}
                stm.properties["filename"] = cand_path.name
                cand_list.append(stm)
            except Exception as e:
                print(f"Error reading candidates: {e}")
                
        for c in cand_list:
            form = c.composition.reduced_formula
            if form not in candidate_dict:
                candidate_dict[form] = []
            candidate_dict[form].append(c)
            num_candidates += 1
        print(f"Loaded {num_candidates} local candidate structure(s).")

    # 3. Match structures
    matcher = StructureMatcher(
        ltol=args.ltol,
        stol=args.stol,
        angle_tol=args.angle_tol,
        primitive_cell=True,
        scale=True,
        attempt_supercell=False,
        allow_subset=False
    )
    
    print("\nMatching structures...")
    all_results = []
    
    # Import literature fallback safely
    try:
        from src.utils.literature_utils import query_openalex
        has_lit_utils = True
    except ImportError:
        has_lit_utils = False

    for target in target_structs:
        target_id = get_identifier(target, "target")
        formula = target.composition.reduced_formula
        
        result = {
            "target": target_id,
            "target_formula": formula,
            "matches": [],
            "match_found": False
        }
        
        # Symmetry for fallback
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            sa = SpacegroupAnalyzer(target)
            sg_symbol = sa.get_space_group_symbol()
            crystal_system = sa.get_crystal_system()
            result["target_spacegroup"] = sg_symbol
            result["target_crystal_system"] = crystal_system
        except Exception:
            sg_symbol, crystal_system = "", ""
            result["target_spacegroup"], result["target_crystal_system"] = None, None
            
        candidates = candidate_dict.get(formula, [])
        for cand in candidates:
            if matcher.fit(target, cand):
                cand_id = get_identifier(cand, "candidate")
                result["matches"].append({
                    "candidate_id": cand_id,
                    "candidate_formula": cand.composition.reduced_formula
                })
                result["match_found"] = True
                
        status = "MATCHED" if result["match_found"] else "NOVEL"
        print(f"[{status}] {target_id} ({formula})")
        if result["match_found"]:
            for m in result["matches"]:
                print(f"  -> Matches: {m['candidate_id']}")
                
        # Literature fallback only if exactly ONE target is provided (to prevent spamming API on bulk runs)
        # OR if requested via a flag, but we'll stick to single-target rule for auto-fallback.
        if not result["match_found"] and len(target_structs) == 1 and has_lit_utils:
            if sg_symbol and crystal_system:
                query_str = f'"{formula}" AND ("{sg_symbol}" OR "{crystal_system}")'
                print(f"  -> Checking literature for '{formula}' with symmetry '{sg_symbol}'...")
            else:
                query_str = f'"{formula}"'
                print(f"  -> Checking literature for '{formula}'...")
                
            try:
                lit_results = query_openalex(query_str, limit=5)
                result["literature_reported"] = len(lit_results) > 0
                result["literature_matches"] = []
                if lit_results:
                    print(f"  -> Found {len(lit_results)} recent papers reporting it.")
                    for i, r in enumerate(lit_results, 1):
                        title, doi = r.get("title", "Unknown"), r.get("doi", "Unknown")
                        print(f"     [{i}] {title} ({doi})")
                        result["literature_matches"].append({"title": title, "doi": doi})
                else:
                    print("  -> No literature found. Truly novel.")
            except Exception as e:
                print(f"  -> Literature check failed: {e}")
                
        all_results.append(result)
        
    novel_count = sum(1 for r in all_results if not r["match_found"])
    print(f"\nTotal targets checked: {len(target_structs)}")
    print(f"Novel structures: {novel_count}")
    print(f"Matched structures: {len(target_structs) - novel_count}")
    
    with open(args.output, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"Results saved to {args.output}")

if __name__ == "__main__":
    main()
