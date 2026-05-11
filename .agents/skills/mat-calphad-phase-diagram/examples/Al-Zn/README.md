# Example: Aluminum-Zinc Phase Diagram

This example reproduces the classic Al-Zn parameterization by S. Mey (1993) using `pycalphad`.

## Files
- `alzn_mey.tdb`: The Thermodynamic Data Base containing the models and fitting parameters for the Al-Zn system.

## Generating the Phase Diagram
To plot the T-x (Temperature vs Mole Fraction of Zn) binary phase diagram from 300 K to 1000 K with a temperature resolution of 10 K, run the following command:

```bash
# Env: calphad-agent
python ../../scripts/plot_phase_diagram.py alzn_mey.tdb --elements Al Zn --t-range 300 1000 10 --output Al-Zn_diagram.png
```

## Interpreting the Output
The resulting `Al-Zn_diagram.png` will show:
- The solidus and liquidus boundaries dividing the all-liquid region from the multi-phase regions.
- A broad miscibility gap at lower temperatures within the FCC phase, typical for the Al-Zn system.
- An invariant reaction/eutectic behavior correctly located for this alloy.

### Literature Validation
The generated phase diagram accurately matches the features reported in literature:
1. **Miscibility gap**: Matches the broad FCC miscibility gap spanning across composition.
2. **Invariant reaction**: The eutectoid-like reaction feature (around 550K / 277°C) matches cleanly with experimental and assessed boundaries.
3. **Liquidus/Solidus**: Matches the steep liquidus drop from pure Al (~933K) to Zn (~692K).

**Reference:**
- Sabine an Mey, "Reevaluation of the Al-Zn system," *Zeitschrift für Metallkunde*, Vol. 84, No. 7, 1993, pp. 451–455.
