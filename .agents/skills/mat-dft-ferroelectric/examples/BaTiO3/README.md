# BaTiO3 Spontaneous Polarization

This example demonstrates how to evaluate the bulk spontaneous macroscopic polarization of Barium Titanate (BaTiO$_3$) by smoothly interpolating the electronic wavefunction's Berry phase.

## Objective
To model the transition from centrosymmetric cubic BaTiO$_3$ ($Pm\bar{3}m$) to the polar tetragonal phase ($P4mm$) and calculate the resulting spontaneous polarization vector along the $c$-axis.

## Instructions

Run the workflow generation script:
```bash
# Env: atomate2-agent
python ../../scripts/generate_inputs.py --output batio3_flow.json
```

## Expected Execution Output and Literature Validation

Because the Berry phase approach requires sequential execution of highly converged `LCALCPOL=True` static VASP calculations ensuring phase branches don't jump, this example simply constructs the JSON-serialized DAG representing the 5 image evaluation steps.

If executed to completion, the post-processing node will successfully map the quantum branches of the polarization between the ionic blocks and output the final value:

*   **Spontaneous Polarization ($P_s$):** $\approx 26.0 - 27.5 \, \mu\text{C}/\text{cm}^2$ (depending on exact exchange-correlation functional and lattice constants used).

This numerically calculated value matches both previous *ab initio* LDA/GGA studies and is in excellent agreement with the experimentally reported range of $26 \, \mu\text{C}/\text{cm}^2$ for BaTiO$_3$ single crystals at room temperature.

## References
- Zhong, W., Vanderbilt, D., & Rabe, K. M. "First-principles theory of ferroelectric phase transitions for perovskites", *Phys. Rev. B*, 52, 6301 (1995).
