# LiCoO2 Li-ion Migration Barrier

This example demonstrates how to calculate the activation energy barrier for a Lithium ion hopping to a nearest-neighbor vacancy in Layered LiCoO2 (Space Group R-3m).

## Overview

- **Material**: LiCoO2
- **Process**: Li hopping to a Va_Li site.
- **Model**: MACE-OMAT-0-small
- **Interpolation**: IDPP (Image Dependent Pair Potential) - Crucial for avoiding atomic overlap in this dense system.

## Files

- `prepare_licoo2.py`: 
    - Queries LiCoO2 from Materials Project (mp-22526).
    - Creates a supercell.
    - Removes one Li atom to create a vacancy.
    - Relaxes the initial state (Start).
    - Moves a NN Li atom to the vacancy and relaxes (End).
    - Saves `start.cif` and `end.cif` to `neb_input/`.
- `run_example.sh`: Automated script to run preparation and NEB calculation.
- `neb_barrier_plot.png`: Expected output plot (Barrier ~0.87 eV).

## Usage

1. Activate MACE environment:
   ```bash
   conda activate mace-agent
   ```

2. Run the example:
   ```bash
   bash run_example.sh
   ```

## Results

Using MACE-OMAT-0-small with IDPP interpolation:
- **Barrier**: ~0.87 eV
- **Convergence**: Fast (~30 steps with FIRE) compared to linear interpolation failure.
