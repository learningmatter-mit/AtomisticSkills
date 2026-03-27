#!/usr/bin/env bash
set -euo pipefail

# Env: matgl-agent
# Cu heat-and-hold scan using ASE + CHGNet (no LAMMPS bridge).

OUT_DIR="${OUT_DIR:-./out-matgl-cu-phase-transition}"
CHGNET_MODEL="${CHGNET_MODEL:-0.3.0}"
HEAT_STEPS="${HEAT_STEPS:-500}"
HOLD_STEPS="${HOLD_STEPS:-500}"
TRAJ_EVERY="${TRAJ_EVERY:-20}"
TIMESTEP_FS="${TIMESTEP_FS:-1.0}"
FRICTION="${FRICTION:-0.02}"

mkdir -p "${OUT_DIR}"

if ! python - <<'PY'
import torch
import numpy as np
from chgnet.model.model import CHGNet  # noqa: F401
if int(np.__version__.split(".")[0]) >= 2:
    raise SystemExit(1)
PY
then
  echo "Repairing runtime (need numpy<2 and CHGNet importable)..."
  python -m pip install "numpy<2" chgnet
  python - <<'PY'
import torch, numpy as np
print("Runtime check passed:", torch.__version__, np.__version__)
PY
fi

OUT_DIR="${OUT_DIR}" CHGNET_MODEL="${CHGNET_MODEL}" HEAT_STEPS="${HEAT_STEPS}" HOLD_STEPS="${HOLD_STEPS}" \
TRAJ_EVERY="${TRAJ_EVERY}" TIMESTEP_FS="${TIMESTEP_FS}" FRICTION="${FRICTION}" \
python - <<'PY'
import json
import os
from pathlib import Path

import numpy as np
import torch
from ase import units
from ase.build import bulk
from ase.io.lammpsdata import write_lammps_data
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary, ZeroRotation

from chgnet.model.dynamics import CHGNetCalculator
from chgnet.model.model import CHGNet

out_dir = Path(os.environ["OUT_DIR"])
chgnet_model = os.environ["CHGNET_MODEL"]
heat_steps = int(os.environ["HEAT_STEPS"])
hold_steps = int(os.environ["HOLD_STEPS"])
traj_every = int(os.environ["TRAJ_EVERY"])
timestep_fs = float(os.environ["TIMESTEP_FS"])
friction = float(os.environ["FRICTION"])

atoms = bulk("Cu", "fcc", a=3.615) * (8, 8, 8)
write_lammps_data(out_dir / "cu_fcc.data", atoms, atom_style="atomic", masses=True)

device = "cuda" if torch.cuda.is_available() else "cpu"
chgnet = CHGNet.load(model_name=chgnet_model, use_device=device)
atoms.calc = CHGNetCalculator(model=chgnet, use_device=device)

MaxwellBoltzmannDistribution(atoms, temperature_K=300.0)
Stationary(atoms)
ZeroRotation(atoms)

traj_frames = []
records = []
step = 0

def record_state():
    global step  # noqa: PLW0603
    pe = atoms.get_potential_energy()
    ke = atoms.get_kinetic_energy()
    temp = atoms.get_temperature()
    records.append({"step": step, "temp_K": temp, "pe_eV": pe, "etotal_eV": pe + ke})
    if step % traj_every == 0:
        traj_frames.append(atoms.copy())
    step += 1

dyn_heat = Langevin(atoms, timestep=timestep_fs * units.fs, temperature_K=1700.0, friction=friction)
dyn_heat.attach(record_state, interval=1)
dyn_heat.run(heat_steps)

dyn_hold = Langevin(atoms, timestep=timestep_fs * units.fs, temperature_K=1700.0, friction=friction)
dyn_hold.attach(record_state, interval=1)
dyn_hold.run(hold_steps)

if not traj_frames:
    traj_frames.append(atoms.copy())

traj_path = out_dir / "cu_heat.lammpstrj"
with traj_path.open("w", encoding="utf-8") as fh:
    for i, frame in enumerate(traj_frames):
        cell = frame.get_cell()
        a, b, c = cell[0], cell[1], cell[2]
        xlo, xhi = 0.0, float(np.linalg.norm(a))
        ylo, yhi = 0.0, float(np.linalg.norm(b))
        zlo, zhi = 0.0, float(np.linalg.norm(c))
        xy, xz, yz = float(b[0]), float(c[0]), float(c[1])
        pos = frame.get_positions()
        types = frame.get_atomic_numbers()
        fh.write("ITEM: TIMESTEP\n")
        fh.write(f"{i * traj_every}\n")
        fh.write("ITEM: NUMBER OF ATOMS\n")
        fh.write(f"{len(frame)}\n")
        fh.write("ITEM: BOX BOUNDS xy xz yz pp pp pp\n")
        fh.write(f"{xlo:.10f} {xhi:.10f} {xy:.10f}\n")
        fh.write(f"{ylo:.10f} {yhi:.10f} {xz:.10f}\n")
        fh.write(f"{zlo:.10f} {zhi:.10f} {yz:.10f}\n")
        fh.write("ITEM: ATOMS id type x y z\n")
        for idx, (atype, p) in enumerate(zip(types, pos), start=1):
            fh.write(f"{idx} {atype} {p[0]:.10f} {p[1]:.10f} {p[2]:.10f}\n")

with (out_dir / "log.matgl").open("w", encoding="utf-8") as f:
    f.write("# step temp_K pe_eV etotal_eV\n")
    for r in records:
        f.write(f"{r['step']} {r['temp_K']:.6f} {r['pe_eV']:.8f} {r['etotal_eV']:.8f}\n")

(out_dir / "run_summary.json").write_text(
    json.dumps(
        {
            "model": f"CHGNet-{chgnet_model}",
            "device": device,
            "natoms": len(atoms),
            "heat_steps": heat_steps,
            "hold_steps": hold_steps,
            "traj_every": traj_every,
            "timestep_fs": timestep_fs,
        },
        indent=2,
    ),
    encoding="utf-8",
)
PY

echo "Finished. Inspect:"
echo "  ${OUT_DIR}/log.matgl"
echo "  ${OUT_DIR}/cu_heat.lammpstrj"
