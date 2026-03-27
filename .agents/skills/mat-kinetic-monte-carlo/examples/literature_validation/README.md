# Literature Validation: H Diffusion in BCC Tungsten

Two validation routes are supported:

- **Route 0** (default): Yang-calibrated coarse-grained KMC. Adopts effective
  Arrhenius parameters from Yang et al. (2016) and verifies the engine reproduces
  the published diffusivity line.
- **Route 1** (`--from_mlip`): First-principles MLIP pipeline.  Computes the
  migration barrier via NEB and the hTST prefactor via phonon/Vineyard, then
  runs KMC with those parameters and compares to literature.

## System

| Parameter | Value |
|---|---|
| Host lattice | BCC W (a = 3.165 A) |
| Diffusing species | H (tetrahedral interstitial sites) |
| Sites per conventional cell | 12 (T-site sublattice) |
| Coordination number (z) | 4 |
| Hop distance (l) | a*sqrt(2)/4 = 1.119 A |
| Correlation factor (f) | 1 (dilute single interstitial) |
| Effective barrier | 0.440 eV (Yang et al. 2016) |
| Effective prefactor | 1.012e14 Hz (derived from Yang et al. D0 + lattice geometry) |
| Supercell | 8x8x8 conventional cells (6144 sites) |
| Carriers | 50 (0.8% occupancy -- dilute limit) |

## Prefactor Derivation

The general relation for a single-species, single-hop network is:

```
D0 = (f * z * l^2 / 6) * nu
```

where f is the correlation factor (1 for dilute single interstitial hops),
z is the coordination number, and l is the hop length.

For BCC T-sites: z = 4, l = a*sqrt(2)/4, l^2 = a^2/8, f = 1:

```
D0 = (1 * 4 * a^2/8 / 6) * nu = (a^2/12) * nu
```

Inverting with Yang et al.'s D0 = 8.45e-7 m^2/s:

```
nu = D0 / (a^2/12) = 8.45e-7 / 8.35e-21 = 1.012e14 Hz
```

**Important:** This nu is an *effective* coarse-grained prefactor that
reproduces Yang et al.'s published Arrhenius line. It is not a first-principles
hTST attempt frequency. It lumps vibrational entropy and other many-body
effects into a single constant-rate model. The KMC then becomes a
coarse-grained model calibrated to reproduce the published diffusivity,
which is the appropriate level for validating the engine.

## Analytical Reference

With these parameters, the analytical random-walk result:

```
D = (f * z * l^2 / 6) * nu * exp(-Eb / kBT)
  = (a^2/12) * nu * exp(-Eb / kBT)
  = 8.45e-7 * exp(-0.440 / kBT)   m^2/s
```

coincides exactly with the Yang et al. (2016) Arrhenius fit. This means
the validation tests both engine correctness (KMC matches analytical) and
physical relevance (the line matches published data) simultaneously.

## Literature Comparisons

| Source | Arrhenius expression | Notes |
|---|---|---|
| Yang et al. (2016) | D = 8.45e-7 * exp(-0.440/kBT) m^2/s | hTST KMC (= our analytical line) |
| Frauenfelder (1969) | D = 4.1e-7 * exp(-0.39/kBT) m^2/s | Experimental permeation data |

Frauenfelder's experimental line has a slightly different slope (Ea = 0.39 eV
vs 0.440 eV) and prefactor, reflecting anharmonic, quantum, and surface effects
not captured by the hTST model. It serves as a reality check that our
calibrated model sits in the right physical regime.

## Running

### Route 0: Yang-calibrated (engine validation)

```bash
python validate_h_in_bcc_w.py --max_steps 500000 --n_replicas 20 --out_dir .
```

### Route 1: MLIP first-principles (end-to-end predictive)

This route requires running NEB and phonon calculations on a GPU machine first.

**Step 1: Prepare structures** (on GPU)
```bash
python prepare_h_migration.py --model_type mace --model_name MACE-OMAT-0-small --output_dir .
```

**Step 2: Run NEB** (on GPU, using neb-barrier skill)
```bash
python ../../chem-neb-barrier/scripts/calculate_barrier.py \
    --start_structure start_relaxed.cif \
    --end_structure end_relaxed.cif \
    --model_type mace --model_name MACE-OMAT-0-small \
    --n_images 5 --fmax 0.02 --interpolation idpp \
    --output_dir neb_results
```

**Step 3: Extract saddle point** from NEB climbing image
```python
from ase.io import read, write, Trajectory
traj = Trajectory("neb_results/neb.traj")
# climbing image is the highest-energy intermediate
images = [traj[i] for i in range(7)]  # n_images + 2 endpoints
energies = [img.get_potential_energy() for img in images]
saddle_idx = energies.index(max(energies[1:-1]))
write("saddle_point.cif", images[saddle_idx])
```

**Step 4: Run phonon at equilibrium and saddle** (on GPU, using phonon skill)
```bash
python ../../mat-phonon/scripts/calculate_phonon.py \
    --structure start_relaxed.cif --model_type mace --model_name MACE-OMAT-0-small \
    --supercell_matrix "[[2,0,0],[0,2,0],[0,0,2]]" --output_dir phonon_eq

python ../../mat-phonon/scripts/calculate_phonon.py \
    --structure saddle_point.cif --model_type mace --model_name MACE-OMAT-0-small \
    --supercell_matrix "[[2,0,0],[0,2,0],[0,0,2]]" --output_dir phonon_ts
```

**Step 5: Compute hTST prefactor** (local, pure numpy/phonopy)
```bash
python compute_htst_prefactor.py \
    --phonon_eq phonon_eq/phonon.yaml \
    --phonon_ts phonon_ts/phonon.yaml \
    --neb_results neb_results/neb_results.json \
    --output htst_results.json
```

**Step 6: Run KMC validation with MLIP parameters**
```bash
python validate_h_in_bcc_w.py --from_mlip htst_results.json \
    --max_steps 500000 --n_replicas 20 --out_dir mlip_validation
```

## Outputs

- `validation_summary.json` -- per-temperature D values and errors
- `validation_plot.png` -- 2-panel Arrhenius + ratio plot
- `runs/` -- per-temperature/replica KMC trace files

## Results (Route 0)

| T (K) | D_KMC (A^2/s) | D_analytical (A^2/s) | Ratio | Error (%) |
|-----:|---:|---:|---:|---:|
| 500 | 3.069e+09 | 3.104e+09 | 0.989 | -1.1 |
| 700 | 5.550e+10 | 5.741e+10 | 0.967 | -3.3 |
| 900 | 2.818e+11 | 2.904e+11 | 0.970 | -3.0 |
| 1100 | 8.278e+11 | 8.146e+11 | 1.016 | +1.6 |
| 1400 | 2.263e+12 | 2.203e+12 | 1.028 | +2.8 |
| 1800 | 5.010e+12 | 4.953e+12 | 1.011 | +1.1 |
| 2300 | 9.175e+12 | 9.178e+12 | 1.000 | -0.0 |

Max error: 3.3%. **PASS** (all temperatures within 5%).

## Route 1: hTST Prefactor (Vineyard Formula)

The Vineyard formula computes the transition state theory attempt frequency
from the ratio of vibrational frequencies at the equilibrium and saddle point:

```
nu_hTST = prod(nu_eq, i=1..3N-3) / prod(nu_ts, j=1..3N-4)
```

where 3N-3 excludes the 3 acoustic (translational) modes at Gamma, and 3N-4
additionally excludes the imaginary mode at the saddle point (the reaction
coordinate).

Expected ranges for H in BCC W:
- NEB barrier: 0.2-0.4 eV
- hTST prefactor: 10^12-10^14 Hz
- D0: same order of magnitude as Yang et al. (8.45e-7 m^2/s) and Frauenfelder (4.1e-7 m^2/s)

## References

1. Yang, C. et al. (2016). Kinetic Monte Carlo Simulation of Hydrogen Diffusion in Tungsten. *International Conference on Nuclear Engineering*.
2. Frauenfelder, R. (1969). Solution and Diffusion of Hydrogen in Tungsten.
   *J. Vac. Sci. Technol.* 6, 388.
3. Heinola, K. & Ahlgren, T. (2010). Diffusion of hydrogen in bcc tungsten
   studied with first principle calculations. *J. Appl. Phys.* 107, 113531.
