#!/bin/bash
# Example: Query magnetic properties of Fe-based materials
# This demonstrates magnetic ordering and magnetization filtering

cd "$(dirname "$0")/.." || exit 1

echo "=== Querying magnetic properties from Materials Project ==="
echo ""

# Query specific material magnetism
echo "1. Querying Fe2O3 (mp-19770) magnetic properties..."
python scripts/get_magnetism.py \
    --material_id mp-19770 \
    --output examples/fe2o3_magnetism.json

echo ""

# Query ferromagnetic materials
echo "2. Querying ferromagnetic materials with high magnetization..."
python scripts/get_magnetism.py \
    --ordering FM \
    --total_magnetization_min 10.0 \
    --output examples/ferromagnetic_materials.json

echo ""
echo "✓ Results saved to:"
echo "  - examples/fe2o3_magnetism.json"
echo "  - examples/ferromagnetic_materials.json"
