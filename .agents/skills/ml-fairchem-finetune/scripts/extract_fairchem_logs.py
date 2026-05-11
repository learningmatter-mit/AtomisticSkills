#!/usr/bin/env python
"""
Extract training metrics from Fairchem CLI output log and save as JSON and plot.

Usage:
    python extract_fairchem_logs.py --log fairchem_cli_output.log --task-name omat --output-dir ./results
"""

import argparse
import ast
import json
import logging
import os
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
from utils.mlips.plot_utils import plot_training_history

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def parse_fairchem_cli_metrics(cli_output_text: str, task_name: str) -> dict:
    """Parse fairchem CLI stdout/stderr to extract training metrics."""
    history = {
        "epoch": [],
        "loss_train": [],
        "loss_val": [],
        "energy_mae_train": [],
        "energy_mae_val": [],
        "force_mae_train": [],
        "force_mae_val": [],
        "stress_mae_train": [],
        "stress_mae_val": [],
        "energy_rmse_train": [],
        "energy_rmse_val": [],
        "force_rmse_train": [],
        "force_rmse_val": [],
        "stress_rmse_train": [],
        "stress_rmse_val": [],
    }
    
    current_train_loss = None
    current_val_metrics = {}
    epoch_count = 0
    
    for line in cli_output_text.split("\n"):
        line = line.strip()
        
        train_dict_match = re.search(r"INFO:root:(\{'train/loss':.+\})", line)
        if train_dict_match:
            dict_str = train_dict_match.group(1)
            try:
                metrics = ast.literal_eval(dict_str)
                current_train_loss = metrics.get("train/loss")
            except (ValueError, SyntaxError):
                pass
            
            # If we have validation metrics and haven't saved epoch 0 yet, this means 
            # we just finished an initial evaluation and are starting training!
            if epoch_count == 0 and current_val_metrics and "loss_val" in current_val_metrics:
                history["epoch"].append(0)
                history["loss_train"].append(None)
                for key in history:
                    if key in ("epoch", "loss_train"): continue
                    history[key].append(current_val_metrics.get(key, None))
                epoch_count = 1
                current_val_metrics = {}
                
            continue
        
        val_loss_match = re.search(r"val/loss:\s*([\d.eE+-]+)", line)
        if val_loss_match:
            current_val_metrics["loss_val"] = float(val_loss_match.group(1))
        
        # MAE Matching
        energy_match = re.search(rf"val/{re.escape(task_name)}\.val,energy,per_atom_mae:\s*([\d.eE+-]+)", line)
        if energy_match:
            current_val_metrics["energy_mae_val"] = float(energy_match.group(1)) * 1000
        
        forces_match = re.search(rf"val/{re.escape(task_name)}\.val,forces,mae:\s*([\d.eE+-]+)", line)
        if forces_match:
            current_val_metrics["force_mae_val"] = float(forces_match.group(1)) * 1000
        
        stress_match = re.search(rf"val/{re.escape(task_name)}\.val,stress,mae:\s*([\d.eE+-]+)", line)
        if stress_match:
            current_val_metrics["stress_mae_val"] = float(stress_match.group(1)) * 1000
            
        # RMSE Matching if available
        energy_rmse_match = re.search(rf"val/{re.escape(task_name)}\.val,energy,per_atom_rmse:\s*([\d.eE+-]+)", line)
        if energy_rmse_match:
            current_val_metrics["energy_rmse_val"] = float(energy_rmse_match.group(1)) * 1000
        
        forces_rmse_match = re.search(rf"val/{re.escape(task_name)}\.val,forces,rmse:\s*([\d.eE+-]+)", line)
        if forces_rmse_match:
            current_val_metrics["force_rmse_val"] = float(forces_rmse_match.group(1)) * 1000
            
        stress_rmse_match = re.search(rf"val/{re.escape(task_name)}\.val,stress,rmse:\s*([\d.eE+-]+)", line)
        if stress_rmse_match:
            current_val_metrics["stress_rmse_val"] = float(stress_rmse_match.group(1)) * 1000
        
        if "Ended train epoch" in line and current_val_metrics:
            history["epoch"].append(epoch_count)
            history["loss_train"].append(current_train_loss)
            for key in history:
                if key in ("epoch", "loss_train"):
                    continue
                history[key].append(current_val_metrics.get(key, None))
            epoch_count += 1
            current_train_loss = None
            current_val_metrics = {}
    
    if current_val_metrics:
        history["epoch"].append(epoch_count)
        history["loss_train"].append(current_train_loss)
        for key in history:
            if key in ("epoch", "loss_train"):
                continue
            history[key].append(current_val_metrics.get(key, None))
            
    return history





def main():
    parser = argparse.ArgumentParser("Extract MACE logs and plot training history")
    parser.add_argument("--log", required=True, help="Path to MACE (or Fairchem) output log file")
    parser.add_argument("--task-name", default="omat", help="Task name used (omat/omol)")
    parser.add_argument("--output-dir", default="./results", help="Directory to save history json and plot")
    
    args = parser.parse_args()
    log_path = Path(args.log)
    
    if not log_path.exists():
        logging.error(f"Log file {log_path} not found.")
        sys.exit(1)
        
    with open(log_path, "r") as f:
        log_text = f.read()
        
    history = parse_fairchem_cli_metrics(log_text, args.task_name)
    
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = out_dir / "training_history.json"
    with open(json_path, "w") as f:
        json.dump(history, f, indent=2)
    logging.info(f"Training history saved to {json_path}")
    
    plot_path = out_dir / "training_history.png"
    plot_training_history(history, save_path=str(plot_path), show=False, model_name="FairChem (UMA)")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
