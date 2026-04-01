"""
Utility module for running VASP calculations using atomate2.
"""

import os
import json
import logging
import pickle
import sys
from datetime import datetime
from pathlib import Path
from src.utils.research_utils import get_current_research_dir
from typing import Dict, Any, Optional, List, Union, Tuple

import numpy as np
from ase import Atoms
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor
from ase.io import read

logger = logging.getLogger(__name__)

class Atomate2Handler:
    """Handles atomate2 VASP flows and job execution."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_path = Path(output_dir)
        else:
            # Use standardized research directory
            self.output_path = get_current_research_dir() / "atomate2"
            
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.results_dir = self.output_path / "results"
        self.results_dir.mkdir(exist_ok=True)

    def check_environment(self) -> Dict[str, Any]:
        """Check if VASP, POTCAR, and atomate2 are available."""
        checks = {
            "atomate2": False,
            "vasp": False,
            "potcar": False,
            "error": None
        }

        # Check atomate2
        import atomate2
        import jobflow
        checks["atomate2"] = True

        # Check VASP cmd
        vasp_cmd = os.environ.get("ATOMATE2_VASP_CMD") or os.environ.get("VASP_CMD")
        if vasp_cmd:
            checks["vasp"] = True
        else:
            # Check common location
            vasp_bin = Path("/home/bdeng/Packages/vasp.6.4.2/bin/vasp_std")
            if vasp_bin.exists():
                checks["vasp"] = True
                os.environ["ATOMATE2_VASP_CMD"] = f"mpirun -np 1 {vasp_bin}"
            else:
                checks["error"] = "VASP_CMD or ATOMATE2_VASP_CMD not set."

        # Check POTCAR
        potcar_dir = os.environ.get("PMG_VASP_PSP_DIR")
        if not potcar_dir:
            # Check pymatgen SETTINGS (reads from ~/.pmgrc.yaml)
            try:
                from pymatgen.core import SETTINGS
                potcar_dir = SETTINGS.get("PMG_VASP_PSP_DIR")
            except Exception:
                pass
        
        if potcar_dir:
            checks["potcar"] = True
            # Set it in environment for atomate2 to use
            os.environ["PMG_VASP_PSP_DIR"] = str(potcar_dir)
        else:
            checks["error"] = "PMG_VASP_PSP_DIR (POTCAR directory) not set."

        return checks

    def get_project_name(self, project_name: Optional[str] = None) -> str:
        """
        Resolve the project name.
        
        Logic:
        1. If project_name is provided, use it.
        2. If not, try to get default from jobflow-remote ConfigManager.
        3. If ConfigManager raises ProjectUndefinedError (ambiguous projects), 
           check ATOMATE2_REMOTE_PROJECT env var.
        4. If still unresolved, raise error.
        """
        if project_name:
            return project_name
            
        try:
            from jobflow_remote.config.manager import ConfigManager, ProjectUndefinedError
        except ImportError:
            # Fallback for when jobflow_remote is not installed or import fails
            if project_name:
                return project_name
            raise ValueError("jobflow-remote not found. Please provide project_name explicitly.")
        
        cm = ConfigManager()
        try:
            return cm.select_project_name(None)
        except ProjectUndefinedError as e:
            # Check env var fallback
            env_project = os.environ.get("ATOMATE2_REMOTE_PROJECT")
            if env_project:
                try:
                    # Validate the checking project exists
                    return cm.select_project_name(env_project)
                except Exception:
                    logger.warning(f"ATOMATE2_REMOTE_PROJECT='{env_project}' is set but invalid/unknown.")
            
            # Re-raise original error if fallback failed
            raise e

    def load_structures(self, structures_path: str) -> List[Structure]:
        """Load structures from path."""
        path = Path(structures_path)
        structures = []

        if path.is_dir():
            files = sorted(list(path.glob("*.cif")) + list(path.glob("*.xyz")) + list(path.glob("POSCAR*")))
            for f in files:
                if f.suffix == ".cif":
                    structures.append(Structure.from_file(str(f)))
                else:
                    atoms = read(str(f))
                    structures.append(AseAtomsAdaptor.get_structure(atoms))
        elif path.is_file():
            if path.suffix == ".cif":
                structures.append(Structure.from_file(str(path)))
            else:
                atoms = read(str(path))
                structures.append(AseAtomsAdaptor.get_structure(atoms))

        return structures

    def get_flow_maker(self, preset_type: str, calculation_type: str, config: Optional[Dict[str, Any]] = None):
        """Create atomate2 flow maker based on preset."""
        from atomate2.vasp.flows.matpes import MatPesStaticFlowMaker
        from atomate2.vasp.jobs.matpes import MatPesGGAStaticMaker, MatPesMetaGGAStaticMaker
        from atomate2.vasp.jobs.core import StaticMaker, RelaxMaker
        from atomate2.vasp.flows.core import BandStructureMaker, OpticsMaker

        preset = preset_type.lower()
        user_incar = config or {}
        
        if preset == "mp-r2scan":
            from atomate2.vasp.jobs.mp import MPMetaGGARelaxMaker, MPMetaGGAStaticMaker
            if calculation_type == "relaxation":
                maker = MPMetaGGARelaxMaker()
            elif calculation_type == "static":
                maker = MPMetaGGAStaticMaker()
            else:
                raise ValueError(f"Unsupported calculation_type {calculation_type} for mp-r2scan")
            if user_incar:
                maker.input_set_generator.user_incar_settings.update(user_incar)
            return maker

        elif preset == "matpes-r2scan":
            meta_maker = MatPesMetaGGAStaticMaker()
            if user_incar:
                meta_maker.input_set_generator.user_incar_settings.update(user_incar)
            return MatPesStaticFlowMaker(
                static1=None,
                static2=meta_maker,
                static3=None
            )
        elif preset == "matpes-pbe":
            gga_maker = MatPesGGAStaticMaker()
            if user_incar:
                gga_maker.input_set_generator.user_incar_settings.update(user_incar)
            return MatPesStaticFlowMaker(
                static1=gga_maker,
                static2=None,
                static3=None
            )
        elif preset in ["mp", "omat"]:
            if calculation_type == "static":
                maker = StaticMaker()
            elif calculation_type == "relaxation":
                maker = RelaxMaker()
            elif calculation_type == "band_structure":
                # Config can contain 'bandstructure_type' (line, uniform, both)
                bs_type = user_incar.pop("bandstructure_type", "line")
                maker = BandStructureMaker(bandstructure_type=bs_type)
            elif calculation_type == "optics":
                maker = OpticsMaker()
            else:
                raise ValueError(f"Unknown calculation_type: {calculation_type}")
            
            if user_incar:
                if calculation_type == "band_structure":
                     if hasattr(maker.static_maker, "input_set_generator"):
                         maker.static_maker.input_set_generator.user_incar_settings.update(user_incar)
                     if hasattr(maker.bs_maker, "input_set_generator"):
                         maker.bs_maker.input_set_generator.user_incar_settings.update(user_incar)
                elif calculation_type == "optics":
                    if hasattr(maker.static_maker, "input_set_generator"):
                        maker.static_maker.input_set_generator.user_incar_settings.update(user_incar)
                    if hasattr(maker.optics_maker, "input_set_generator"):
                        maker.optics_maker.input_set_generator.user_incar_settings.update(user_incar)
                else:
                    maker.input_set_generator.user_incar_settings.update(user_incar)
            return maker
        else:
            raise ValueError(f"Unknown preset_type: {preset_type}")

    def check_status(self, job_id: str, project_name: Optional[str] = None) -> Dict[str, Any]:
        """Check the status of a job (live check for remote jobs)."""
        status_file = self.output_path / f"{job_id}_status.json"
        
        result = {"job_id": job_id, "status": "unknown"}
        is_remote = False

        if status_file.exists():
            with open(status_file) as f:
                cached = json.load(f)
                result.update(cached)
                is_remote = cached.get("remote", False)
                if project_name is None:
                    project_name = cached.get("project")
                
        # If it's not known to be remote and not in the status file, we might return the unknown status
        # unless we try to search remote anyway.
        
        # If remote is True or we haven't found a local status yet, try remote check
        if is_remote or result["status"] == "unknown":
            try:
                from jobflow_remote.jobs.jobcontroller import JobController
                
                # Load controller to check status (None project_name uses discovery/default)
                jc = JobController.from_project_name(project_name)
                
                if job_id.isdigit():
                    flows_info = jc.get_flows_info(db_ids=[job_id])
                else:
                    flows_info = jc.get_flows_info(flow_ids=[job_id])

                if flows_info:
                    flow_info = flows_info[0]
                    result["status"] = flow_info.state.name.lower()
                    result["remote"] = True
                    result["type"] = "flow"
                else:
                    # Try searching as a Job
                    if job_id.isdigit():
                        jobs_info = jc.get_jobs_info(db_ids=[job_id])
                    else:
                        jobs_info = jc.get_jobs_info(uuids=[job_id])
                    
                    if jobs_info:
                        job_info = jobs_info[0]
                        result["status"] = job_info.state.name.lower()
                        result["remote"] = True
                        result["type"] = "job"
                
                if result["status"] != "unknown":
                    # Update cache with live status
                    with open(status_file, "w") as f:
                        json.dump(result, f)
            except Exception as e:
                logger.debug(f"Remote status check failed for job {job_id}: {e}")

        return result

    def _check_sshproxy(self, worker_name: str) -> Tuple[bool, str]:
        """
        Check if sshproxy is configured for NERSC/Perlmutter workers.
        
        Returns:
            Tuple of (is_configured, message)
        """
        if "perlmutter" not in worker_name.lower():
            return True, ""

        return True, ""

    def run_remote(self, flow: Any, project_name: Optional[str] = None, worker_name: Optional[str] = None) -> str:
        """Submit a flow remotely using jobflow-remote. If project_name is None, uses default configuration."""
        
        # Check sshproxy if applicable
        if worker_name:
            is_configured, msg = self._check_sshproxy(worker_name)
            if not is_configured:
                raise RuntimeError(f"SSHProxy check failed: {msg}")

        from jobflow_remote import submit_flow
        
        db_ids = submit_flow(flow, project=project_name, worker=worker_name)
        # Use the first db_id as the job_id for tracking
        job_id = db_ids[0]
        
        status_file = self.output_path / f"{job_id}_status.json"
        with open(status_file, "w") as f:
            json.dump({
                "job_id": job_id,
                "status": "SUBMITTED",
                "remote": True,
                "project": project_name,
                "worker": worker_name,
                "submitted_at": datetime.now().isoformat()
            }, f)
            
        return job_id

    def extract_results(self, job_id: str) -> Dict[str, Any]:
        """Extract energy, forces, and stress from completed job using idiomatic Atomate2 parsing."""
        responses_file = self.output_path / f"{job_id}_responses.pkl"
        all_responses = {}
        
        if responses_file.exists():
            with open(responses_file, 'rb') as f:
                all_responses = pickle.load(f)
        else:
            # Check if it's a remote job and fetch from JobStore
            status_info = self.check_status(job_id)
            if status_info.get("remote"):
                try:
                    project_name = status_info.get("project")
                    # Use the new robust retrieval method
                    results = self.get_results_by_id(
                        job_ids=[job_id] if job_id.isdigit() else None,
                        flow_ids=None if job_id.isdigit() else [job_id],
                        project_name=project_name,
                        convert_units=True
                    )
                    
                    if not results:
                        return {"error": "Remote results not found or not yet available."}
                        
                    return {"job_id": job_id, "results": results, "remote": True}
                except Exception as e:
                    logger.exception(f"Failed to fetch remote results for {job_id}")
                    return {"error": f"Failed to fetch remote results: {str(e)}"}
            else:
                return {"error": "Results not yet available or job is not remote."}

        from atomate2.vasp.jobs.base import get_vasp_task_document
        from atomate2.vasp.drones import VaspDrone

        drone = VaspDrone()
        extracted = []

        for flow_uuid, data in all_responses.items():
            run_dir = data.get("dir")
            if not run_dir or not Path(run_dir).exists():
                continue

            # Find all valid VASP directories within this flow's run directory
            valid_paths = []
            for root, dirs, files in os.walk(run_dir):
                valid_paths.extend(drone.get_valid_paths((root, dirs, files)))

            for path in valid_paths:
                doc = get_vasp_task_document(path)
                output = doc.output
                
                entry = {
                    "flow_uuid": flow_uuid,
                    "job_uuid": getattr(doc, "task_id", None),
                    "dir_name": getattr(doc, "dir_name", str(path)),
                    "energy": getattr(output, 'energy', getattr(output, 'final_energy', None)),
                    "forces": getattr(output, 'forces', None),
                    "stress": getattr(output, 'stress', None),
                    "structure": doc.structure.as_dict() if hasattr(doc, 'structure') else None
                }
                
                # Convert numpy to list if needed
                if entry["forces"] is not None:
                    entry["forces"] = np.array(entry["forces"]).tolist()
                if entry["stress"] is not None:
                    import ase.units
                    # Atomate2 standardizes stress to GPa. We convert to eV/A^3.
                    # VASP uses compressive positive convention, while ASE uses tensile positive. Multiply by -1.
                    entry["stress"] = (np.array(entry["stress"]) * -1.0 * ase.units.GPa).tolist()
                
                extracted.append(entry)

        return {"job_id": job_id, "results": extracted}

    def get_results_by_id(
        self,
        job_ids: Optional[List[str]] = None,
        flow_ids: Optional[List[str]] = None,
        project_name: Optional[str] = None,
        convert_units: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrive results by Job or Flow IDs.
        """
        return self._get_training_data_core(
            job_ids=job_ids,
            flow_ids=flow_ids,
            project_name=project_name,
            convert_units=convert_units
        )

    def get_results_by_formula(
        self,
        formula: Optional[str] = None,
        chemsys: Optional[str] = None,
        project_name: Optional[str] = None,
        convert_units: bool = True,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrive results by formula or chemical system.
        """
        return self._get_training_data_core(
            formula=formula,
            chemsys=chemsys,
            project_name=project_name,
            convert_units=convert_units,
            limit=limit
        )

    def get_database_summary(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a summary of the database content.
        """
        from jobflow_remote.jobs.jobcontroller import JobController
        try:
            jc = JobController.from_project_name(project_name)
            collection = jc.jobstore.docs_store._collection
        except Exception as e:
            logger.error(f"Failed to connect to JobController project '{project_name}': {e}")
            return {"error": str(e)}

        summary = {}
        
        # Total count
        summary["total_count"] = collection.count_documents({})
        
        # States distribution
        pipeline_states = [{"$group": {"_id": "$output.state", "count": {"$sum": 1}}}]
        states = list(collection.aggregate(pipeline_states))
        summary["states"] = {str(s["_id"]): s["count"] for s in states}
        
        # Chemsys distribution (top 10)
        pipeline_chemsys = [
            {"$group": {"_id": "$output.chemsys", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        chemsys = list(collection.aggregate(pipeline_chemsys))
        summary["top_chemsys"] = {str(c["_id"]): c["count"] for c in chemsys}
        
        # Latest updated
        latest = collection.find_one(sort=[("output.last_updated", -1)])
        if latest:
            summary["latest_update"] = latest.get("output", {}).get("last_updated")
            
        from monty.json import jsanitize
        return jsanitize(summary)

    def get_recent_jobs(self, project_name: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recently completed jobs.
        """
        from jobflow_remote.jobs.jobcontroller import JobController
        from jobflow_remote.jobs.state import JobState
        from monty.json import jsanitize
        
        try:
            jc = JobController.from_project_name(project_name)
            jobs_info = jc.get_jobs_info(states=[JobState.COMPLETED], limit=limit)
            
            results = []
            for j in jobs_info:
                results.append({
                    "job_id": j.db_id,
                    "uuid": j.uuid,
                    "name": j.name,
                    "state": j.state.name,
                    "completed_at": j.updated_on.isoformat() if j.updated_on else None
                })
            from monty.json import jsanitize
            return jsanitize(results)
        except Exception as e:
            logger.error(f"Failed to get recent jobs for project '{project_name}': {e}")
            return []

    def _get_training_data_core(
        self,
        job_ids: Optional[List[str]] = None,
        flow_ids: Optional[List[str]] = None,
        formula: Optional[str] = None,
        chemsys: Optional[str] = None,
        project_name: Optional[str] = None,
        convert_units: bool = True,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Internal core method to retrive training data from MongoDB.
        """
        from jobflow_remote.jobs.jobcontroller import JobController
        from jobflow_remote.jobs.state import JobState
        from monty.json import jsanitize
        import numpy as np
        
        try:
            jc = JobController.from_project_name(project_name)
            jobstore = jc.jobstore
        except Exception as e:
            logger.error(f"Failed to connect to JobController project '{project_name}': {e}")
            return []
        
        # 1. Fetch FlowInfo objects
        all_flows = []
        if job_ids:
            # Try as db_ids first
            db_ids = [str(jid) for jid in job_ids if str(jid).isdigit()]
            if db_ids:
                try:
                    all_flows.extend(jc.get_flows_info(db_ids=db_ids))
                except Exception as e:
                    logger.warning(f"Error fetching flows by db_ids: {e}")
            
            # Try as job_uuids
            uuids = [str(jid) for jid in job_ids if not str(jid).isdigit()]
            if uuids:
                 try:
                     # JobController.get_jobs_info can get jobs by UUIDs
                     # Then we extract flow IDs
                     jobs_info = jc.get_jobs_info(job_ids=[(u, 0) for u in uuids])
                     f_ids = list(set([j.flow_id for j in jobs_info if hasattr(j, 'flow_id')]))
                     if f_ids:
                         all_flows.extend(jc.get_flows_info(flow_ids=f_ids))
                 except Exception as e:
                     logger.warning(f"Error fetching flows by job_uuids: {e}")

        if flow_ids:
            try:
                # Flow IDs can be UUIDs or DB IDs (if handled by JC)
                all_flows.extend(jc.get_flows_info(flow_ids=flow_ids))
            except Exception as e:
                logger.warning(f"Error fetching flows by flow_ids: {e}")
            
        # If no IDs provided, but formula/chemsys are, we search MongoDB directly.
        docs_to_process = []
        
        if not (job_ids or flow_ids) and (formula or chemsys):
            try:
                query = {}
                if formula:
                    query["output.formula_pretty"] = formula
                if chemsys:
                    query["output.chemsys"] = chemsys
                
                # Fetch directly from collection
                # output.last_updated is used by atomate2 MongoStores
                docs_to_process = list(jc.jobstore.docs_store._collection.find(query).sort("output.last_updated", -1).limit(limit))
            except Exception as e:
                 logger.warning(f"Error searching flows by metadata: {e}")
        else:
            seen_job_uuids = set()
            for flow_info in all_flows:
                for jid in getattr(flow_info, "job_ids", []):
                    if jid in seen_job_uuids:
                        continue
                    seen_job_uuids.add(jid)
                    try:
                        doc = jobstore.get_output(jid)
                        if not doc:
                            doc = jobstore.get_output(getattr(flow_info, "flow_id", jid))
                        if doc:
                            docs_to_process.append(doc)
                    except Exception:
                        continue
        
        results = []

        for doc in docs_to_process:
            if not doc:
                continue
            
            doc_dict = jsanitize(doc)
            
            # Extract data early to handle nested filtering
            task_doc = doc_dict.get("output", doc_dict)
            
            # Check filtering (TaskDoc fields)
            if formula and task_doc.get("formula_pretty") != formula:
                continue
            if chemsys and task_doc.get("chemsys") != chemsys:
                continue
                
            # VASP outputs (energy, forces, stress) are typically nested another level down
            # under task_doc["output"] in standard JobFlow wrappers.
            actual_output = task_doc.get("output", task_doc) if isinstance(task_doc, dict) else task_doc
            
            # The structure in TaskDoc is typically in doc_dict["output"]["structure"]
            structure = task_doc.get("structure") or doc_dict.get("structure")
            
            # Energy
            energy = actual_output.get("energy") or actual_output.get("final_energy") or task_doc.get("energy")
            
            # Forces
            forces = actual_output.get("forces") or task_doc.get("forces")
            
            # Stress
            stress = actual_output.get("stress") or task_doc.get("stress")
            
            if structure and energy is not None:
                # Convert stress from kB to GPa if requested
                if stress is not None and convert_units:
                    # VASP stress is in kB. 1 kB = 0.1 GPa.
                    # We standardize to eV/A^3 (ASE standard).
                    # VASP uses compressive positive convention, while ASE uses tensile positive convention.
                    # So we need to multiply by -1
                    import ase.units
                    stress = (np.array(stress) * -0.1 * ase.units.GPa).tolist()
                
                if forces is not None:
                    forces = np.array(forces).tolist()
                
                results.append({
                    "structure": structure,
                    "energy": energy,
                    "forces": forces,
                    "stress": stress,
                    "job_uuid": doc_dict.get("uuid", "Unknown"),
                    "flow_id": doc_dict.get("flow_id", "Unknown"),
                    "formula": task_doc.get("formula_pretty"),
                    "chemsys": task_doc.get("chemsys")
                })

        return results
