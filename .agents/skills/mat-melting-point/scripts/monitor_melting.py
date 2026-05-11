import argparse
import time
import os
import sys
import numpy as np
import pandas as pd
import subprocess

def monitor_melting(log_path, analysis_window_ps=1.0, stability_duration_ps=5.0, timestep_fs=1.0, stop_file="MD_STOP"):
    """
    Monitor MD log for stability in T and Epot.
    Instead of fixed tolerance, check if the standard deviation of T and Epot 
    (calculated over analysis_window_ps) stabilizes/flattens over stability_duration_ps.
    """
    print(f"Monitoring {log_path}...")
    print(f"Analysis Window: {analysis_window_ps}ps")
    print(f"Stability Duration: {stability_duration_ps}ps (checking for flattened StdDev)")
    
    # History of (time, std_t, std_epot)
    stats_history = []
    
    # Wait for file
    timeout = 60
    start_wait = time.time()
    while not os.path.exists(log_path):
        if time.time() - start_wait > timeout:
            print(f"Timeout waiting for {log_path}")
            return
        time.sleep(1)

    print(f"Found log file. Watching...")
    
    while True:
        try:
            if not os.path.exists(log_path):
                 time.sleep(1)
                 continue

            try:
                df = pd.read_csv(log_path, sep=r'\s+', comment='-')
            except Exception:
                time.sleep(1)
                continue
                
            if df.empty or len(df) < 5:
                time.sleep(1)
                continue
                
            # Identify columns
            cols = [c for c in df.columns]
            t_col = next((c for c in cols if 'Time' in c), None)
            temp_col = next((c for c in cols if 'T[K]' in c or 'Temp' in c), None)
            epot_col = next((c for c in cols if 'PE' in c or 'Epot' in c), None)
            
            if not t_col or not temp_col or not epot_col:
                time.sleep(1)
                continue

            # Get full data arrays
            times = df[t_col].values
            temps = df[temp_col].values
            epots = df[epot_col].values
            
            current_time = times[-1]
            
            # --- 1. Calculate current local StdDev over analysis_window ---
            start_window = current_time - analysis_window_ps
            mask = times >= start_window
            win_temps = temps[mask]
            win_epots = epots[mask]
            
            if len(win_temps) < 10:
                time.sleep(1)
                continue
                
            curr_std_t = np.std(win_temps)
            curr_std_epot = np.std(win_epots)
            
            # Append to history
            stats_history.append({
                "time": current_time,
                "std_t": curr_std_t,
                "std_epot": curr_std_epot
            })
            
            # --- 2. Check Trend over Stability Duration ---
            
            # Filter stats history to keep only last stability_duration_ps
            cutoff_time = current_time - stability_duration_ps
            recent_stats = [s for s in stats_history if s["time"] >= cutoff_time]
            
            # Prune main list to avoid infinite growth
            stats_history = recent_stats 
            
            # Check if we have enough time span coverage
            if len(recent_stats) > 2:
                span = recent_stats[-1]["time"] - recent_stats[0]["time"]
            else:
                span = 0
            
            msg = f"Time: {current_time:.2f}ps | Std(T): {curr_std_t:.2f}K | Std(E): {curr_std_epot:.4f}eV"
            
            if span >= (stability_duration_ps * 0.9):
                # Calculate variation of the StdDevs over this period
                std_t_values = np.array([s["std_t"] for s in recent_stats])
                std_e_values = np.array([s["std_epot"] for s in recent_stats])
                
                # Check 1: Is the StdDev flattening? (Low variance/RSD of the StdDev itself)
                mean_std_t = np.mean(std_t_values)
                rsd_std_t = np.std(std_t_values) / (mean_std_t + 1e-6) # Avoid div/0
                
                mean_std_e = np.mean(std_e_values)
                rsd_std_e = np.std(std_e_values) / (mean_std_e + 1e-6)
                
                # Thresholds for "flatness" of the noise profile (15%)
                STABILITY_RSD_THRESHOLD = 0.15
                
                msg += f" | RSD_Std(T): {rsd_std_t:.2f} | RSD_Std(E): {rsd_std_e:.2f}"
                print(msg)
                
                # USER REQUEST: Stop if temp std < 50
                if curr_std_t < 50.0:
                    print(f"STABILITY REACHED at {current_time:.2f}ps (Temp StdDev {curr_std_t:.2f} < 50)")
                    print("Attempting to terminate MD process...")
                    
                    # Try to find MD.pid file
                    log_dir = os.path.dirname(os.path.abspath(log_path))
                    pid_file = os.path.join(log_dir, "MD.pid")
                    
                    pid = None
                    if os.path.exists(pid_file):
                        try:
                            with open(pid_file, "r") as f:
                                pid = int(f.read().strip())
                        except Exception as pe:
                            print(f"Error reading PID file: {pe}")
                    
                    if pid:
                        print(f"Reading PID {pid} from {pid_file}")
                        if pid != os.getpid():
                            print(f"Killing process {pid}...")
                            try:
                                os.kill(pid, 15) # SIGTERM
                                time.sleep(1)
                                try:
                                    os.kill(pid, 0) # Check if alive
                                    print(f"Process {pid} still alive, sending SIGKILL...")
                                    os.kill(pid, 9)
                                except OSError:
                                    pass # Process dead
                            except Exception as k_err:
                                print(f"Kill failed: {k_err}")
                        else:
                            print("PID in file matches monitor PID! Skipping kill.")
                    else:
                        print(f"Could not find PID file at {pid_file}. Attempting lsof fallback...")
                        try:
                            pid_bytes = subprocess.check_output(["lsof", "-t", log_path])
                            pids = pid_bytes.decode().strip().split('\n')
                            for pid_str in pids:
                                if not pid_str: continue
                                pid_l = int(pid_str)
                                if pid_l == os.getpid(): continue
                                print(f"Killing process {pid_l} (lsof)...")
                                os.kill(pid_l, 15)
                        except Exception as k_err:
                            print(f"Fallback kill failed: {k_err}. Please stop manually.")
                    return
            else:
                 print(msg + " (Accumulating history...)")

            time.sleep(2)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_path")
    parser.add_argument("--window", type=float, default=1.0, help="Window to calc local StdDev (ps)")
    parser.add_argument("--stability_duration", type=float, default=5.0, help="Duration StdDev must be flat (ps)")
    parser.add_argument("--stop_file", default="MD_STOP")
    
    args = parser.parse_args()
    
    monitor_melting(args.log_path, analysis_window_ps=args.window, stability_duration_ps=args.stability_duration, stop_file=args.stop_file)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
