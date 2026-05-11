import os
import subprocess

orca_bin = os.getenv("ORCA_BINARY_PATH")
if orca_bin is None:
    raise RuntimeError("'ORCA_BINARY_PATH' is not set!")
if not os.path.exists(orca_bin):
    raise RuntimeError("'ORCA_BINARY_PATH' is set but does not point to a valid path!")

inputfile_text = """
!HF DEF2-SVP
* xyz 0 1
O   0.0000   0.0000   0.0626
H  -0.7920   0.0000  -0.4973
H   0.7920   0.0000  -0.4973
*
"""
with open("test_calc.inp", "w") as f:
    f.write(inputfile_text)

with open("test_calc.out", "w") as f:
    subprocess.run([orca_bin, "test_calc.inp"], stdout=f)
with open("test_calc.out", "r") as f:
    if "ORCA TERMINATED NORMALLY" not in f.read():
        raise RuntimeError("ORCA calculation was not successful")
