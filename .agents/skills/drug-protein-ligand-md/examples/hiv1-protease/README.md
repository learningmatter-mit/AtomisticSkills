# HIV-1 Protease Protein-Ligand MD Example (PDB 1HSG)

## Goal
Demonstrate the full MD pipeline (minimize, NVT equilibration, NPT equilibration, production) using the solvated 1HSG complex from the system builder example.

## Input Files
Uses outputs from `drug-complex-system-builder/examples/hiv1-protease/system/`:
- `system.xml`: serialized OpenMM System
- `complex_solvated.pdb`: solvated complex topology

## Steps

Short test run (2 ps total, for pipeline validation only):

```bash
# Env: drugmd-agent
python .agents/skills/drug-protein-ligand-md/scripts/run_md.py \
  --system_xml <path_to>/system/system.xml \
  --input_pdb <path_to>/system/complex_solvated.pdb \
  --temperature 300 \
  --timestep 2.0 \
  --minimize_steps 5000 \
  --equil_nvt_steps 500 \
  --equil_npt_steps 500 \
  --production_steps 1000 \
  --reporting_interval 100 \
  --checkpoint_interval 500 \
  --seed 42 \
  --output_dir run/
```

## Expected Output
- `run/minimized.pdb`: structure after energy minimization (PE ~ -935,000 kJ/mol)
- `run/nvt_equilibration.log`: NVT equilibration energy/temperature log
- `run/npt_equilibration.log`: NPT equilibration energy/temperature/density log
- `run/production.dcd`: 10-frame production trajectory (~6 MB)
- `run/production.log`: temperature converging toward 300 K, density toward ~1.0 g/mL
- `run/final_state.xml`: serialized state for restarts
- `run/md_provenance.json`: all simulation parameters

## Notes
- This test uses 2 fs timestep (not 4 fs) and minimal step counts for fast validation.
- The 100-step minimization from the first attempt caused NaN energies; 5000 steps resolved it. Always use sufficient minimization for newly built systems.
- Wall time: ~58 s on CPU (OpenCL) for this tiny run.
