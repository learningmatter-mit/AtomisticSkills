"""
Query and rank synthesis recipes from Materials Project using text-mined literature data.

This script searches the Materials Project database for synthesis recipes extracted from
scientific literature using natural language processing. It provides precursor materials,
synthesis procedures, reaction equations, and DOI references.

Usage:
    python recommend_synthesis.py LiFePO4 --limit 10 --output recipes.json
    python recommend_synthesis.py "Li2CO3" --type solid-state --min-temp 500

Requirements:
    - Conda environment: base-agent
    - Required packages: mp-api, pymatgen
    - MP_API_KEY environment variable or ~/.atomistic_skills.yaml configuration
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any

try:
    from mp_api.client import MPRester
    from pymatgen.core import Composition
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("Please activate the base-agent conda environment")
    sys.exit(1)


def load_api_key() -> Optional[str]:
    """
    Load Materials Project API key from environment variable or config file.
    
    Returns:
        API key string, or None if not found
    """
    # Try environment variable first
    api_key = os.getenv("MP_API_KEY")
    if api_key:
        return api_key
    
    # Try config file
    config_path = Path.home() / ".atomistic_skills.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
                api_key = config.get("mp_api_key")
                if api_key:
                    return api_key
        except Exception as e:
            print(f"Warning: Could not read config file: {e}")
    
    return None


def query_synthesis_recipes(
    formula: str,
    api_key: str,
    synthesis_type: Optional[str] = None,
    min_temp: Optional[float] = None,
    max_temp: Optional[float] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Query Materials Project for synthesis recipes.
    
    Args:
        formula: Target material formula (e.g., "LiFePO4")
        api_key: Materials Project API key
        synthesis_type: Filter by synthesis type (optional)
        min_temp: Minimum synthesis temperature in °C (optional)
        max_temp: Maximum synthesis temperature in °C (optional)
        limit: Maximum number of recipes to return
        
    Returns:
        List of synthesis recipe dictionaries
    """
    with MPRester(api_key=api_key) as mpr:
        try:
            # Normalize formula using pymatgen
            comp = Composition(formula)
            normalized_formula = comp.reduced_formula
            
            print(f"Searching for synthesis recipes for {normalized_formula}...")
            
            # Query synthesis database
            recipes = mpr.synthesis.search(
                target_formula=normalized_formula,
                num_chunks=limit
            )
            
            if not recipes:
                print(f"No synthesis recipes found for {normalized_formula}")
                return []
            
            print(f"Found {len(recipes)} recipes")
            
            # Convert to dictionaries and extract relevant fields
            results = []
            for recipe in recipes:
                recipe_dict = recipe.dict() if hasattr(recipe, 'dict') else recipe
                
                # Apply filters
                if synthesis_type and recipe_dict.get('synthesis_type'):
                    if synthesis_type.lower() not in recipe_dict['synthesis_type'].lower():
                        continue
                
                # Temperature filtering (if available in recipe)
                if 'operations' in recipe_dict and recipe_dict['operations']:
                    temps = []
                    for op in recipe_dict['operations']:
                        if isinstance(op, dict) and 'conditions' in op:
                            for condition in op['conditions']:
                                if isinstance(condition, dict) and condition.get('type') == 'temperature':
                                    if 'values' in condition and condition['values']:
                                        temps.extend(condition['values'])
                    
                    if temps and (min_temp or max_temp):
                        avg_temp = sum(temps) / len(temps)
                        if min_temp and avg_temp < min_temp:
                            continue
                        if max_temp and avg_temp > max_temp:
                            continue
                
                results.append(recipe_dict)
            
            return results[:limit]
            
        except Exception as e:
            print(f"Error querying Materials Project: {e}")
            raise


def rank_recipes(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank synthesis recipes by simplicity and practicality.
    
    Ranking criteria:
    1. Fewer precursors (simpler)
    2. Lower synthesis temperature (easier)
    3. Common synthesis types preferred (solid-state, hydrothermal)
    
    Args:
        recipes: List of recipe dictionaries
        
    Returns:
        Ranked list of recipes
    """
    def score_recipe(recipe: Dict[str, Any]) -> tuple:
        """Calculate ranking score (lower is better)."""
        # Count precursors
        num_precursors = len(recipe.get('precursors', []))
        
        # Extract average temperature
        avg_temp = 1000  # Default high value
        if 'operations' in recipe and recipe['operations']:
            temps = []
            for op in recipe['operations']:
                if isinstance(op, dict) and 'conditions' in op:
                    for condition in op['conditions']:
                        if isinstance(condition, dict) and condition.get('type') == 'temperature':
                            if 'values' in condition and condition['values']:
                                temps.extend(condition['values'])
            if temps:
                avg_temp = sum(temps) / len(temps)
        
        # Prefer common synthesis types
        synthesis_type = recipe.get('synthesis_type', '').lower()
        type_penalty = 0
        if 'solid' in synthesis_type or 'ceramic' in synthesis_type:
            type_penalty = 0
        elif 'hydrothermal' in synthesis_type or 'sol-gel' in synthesis_type:
            type_penalty = 1
        else:
            type_penalty = 2
        
        return (num_precursors, avg_temp, type_penalty)
    
    return sorted(recipes, key=score_recipe)


def format_recipe_output(recipe: Dict[str, Any], index: int) -> str:
    """
    Format a recipe for human-readable output.
    
    Args:
        recipe: Recipe dictionary
        index: Recipe number (for display)
        
    Returns:
        Formatted string representation
    """
    lines = [f"\n{'='*70}"]
    lines.append(f"Recipe #{index}")
    lines.append('='*70)
    
    # Target material
    if 'target' in recipe:
        lines.append(f"Target: {recipe['target']}")
    
    # Precursors
    if 'precursors' in recipe and recipe['precursors']:
        precursors_str = ', '.join(str(p) for p in recipe['precursors'])
        lines.append(f"Precursors: {precursors_str}")
    
    # Synthesis type
    if 'synthesis_type' in recipe:
        lines.append(f"Synthesis Type: {recipe['synthesis_type']}")
    
    # Reaction string
    if 'reaction_string' in recipe and recipe['reaction_string']:
        lines.append(f"Reaction: {recipe['reaction_string']}")
    
    # Procedure
    if 'paragraph_string' in recipe and recipe['paragraph_string']:
        # Truncate long paragraphs
        para = recipe['paragraph_string']
        if len(para) > 300:
            para = para[:300] + "..."
        lines.append(f"Procedure: {para}")
    
    # DOI
    if 'doi' in recipe and recipe['doi']:
        lines.append(f"DOI: https://doi.org/{recipe['doi']}")
    
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Query and rank synthesis recipes from Materials Project"
    )
    parser.add_argument(
        "formula",
        help="Target material formula (e.g., 'LiFePO4', 'Li2CO3')"
    )
    parser.add_argument(
        "--type",
        dest="synthesis_type",
        help="Filter by synthesis type (e.g., 'solid-state', 'hydrothermal', 'sol-gel')"
    )
    parser.add_argument(
        "--min-temp",
        type=float,
        help="Minimum synthesis temperature in °C"
    )
    parser.add_argument(
        "--max-temp",
        type=float,
        help="Maximum synthesis temperature in °C"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of recipes to display (default: 10)"
    )
    parser.add_argument(
        "--output",
        help="Output file path for JSON results (optional)"
    )
    parser.add_argument(
        "--api-key",
        help="Materials Project API key (overrides environment variable)"
    )
    
    args = parser.parse_args()
    
    # Load API key
    api_key = args.api_key or load_api_key()
    if not api_key:
        print("Error: Materials Project API key not found")
        print("Please set MP_API_KEY environment variable or configure ~/.atomistic_skills.yaml")
        sys.exit(1)
    
    # Query recipes
    try:
        recipes = query_synthesis_recipes(
            formula=args.formula,
            api_key=api_key,
            synthesis_type=args.synthesis_type,
            min_temp=args.min_temp,
            max_temp=args.max_temp,
            limit=args.limit
        )
    except Exception as e:
        print(f"Failed to query recipes: {e}")
        sys.exit(1)
    
    if not recipes:
        print(f"No recipes found matching the criteria for {args.formula}")
        sys.exit(0)
    
    # Rank recipes
    ranked_recipes = rank_recipes(recipes)
    
    # Display results
    print(f"\nFound {len(ranked_recipes)} synthesis recipes for {args.formula}")
    print("(Ranked by simplicity: fewer precursors, lower temperature)")
    
    for i, recipe in enumerate(ranked_recipes, 1):
        print(format_recipe_output(recipe, i))
    
    # Save to file if requested
    if args.output:
        output_data = {
            "target": args.formula,
            "num_recipes": len(ranked_recipes),
            "recipes": ranked_recipes
        }
        
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
