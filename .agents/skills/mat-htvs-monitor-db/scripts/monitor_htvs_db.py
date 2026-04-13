import os
import sys
import time
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.htvs import HTVSDbHandler, HTVSJobHandler, HTVSConfigHandler
from src.utils.research_utils import get_current_research_dir

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HTVSMonitor")

def load_tracking_data(res_dir: Path):
    """Load Job IDs to monitor from tracking JSONs."""
    job_ids = set()
    tracking_files = list(res_dir.glob("*tracking.json"))
    
    for f in tracking_files:
        try:
            with open(f, "r") as json_file:
                data = json.load(json_file)
                if not isinstance(data, list):
                    data = [data]
                for entry in data:
                    if "job_pks" in entry:
                        job_ids.update(entry["job_pks"])
                    elif "ids" in entry and isinstance(entry["ids"], list):
                        # This might be structure IDs, but we focus on jobs
                        pass
        except Exception as e:
            logger.warning(f"Failed to read {f}: {e}")
            
    return sorted(list(job_ids))

def poll_jobs(db_handler: HTVSDbHandler, group_name: str, job_ids: list):
    """Query DB for current status of specific job IDs."""
    logger.info(f"Querying status for {len(job_ids)} jobs in group '{group_name}'...")
    
    # query_jobs returns all jobs, we need to filter or query specifically
    # For robusticity, we query the whole group and filter locally
    try:
        results_str = db_handler.query_jobs(group_name=group_name)
        all_jobs = json.loads(results_str)
        
        if job_ids:
            target_jobs = [j for j in all_jobs if j.get("job_id") in job_ids]
        else:
            target_jobs = all_jobs
        
        status_counts = {}
        for j in target_jobs:
            status = j.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
        return target_jobs, status_counts
    except Exception as e:
        logger.error(f"DB Query failed: {e}")
        return None, None

def main():
    parser = argparse.ArgumentParser(description="Monitor HTVS jobs and parse results.")
    parser.add_argument("--group_name", help="HTVS Project Group")
    parser.add_argument("--settings_module", default="orgel", help="Django settings module")
    parser.add_argument("--poll_interval", type=int, default=60, help="Seconds between polls")
    parser.add_argument("--max_retries", type=int, default=1440, help="Max polling attempts")
    parser.add_argument("--auto_parse", type=bool, default=True, help="Auto-parse on completion")
    parser.add_argument("--completed_path", help="Path to completed jobs directory")
    
    args = parser.parse_args()
    
    # Load global config defaults
    config = HTVSConfigHandler().load_config()
    group_name = args.group_name or config.get("group_name")
    settings_module = args.settings_module or config.get("settings_module")
    completed_path = args.completed_path or config.get("completed_path")
    
    if not group_name:
        logger.error("No group_name provided and not found in config.")
        sys.exit(1)
        
    res_dir = get_current_research_dir()
    if not res_dir:
        logger.error("No active research directory found. Tracking data cannot be loaded.")
        sys.exit(1)
        
    job_ids = load_tracking_data(res_dir)
    if not job_ids:
        logger.warning(f"No job IDs found in tracking files at {res_dir}. Monitoring all jobs in group '{group_name}'.")
    else:
        logger.info(f"Found {len(job_ids)} job IDs to monitor from tracking files.")

    db_handler = HTVSDbHandler(settings_module)
    job_handler = HTVSJobHandler(settings_module)
    
    retries = 0
    while retries < args.max_retries:
        target_jobs, status_counts = poll_jobs(db_handler, group_name, job_ids)
        
        if target_jobs is not None:
            done_count = status_counts.get("done", 0)
            error_count = status_counts.get("error", 0)
            total = len(target_jobs) if job_ids else status_counts.get("done", 0) + status_counts.get("error", 0) + status_counts.get("claimed", 0) + status_counts.get("requested", 0)
            
            logger.info(f"Progress: {done_count} done, {error_count} error, {total} total tracked.")
            logger.info(f"Status breakdown: {status_counts}")
            
            # Check if all jobs are finished (done or error)
            all_finished = False
            if job_ids:
                all_finished = (done_count + error_count >= len(job_ids))
            else:
                # If no specific IDs, we look for any non-finished jobs in group
                active = status_counts.get("claimed", 0) + status_counts.get("requested", 0)
                all_finished = (active == 0 and total > 0)
                
            if all_finished:
                logger.info("All tracked jobs have finished.")
                
                if args.auto_parse and completed_path:
                    if os.path.exists(completed_path):
                        logger.info(f"Triggering auto-parse from {completed_path}...")
                        try:
                            parse_result = job_handler.parse_jobs(group_name, completed_path)
                            logger.info(f"Parse Result: {parse_result}")
                        except Exception as e:
                            logger.error(f"Auto-parse failed: {e}")
                    else:
                        logger.warning(f"Auto-parse skipped: completed_path '{completed_path}' does not exist.")
                
                break
        
        logger.info(f"Waiting {args.poll_interval} seconds...")
        time.sleep(args.poll_interval)
        retries += 1

    if retries >= args.max_retries:
        logger.warning("Reached maximum retries. Monitoring stopped.")

if __name__ == "__main__":
    main()
