#!/usr/bin/env python
import os
import sys
import argparse
import time
import logging
import subprocess
from datetime import datetime

# Robustly detect project root relative to this script:
script_path = os.path.abspath(__file__)
# .agents/skills/mat-htvs-autopilot/scripts/run_autopilot.py -> 5 levels up
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_path)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import workflows and base
try:
    from workflows import WORKFLOW_REGISTRY
except ImportError:
    # If running from within scripts directory
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from workflows import WORKFLOW_REGISTRY

# Define logger at module level, but configure in main()
logger = logging.getLogger(__name__)

def ping_completion():
    """Signals completion via terminal bell and high-visibility alert."""
    alert = """
    ************************************************************
    *                                                          *
    *        🚀 HTVS AUTO-PILOT CAMPAIGN COMPLETE! 🚀          *
    *                                                          *
    *   Your final analysis results are ready for review.      *
    *                                                          *
    ************************************************************
    """
    print(alert)
    sys.stdout.write('\a')
    sys.stdout.flush()
    try:
        subprocess.run(["notify-send", "HTVS Auto-Pilot", "Campaign Complete!"], check=False)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="HTVS General-Purpose Auto-Pilot Orchestrator")
    parser.add_argument("--group_name", required=True, help="HTVS Project Group Name")
    parser.add_argument("--settings", required=True, help="Django settings module (e.g. djangochem.settings.toy)")
    parser.add_argument("--completed_path", required=True, help="Path to completed jobs directory")
    parser.add_argument("--workflow", default="task", choices=list(WORKFLOW_REGISTRY.keys()), help="Workflow plugin to run")
    parser.add_argument("--task_file", type=str, help="Path to a JSON/YAML task file for declarative workflows")
    parser.add_argument("--poll_interval", type=int, default=600, help="Polling interval in seconds (default: 600)")
    parser.add_argument("--research_dir", type=str, default=".", help="Research directory for outputs")
    parser.add_argument("--reaction", type=str, help="Specific reaction variable")
    parser.add_argument("--tmux", type=str, help="Launch autopilot in a detached tmux session with the given name")
    parser.add_argument("--status_file", type=str, default="autopilot_status.txt", help="Filename to output clean status snapshot")
    
    args = parser.parse_args()

    # Handle tmux spawning before any heavy initialization
    if args.tmux:
        session_name = args.tmux
        # Reconstruct the command without the --tmux flag
        cmd_parts = [sys.executable, os.path.abspath(__file__)]
        for action in parser._actions:
            if action.dest == "tmux" or action.dest == "help":
                continue
            val = getattr(args, action.dest)
            if val is not None:
                if action.dest == "workflow" and val == "task" and "--workflow" not in sys.argv:
                    continue # skip default if not explicitly passed
                cmd_parts.extend([action.option_strings[0], str(val)])
                
        cmd_str = " ".join(cmd_parts)
        print(f"🚀 Spawning HTVS Auto-Pilot in tmux session: {session_name}")
        try:
            subprocess.run(["tmux", "new-session", "-d", "-s", session_name, cmd_str], check=True)
            print(f"✅ Successfully launched in background.")
            print(f"👉 To attach to the session, run: tmux attach -t {session_name}")
            print(f"👉 Quick status check: cat {os.path.join(args.research_dir, args.status_file)}")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Failed to launch tmux: {e}")
            sys.exit(1)

    # Set up logging to both console and research directory
    log_file = os.path.join(args.research_dir, "autopilot_orchestrator.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )
    logger = logging.getLogger(__name__)
    python_exe = sys.executable

    logger.info("="*50)
    logger.info(f"HTVS DECLARATIVE AUTO-PILOT INITIATED")
    logger.info(f"Group: {args.group_name} | Workflow: {args.workflow}")
    logger.info(f"Settings: {args.settings}")
    if args.task_file:
        logger.info(f"Task File: {args.task_file}")
    logger.info("="*50)

    # --- STAGE 0: WORKFLOW INITIALIZATION ---
    workflow_cls = WORKFLOW_REGISTRY.get(args.workflow)
    if not workflow_cls:
        logger.error(f"Unknown workflow: {args.workflow}")
        sys.exit(1)
    
    # Load task data if provided
    task_data = {}
    if args.task_file:
        import json
        try:
            with open(args.task_file, 'r') as f:
                task_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load task file {args.task_file}: {e}")
            sys.exit(1)
    
    # Extract variables for interpolation
    variables = vars(args)
    variables.update(task_data.get("vars", {}))

    # Initialize workflow instance
    workflow = workflow_cls(args.settings, args.group_name, args.research_dir)
    if hasattr(workflow, "set_task"):
        workflow.set_task(task_data, variables)

    logger.info(f"--- STAGE 0: PRE-FLIGHT CHECK ({args.workflow}) ---")
    if not workflow.pre_flight_check():
        logger.error(f"PRE-FLIGHT FAILED for workflow '{args.workflow}'. Aborting.")
        sys.exit(1)

    # --- STAGE 1: MONITOR & PARSE LOOP ---
    logger.info("--- STAGE 1: MONITOR & PARSE LOOP ---")
    while True:
        counts = workflow.get_job_counts()
        pending_count = counts["pending"]
        done_count = counts["done"]
        total_count = counts["total"]
        
        logger.info(f"STATUS: {done_count}/{total_count} jobs 'done'. ({pending_count} pending)")
        
        if total_count > 0 and pending_count == 0:
            logger.info("MONITOR: All jobs in group are marked 'done'. Proceeding to final steps.")
            break
        elif total_count == 0:
            logger.warning("MONITOR: No jobs found in group. Continuing to wait or skip if intended.")
            # Depending on workflow, we might want to wait for jobs to be created
            
        # Write clean status snapshot
        status_path = os.path.join(args.research_dir, args.status_file)
        try:
            with open(status_path, 'w') as f:
                f.write(f"=== HTVS AUTOPILOT STATUS ===\n")
                f.write(f"Last Updated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Group        : {args.group_name}\n")
                f.write(f"Settings     : {args.settings}\n")
                f.write(f"-----------------------------\n")
                f.write(f"Jobs Done    : {done_count}\n")
                f.write(f"Jobs Pending : {pending_count}\n")
                f.write(f"Total Jobs   : {total_count}\n")
                f.write(f"=============================\n")
        except Exception as e:
            logger.warning(f"Failed to write status file: {e}")

        # Run active monitoring hooks
        if hasattr(workflow, 'run_active_monitoring'):
            workflow.run_active_monitoring()
            
        try:
            from src.utils.htvs import HTVSJobHandler
            handler = HTVSJobHandler(args.settings)
            
            # Monitor jobs (modular implementation)
            handler.monitor_jobs(args.group_name)
            
            # Trigger parsing (modular implementation)
            handler.parse_jobs(args.group_name, args.completed_path)
            
        except Exception as e:
            logger.warning(f"HTVS tool error: {e}. Falling back to passive monitoring.")
        
        logger.info(f"WAITING: Sleeping for {args.poll_interval}s...")
        time.sleep(args.poll_interval)

    # --- STAGE 2: POST-PROCESSING ---
    logger.info(f"--- STAGE 2: POST-PROCESSING ({args.workflow}) ---")
    if workflow.post_process():
        logger.info("AUTO-PILOT: Campaign complete.")
        ping_completion()
    else:
        logger.error("AUTO-PILOT: Post-processing stage failed.")
        sys.exit(1)

    logger.info("="*50)
    logger.info(f"HTVS AUTO-PILOT FINISHED AT {datetime.now()}")
    logger.info("="*50)

if __name__ == "__main__":
    main()

