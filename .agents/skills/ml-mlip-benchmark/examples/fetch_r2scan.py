import os
import json
from mp_api.client import MPRester
from typing import List, Dict

def fetch_r2scan_data(limit=100):
    dataset = []
    
    with MPRester() as mpr:
        print("Querying MP API for r2SCAN Thermo Documents...")
        try:
            thermo_docs = mpr.materials.thermo.search(
                thermo_types=["R2SCAN"],
                fields=["material_id", "uncorrected_energy_per_atom"],
                chunk_size=400,
                num_chunks=1
            )
            
            energy_map = {str(d.material_id): d.uncorrected_energy_per_atom for d in thermo_docs}
            mat_ids = list(energy_map.keys())
            
            print(f"Fetching structures for {len(mat_ids)} materials...")
            struct_docs = mpr.materials.summary.search(
                material_ids=mat_ids,
                fields=["material_id", "structure", "nsites"],
                chunk_size=len(mat_ids),
                num_chunks=1
            )
            
            for doc in struct_docs:
                if len(dataset) >= limit:
                    break
                    
                mp_id = str(doc.material_id)
                struct = doc.structure
                nsites = doc.nsites
                e_per_atom = energy_map.get(mp_id)
                
                if struct and e_per_atom is not None:
                    # Filter out Lanthanoids and Actinoids (f-block)
                    has_f_block = any(e.is_lanthanoid or e.is_actinoid for e in struct.composition.elements)
                    if has_f_block:
                        continue
                        
                    total_energy = e_per_atom * nsites
                    dataset.append({
                        "task_id": mp_id,
                        "structure": struct.as_dict(),
                        "energy": float(total_energy)
                    })
                    
            print(f"Successfully collected {len(dataset)} valid r2SCAN structures.")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error querying API: {e}")
            
    out_path = os.path.join(os.path.dirname(__file__), "r2scan_data.json")
    with open(out_path, "w") as f:
        json.dump(dataset, f)
    print(f"Saved dataset to {out_path}")

if __name__ == "__main__":
    fetch_r2scan_data(100)
