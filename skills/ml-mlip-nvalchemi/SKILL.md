---
name: ml-mlip-nvalchemi
description: Optional experimental GPU-accelerated batched inference for MACE, MatGL (TensorNet/M3GNet/CHGNet), and FairChem MLIPs using NValchemi, enabling parallel static, relax, and MD workflows across multiple structures simultaneously.
metadata:
  category: [machine-learning]
  venv: [fairchem, mlip]
---

# ml-mlip-nvalchemi

## Goal

Run optional GPU-parallel static predictions, relaxation and MD across multiple
structures with NValchemi. **This backend is experimental and disabled by
default in AtomisticSkills 2.0.0.** List and directory inputs normally run each
structure through the model's native calculator and ASE/MatCalc. Installing
`nvalchemi-toolkit` or selecting a GPU does not enable the batch engine.

> [!WARNING]
> The locked toolkit 0.2.0 has confirmed batch-dynamics correctness defects.
> Same-size refills and variable-cell changes can omit periodic neighbors;
> AtomisticSkills guards this cache defect for 0.2.x, with measurable overhead.
> A separate defect can leave live energies inconsistent with frozen geometry
> after convergence; preserving the first converged snapshot reduces exposure
> but does not repair the upstream live batch. MatGL inflight remains disabled.
> Native NPT currently falls back to ASE because initial stress is missing.
> Static predictions do not reuse the defective dynamics cache, but this does
> not establish correctness for every model or structure. Historical speedups
> are workload-specific and do not certify the release's dynamics paths.

**Explicit selection:** pass `use_nvalchemi=True` on each batch call to
`static_calculation`, `relax_structure` or `run_md`. MCP tools expose the same
flag on `predict_structure`, `relax_structure` and `run_md`. The default is
`False`; the choice does not persist into later calls. Runtime logs identify
experimental use, and batch results report the actual `backend`.

When offering this option, explain these limitations. Do not enable it merely
because batching could be faster. Validate a small representative case against
the default path before a larger run, and check `backend` for any fallback.
Single-structure calls continue using their normal calculator.

## Background

NValchemi provides batched dynamics integrators (FIRE, NVT Nose-Hoover, NPT, etc.) and a `BaseModelMixin` interface. AtomisticSkills wraps each MLIP in a `BaseModelMixin`-compatible class:

| MLIP | NValchemi wrapper | Location |
|------|------------------|----------|
| MACE | `nvalchemi.models.mace.MACEWrapper` | upstream (nvalchemi-toolkit) |
| MatGL TensorNet | `matgl.ext._alchmtk.TensorNetWrapper` | matgl package |
| MatGL M3GNet | `M3GNetWrapper` | `src/utils/mlips/nvalchemi/matgl_wrappers.py` |
| MatGL CHGNet | `CHGNetWrapper` | `src/utils/mlips/nvalchemi/matgl_wrappers.py` |
| MatGL QET | `QETWrapper` | matgl package |
| FairChem UMA | `FairChemWrapper` | `src/utils/mlips/nvalchemi/fairchem_nv.py` |

With `use_nvalchemi=True`, `src/utils/mlips/base.py` dispatches as follows:

- `static_calculation(list, use_nvalchemi=True)` → `_batch_static_nvalchemi()` → single batched forward
- `relax_structure(list, use_nvalchemi=True)` → `_batch_relax_nvalchemi()` → batched FIRE
- `run_md(list, use_nvalchemi=True)` → `_batch_md_nvalchemi()` → batched NVT/NVE/NPT integrator

### Inflight batching (relaxation)

After explicit opt-in, relaxation can choose fixed-batch or inflight execution:

```
_batch_relax()
 ├─ use_nvalchemi=True AND nvalchemi available AND model loads?
 │    YES → _batch_relax_nvalchemi()
 │              └─ sum(atoms) > max_batch_atoms AND model._nvalchemi_supports_inflight?
 │                   YES → _batch_relax_nvalchemi_inflight()   ← rolling GPU window
 │                   NO  → fixed-batch NValchemi               ← all structures at once
 │    NO  → _batch_relax_sequential()                          ← plain ASE FIRE, one by one
```

> **Note**: All MatGL wrappers (`TensorNetWrapper`, `M3GNetWrapper`, `CHGNetWrapper`) set `_nvalchemi_supports_inflight=False` and use fixed-batch NValchemi regardless of structure count, because after graduation, energies are wrong (TensorNet Cu −83.70 vs −86.57 eV fixed-batch; CHGNet 0.26 eV; M3GNet 28 meV), MACE inflight is available after opt-in with the cache guard.

**Inflight batching** keeps only `max_batch_atoms` atoms on the GPU at once.  As each structure converges or exhausts its step budget it is evicted and a new one is loaded.  This is necessary when the full set of structures would exceed GPU memory.

**`max_batch_atoms` — how it is set:**

| How | Behaviour |
|-----|-----------|
| `max_batch_atoms=None` (default) | Auto-estimated: `free_VRAM × 0.5 / bytes_per_atom` using per-architecture calibration (FairChem 0.15 B/param/atom, MACE 0.5, M3GNet 4.0, fallback 5 MB/atom) |
| Explicit integer (e.g. `500`) | Forces inflight for almost any real dataset; recommended on shared GPUs |
| Very large integer | Forces fixed-batch (all structures in one GPU call) |

### How to tell which backend ran

Every batch result dict carries a `"backend"` key:

| `"backend"` value | Meaning |
|---|---|
| `"nvalchemi_inflight"` | Inflight rolling-window (large datasets / shared GPU) |
| `"nvalchemi"` | Fixed-batch NValchemi (entire set fits in one GPU pass) |
| `"sequential"` | Plain ASE FIRE, one structure at a time |

```python
result = wrapper.relax_structure(structures, fmax=0.05, steps=500, use_nvalchemi=True)
print(result["backend"])   # "nvalchemi_inflight" / "nvalchemi" / "sequential"
```

Logger messages (written to stderr / MCP server log) also signal transitions:
- `"Total atoms (N) exceeds batch limit (M); switching to inflight batching."`
- `"NValchemi inflight relax: N structures, live batch ≤M atoms, ≤S steps/structure."`

### Variable-cell relaxation validation

Variable-cell relaxation uses upstream `FIRE2VariableCell` with `dt=0.05`,
`tmax=0.5`, `delaystep=5`, and `maxstep=0.2`. Its cell force is already normalized
by system size; AtomisticSkills no longer applies an additional atom-count
scaling. Standard-form cell preparation is retained.

All three relaxation modes report `success` only on convergence,
`not_converged` at the step limit, and `failed` for execution errors. Results
include `converged` and per-structure `steps`, with separate aggregate counts.
For variable-cell runs, convergence includes the per-atom virial row norm as
well as atomic forces. This is the small-strain counterpart of ASE's
`FrechetCellFilter` criterion, not exact equality at finite strain.

**Neighbor-cache handling in 2.0.0:** NValchemi 0.2.x can omit neighbors after
same-size refills or gradual cell changes. AtomisticSkills uses a version-gated
guard for every neighbor hook in fixed relaxation, inflight relaxation and
batch MD. Changes to cell, PBC or atom partition trigger a complete allocation
refresh; ordinary fixed-cell steps retain their buffers. Installed packages
are unchanged. MACE inflight stays available after opt-in, and FairChem builds its own graph
without this hook. See the [exposure and timing report](../../docs/verification/nvalchemi-neighbor-cache.md).

The separate upstream inactive-output defect can still return live energies
inconsistent with frozen coordinates after convergence. MatGL inflight remains
disabled pending validation of that repair. Trajectory extraction preserves
the first converged snapshot; turning extraction off exposes the live-batch
output limitation. A corrected upstream release is still needed to retire
the compatibility guard.

The former variable-cell speedup tables used force-only convergence and are
withdrawn. New speedups remain pending a supported upstream release containing
the neighbor-cache and inactive-output repairs. A source-checkout validation
run must not be presented as performance of the committed dependency locks.
Static-inference and MD tables below measure different operations.

### Molecular Dynamics (MD) Benchmark: Sequential vs. Batched (20 structures, 100 steps)

Speedup comparison for a 100-step MD simulation under the `nvt_nose_hoover` ensemble at 300 K on 20 strained Cu FCC structures, each expanded to a fixed 108-atom cubic supercell ($\ge 10\text{ \AA}$ sides). Sequential = NValchemi disabled, structures run one at a time; Batched = all 20 driven through NValchemi integrators in a single GPU batch. Best-of-2 wall time, measured serially (one environment at a time to avoid GPU contention).

#### MACE-OMAT-0-small (`mlip`)
- **Sequential MD:** 53.1 s (earlier record: 54.48 s)
- **Batched MD (NValchemi):** 38.0 s (**1.40x speedup**), peak GPU memory 19.9 GB. An earlier record of 11.12 s (4.90x) does not reproduce with the committed locks: one batched forward on 2160 atoms takes ~398 ms, so the batched step is bound by the model forward. See the [example](examples/cu_batch_static_accuracy/README.md).

#### TensorNet-PES-MatPES-PBE-2025.2 (`mlip`)
- **Sequential MD:** baseline
- **Batched MD (NValchemi):** **1.8× speedup** over sequential (16 structures × 200 steps on GB10; batch NVE energy drift equals sequential, max 0.02 meV/atom)

#### FairChem uma-s-1p2 (`fairchem`)
- **Sequential MD:** 339.74 s
- **Batched MD:** disabled — routed to sequential (see note below; measured ~0.64x, i.e. *slower*, before being disabled)

> **When does batched MD help?** Batched MD gives modest speedups for launch-latency-bound models at small system sizes (MACE **1.40x** in the latest re-run, TensorNet **1.8x** in the earlier record), at a much larger memory cost than static inference (≈20 GB GPU for 20 × 108-atom MACE structures; a TensorNet re-run of the same benchmark exceeded 37 GB and was stopped). Estimate memory before batching MD. For heavy models like FairChem uma-s-1p2 whose single-system path is already compute-bound, batching provides no speedup and MD is routed to sequential. The wrappers still accept a list of structures (and batch **static/relax** remain available); only FairChem's MD path is gated. Measured on NVIDIA GB10 (aarch64, CUDA 13, Warp 1.14).

> **FairChem batched MD disabled (`_nvalchemi_supports_batch_md = False`):** uma-s-1p2's forward scales **superlinearly per atom** — ≈1.57 ms/atom at batch=1 (108 atoms) rising to ≈2.43 ms/atom at batch=20 (2160 atoms), 1.55x worse — so a single large batched step is *slower* than running the structures one at a time through the model's optimized single-system path (batched 0.64x). Two facts pin this down: (1) the cost is intrinsic to the eSCN/MoE forward, not the neighbor list — correcting the wrapper cutoff (12 A → the model's true 6 A) cut `adapt_input` edges from 530 to 78 per atom but left the per-step time unchanged at ~5.25 s; (2) uma-s-1p2 runs with `external_graph_gen=False`, so it **rebuilds its own graph internally and ignores the edges `adapt_input` provides** (energies are identical for any cutoff we pass, including a 0-edge 2 A list). Batched MD is therefore correct (energies match sequential to 0.00 meV/atom) but never a speedup, so `run_md` falls back to sequential.

> **TensorNet batched MD enabled with stream fix:** TensorNet batch MD is re-enabled. The `NeighborListHook` "race" it was previously disabled for was a CUDA stream mismatch, now fixed by `warp_on_torch_stream` in `src/utils/mlips/nvalchemi/nvalchemi_utils.py`. Batch NVE energy drift equals sequential (max 0.02 meV/atom), and batch MD is 1.8× faster than sequential for 16 structures × 200 steps on GB10.


## Instructions

### Step 1 — Verify NValchemi is Available

```python
# (or venv/fairchem for FairChem models)
from src.utils.mlips.nvalchemi.nvalchemi_utils import NVALCHEMI_AVAILABLE
print(NVALCHEMI_AVAILABLE)  # must be True

from src.utils.mlips.mace.mace_wrapper import MACEWrapper
wrapper = MACEWrapper(model_name="MACE-OMAT-0-small", device="cuda")
wrapper.load()
nv = wrapper._get_nvalchemi_model()
print(nv)  # should be non-None MACEWrapper(nvalchemi)
```

### Step 2 — Batch Static Calculation

Pass a list of ASE Atoms objects to `static_calculation`. The result dict includes a `"backend": "nvalchemi"` key when the batch path was used:

```python
from ase.build import bulk
import numpy as np

structures = [bulk("Cu", "fcc", a=3.6 * s) for s in np.linspace(0.96, 1.04, 10)]
result = wrapper.static_calculation(structures, use_nvalchemi=True)
# result["backend"] == "nvalchemi"
# result["total_structures"] == 10
# result["results"][i] == {"energy": ..., "forces": ..., "stress": ...}
```

Identical API for MatGL and FairChem wrappers:

```python
from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
wrapper = MatGLWrapper(model_name="TensorNet-PES-MatPES-PBE-2025.2", device="cuda")
wrapper.load()
result = wrapper.static_calculation(structures, use_nvalchemi=True)
```

```python
from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper
wrapper = FAIRCHEMWrapper(model_name="uma-s-1p2", device="cuda")
wrapper.load()
result = wrapper.static_calculation(structures, use_nvalchemi=True)
```

### Step 3 — Batch Geometry Relaxation

```python
result = wrapper.relax_structure(
    structure_data=structures,   # list of ASE Atoms
    use_nvalchemi=True,          # explicit experimental-backend selection
    fmax=0.05,                   # eV/Å convergence
    steps=500,
    output_dir="/path/to/output",
    # relax_cell=True,           # optional: variable-cell relaxation
    # max_batch_atoms=500,       # optional: set explicitly on shared GPUs to force
    #                            # inflight mode and avoid OOM; None = auto from VRAM
)
print(result["backend"])         # "nvalchemi_inflight", "nvalchemi", or "sequential"
```

Variable-cell batch relaxation (`relax_cell=True`) converges only when the per-atom virial row norm is also below `fmax` (the small-strain counterpart of ASE's `FrechetCellFilter`). Per-structure `relax.log` files (ASE FIRE format) are written incrementally to `{output_dir}/{structure_name}/relax.log` during inflight runs, so partial results survive an OOM abort.

### Step 4 — Batch Molecular Dynamics

```python
result = wrapper.run_md(
    structure_data=structures,
    use_nvalchemi=True,
    temperature=1000,
    steps=1000,
    timestep=2.0,                # fs
    ensemble="nvt_nose_hoover",
    output_dir="/path/to/output"
)
```

Validated fixed-cell batch families: `nve`, `nvt_nose_hoover`, `nvt_langevin`.
NPT aliases select a NValchemi integrator but currently fall back to ASE because
the integration does not publish initial stress; native NPT is not validated.
Unsupported (Berendsen, Andersen, inhomogeneous NPT) fall back to sequential automatically.

### Step 5 — Use the Default Backend

Omit the flag, or set it to `False`; no module patching is needed:

```python
result = wrapper.static_calculation(structures)
assert result["backend"] == "sequential"
result = wrapper.relax_structure(structures, use_nvalchemi=False)
```

MCP/CLI example of an explicit experimental request (two structure files):

```bash
${CLAUDE_SKILL_DIR}/../../venv/run mlip python -m src.mcp_server.cli mace \
    load_model model_name=MACE-OMAT-0-small device=cuda \
    predict_structure 'structure_data=["first.cif","second.cif"]' use_nvalchemi=true
```

### Step 6 — Run the Benchmark Script

To re-run the full accuracy and speed benchmark for any environment:

```bash
${CLAUDE_SKILL_DIR}/../../venv/run mlip python ${CLAUDE_SKILL_DIR}/scripts/run_nvalchemi_benchmark.py \
    --env mace \
    --n-repeat 3 \
    --output results_mace.json

${CLAUDE_SKILL_DIR}/../../venv/run mlip python ${CLAUDE_SKILL_DIR}/scripts/run_nvalchemi_benchmark.py \
    --env matgl \
    --n-repeat 3 \
    --output results_matgl.json

${CLAUDE_SKILL_DIR}/../../venv/run fairchem python ${CLAUDE_SKILL_DIR}/scripts/run_nvalchemi_benchmark.py \
    --env fairchem \
    --n-repeat 3 \
    --output results_fairchem.json
```

The script tests N=2, 5, 10, 20 structures and prints a speedup/accuracy table.

## Benchmark Results

See [resources/benchmark_results.md](resources/benchmark_results.md) for the full results table.

### Speedup Summary (GPU, NVIDIA GB10 Blackwell cc12.1, best-of-3, N=20 structures)

| Model | Speedup (N=5) | Speedup (N=20) | ΔE max (eV) |
|-------|:---:|:---:|:---:|
| MACE-OMAT-0-small | 21.7× | **68×** | 9.5e-07 |
| MACE-OMAT-0-medium | 22.9× | **72×** | 9.5e-07 |
| MACE-MH-1/omat_pbe | 14.3× | **34×** | 1.6e-07 |
| MACE-MH-1/matpes_r2scan | 14.4× | **34×** | 1.2e-07 |
| MACE-MP-medium-0b3 | 22.9× | **76×** | 1.4e-06 |
| MACE-MATPES-PBE-0 | 23.6× | **77×** | 7.2e-07 |
| MACE-MATPES-R2SCAN-0 | 24.2× | **76×** | 1.9e-06 |
| TensorNet-PES-MatPES-PBE-2025.2 | 3.6× | **11×** | 1.4e-07 |
| TensorNet-PES-MatPES-r2SCAN-2025.2 | 3.8× | **12×** | 8.0e-07 |
| M3GNet-PES-MatPES-PBE-2025.2 | 3.7× | **11×** | 1.3e-03¹ |
| M3GNet-PES-MatPES-r2SCAN-2025.2 | 3.9× | **11×** | 7.2e-04¹ |
| CHGNet-PES-MatPES-PBE-1M-2026.9 | 4.3× | **12×** | 2.4e-07 |
| CHGNet-PES-MatPES-r2SCAN-1M-2026.9 | 4.2× | **13×** | 9.5e-07 |
| QET-PES-MatPES-PBE-2025.2 | 4.2× | **13×** | 7.2e-07 |
| QET-PES-MatPES-r2SCAN-2025.2 | 3.9× | **14×** | 9.5e-07 |
| SO3Net-PES-ANI-1x-Subset | — | — | not supported |
| FairChem uma-s-1p2 (omat) | 3.0× | 2.9× | 1.6e-07 |
| FairChem uma-m-1p1 (omat) | 2.9× | 3.5× | 1.7e-07 |
| FairChem uma-s-1p1 (omat) | 3.4× | 5.5× | 2.5e-07 |

¹ M3GNet energy errors (~0.7–1.8×10⁻³ eV) from different neighbor-list graph connectivity (NValchemi GPU warp kernel vs. CPU `radius_graph_pbc`). Forces are exact (ΔF = 0). Within 5×10⁻³ eV tolerance for PES screening.

## Examples

- [Batched vs sequential static inference on strained Cu](examples/cu_batch_static_accuracy/README.md): re-runs `run_nvalchemi_benchmark.py` for MACE-OMAT-0-small and TensorNet-PES-MatPES-PBE-2025.2 (N = 2–20). Batched and sequential results agree to float32 round-off (ΔF = 0, ΔE ≤ 1.9e-6 eV), with speedups reported next to the stored table. A batched-MD re-run gives 1.4× for MACE (stored 4.9×; now bound by the model forward) and peaks at 20 GB GPU, while TensorNet batched MD exceeded 37 GB.

## Constraints

- **Explicit opt-in required**: Set `use_nvalchemi=True` for each batch request.
- **NValchemi required**: `nvalchemi-toolkit` must be installed. Check `NVALCHEMI_AVAILABLE` flag. Falls back to sequential if unavailable.
- **Environment isolation**: Must use the correct uv environment per MLIP:
  - `mlip` — MACE models and MatGL (TensorNet, M3GNet, CHGNet)
  - `fairchem` — FairChem UMA
- **Stress format**: NValchemi returns 3×3 Cauchy stress tensor (eV/Å³); sequential path returns ASE Voigt-6. Both formats are accepted downstream — `_extract_static()` in tests handles the conversion.
- **FairChem dataset field**: UMA model requires `dataset` (e.g., `"omat"`) passed to `FCAtomicData`. This is handled automatically by `FairChemWrapper`; defaults to `"omat"` when `task_name=None`.
- **CHGNet batch speedup**: CHGNet directed line graph construction parallelizes well on GPU (12–13× at N=20). CPU performance is marginal (<3×); always use `device="cuda"` for batch workloads.
- **SO3Net not supported**: `SO3Net-PES-ANI-1x-Subset` falls back to sequential automatically (`_get_nvalchemi_model()` returns `None`).
- **ANI-1x models with transition metals**: TensorNet-PES-ANI-1x and M3GNet-PES-ANI-1x training sets cover only H/C/N/O. Using them with Cu or other transition metals causes a CUDA index OOB error that corrupts the CUDA context for the session. Run ANI-1x models in a separate process from other models.
- **MatGL models (TensorNet, CHGNet, M3GNet) inflight batching not supported**: Inflight batching stays off for the MatGL wrappers (TensorNet, M3GNet, CHGNet), for a measured reason: after graduation, energies are wrong (TensorNet Cu −83.70 vs −86.57 eV fixed-batch; CHGNet 0.26 eV; M3GNet 28 meV), while MACE inflight agrees to meV. All MatGL wrappers set `_nvalchemi_supports_inflight=False`; when the total atom count exceeds the batch budget, they fall through to fixed-batch NValchemi (all structures in one GPU pass) rather than inflight. For large MatGL sets, split inputs into smaller calls or retain default sequential execution. `max_batch_atoms` does not cap the fixed-batch allocation when inflight is disabled.
- **Unsupported ensembles for batch MD**: `nvt_berendsen`, `nvt_andersen`, `nvt_bussi`, `npt_berendsen`, and `npt_inhomogeneous` have no NValchemi equivalent and always run sequentially.

## References

- NValchemi toolkit: NVIDIA internal package (nvalchemi-toolkit, PyPI: `https://pypi.nvidia.com`)
- MACE: Batatia et al., "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields", *NeurIPS 2022*. [arXiv:2206.07697](https://arxiv.org/abs/2206.07697)
- MatGL / TensorNet: Chen & Ong, "A Universal Graph Deep Learning Interatomic Potential for the Periodic Table", *Nature Computational Science 2023*. [DOI:10.1038/s43588-022-00349-3](https://doi.org/10.1038/s43588-022-00349-3)
- M3GNet: Chen & Ong, "A universal graph deep learning interatomic potential for the periodic table", *Nature Computational Science 2022*.
- CHGNet: Deng et al., "CHGNet as a pretrained universal neural network potential for charge-informed atomistic modelling", *Nature Machine Intelligence 2023*. [DOI:10.1038/s42256-023-00716-3](https://doi.org/10.1038/s42256-023-00716-3)
- FairChem UMA: Meta FAIR, "Scaling Universal Molecular Atomistic Machine Learning for Open Catalyst 2024". [arXiv:2411.12234](https://arxiv.org/abs/2411.12234)

---

**Author:** Bowen Deng
**Contact:** [github.com/bowen-bd](https://github.com/bowen-bd)
