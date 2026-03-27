---
description: End-to-end workflow for digitizing an XRD plot image and identifying its crystalline phases.
---

# Image to XRD Phase Analysis

This workflow guides you through computationally identifying the crystalline phases of a material when your only starting point is an image or screenshot of an X-Ray Diffraction (XRD) plot.

**Scientific Problem:** 
Often in literature analysis or quick experimental checks, raw diffractometer data (`.xy` or `.xrdml` files) is unavailable, and researchers only have access to a published image of the XRD spectrum. To computationally index these peaks and confirm the phase purity or exact polymorph of the sample against a database (like the Crystallography Open Database), the image must first be transformed into a numerical dataset. This workflow connects visual AI Agent data extraction with mathematical pseudo-Voigt profiling and high-throughput DARA phase searching to achieve end-to-end phase identification from a pure visual input.

## Step-by-Step Methodology

### Step 1: Visual Peak Extraction and Digitization
Provide the AtomisticSkills Agent with the image of the XRD plot and the target chemical system.

- **Skill:** Use the `mat-xrd-digitizer` skill.
- **Action:** Instruct the Agent to use its vision capabilities to extract the 2-theta positions and relative intensities of the major peaks in the image into a `peaks.json` file. The Agent will then run the `digitize_plot.py` script on the `peaks.json` file to fit mathematical pseudo-Voigt profiles to the extracted peaks, synthesizing a realistic diffraction curve.
- **Output:** An `example.xy` data file and a verification `example.png` plot.

### Step 2: Phase Identification
Search the numerical dataset against a structural database to find the matching phases.

- **Skill:** Use the `mat-xrd-phase-analysis` skill.
- **Action:** The Agent will query the database (e.g., COD) for Candidate CIFs using the provided chemical system. It will then use DARA's BGMN-backed tree search to match the experimental `.xy` pattern against combinations of these CIFs.
- **Decision:** Review the $R_{wp}$ (Weighted Profile R-factor) of the resulting solutions. If the $R_{wp}$ is very high or the residual plot is poor, you may need to ask the Agent to re-extract the peaks more carefully in Step 1, or try a different chemical system.
- **Output:** A `results_summary.json` ranking the best matching phases, and refined fit plots bridging the digitized input with the theoretical models. 

### Optional Step 3: Refinement
If you already know the phases and simply want to refine their lattice parameters or weight fractions against the digitized plot.

- **Skill:** Use the `mat-xrd-refinement` skill.
- **Action:** Provide the specific `.cif` files directly to the DARA refinement script along with the digitized `.xy` file.

### Step 4: Synthesis Recommendation
Once the correct phase or target material is successfully identified, determine how to synthesize it experimentally.

- **Skill:** Use the `mat-synthesis-recommendation` skill.
- **Action:** Query the experimental synthesis database (such as the Materials Project text-mined database) for the identified phase's chemical formula or exact material ID.
- **Output:** A ranked list of literature-backed synthesis recipes, detailing the precursors, heating procedures, operations, and associated publication references.

## References
- DARA Automated Rietveld Analysis: [cedergrouphub.github.io/dara](https://cedergrouphub.github.io/dara)
- Pseudo-Voigt profile generation is a standard practice for profile fitting in powder diffraction.
