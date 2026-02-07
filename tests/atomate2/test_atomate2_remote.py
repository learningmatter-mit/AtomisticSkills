
import os
import sys
import json
import time
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.mcp_server.atomate2_server import run_atomate2_vasp_calculation
from src.utils.dft.atomate2_utils import Atomate2Handler
from pymatgen.core import Structure

def test_remote_submission():
    output_dir = ".agent/test/remote_test_si"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a small Si structure
    si = Structure(
        lattice=[[0, 2.715, 2.715], [2.715, 0, 2.715], [2.715, 2.715, 0]],
        species=["Si", "Si"],
        coords=[[0, 0, 0], [0.25, 0.25, 0.25]],
    )
    si_path = os.path.join(output_dir, "Si.cif")
    si.to(filename=si_path)
    
    try:
        # 1. Submit remotely
        print("Submitting job remotely...")
        response = run_atomate2_vasp_calculation(
            structures_path=si_path,
            output_dir=output_dir,
            preset_type="omat",
            calculation_type="static",
            config={"NELM": 1}, # Very fast run
            execution_mode="remote"
        )
        print(f"Response: {response}")
        
        # Extract job_id from response
        import re
        match = re.search(r"Job ID: (\w+)", response)
        if not match:
            print("Failed to get Job ID from response")
            return
        job_id = match.group(1)
        print(f"Job ID: {job_id}")
        
        # 2. Check status (should be SUBMITTED)
        status_response = run_atomate2_vasp_calculation(
            structures_path=si_path,
            output_dir=output_dir,
            check_only=True,
            job_id=job_id
        )
        status = json.loads(status_response)
        print(f"Status: {status['status']}")
        
        # 3. Manually run the job (since we didn't start the daemon)
        print("Executing job manually using jf runner run...")
        import subprocess
        # Run jf runner run for the project
        res = subprocess.run(["jf", "runner", "run"], capture_output=True, text=True)
        print(f"Runner output: {res.stdout}")
        if res.stderr:
            print(f"Runner error: {res.stderr}")

        # 4. Check status again (should be COMPLETED)
        status_response = run_atomate2_vasp_calculation(
            structures_path=si_path,
            output_dir=output_dir,
            check_only=True,
            job_id=job_id
        )
        status = json.loads(status_response)
        print(f"New Status: {status['status']}")
        
        # 5. Extract results
        print("Extracting results...")
        results_response = run_atomate2_vasp_calculation(
            structures_path=si_path,
            output_dir=output_dir,
            job_id=job_id
        )
        print(f"Results message: {results_response}")
        
        # Verify results from handler directly
        handler = Atomate2Handler(output_dir)
        results = handler.extract_results(job_id)
        if "results" in results and len(results["results"]) > 0:
            print("Successfully retrieved results from JobStore!")
            print(f"Energy: {results['results'][0].get('energy')}")
        else:
            print("Failed to retrieve results.")
            print(f"Handler output: {results}")
    finally:
        # Cleanup
        if os.path.exists(output_dir):
            import shutil
            shutil.rmtree(output_dir)

if __name__ == "__main__":
    test_remote_submission()
