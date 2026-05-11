# calphad-agent Environment

Isolated Conda environment for macroscopic computational thermodynamics.
Powers the `mat-calphad-phase-diagram` and `mat-calphad-property-diagram` skills using the open-source `pycalphad` library.

## Installation
Run the provided installer script:

```bash
./install.sh
```

## Description
This environment avoids complex DFT/MLIP specific dependencies from other skills and relies entirely on purely thermodynamic calculation tools.
