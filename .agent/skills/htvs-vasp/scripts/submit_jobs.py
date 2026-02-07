import os
import sys
import json
import glob
import argparse
import numpy as np
from django.core.management import call_command
import django
from ase import io

# Pymatgen integration for automated VASP inputs
try:
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.io.vasp.sets import MPStaticSet, MatPESStaticSet, MPRelaxSet
    PYMATGEN_AVAILABLE = True
except ImportError:
    PYMATGEN_AVAILABLE = False

# Mapping from VASP INCAR tags to HTVS 'details' keys
VASP_TO_HTVS_MAPPING = {
    "ENCUT": "encut",
    "ISMEAR": "ismear",
    "SIGMA": "sigma",
    "ISPIN": "ispin",
    "LORBIT": "lorbit",
    "LREAL": "lreal",
    "NSW": "nsteps",
    "IBRION": "ibrion",
    "ISIF": "isif",
    "EDIFF": "ediff",
    "EDIFFG": "ediffg",
    "POTIM": "timestep",
    "TEBEG": "temperature",
    "ALGO": "algo",
    "PREC": "prec",
    "SYMPREC": "symprec",
    "NCORE": "ncore",
    "KPAR": "kpar",
}

def get_magmoms(atoms):
    """Calculates magmoms based on chemical species (Cr, Co, Ni)."""
    mag_map = {"Cr": 5.0, "Co": 1.6, "Ni": 0.6}
    return [mag_map.get(s, 0.0) for s in atoms.get_chemical_symbols()]

def get_miller_index(hkl):
    from pgmols.models import MillerIndex
    mi, _ = MillerIndex.objects.get_or_create(hkl=hkl)
    return mi

def create_job(parent, group_obj, config_obj):
    from jobs.models import Job
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    return Job(
        config=config_obj,
        group=group_obj,
        status="done",
        parentct=ContentType.objects.get_for_model(parent),
        parentid=parent.id,
        completetime=timezone.now(),
    )

def get_or_create_group(name):
    from pgmols.models import Group
    group, created = Group.objects.get_or_create(name=name)
    if created:
        print(f"Created new group: {name}")
    else:
        print(f"Using existing group: {name}")
    return group

def save_structures(file_path, group_obj, parent_config_name, framework_name=None, parent_bulk_id=None, default_miller_index=[1, 1, 1]):
    """Imports structures (Crystals or Surfaces) from a file into the database."""
    from pgmols.models import Crystal, Surface, Group, Method, Stoichiometry, Species, SpaceGroup, MillerIndex, Framework
    from jobs.models import Job, JobConfig
    from django.utils import timezone
    from django.contrib.contenttypes.models import ContentType
    
    if not os.path.exists(file_path):
        print(f"Warning: File not found {file_path}")
        return []

    atoms_list = io.read(file_path, ":")
    default_method, _ = Method.objects.get_or_create(name="manual_import")
    
    try:
        parent_config = JobConfig.objects.get(name=parent_config_name)
    except JobConfig.DoesNotExist:
        parent_config, _ = JobConfig.objects.get_or_create(name=parent_config_name)

    # Try to find parent bulk structure if ID provided
    parent_obj = None
    if parent_bulk_id:
        try:
            parent_obj = Surface.objects.get(id=parent_bulk_id)
        except Surface.DoesNotExist:
            try:
                parent_obj = Crystal.objects.get(id=parent_bulk_id)
            except Crystal.DoesNotExist:
                print(f"Warning: Parent bulk ID {parent_bulk_id} not found.")

    created_ids = []
    print(f"Importing {len(atoms_list)} structures from {os.path.basename(file_path)}...")
    
    for atoms in atoms_list:
        if "bulk" in os.path.basename(file_path).lower():
            obj = Crystal.from_ase_atoms(atoms)
        else:
            obj = Surface.from_ase_atoms(atoms, reorder=True)
            
            # Inherit from parent or use default
            if parent_obj:
                obj.method = parent_obj.method
                if hasattr(parent_obj, "miller_index"):
                     obj.miller_index = parent_obj.miller_index
                else:
                     obj.miller_index = get_miller_index(default_miller_index)
            else:
                obj.method = default_method
                if not obj.miller_index:
                    obj.miller_index = get_miller_index(default_miller_index)
            
            obj.chemical_tag = obj.generate_hash()
            
            # Handle surface/adsorbate atoms tagging
            if atoms.info.get("surf_atoms", None) is not None:
                surf_atoms = atoms.info.get("surf_atoms")
                obj.surface_atoms = np.array(surf_atoms, dtype=int).tolist()
                try:
                    obj.adsorbate_atoms = np.array(atoms.ads_atoms, dtype=int).tolist()
                except AttributeError:
                    adsorbate_atoms = atoms.get_tags() == 2
                    obj.adsorbate_atoms = adsorbate_atoms.tolist()
            elif hasattr(atoms, "get_surface_atoms"):
                obj.surface_atoms = np.isin(
                    np.arange(len(atoms)),
                    np.array(atoms.get_surface_atoms(), dtype=int),
                ).tolist()
                try:
                    surf_indices = np.array(atoms.get_adsorbate_atoms(), dtype=int).tolist()
                except AttributeError:
                    surf_indices = []
                obj.adsorbate_atoms = np.isin(np.arange(len(atoms)), surf_indices).tolist()
            else:
                surface_atoms = atoms.get_tags() == 1
                adsorbate_atoms = atoms.get_tags() == 2
                obj.surface_atoms = surface_atoms.tolist()
                obj.adsorbate_atoms = adsorbate_atoms.tolist()
        
        obj.method = default_method
        
        # Create Parent Job and link
        if parent_obj:
            job = create_job(parent_obj, group_obj, parent_config)
            job.save()
            obj.parentjob = job
        elif not hasattr(obj, 'parentjob') or not obj.parentjob:
            # Fallback for bulk or if no parent bulk provided
            job = create_job(obj, group_obj, parent_config)
            job.save()
            obj.parentjob = job
            
        obj.save() 
        
        # 2. Handle Framework if requested
        if framework_name:
            # Use the provided name, or suffix it if multiple structures in one file?
            # User's snippet used self.framework_name directly
            f_name = framework_name
            if len(atoms_list) > 1:
                # If multiple structures, we might want unique framework names? 
                # But let's follow user snippet literally first.
                pass
                
            framework = Framework(name=f_name, prototype=obj, group=group_obj)
            framework.save()
            obj.framework = framework
            obj.save()
            
        created_ids.append((obj.id, obj.__class__.__name__))
        
    return created_ids

def main():
    parser = argparse.ArgumentParser(description="Submit HTVS jobs.")
    parser.add_argument("--structure_dir", required=True, help="Directory containing structure files")
    parser.add_argument("--group_name", required=True, help="HTVS Group Name")
    parser.add_argument("--chem_config", required=True, help="HTVS Chemical Configuration")
    parser.add_argument("--parent_config", required=True, help="Parent Job Configuration Name")
    parser.add_argument("--framework_name", help="HTVS Framework Name (optional)")
    parser.add_argument("--parent_bulk_id", type=int, help="ID of parent bulk structure for surfaces (optional)")
    parser.add_argument("--miller_index", type=int, nargs=3, default=[1, 1, 1], help="Default Miller Index [h, k, l]")
    parser.add_argument("--compute_platform", required=True, help="Compute Platform")
    parser.add_argument("--requester", required=True, help="User requesting the job")
    parser.add_argument("--settings_module", required=True, help="Django Settings Module")
    parser.add_argument("--inbox_path", required=True, help="Directory for generated job files")
    parser.add_argument("--details", help="Additional job details as JSON string (optional)")
    parser.add_argument("--preset_type", default="mp", choices=["mp", "omat", "matpes-pbe", "matpes-r2scan"], help="Pymatgen VASP preset")
    parser.add_argument("--calculation_type", default="static", choices=["static", "relaxation"], help="VASP calculation type")
    
    args = parser.parse_args()
    
    # --- Setup Django ---
    htvs_repo = os.environ.get("HTVS_DIR")
    if not htvs_repo:
        djangochem_dir = os.environ.get("HTVS_DJANGOCHEM_DIR")
        if djangochem_dir:
            htvs_repo = os.path.dirname(djangochem_dir)
            
    if htvs_repo and htvs_repo not in sys.path:
        sys.path.append(htvs_repo)
        
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", args.settings_module)

    try:
        django.setup()
    except ModuleNotFoundError as e:
        print(f"Error setting up Django: {e}")
        sys.exit(1)

    # 1. Ensure Group
    group = get_or_create_group(args.group_name)
    
    # 2. Import Structures
    structure_files = glob.glob(os.path.join(args.structure_dir, "*.xyz")) + \
                      glob.glob(os.path.join(args.structure_dir, "*.cif"))
                      
    if not structure_files:
        print(f"No structure files found in {args.structure_dir}!")
        return

    print(f"Found {len(structure_files)} files.")
    
    imported_objects = []
    for f in structure_files:
        objs = save_structures(f, group, args.parent_config, args.framework_name, args.parent_bulk_id, args.miller_index)
        imported_objects.extend(objs)
        
    print(f"Imported {len(imported_objects)} objects total.")
    
    # 3. Request Jobs
    from pgmols.models import Crystal, Surface
    from jobs.models import Job, JobConfig
    from django.utils import timezone
    from django.contrib.contenttypes.models import ContentType

    try:
        config = JobConfig.objects.get(name=args.chem_config)
    except JobConfig.DoesNotExist:
        print(f"Error: Chem Config '{args.chem_config}' not found in database.")
        return

    # Base HTVS details (Essential defaults required by templates)
    base_details = {
        "compute_platform": args.compute_platform,
        "priority": 100,
        "force": True,
        "fix_cell": True,
        "symprec": 1e-5,
        "ediffg": -0.01,
        "ncore": 4,
        "kpar": 4,
        "notes": f"Imported from {args.structure_dir}"
    }

    if "perlmutter" in args.compute_platform.lower():
        base_details["project_name"] = "m5068"

    # Merge custom details if provided
    if args.details:
        try:
            custom_details = json.loads(args.details)
            base_details.update(custom_details)
        except json.JSONDecodeError as e:
            print(f"Error parsing --details JSON: {e}")
            return

    print("Requesting jobs with automated VASP details...")
    
    for obj_id, obj_type in imported_objects:
        if obj_type == "Crystal":
            obj = Crystal.objects.get(id=obj_id)
        else:
            obj = Surface.objects.get(id=obj_id)
            
        atoms = obj.as_ase_atoms()
        job_details = base_details.copy()
        
        # Automated VASP input generation using Pymatgen
        if PYMATGEN_AVAILABLE:
            presets = {
                "omat": MPStaticSet,
                "mp": MPStaticSet,
                "matpes-pbe": MatPESStaticSet,
                "matpes-r2scan": MatPESStaticSet,
            }
            set_class = presets.get(args.preset_type, MPStaticSet)
            if args.calculation_type == "relaxation":
                set_class = MPRelaxSet
            
            set_kwargs = {}
            if args.preset_type == "matpes-r2scan":
                set_kwargs["xc_functional"] = "R2SCAN"
            elif args.preset_type == "matpes-pbe":
                set_kwargs["xc_functional"] = "PBE"

            pmg_structure = AseAtomsAdaptor.get_structure(atoms)
            vis = set_class(pmg_structure, **set_kwargs)
            
            # Map INCAR tags to HTVS details
            incar = vis.incar
            for vasp_tag, value in incar.items():
                htvs_key = VASP_TO_HTVS_MAPPING.get(vasp_tag, vasp_tag.lower())
                # Only add if not already in base_details (allows override)
                if htvs_key not in job_details:
                    job_details[htvs_key] = value
            
            # Add KPOINTS info
            if hasattr(vis, 'kpoints') and vis.kpoints:
                # Use kpoints density if available
                # Pymatgen static sets often use kpoints per reciprocal atom (kppa)
                # HTVS mapping uses kppa for KPOINT_DENSITY
                # Let's check vis.kpoints for clues or just set a safe default if not found
                if hasattr(vis, 'kppa'):
                    job_details['kppa'] = vis.kppa
                elif not job_details.get('kpoints_density'):
                    # Fallback to a safe default if nothing found
                    job_details['kpoints_density'] = 3000

        job_details["magmom"] = get_magmoms(atoms)
        job_details["requester"] = args.requester
        
        job = Job(
            config=config,
            group=group,
            status="",
            parentct=ContentType.objects.get_for_model(obj),
            parentid=obj.id,
            details=job_details,
            createtime=timezone.now(),
        )
        job.save()
        print(f"Requested job for {obj_type} {obj_id} (Job ID: {job.id})")
    
    # 4. Build Jobs
    print(f"Building jobs in: {args.inbox_path}")
    import io as python_io
    out = python_io.StringIO()
    call_command(
        'buildjobs',
        args.group_name,
        args.inbox_path,
        config=args.chem_config,
        compute_platform=args.compute_platform,
        stdout=out
    )
    
    output_text = out.getvalue()
    print(output_text)
    
    # Extract created job directories
    job_dirs = []
    for line in output_text.splitlines():
        if "created:" in line:
            job_path = line.split("created:")[1].strip()
            job_dirs.append(os.path.basename(job_path))
            
    if job_dirs:
        tracking_file = os.path.join(args.structure_dir, "job_tracking.json")
        tracking_data = {
            "group_name": args.group_name,
            "chem_config": args.chem_config,
            "inbox_path": args.inbox_path,
            "job_dirs": job_dirs,
            "timestamp": timezone.now().isoformat()
        }
        with open(tracking_file, 'w') as f:
            json.dump(tracking_data, f, indent=2)
        print(f"Saved {len(job_dirs)} job directory names to {tracking_file}")
    
    print("Submission complete.")

if __name__ == "__main__":
    main()
