import argparse
import os
import sys
import shutil
import tempfile
from types import SimpleNamespace
from pathlib import Path

# Add the current directory to path to ensure imports work if needed
sys.path.append(os.getcwd())

try:
    from reactot.run_model import pred_ts
    import torch
except ImportError as e:
    print(f"Error: Could not import 'reactot' or dependencies: {e}")
    # print traceback
    import traceback
    traceback.print_exc()
    print("Ensure you are in the 'react-ot-agent' environment.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Generate Transition State using React-OT")
    parser.add_argument("--reactants", required=True, help="Path to reactant structure file (xyz)")
    parser.add_argument("--products", required=True, help="Path to product structure file (xyz)")
    parser.add_argument("--output_dir", required=True, help="Directory to save outputs")
    parser.add_argument("--checkpoint", default=None, help="Path to model checkpoint")
    parser.add_argument("--nfe", type=int, default=10, help="Number of function evaluations (default: 10)")
    parser.add_argument("--solver", type=str, default="ode", choices=["ode", "ddpm", "ei"], help="Solver method (default: ode)")
    parser.add_argument("--batch_size", type=int, default=1, help="Batch size (default: 1)")
    
    args = parser.parse_args()

    # Resolve paths
    reactants_path = os.path.abspath(args.reactants)
    products_path = os.path.abspath(args.products)
    output_dir = os.path.abspath(args.output_dir)
    
    # Default checkpoint path: ~/.cache/react-ot/checkpoints/sb-pretrained.ckpt
    if args.checkpoint is None:
        default_ckpt = os.path.join(
            os.path.expanduser("~"), ".cache", "react-ot", "checkpoints", "sb-pretrained.ckpt"
        )
        if os.path.exists(default_ckpt):
            checkpoint_path = default_ckpt
        else:
            print(f"Error: Checkpoint not found at {default_ckpt}. Please run download_models.py.")
            sys.exit(1)
    else:
        checkpoint_path = os.path.abspath(args.checkpoint)
        if not os.path.exists(checkpoint_path):
            print(f"Error: Checkpoint not found at {checkpoint_path}")
            sys.exit(1)

    # React-OT writes temp files to the input directory and expects specific naming conventions
    # like *-r.xyz and *-p.xyz. It extracts the name from -r.xyz split.
    # To ensure predictable output filenames, we rename inputs to standard names in a temp dir.
    with tempfile.TemporaryDirectory() as temp_dir:
        # Use simple name without underscores to avoid truncation in React-OT export
        base_name = "reaction" 
        temp_r = os.path.join(temp_dir, f"{base_name}-r.xyz")
        temp_p = os.path.join(temp_dir, f"{base_name}-p.xyz")
        
        # Copy inputs
        shutil.copy(reactants_path, temp_r)
        shutil.copy(products_path, temp_p)
        
        # Construct options namespace expected by pred_ts
        opt = SimpleNamespace(
            batch_size=args.batch_size,
            nfe=args.nfe,
            solver=args.solver,
            checkpoint_path=checkpoint_path,
            order=1,          # Default from service_ot.py
            diz='linear',     # Default from service_ot.py
            method='midpoint',# Default from service_ot.py
            atol=1e-2,        # Default from service_ot.py
            rtol=1e-2         # Default from service_ot.py
        )
        
        print(f"Running React-OT inference...")
        print(f"Reactants: {reactants_path}")
        print(f"Products: {products_path}")
        print(f"Checkpoint: {checkpoint_path}")
        print(f"Solver: {args.solver}, NFE: {args.nfe}")
        
        try:
            # Run prediction
            success = pred_ts(temp_r, temp_p, opt, output_dir)
            
            if success:
                print(f"Success! Output saved to {output_dir}")
                
                # Check for expected output file
                # React-OT output naming: {name_index.split('_')[0]}_ts.xyz
                # name_index = base_name (since we used base_name-r.xyz)
                # So output should be base_name_ts.xyz => reaction_ts.xyz
                expected_out = os.path.join(output_dir, f"{base_name}_ts.xyz")
                
                if os.path.exists(expected_out):
                    print(f"Generated TS file: {expected_out}")
                    # Optionally rename to ts.xyz
                    final_ts = os.path.join(output_dir, "ts_generated.xyz")
                    shutil.move(expected_out, final_ts)
                    print(f"Renamed to: {final_ts}")
                else:
                    print(f"Warning: Expected output {expected_out} not found. lists: {os.listdir(output_dir)}")
                    
            else:
                print("React-OT returned failure.")
                sys.exit(1)
                
        except Exception as e:
            print(f"Error during execution: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()
