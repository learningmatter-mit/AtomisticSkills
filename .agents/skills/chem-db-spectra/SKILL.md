---
name: chem-db-spectra
description: Search and download experimental InfraRed (IR), Mass spectra, and UV-Vis spectra data (JCAMP-DX format) for molecules.
category: chemistry
---

# chem-db-spectra

## Goal
To query experimental molecular spectra—such as Infrared (IR), Mass Spectrometry, and UV-Vis—from standard experimental databases like the NIST Chemistry WebBook for baseline comparison against properties computed via MLIPs or DFT.

## Instructions

### Step 1. Query Spectra Data

Use the `query_spectra.py` script to fetch available spectrographic data for a given chemical formula. The script automatically searches the NIST Chemistry WebBook, resolves the compound, and downloads all available JCAMP-DX (`.jdx`) formatted spectra into the specified directory.

```bash
# Env: base-agent
python .agents/skills/chem-db-spectra/scripts/query_spectra.py <formula> <output_dir> [--type {IR,Mass,UVVis,All}]
```

Parameters:
- `formula`: The chemical formula to query (e.g., `CH4`, `C2H6O`).
- `output_dir`: The directory path to save the downloaded JCAMP-DX (`.jdx`) spectrum files.
- `--type`: Filter the spectrum type to download (options: `IR`, `Mass`, `UVVis`, `All`). Default is `All`.

## Constraints
- **Environments**: The scripts require the `base-agent` Conda environment.
- **Spectrum Format**: Output data is universally saved in JCAMP-DX (`.jdx`) standard format. You must use appropriate spectroscopic python package (e.g., `jcamp`) if you need to parse it back into numpy arrays.
- **Scraping Dependability**: This script utilizes HTML scraping (`beautifulsoup4`). If the NIST WebBook layout changes in the future, the selectors may need to be updated.

## References
- Linstrom, P.J. and Mallard, W.G., Eds., *NIST Chemistry WebBook, NIST Standard Reference Database Number 69*, National Institute of Standards and Technology, Gaithersburg MD. [URL](https://webbook.nist.gov)
- JCAMP-DX for Infrared, Raman, and Related Data. [URL](https://jcamp-dx.org)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
