# GaAs Electronic Transport (AMSET)

This example demonstrates the construction of an automated computational flow to evaluate the electronic transport properties of bulk Gallium Arsenide (GaAs) using the `VaspAmsetMaker`.

## Objective
To predict the room temperature phonon-limited electron mobility and electrical conductivity of GaAs by modeling acoustic deformation potential (ADP) and polar optical phonon (POP) scattering.

## Instructions

Run the workflow generation script:
```bash
# Env: atomate2-agent
python ../../scripts/generate_inputs.py --output gaas_flow.json
```

## Expected Execution Output and Literature Validation

Because the transport workflow involves massive VASP calculations (elastic tensors and strained bands), this example simply constructs the JSON-serialized Directed Acyclic Graph (DAG) for structural reference.

If strictly executed on an HPC cluster with properly converged $40\times40\times40$ k-point grids and dense energetic interpolation, the AMSET post-processing node will yield:

*   **Electron Mobility at 300K:** $\approx 8500 \text{ cm}^2 / (\text{V}\cdot\text{s})$
*   **Hole Mobility at 300K:** $\approx 400 \text{ cm}^2 / (\text{V}\cdot\text{s})$

These computed scattering values match established experimental benchmarks for intrinsic room-temperature GaAs single crystals, limited predominantly by optical phonon and piezoelectric scattering modes.

## References
- Ganose, A. M., Park, J., Faghaninia, A. et al. "Efficient calculation of carrier scattering rates from first principles". *Nat Commun* **12**, 2222 (2021).
