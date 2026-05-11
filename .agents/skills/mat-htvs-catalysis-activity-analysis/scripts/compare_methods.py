import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.stats import spearmanr

def parse_args():
    parser = argparse.ArgumentParser(description="Compare Catalysis Prescreening Data vs Verification Data")
    parser.add_argument('--base_data', type=str, required=True, help="Path to base CSV (e.g. DFT)")
    parser.add_argument('--target_data', type=str, required=True, help="Path to target CSV (e.g. MLIP)")
    parser.add_argument('--output_dir', type=str, default='.', help="Directory to save plots")
    parser.add_argument('--base_label', type=str, default='DFT', help="Label for base data (X-axis)")
    parser.add_argument('--target_label', type=str, default='MLIP', help="Label for target data (Y-axis)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Load datasets
    df_base = pd.read_csv(args.base_data)
    df_target = pd.read_csv(args.target_data)
    
    # Merge datasets to ensure 1-to-1 matching based on surface_id
    df_merged = pd.merge(df_target, df_base, on='surface_id', suffixes=('_target', '_base'))
    
    if len(df_merged) == 0:
        print("Error: No matching surface_ids found between datasets.")
        return
        
    print(f"Comparing {len(df_merged)} overlapping surface facets.")
    
    # --- OPTION 1: Binding Energy Parity Plot ---
    fig_be, ax_be = plt.subplots(figsize=(7, 6))
    
    species = ['OH', 'O', 'OOH']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    markers = ['o', 's', '^']
    
    all_target_be = []
    all_base_be = []
    
    for i, spec in enumerate(species):
        if f'dG_{spec}_target' not in df_merged.columns or f'dG_{spec}_base' not in df_merged.columns:
            continue
            
        target_vals = df_merged[f'dG_{spec}_target'].values
        base_vals = df_merged[f'dG_{spec}_base'].values
        
        all_target_be.extend(target_vals)
        all_base_be.extend(base_vals)
        
        mae = np.mean(np.abs(base_vals - target_vals))
        
        ax_be.scatter(base_vals, target_vals, color=colors[i], marker=markers[i], 
                      s=60, alpha=0.7, edgecolors='white', linewidth=0.5,
                      label=f'${spec}^*$ (MAE: {mae:.2f} eV)')
    
    if all_target_be and all_base_be:
        all_base_be = np.array(all_base_be)
        all_target_be = np.array(all_target_be)
        overall_mae = np.mean(np.abs(all_base_be - all_target_be))
        overall_rmse = np.sqrt(np.mean((all_base_be - all_target_be)**2))
        
        min_val = min(min(all_target_be), min(all_base_be)) - 0.5
        max_val = max(max(all_target_be), max(all_base_be)) + 0.5
        ax_be.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.5)
        
        ax_be.set_xlim(min_val, max_val)
        ax_be.set_ylim(min_val, max_val)
        ax_be.set_xlabel(f'{args.base_label} $\\Delta G$ (eV)', fontweight='bold', fontsize=12)
        ax_be.set_ylabel(f'{args.target_label} $\\Delta G$ (eV)', fontweight='bold', fontsize=12)
        
        metrics_text = f'Overall MAE: {overall_mae:.2f} eV\nRMSE: {overall_rmse:.2f} eV'
        ax_be.text(0.05, 0.95, metrics_text, transform=ax_be.transAxes, 
                   fontsize=12, verticalalignment='top', 
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        ax_be.grid(True, linestyle='--', alpha=0.6)
        ax_be.legend(frameon=False, fontsize=11, loc='lower right')
        
        plt.tight_layout()
        os.makedirs(args.output_dir, exist_ok=True)
        out_be = os.path.join(args.output_dir, 'parity_binding.png')
        fig_be.savefig(out_be, dpi=300, bbox_inches='tight')
        plt.close(fig_be)
        print(f"Saved {out_be} (MAE: {overall_mae:.3f} eV)")
    
    # --- OPTION 2: Overpotential & Rank Correlation ---
    if 'overpotential_target' in df_merged.columns and 'overpotential_base' in df_merged.columns:
        fig_act, ax_act = plt.subplots(figsize=(7, 6))
        
        target_eta = df_merged['overpotential_target'].values
        base_eta = df_merged['overpotential_base'].values
        
        mae_eta = np.mean(np.abs(base_eta - target_eta))
        
        # Calculate Spearman Rank Correlation
        spearman_corr, p_value = spearmanr(base_eta, target_eta)
        
        ax_act.scatter(base_eta, target_eta, color='#9467bd', marker='D',
                       s=80, alpha=0.7, edgecolors='white', linewidth=0.5)
        
        min_eta = min(min(target_eta), min(base_eta)) - 0.2
        max_eta = max(max(target_eta), max(base_eta)) + 0.2
        ax_act.plot([min_eta, max_eta], [min_eta, max_eta], 'k--', alpha=0.5)
        
        ax_act.set_xlim(min_eta, max_eta)
        ax_act.set_ylim(min_eta, max_eta)
        ax_act.set_xlabel(f'{args.base_label} $\\eta$ (V)', fontweight='bold', fontsize=12)
        ax_act.set_ylabel(f'{args.target_label} $\\eta$ (V)', fontweight='bold', fontsize=12)
        
        metrics_text_act = f'MAE: {mae_eta:.2f} V\nSpearman $\\rho$: {spearman_corr:.2f}'
        ax_act.text(0.05, 0.95, metrics_text_act, transform=ax_act.transAxes, 
                    fontsize=12, verticalalignment='top', 
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                    
        ax_act.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        out_act = os.path.join(args.output_dir, 'parity_activity.png')
        fig_act.savefig(out_act, dpi=300, bbox_inches='tight')
        plt.close(fig_act)
        print(f"Saved {out_act} (Spearman Rank: {spearman_corr:.3f})")

if __name__ == "__main__":
    main()
