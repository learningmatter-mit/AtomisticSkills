import argparse
import json
import logging
import os
import matplotlib.pyplot as plt
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_parity_plot(preds, targets, title, unit, mae, rmse, save_path):
    if not preds or not targets:
         return
    
    p = np.array(preds).flatten()
    t = np.array(targets).flatten()
    
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # Scatter points
    # Alpha proportional to density could be nice, but simple alpha works
    ax.scatter(t, p, alpha=0.5, marker="o", edgecolors="none")
    
    # Parity diagonal
    min_val = min(np.min(t), np.min(p))
    max_val = max(np.max(t), np.max(p))
    ax.plot([min_val, max_val], [min_val, max_val], "k--", linewidth=1.5)

    # Annotations
    text_str = f"MAE: {mae:.3f} {unit}\nRMSE: {rmse:.3f} {unit}"
    props = dict(boxstyle="round", facecolor="white", alpha=0.8)
    ax.text(0.05, 0.95, text_str, transform=ax.transAxes, fontsize=12,
            verticalalignment="top", bbox=props)
            
    # Labels
    ax.set_title(f"{title} Parity Plot")
    ax.set_xlabel(f"Ground Truth ({unit})")
    ax.set_ylabel(f"Prediction ({unit})")
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved plot: {save_path}")

def main():
    parser = argparse.ArgumentParser(description="Plot parity graphs from MLIP benchmark")
    parser.add_argument("--results", type=str, required=True, help="benchmark_results.json file")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save plots")
    
    args = parser.parse_args()
    
    with open(args.results, "r") as f:
        res = json.load(f)
        
    metrics = res.get("metrics", {})
    pts = res.get("data_points", [])
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Aggregate data
    all_energy_p, all_energy_t = [], []
    all_forces_p, all_forces_t = [], []
    all_stress_p, all_stress_t = [], []
    
    for dp in pts:
        if "energy_target" in dp and "energy_pred" in dp:
             all_energy_t.append(dp["energy_target"])
             all_energy_p.append(dp["energy_pred"])
        if "forces_target" in dp and "forces_pred" in dp:
             all_forces_t.extend(np.array(dp["forces_target"]).flatten())
             all_forces_p.extend(np.array(dp["forces_pred"]).flatten())
        if "stress_target" in dp and "stress_pred" in dp:
             all_stress_t.extend(np.array(dp["stress_target"]).flatten())
             all_stress_p.extend(np.array(dp["stress_pred"]).flatten())
             
    # Plot Energy
    e_metrics = metrics.get("energy")
    if e_metrics and all_energy_p:
        # Convert Energy to meV/atom for better readability in plots
        mae_mev = e_metrics["mae"] * 1000.0
        rmse_mev = e_metrics["rmse"] * 1000.0
        create_parity_plot(
            [e * 1000.0 for e in all_energy_p], [e * 1000.0 for e in all_energy_t],
             "Energy (per atom)", "meV/atom", mae_mev, rmse_mev, 
             os.path.join(args.output_dir, "parity_energy.png")
        )

    # Plot Forces
    f_metrics = metrics.get("forces")
    if f_metrics and all_forces_p:
        mae_f_mev = f_metrics["mae"] * 1000.0
        rmse_f_mev = f_metrics["rmse"] * 1000.0
        create_parity_plot(
            [f * 1000.0 for f in all_forces_p], [f * 1000.0 for f in all_forces_t],
             "Forces", "meV/Å", mae_f_mev, rmse_f_mev, 
             os.path.join(args.output_dir, "parity_forces.png")
        )
        
    # Plot Stress
    s_metrics = metrics.get("stress")
    if s_metrics and all_stress_p:
        mae_s = s_metrics["mae"]
        rmse_s = s_metrics["rmse"]
        create_parity_plot(
            all_stress_p, all_stress_t,
             "Stress", "eV/Å³", mae_s, rmse_s, 
             os.path.join(args.output_dir, "parity_stress.png")
        )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

if __name__ == "__main__":
    main()
