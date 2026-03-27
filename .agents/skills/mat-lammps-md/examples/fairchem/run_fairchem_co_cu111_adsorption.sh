#!/usr/bin/env bash
set -euo pipefail

# Env: fairchem-agent
# CO adsorption on Cu(111) via FAIR-Chem lmp_fc.

OUT_DIR="${OUT_DIR:-./out-fairchem-co-cu111}"
TASK_NAME="${TASK_NAME:-omol}"
LMP_FC_BIN="${LMP_FC_BIN:-lmp_fc}"

mkdir -p "${OUT_DIR}"

if ! command -v "${LMP_FC_BIN}" >/dev/null 2>&1; then
  echo "Missing '${LMP_FC_BIN}' in PATH." >&2
  echo "Install with: bash conda-envs/fairchem-agent/install_lammps.sh" >&2
  exit 1
fi

OUT_DIR="${OUT_DIR}" python - <<'PY'
from ase.build import add_adsorbate
from ase.build import fcc111
from ase.build import molecule
from ase.io.lammpsdata import write_lammps_data
import os

out_dir = os.environ["OUT_DIR"]

slab = fcc111("Cu", size=(4, 4, 4), vacuum=15.0, orthogonal=True)
slab.center(axis=2, vacuum=15.0)

co = molecule("CO")
co.rotate(90.0, "y", center="COM")
co.center(vacuum=12.0)
co.set_pbc((True, True, True))

ads = slab.copy()
add_adsorbate(ads, co, height=1.85, position="ontop")
ads.center(axis=2, vacuum=15.0)

write_lammps_data(f"{out_dir}/cu111_clean.data", slab, atom_style="atomic", masses=True)
write_lammps_data(f"{out_dir}/co_gas.data", co, atom_style="atomic", masses=True)
write_lammps_data(f"{out_dir}/co_on_cu111.data", ads, atom_style="atomic", masses=True)
PY

run_case() {
  local datafile="$1"
  local energyfile="$2"
  local logfile="$3"
  local infile="$4"

  cat > "${infile}" <<EOF
units           metal
atom_style      atomic
boundary        p p p

read_data       ${datafile}

neighbor        2.0 bin
neigh_modify    delay 0 every 1 check yes
thermo          1
thermo_style    custom step pe etotal

run             0
EOF

  "${LMP_FC_BIN}" lmp_in="${infile}" task_name="${TASK_NAME}" > "${logfile}" 2>&1

  python - <<PY
import re
from pathlib import Path

log_text = Path("${logfile}").read_text()
matches = re.findall(r"^\\s*\\d+\\s+([-+0-9.eE]+)\\s+[-+0-9.eE]+\\s*$", log_text, flags=re.MULTILINE)
if not matches:
    raise SystemExit("Could not parse thermo PE from ${logfile}")
Path("${energyfile}").write_text(matches[-1] + "\\n")
PY
}

run_case \
  "${OUT_DIR}/cu111_clean.data" \
  "${OUT_DIR}/E_cu111.txt" \
  "${OUT_DIR}/log_cu111.lammps" \
  "${OUT_DIR}/in.cu111_fairchem_fc"

run_case \
  "${OUT_DIR}/co_gas.data" \
  "${OUT_DIR}/E_co.txt" \
  "${OUT_DIR}/log_co.lammps" \
  "${OUT_DIR}/in.co_fairchem_fc"

run_case \
  "${OUT_DIR}/co_on_cu111.data" \
  "${OUT_DIR}/E_co_on_cu111.txt" \
  "${OUT_DIR}/log_ads.lammps" \
  "${OUT_DIR}/in.co_on_cu111_fairchem_fc"

OUT_DIR="${OUT_DIR}" python - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(os.environ["OUT_DIR"])

e_slab = float((out_dir / "E_cu111.txt").read_text().strip())
e_co = float((out_dir / "E_co.txt").read_text().strip())
e_ads_sys = float((out_dir / "E_co_on_cu111.txt").read_text().strip())
e_ads = e_ads_sys - e_slab - e_co

result = {
    "E_cu111_eV": e_slab,
    "E_co_eV": e_co,
    "E_co_on_cu111_eV": e_ads_sys,
    "E_adsorption_eV": e_ads,
    "formula": "E_ads = E(CO/Cu111) - E(Cu111) - E(CO)",
}

(out_dir / "energies.json").write_text(json.dumps(result, indent=2))
(out_dir / "adsorption_summary.txt").write_text(
    "CO on Cu(111) adsorption example\n"
    f"E_adsorption_eV = {e_ads:.6f}\n"
    "Negative values indicate exothermic adsorption.\n"
)
PY

echo "Finished. Inspect:"
echo "  ${OUT_DIR}/energies.json"
echo "  ${OUT_DIR}/adsorption_summary.txt"
