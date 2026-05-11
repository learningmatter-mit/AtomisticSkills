# Example: Querying Experimental Spectra for Methane

This example demonstrates how to use the `query_spectra.py` script to retrieve available experimental spectra (in JCAMP-DX `.jdx` format) for Methane ($CH_4$).

## Instructions

Run the query script:
```bash
# Env: base-agent
python ../../scripts/query_spectra.py CH4 output_spectra/
```

## Expected Output

The script will query the NIST WebBook, locate the specific compound id for Methane, and check for available IR, Mass, and UV-Vis spectra. It will iteratively download the associated JCAMP spectra.

In the `output_spectra/` directory, you should find files like:
- `C74828_IR_0.jdx` (The primary InfraRed spectrum of Methane)
- `C74828_Mass_0.jdx` (The Mass spectroscopy data of Methane)

*Note: You can open `.jdx` files in standard text editors as they are human-readable, or parse them programmatically using python libraries like `jcamp`.*
