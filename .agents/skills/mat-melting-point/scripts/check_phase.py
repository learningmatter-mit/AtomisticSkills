#!/usr/bin/env python
"""
Phase identification using pre-computed MLIP latent features.

This script takes atomic features (descriptors) as input and determines
whether the structure is solid, liquid, or coexisting based on projection
onto the solid-liquid axis.

Usage:
    python check_phase.py <features.json> --research_dir <dir>
    
Where features.json contains:
    {
        "atomic_features": [[...], [...], ...],
        "num_atoms": N,
        "feature_dim": D
    }
"""
import numpy as np
import json
import argparse
from pathlib import Path


def load_references(ref_file):
    """Load reference descriptors for solid and liquid phases."""
    if not ref_file.exists():
        raise FileNotFoundError(f"Reference file not found: {ref_file}")
    
    refs = np.load(ref_file)
    return refs["solid_mean"], refs["liquid_mean"]


def project_and_classify(descriptors, mu_solid, mu_liquid):
    """
    Project atomic descriptors onto solid-liquid axis and classify.
    
    Args:
        descriptors: np.array of shape (N_atoms, feature_dim)
        mu_solid: Mean descriptor for solid phase
        mu_liquid: Mean descriptor for liquid phase
        
    Returns:
        is_solid: Boolean array indicating solid atoms
        projections: Projection values for each atom
        solid_fraction: Fraction of solid atoms
    """
    # Solid-liquid axis
    v = mu_liquid - mu_solid
    v_norm_sq = np.dot(v, v)
    
    # Project: p = (d - mu_solid) . v / |v|^2
    # p = 0 means at mu_solid (solid reference)
    # p = 1 means at mu_liquid (liquid reference)
    projections = np.dot(descriptors - mu_solid, v) / v_norm_sq
    
    # Classification: atoms closer to solid (p < 0.5) are solid
    is_solid = projections < 0.5
    solid_fraction = np.mean(is_solid)
    
    return is_solid, projections, solid_fraction


def main():
    parser = argparse.ArgumentParser(
        description="Analyze phase using pre-computed MLIP atomic features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("features_file", help="JSON file with atomic features")
    parser.add_argument("--research_dir", required=True, help="Research directory with phase_references.npz")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()
    
    # Load reference descriptors
    ref_file = Path(args.research_dir) / "phase_references.npz"
    mu_solid, mu_liquid = load_references(ref_file)
    
    # Load atomic features from JSON
    with open(args.features_file) as f:
        features_data = json.load(f)
    
    descriptors = np.array(features_data["atomic_features"])
    
    if args.verbose:
        print(f"Loaded features: {descriptors.shape[0]} atoms, {descriptors.shape[1]} features")
        print(f"Solid reference: {mu_solid.shape}")
        print(f"Liquid reference: {mu_liquid.shape}")
    
    # Classify
    is_solid, projections, solid_fraction = project_and_classify(descriptors, mu_solid, mu_liquid)
    
    # Report results
    print(f"\n{'='*60}")
    print(f"Phase Analysis Results")
    print(f"{'='*60}")
    print(f"  Total Atoms:      {len(descriptors)}")
    print(f"  Solid Atoms:      {np.sum(is_solid)} ({solid_fraction:.2%})")
    print(f"  Liquid Atoms:     {np.sum(~is_solid)} ({1.0 - solid_fraction:.2%})")
    print(f"  Mean Projection:  {np.mean(projections):.3f}")
    print(f"  Std Projection:   {np.std(projections):.3f}")
    print(f"{'='*60}")
    
    # Determine overall phase
    if solid_fraction > 0.95:
        result = "LIKELY_SOLID"
        print(f"  Phase: ✓ {result}")
    elif solid_fraction < 0.05:
        result = "LIKELY_LIQUID"
        print(f"  Phase: ✓ {result}")
    else:
        result = "LIKELY_INTERFACE_COEXISTENCE"
        print(f"  Phase: ⚠ {result}")
    
    print(f"{'='*60}\n")
    
    return result


if __name__ == "__main__":
    main()
