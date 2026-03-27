#!/bin/bash
# Example: Query elastic properties of Si and related materials
# This demonstrates elastic modulus filtering

cd "$(dirname "$0")/.." || exit 1

echo "=== Querying elastic properties from Materials Project ==="
echo ""

# Query Si elasticity
echo "1. Querying Si (mp-149) elastic properties..."
python scripts/get_elasticity.py \
    --material_id mp-149 \
    --output examples/si_elasticity.json

echo ""

# Query materials with high bulk modulus
echo "2. Querying materials with bulk modulus 200-400 GPa..."
python scripts/get_elasticity.py \
    --bulk_modulus_min 200 \
    --bulk_modulus_max 400 \
    --output examples/high_bulk_modulus.json

echo ""
echo "✓ Results saved to:"
echo "  - examples/si_elasticity.json"
echo "  - examples/high_bulk_modulus.json"
