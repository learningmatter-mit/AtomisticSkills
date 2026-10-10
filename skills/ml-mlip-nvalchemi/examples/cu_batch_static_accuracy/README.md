# Batched vs sequential static inference on strained Cu (MACE-OMAT-0-small, TensorNet)

## Goal

Reproduce part of [`resources/benchmark_results.md`](../../resources/benchmark_results.md) with the
skill's benchmark script, for two models:

- **Accuracy (the validation).** NValchemi-batched energies, forces and stresses must equal the
  default sequential path (the model's own ASE calculator) to floating-point precision.
- **Speed.** Batched vs sequential wall time. This depends on hardware and load, so it is reported
  next to the stored values rather than treated as a pass/fail check.

The NValchemi backend is **experimental and opt-in**. The script requests it explicitly with
`static_calculation(structures, use_nvalchemi=True)`. Every batched call logged
`Using experimental NValchemi batching. Toolkit 0.2.0 dynamics has known correctness limitations`,
and the script rejects any call whose result does not report `backend == "nvalchemi"` (a silent
sequential fallback). All rows below passed that check. The baseline is the same call without the
flag (`backend == "sequential"`).

## Inputs

N = 2, 5, 10 and 20 primitive FCC Cu cells (1 atom each), `a = 3.6 Å` scaled by 0.96–1.04
(`np.linspace(0.96, 1.04, N)`), built inside the script. Timing is best of 3. The header of
`benchmark_results.md` says "4 atoms", but `_make_cu_structures` calls `bulk("Cu", "fcc", a=...)`
without `cubic=True`, which gives the 1-atom primitive cell.

## Commands (repository root)

```bash
venv/run mlip python skills/ml-mlip-nvalchemi/scripts/run_nvalchemi_benchmark.py \
    --env mace --models MACE-OMAT-0-small --device cuda --n-repeat 3 --output results_mace.json
venv/run mlip python skills/ml-mlip-nvalchemi/scripts/run_nvalchemi_benchmark.py \
    --env matgl --models TensorNet-PES-PBE --device cuda --n-repeat 3 --output results_matgl.json
```

`--models` filters by label substring; `TensorNet-PES-PBE` selects
`TensorNet-PES-MatPES-PBE-2025.2`. Outputs: [`results_mace.json`](results_mace.json) and
[`results_matgl.json`](results_matgl.json).

**Hardware:** NVIDIA GB10, unified memory (mlip env: mace-torch 0.3.16, matgl 4.1.0,
nvalchemi-toolkit 0.2.0). Peak memory of each run: 3.0 GB GPU / 2.9 GB RSS (MACE) and
0.5 GB GPU / 2.4 GB RSS (TensorNet). Each run takes under a minute.

## Results

### Accuracy: batched minus sequential (max over the N structures)

| Model | N | ΔE max (eV) | ΔF max (eV/Å) | ΔS max (eV/Å³) | Stored ΔE / ΔF / ΔS |
| :--- | :---: | :---: | :---: | :---: | :--- |
| MACE-OMAT-0-small | 2 | 4.8e-07 | 0.0 | 9.2e-08 | 4.8e-07 / 0.0 / 1.8e-07 |
| | 5 | 0.0 | 0.0 | 2.3e-07 | 9.5e-07 / 0.0 / 2.2e-07 |
| | 10 | 1.9e-06 | 0.0 | 3.9e-07 | 1.4e-06 / 0.0 / 2.5e-07 |
| | 20 | 1.4e-06 | 0.0 | 3.0e-07 | 9.5e-07 / 0.0 / 2.5e-07 |
| TensorNet-PES-MatPES-PBE-2025.2 | 2 | 5.7e-07 | 0.0 | 4.1e-08 | 3.8e-07 / 0.0 / 8.9e-08 |
| | 5 | 5.7e-07 | 0.0 | 1.3e-07 | 1.4e-07 / 0.0 / 1.8e-07 |
| | 10 | 8.6e-07 | 0.0 | 1.3e-07 | 8.6e-07 / 0.0 / 1.1e-07 |
| | 20 | 8.6e-07 | 0.0 | 4.3e-07 | 1.3e-06 / 0.0 / 2.4e-07 |

**Validation passes.** Forces are identical (ΔF = 0) and energy and stress differences are
≤ 1.9 × 10⁻⁶ eV and ≤ 4.3 × 10⁻⁷ eV/Å³. That is float32 round-off: the total energies are about
4 eV (MACE-OMAT) per structure, and float32 resolves about 1 part in 10⁷ (≈ 5 × 10⁻⁷ eV). The values
have the same magnitude as the stored table, whose notes attribute them to nondeterministic kernel
ordering. They are well inside the 5 × 10⁻³ eV screening tolerance used in
`benchmark_results.md`.

### Speed: wall time and speedup (best of 3)

| Model | N | NV (ms) | Seq (ms) | Speedup | Stored NV / Seq / speedup |
| :--- | :---: | ---: | ---: | ---: | :--- |
| MACE-OMAT-0-small | 2 | 173 | 160 | 0.93× | 158 / 143 / 0.90× |
| | 5 | 21 | 382 | 18.4× | 17 / 361 / 21.7× |
| | 10 | 38 | 952 | 25.1× | 18 / 733 / 41.2× |
| | 20 | 25 | 1562 | 61.7× | 21 / 1420 / 68.0× |
| TensorNet-PES-MatPES-PBE-2025.2 | 2 | 22 | 29 | 1.36× | 19 / 30 / 1.6× |
| | 5 | 22 | 74 | 3.37× | 21 / 75 / 3.6× |
| | 10 | 24 | 145 | 6.07× | 22 / 153 / 7.0× |
| | 20 | 27 | 290 | 10.6× | 28 / 310 / 11.1× |

The trend reproduces. The batched call costs about the same for every N, while the sequential cost
grows linearly with N, so the speedup grows roughly as N. The per-N values are within 10–40 % of
the stored ones. The largest gap is MACE at N = 10, whose batched time (38 ms) is an outlier.

Read the speedups with two caveats:

- **The sequential baseline is dominated by per-structure overhead.** For MACE it rebuilds the ASE
  calculator for every structure: about 75 ms per 1-atom cell, against about 7 ms per structure
  for TensorNet. For 1-atom cells the comparison mostly measures Python and launch overhead, not
  model throughput. It says nothing about MD or relaxation speed.
- **N = 2 for MACE is slower when batched** (0.93×), in both this run and the stored table. The
  first batched call includes NValchemi warm-up that best-of-3 does not fully hide.

## Batched MD timing (`run_md_benchmark.py`)

The script runs 20 strained Cu FCC supercells (108 atoms each, 2160 in the batch) for 100 steps of
`nvt_nose_hoover` at 300 K, dt = 2 fs. It compares one-at-a-time `run_md` calls (default path)
with a single `run_md(..., use_nvalchemi=True)` batch, best of 2. It ran on an otherwise idle GPU:

```bash
venv/run mlip python skills/ml-mlip-nvalchemi/scripts/run_md_benchmark.py --env mace --n-repeat 2
venv/run mlip python skills/ml-mlip-nvalchemi/scripts/run_md_benchmark.py --env matgl --n-repeat 2
```

| Model | Sequential (s) | Batched (s) | Speedup | Stored (SKILL.md) | Peak GPU memory |
| :--- | ---: | ---: | ---: | :--- | ---: |
| MACE-OMAT-0-small | 53.1 | 38.0 (`backend=nvalchemi`) | **1.40×** | 54.5 / 11.1 s, 4.90× | 19.9 GB (batched) |
| TensorNet-PES-MatPES-PBE-2025.2 | 59.4 | stopped (> 37 GB) | — | 1.8× (16 structures × 200 steps) | > 37 GB (batched) |

- **MACE: the sequential time reproduces (−3 %), the batched time does not (3.4× slower).** One
  batched NValchemi forward on the 2160-atom batch takes 398 ms, against 28 ms for one 108-atom
  structure (552 ms for 20). The batched step (about 380 ms) is therefore bound by the model
  forward, and about 1.4× is the ceiling for this workload with the current stack (mace-torch
  0.3.16, nvalchemi-toolkit 0.2.0, no cuEquivariance). The stored 11.1 s (June 2026, mace-torch
  0.3.15) implies a forward 3.6× faster than today's. The 2.0.0 neighbor-cache guard adds only
  6–8 % for MACE ([verification report](../../../../docs/verification/nvalchemi-neighbor-cache.md)),
  so it does not explain the gap. As `SKILL.md` warns, historical speedups do not certify the
  current release.
- **TensorNet batched MD was stopped for memory safety.** GPU use jumped above 37 GB (from below
  28 GB within one second) on this unified-memory machine, and the run was killed before
  finishing. Batched TensorNet MD for 20 × 108 atoms is not safe on a shared GB10. Use fewer or
  smaller structures per batch.
- Batched MD memory is far larger than static inference. MACE needed 19.9 GB here versus 3 GB for
  the static benchmark above, so size batches from a small trial run.

## References

- I. Batatia et al., "A foundation model for atomistic materials chemistry",
  [arXiv:2401.00096](https://arxiv.org/abs/2401.00096) (MACE foundation models).
- MatGL / TensorNet: see [`../../SKILL.md`](../../SKILL.md) References.
- Stored values: [`resources/benchmark_results.md`](../../resources/benchmark_results.md)
  (NVIDIA GB10, best of 3, same script).
