import argparse
import json
import logging
import os
import sys
import numpy as np

# ensure we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from pymatgen.core import Structure

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def evaluate_metrics(preds, targets):
    p = np.array(preds).flatten()
    t = np.array(targets).flatten()
    if len(p) == 0 or len(t) == 0:
        return {"mae": 0.0, "rmse": 0.0}
    mae = np.mean(np.abs(p - t))
    rmse = np.sqrt(np.mean((p - t)**2))
    return {"mae": float(mae), "rmse": float(rmse)}

def main():
    parser = argparse.ArgumentParser(description="Evaluate MLIP over labeled dataset")
    parser.add_argument("--data_path", type=str, required=True, help="Path to JSON with labeled data")
    parser.add_argument("--model", type=str, required=True, help="Path or name of the model")
    parser.add_argument("--backend", type=str, required=True, choices=["mace", "fairchem", "matgl"])
    parser.add_argument("--task_name", type=str, default=None, help="Optional task name (omat_pbe, oc20, etc.)")
    parser.add_argument("--output", type=str, required=True, help="Output JSON for metrics and parity data")
    parser.add_argument("--vasp-stress-conversion", action="store_true", help="If flag is present, multiplies target stress arrays by -1/1602.1766208 to convert from kB (VASP) to eV/Å³")
    
    args = parser.parse_args()
    
    logger.info(f"Loading data from {args.data_path}...")
    with open(args.data_path, "r") as f:
        dataset = json.load(f)
    
    if not dataset:
        logger.error("Empty dataset provided.")
        sys.exit(1)
        
    logger.info(f"Loading {args.backend} model: {args.model}...")
    from src.utils.mlips.loader import load_wrapper
    wrapper = load_wrapper(args.backend, args.model, device="cuda", task_name=args.task_name, use_mcp_config=False)
    
    all_energy_preds = []
    all_energy_targs = []
    all_forces_preds = []
    all_forces_targs = []
    all_stress_preds = []
    all_stress_targs = []
    
    valid_data = []

    for i, data in enumerate(dataset):
        struct_data = data.get("structure") or data.get("atoms")
        targ_e_raw = data.get("energy") if data.get("energy") is not None else data.get("vasp_e")
        targ_f_raw = data.get("forces") if data.get("forces") is not None else data.get("vasp_f")
        targ_s_raw = data.get("stress") if data.get("stress") is not None else data.get("vasp_s")
        
        if struct_data is None or (targ_e_raw is None and targ_f_raw is None):
            continue
            
        system = Structure.from_dict(struct_data)
        num_atoms = len(system)
        
        try:
            pred = wrapper.static_calculation(system)
        except Exception as e:
            logger.warning(f"Prediction failed for structure {i}: {e}")
            continue

        valid_point = {"id": i, "num_atoms": num_atoms}
        
        # Energy
        if targ_e_raw is not None:
            # We standardize to energy per atom for comparison
            # targ_e_raw is typically total energy string or float
            targ_e = float(targ_e_raw) / num_atoms
            pred_e = float(pred["energy"]) / num_atoms
            all_energy_targs.append(targ_e)
            all_energy_preds.append(pred_e)
            valid_point["energy_target"] = targ_e
            valid_point["energy_pred"] = pred_e
            
        # Forces
        if targ_f_raw is not None:
            targ_f = np.array(targ_f_raw)
            pred_f = np.array(pred["forces"])
            if targ_f.shape == pred_f.shape:
                all_forces_targs.extend(targ_f.flatten())
                all_forces_preds.extend(pred_f.flatten())
                valid_point["forces_target"] = targ_f.tolist()
                valid_point["forces_pred"] = pred_f.tolist()
                
        # Stress
        if targ_s_raw is not None and "stress" in pred and pred["stress"] is not None:
            targ_s = np.array(targ_s_raw)
            if args.vasp_stress_conversion:
                targ_s = targ_s * (-1.0 / 1602.1766208)
            pred_s = np.array(pred["stress"])
            
            # Convert 3x3 to 6-element Voigt if necessary
            def to_voigt(s):
                s = np.array(s)
                if s.shape == (3, 3):
                    return np.array([s[0,0], s[1,1], s[2,2], s[1,2], s[0,2], s[0,1]])
                return s
                
            targ_s_6 = to_voigt(targ_s)
            pred_s_6 = to_voigt(pred_s)
            
            if targ_s_6.shape == pred_s_6.shape:
                all_stress_targs.extend(targ_s_6.tolist())
                all_stress_preds.extend(pred_s_6.tolist())
                valid_point["stress_target"] = targ_s_6.tolist()
                valid_point["stress_pred"] = pred_s_6.tolist()
            
        valid_data.append(valid_point)

    logger.info("Computing validation metrics...")
    
    metrics = {
        "energy": evaluate_metrics(all_energy_preds, all_energy_targs) if all_energy_preds else None,
        "forces": evaluate_metrics(all_forces_preds, all_forces_targs) if all_forces_preds else None,
        "stress": evaluate_metrics(all_stress_preds, all_stress_targs) if all_stress_preds else None
    }
    
    logger.info(f"Energy Metrics (eV/atom): {metrics['energy']}")
    logger.info(f"Forces Metrics (eV/Å):    {metrics['forces']}")
    if metrics['stress']:
         logger.info(f"Stress Metrics (eV/Å^3):  {metrics['stress']}")

    results = {
        "metrics": metrics,
        "data_points": valid_data
    }
    
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
        
    logger.info(f"Benchmark completed successfully. Saved to {args.output}")

if __name__ == "__main__":
    main()
