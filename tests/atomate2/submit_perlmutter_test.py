import os
from jobflow import Flow, job
from jobflow.managers.fireworks import flow_to_workflow
from jobflow_remote.submission import submit_flow
from jobflow_remote.client import JobflowRemote
from atomate2.vasp.jobs.core import RelaxMaker
from pymatgen.core import Structure

# Define a simple job
def submit_test_job():
    # standard Si structure
    structure = Structure(
        lattice=[[0, 2.73, 2.73], [2.73, 0, 2.73], [2.73, 2.73, 0]],
        species=["Si", "Si"],
        coords=[[0, 0, 0], [0.25, 0.25, 0.25]],
    )

    # fast relaxation
    job = RelaxMaker().make(structure)
    job.name = "Perlmutter Test Job"

    # Submit to remote
    project_name = "remote_perlmutter"
    
    print(f"Submitting job to project: {project_name}")
    try:
        submit_flow(job, project=project_name)
        print("Flow submitted successfully.")
        print("Now run the following command to push it to Perlmutter:")
        print(f"  jf runner run -p {project_name}")
        print("\nThen check status with:")
        print(f"  jf remote status -p {project_name}")
    except Exception as e:
        print(f"Failed to submit flow: {e}")
        # Hint about potential config issues
        print("\nCheck if your ~/.jfremote/projects/remote_perlmutter.yaml is valid.")

if __name__ == "__main__":
    submit_test_job()
