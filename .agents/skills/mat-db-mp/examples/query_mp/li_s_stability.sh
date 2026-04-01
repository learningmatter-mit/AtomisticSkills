#!/bin/bash
# Example: Query stable Li-S materials from Materials Project
# This demonstrates the basic usage of query_mp.py with stability filtering

cd "$(dirname "$0")/.." || exit 1

echo "=== Querying stable Li-S materials from Materials Project ==="
echo ""

python scripts/query_mp.py \
    --chemsys "Li-S" \
    --properties energy_above_hull formation_energy_per_atom band_gap \
    --e_above_hull_max 0.05 \
    --limit 10 \
    --output examples/li_s_stable.json

echo ""
echo "✓ Results saved to examples/li_s_stable.json"
echo "  Query: Li-S chemical system"
echo "  Filter: energy_above_hull < 0.05 eV/atom (stable materials)"
echo "  Properties: energy_above_hull, formation_energy_per_atom, band_gap"
