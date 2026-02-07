import os
import sys
import argparse

def setup_django(settings_module, djangochem_dir):
    """Sets up Django environment for HTVS and returns if successful."""
    try:
        sys.path.append(djangochem_dir)
        sys.path.append(os.path.abspath(os.path.join(djangochem_dir, "..")))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
        import django
        django.setup()
        return True
    except Exception as e:
        print(f"Error setting up Django: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Parse completed HTVS jobs.")
    parser.add_argument("--group_name", required=True, help="HTVS Project/Group name")
    parser.add_argument("--completed_path", required=True, help="Path to the completed jobs directory")
    parser.add_argument("--settings_module", required=True, help="Django Settings Module")
    parser.add_argument("--config_name", help="Filter by specific configuration name")
    parser.add_argument("--limit", type=int, help="Max number of jobs to parse")
    
    args = parser.parse_args()
    
    htvs_repo = os.environ.get("HTVS_DIR")
    if not htvs_repo:
        # Fallback to a common location if HTVS_DIR is not set
        htvs_repo = "/home/hojechun/ssd_mnt/repos/htvs"
        if not os.path.exists(htvs_repo):
            print("\nError: HTVS_DIR environment variable not set and fallback path not found.")
            return
            
    djangochem_dir = os.path.join(htvs_repo, "djangochem")
    
    if setup_django(args.settings_module, djangochem_dir):
        from django.core.management import call_command
        print(f"\nRunning parsejobs for group '{args.group_name}' in '{args.completed_path}'...")
        
        kwargs = {
            'settings': args.settings_module,
        }
        if args.config_name:
            kwargs['config'] = args.config_name
        if args.limit:
            kwargs['limit'] = args.limit
            
        try:
            call_command(
                'parsejobs',
                args.group_name,
                args.completed_path,
                **kwargs
            )
            print("Parsing complete.")
        except Exception as e:
            print(f"Error running parsejobs: {e}")

if __name__ == "__main__":
    main()
