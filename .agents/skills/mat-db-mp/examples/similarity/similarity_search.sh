#!/bin/bash
# Example: Find structurally similar materials to Si
# This demonstrates crystal structure similarity search

cd "$(dirname "$0")/.." || exit 1

echo "=== Finding structurally similar materials ==="
echo ""

# Find materials similar to Si
echo "1. Finding structures similar to Si (mp-149)..."
python scripts/find_similar_structures.py \
    --material_id mp-149 \
    --top 15 \
    --output examples/similar_to_si.json

echo ""

# Find similar structures with chemical system filter
echo "2. Finding C structures similar to Si..."
python scripts/find_similar_structures.py \
    --material_id mp-149 \
    --top 20 \
    --chemsys "C" \
    --output examples/similar_si_carbon_only.json

echo ""
echo "✓ Results saved to:"
echo "  - examples/similar_to_si.json"
echo "  - examples/similar_si_carbon_only.json"
