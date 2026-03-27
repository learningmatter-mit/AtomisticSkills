#!/usr/bin/env python
"""
Extract MACE training history from the results directory.
Parses the training log to output standard `training_history.json` and optionally copies `training_history.png`.

Usage:
    python extract_mace_logs.py --results-dir path/to/results
"""

import os
import sys
import glob
import json
import argparse
import shutil
import ast

def main():
    parser = argparse.ArgumentParser(description="Extract MACE training history")
    parser.add_argument("--results-dir", required=True, help="Path to MACE results directory")
    args = parser.parse_args()

    results_dir = args.results_dir
    if not os.path.exists(results_dir):
        print(f"Error: Directory {results_dir} not found.")
        sys.exit(1)

    # Find the training logtxt
    txt_files = glob.glob(os.path.join(results_dir, "*_train.txt"))
    if not txt_files:
        print(f"Error: No training txt found in {results_dir}")
        sys.exit(1)
        
    log_file = max(txt_files, key=os.path.getctime)
    
    # Also find the training plot
    png_files = glob.glob(os.path.join(results_dir, "*_train_*.png"))
    
    output_dir = os.path.dirname(results_dir)
    json_path = os.path.join(output_dir, "training_history.json")
    png_path = os.path.join(output_dir, "training_history.png")
    
    history = {
        'loss_train': [],
        'loss_val': [],
        'energy_mae_train': [],
        'energy_mae_val': [],
        'force_mae_train': [],
        'force_mae_val': [],
        'stress_mae_train': [],
        'stress_mae_val': [],
        'energy_rmse_train': [],
        'energy_rmse_val': [],
        'force_rmse_train': [],
        'force_rmse_val': [],
        'stress_rmse_train': [],
        'stress_rmse_val': [],
        'epoch': []
    }
    
    current_epoch_train_losses = []

    import ast
    
    # Add project root to path for imports
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    try:
        from src.utils.mlips.plot_utils import plot_training_history
        can_plot = True
    except ImportError as e:
        can_plot = False
        print(f"Warning: Could not import plot_training_history. Error: {e}")

    with open(log_file, 'r') as f:
        for line in f:
            if '{' not in line:
                continue
                
            try:
                line_dict_str = line[line.find('{'):line.rfind('}')+1]
                data = json.loads(line_dict_str)
            except:
                try:
                    data = ast.literal_eval(line_dict_str)
                except:
                    continue
                    
            mode = data.get('mode')
            raw_epoch = data.get('epoch')
            
            # MACE logs pre-training eval as epoch=None. We will map this to 0.
            if mode == 'eval' and raw_epoch is None:
                epoch = 0
            else:
                epoch = raw_epoch
            
            if mode == 'opt' and epoch is not None:
                current_epoch_train_losses.append(data.get('loss', 0.0))
            elif mode == 'eval' and epoch is not None:
                # End of epoch evaluation (or initial evaluation at epoch 0)
                history['epoch'].append(epoch)
                
                # Average train loss (will be 0.0 for initial epoch 0)
                if epoch == 0:
                    avg_train_loss = None
                else:
                    avg_train_loss = sum(current_epoch_train_losses) / len(current_epoch_train_losses) if current_epoch_train_losses else 0.0
                history['loss_train'].append(avg_train_loss)
                current_epoch_train_losses = [] # reset for next epoch
                
                history['loss_val'].append(data.get('loss', None))
                
                # MAE Extraction
                e_mae = data.get('mae_e_per_atom', data.get('mae_e'))
                history['energy_mae_val'].append(e_mae * 1000 if e_mae is not None else None)
                f_mae = data.get('mae_f')
                history['force_mae_val'].append(f_mae * 1000 if f_mae is not None else None)
                s_mae = data.get('mae_stress')
                history['stress_mae_val'].append(s_mae * 1000 if s_mae is not None else None)
                
                history['energy_mae_train'].append(None)
                history['force_mae_train'].append(None)
                history['stress_mae_train'].append(None)
                
                # RMSE Extraction
                e_rmse = data.get('rmse_e_per_atom', data.get('rmse_e'))
                history['energy_rmse_val'].append(e_rmse * 1000 if e_rmse is not None else None)
                f_rmse = data.get('rmse_f')
                history['force_rmse_val'].append(f_rmse * 1000 if f_rmse is not None else None)
                s_rmse = data.get('rmse_stress')
                history['stress_rmse_val'].append(s_rmse * 1000 if s_rmse is not None else None)
                
                history['energy_rmse_train'].append(None)
                history['force_rmse_train'].append(None)
                history['stress_rmse_train'].append(None)

    with open(json_path, 'w') as f:
        json.dump(history, f, indent=4)
        print(f"Saved history to {json_path}")
        
    if can_plot:
        try:
            from src.utils.mlips.plot_utils import plot_training_history
            plot_training_history(history, save_path=png_path, show=False, model_name="MACE Fine-tune")
            print(f"Generated standardized training plot at {png_path}")
        except Exception as e:
            print(f"Could not generate training plot: {e}")

if __name__ == "__main__":
    main()
