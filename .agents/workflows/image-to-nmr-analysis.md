---
description: Digitize an NMR spectrum image and quantify its mixture composition — combines plot digitization with reaction product prediction and Wasserstein deconvolution.
---

# Image to NMR Mixture Analysis

This workflow is a specialization of `reaction-to-nmr-quantification.md` where the user's starting point is an **image** of a 1H NMR spectrum rather than a numeric data file.

The agent should follow `reaction-to-nmr-quantification.md` starting from **Step 0 (Digitize Spectrum Images)**, which invokes the `general-plot-digitizer` skill to convert the image to a two-column `.csv` file before proceeding with the standard quantification pipeline.

See: [reaction-to-nmr-quantification.md](reaction-to-nmr-quantification.md)
