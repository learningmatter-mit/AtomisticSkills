"""
Evaluate synthetic accessibility and predicting retrosynthetic pathways using IBM RXN.

Usage:
    export RXN_API_KEY="your-key"
    python evaluate_ibm_rxn.py "FC(F)(F)C(F)=C" --steps 3

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: rxn4chemistry
"""

import argparse
import os
import sys
import time

try:
    from rxn4chemistry import RXN4ChemistryWrapper
except ImportError:
    print("Error: The 'rxn4chemistry' package is required but not installed.")
    print("Please install it in this environment by running:\n    pip install rxn4chemistry")
    sys.exit(1)

def evaluate_retrosynthesis(smiles: str, max_steps: int = 3):
    """
    Submits a retrosynthesis job to IBM RXN and polls until completion.
    
    Args:
        smiles: Target molecule SMILES string
        max_steps: Maximum number of retrosynthetic steps to explore
    """
    api_key = os.environ.get("RXN_API_KEY")
    if not api_key:
        print("Error: RXN_API_KEY environment variable not set.")
        print("Please export RXN_API_KEY='your_api_key' before running.")
        sys.exit(1)
        
    wrapper = RXN4ChemistryWrapper(api_key=api_key)
    wrapper.create_project('AtomisticSkills_Retrosynthesis')
    
    print(f"Submitting retrosynthesis prediction for SMILES: {smiles} ...")
    try:
        response = wrapper.predict_automatic_retrosynthesis(smiles=smiles, max_steps=max_steps)
        job_id = response['prediction_id']
        print(f"Job successfully submitted! (ID: {job_id})")
        print("Polling for completion... (This may take a few minutes for complex molecules)")
    except Exception as e:
        print(f"Failed to submit to IBM RXN: {e}")
        sys.exit(1)
        
    status = ""
    results = None
    
    while True:
        try:
            results = wrapper.get_predict_automatic_retrosynthesis_results(job_id)
            status = results['status']
            if status == 'SUCCESS':
                break
            elif status == 'ERROR':
                print("The retrosynthesis job encountered an error on the IBM RXN server.")
                sys.exit(1)
                
            print(f"Status: {status}... waiting 10s")
            time.sleep(10)
        except Exception as e:
            print(f"Error polling job status: {e}")
            sys.exit(1)
            
    # Process Success
    pathways = results.get('retrosynthetic_paths', [])
    if not pathways:
        print("\nNo viable retrosynthetic pathways found for this molecule.")
        return
        
    print(f"\n✅ Retrosynthesis completed! Found {len(pathways)} total possible pathways.")
    print("-" * 80)
    
    # Analyze top pathway
    top_path = pathways[0]
    confidence = top_path.get('confidence', 0.0)
    
    print(f"Top Recommended Pathway (Confidence: {confidence:.2f})")
    
    # Helper recursive function to print tree
    def print_tree(node, depth=0):
        indent = "  " * depth
        smiles_part = node.get('smiles', 'Unknown')
        is_commercially_available = "📦 (commercial)" if node.get('is_commercial', False) else ""
        print(f"{indent}↳ {smiles_part} {is_commercially_available}")
        
        children = node.get('children', [])
        for child in children:
            print_tree(child, depth + 1)
            
    print_tree(top_path)
    print("-" * 80)
    print("For full interactive visualization, check the project in your IBM RXN dashboard.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate synthetic accessibility using IBM RXN")
    parser.add_argument("smiles", help="Target molecule SMILES string")
    parser.add_argument("--steps", type=int, default=3, help="Maximum number of synthesis steps to explore")
    
    args = parser.parse_args()
    evaluate_retrosynthesis(args.smiles, max_steps=args.steps)
