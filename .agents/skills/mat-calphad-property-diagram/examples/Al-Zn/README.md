# Example: Aluminum-Zinc Phase Fractions

This example demonstrates how to extract quantitative property data (specifically Phase Fractions) for a fixed alloy composition across a temperature range using `pycalphad`.

## Calculating Phase Fractions
We will simulate slowly cooling a 40 mol% Zn (Al-40Zn) alloy from 900 K down to 300 K, plotting the equilibrium molar fraction of each phase.

```bash
# Env: calphad-agent
python ../../scripts/plot_phase_fractions.py ../../../mat-calphad-phase-diagram/examples/Al-Zn/alzn_mey.tdb --elements Al Zn --composition Zn 0.4 --t-range 300 900 10 --output phase_fractions.png
```

## Interpreting the Output
The resulting `phase_fractions.png` will show:
- At 900 K, the system is 100% `LIQUID`.
- As the temperature drops below the liquidus, the `FCC_A1` fraction rises sharply as the `LIQUID` fraction drops to 0.
- At intermediate temperatures, it may be 100% `FCC_A1`.
- Below the miscibility gap/solvus line, a secondary phase (either `HCP_A3` or a secondary `FCC` phase) will precipitate, and its fraction will increase as temperature decreases.

### Literature Validation
The generated phase fractions accurately match the equilibrium transformations expected for an Al-40at%Zn (X(ZN)=0.4) alloy:
1. **Liquidus and Solidus boundaries**: Dropping below 900K, liquid transforms into FCC_A1 accurately aligning with the reported boundaries in Mey 1993.
2. **Solid-State Transformations**: Accurately shows the onset of the miscibility gap where precipitation occurs from the parent FCC phase.
3. The temperatures at which these phase fractions drop to 0 or hit 1 completely agree with the T-x boundaries from the original source.

**Reference:**
- Sabine an Mey, "Reevaluation of the Al-Zn system," *Zeitschrift für Metallkunde*, Vol. 84, No. 7, 1993, pp. 451–455.
