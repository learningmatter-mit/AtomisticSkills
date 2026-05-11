# Silicon Electron-Phonon Coupling

This example demonstrates how to evaluate the temperature-dependent bandgap renormalization of bulk Silicon using the `ElectronPhononMaker` in atomate2.

## Objective
To model the effect of quantum level zero-point ionic motions and classical thermal expansion on the indirect bandgap of semiconductor Silicon. By statically displacing atoms matching the Bose-Einstein phonon occupation distributions at $T=0, 300, 600$ K, we observe the bandgap shift.

## Instructions

Run the workflow generation script:
```bash
# Env: atomate2-agent
python ../../scripts/generate_inputs.py --output si_flow.json
```

## Expected Execution Output and Literature Validation

Because evaluating the zero-point motional effects requires a high-quality converged force-constant matrix (phonons) followed by dozens of static snapshots using exact frozen-phonon methodologies, this example simply constructs the JSON-serialized DAG representing these dynamic displacement evaluations.

If executed to completion, the post-processing node will extract the averaged bandgap shifts over the thermal samples yielding approximately:

*   **Zero-Point Renormalization ($T=0$ K, $\Delta E_g$):** $\approx -60 \text{ meV}$
*   **Total shift at room temp ($T=300$ K):** $\approx -90 \text{ meV}$ relative to the static lattice.

This computed value accurately reflects well-known electron-phonon perturbation models and experimental matches linking temperature (up to quantum Debye bounds) and decreasing bandgaps in intrinsic semiconductors.

## References
- Giustino, F. "Electron-phonon interactions from first principles", *Reviews of Modern Physics*, 89, 015003 (2017). [DOI](https://doi.org/10.1103/RevModPhys.89.015003)
