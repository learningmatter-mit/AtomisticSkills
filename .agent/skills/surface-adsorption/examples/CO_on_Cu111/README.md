# Example: CO Adsorption on Cu(111)

This example demonstrates calculating the adsorption energy of a CO molecule on the (111) surface of FCC copper.

## Files

- `Cu_bulk.cif`: FCC Cu bulk structure (mp-30 from Materials Project)
- `CO.xyz`: CO molecule with optimized gas-phase geometry
- `CO_Cu111_initial.cif`: Initial structure of CO adsorbed on Cu(111) slab
- `CO_Cu111_relaxed.cif`: Relaxed structure after optimization (example)
- `adsorption_results.json`: Example output showing calculated adsorption energies

## Running the Calculation

```bash
# Env: mace-agent
python .agent/skills/surface-adsorption/scripts/calculate_adsorption.py \
    --bulk .agent/skills/surface-adsorption/examples/CO_on_Cu111/Cu_bulk.cif \
    --adsorbate .agent/skills/surface-adsorption/examples/CO_on_Cu111/CO.xyz \
    --miller_index '[1,1,1]' \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --fmax 0.05 \
    --output_dir research/CO_Cu111_adsorption
```

## Expected Results

The calculation will:
1. Relax the Cu bulk structure
2. Generate a Cu(111) slab  
3. Relax the clean slab
4. Relax the CO molecule in gas phase
5. Place CO at various adsorption sites (ontop, bridge, hollow)
6. Relax each adsorbate-slab configuration
7. Calculate adsorption energies

Typical adsorption energy for CO on Cu(111): **-0.5 to -1.5 eV** (ontop site is typically most stable)

## Notes

- The Cu(111) surface is a close-packed FCC surface, ideal for testing adsorption calculations  
- CO typically binds via the carbon atom (C-down orientation)
- Multiple adsorption sites will be automatically identified and calculated
- The most stable site and its energy will be reported in the results
