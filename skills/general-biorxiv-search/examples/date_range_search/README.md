# Date-Range Search: bioRxiv, 2021-10-01 to 2021-10-07

## Goal

Search a fixed past window of bioRxiv postings, so the output is reproducible, with two filters:

1. **Keyword only**: preprints mentioning "AlphaFold" in title or abstract. The window
   contains the first posting of AlphaFold-Multimer (2021-10-04), a known record that
   must appear in the results.
2. **Keyword + multi-word category**: preprints mentioning "single-cell" in
   **cell biology**. This exercises the category filter for a name containing a space.

## Commands

Run from the repository root:

```bash
venv/run cpu python skills/general-biorxiv-search/scripts/biorxiv_search.py "AlphaFold" \
    --start 2021-10-01 --end 2021-10-07 --max_results 10 \
    --output skills/general-biorxiv-search/examples/date_range_search/alphafold_keyword/results.json

venv/run cpu python skills/general-biorxiv-search/scripts/biorxiv_search.py "single-cell" \
    --category cell-bio --start 2021-10-01 --end 2021-10-07 --max_results 10 \
    --output skills/general-biorxiv-search/examples/date_range_search/single_cell_cell_biology/results.json
```

Keyword filtering happens client-side, so each run pages through the whole window: 1,027
records, 35 requests of 30, about 2 minutes. Every posted version is its own record, so a
revision posted inside the window appears with its version number and that version's date.

## Output Files

- `alphafold_keyword/results.json`, `alphafold_keyword/input_configs.yaml`
- `single_cell_cell_biology/results.json`, `single_cell_cell_biology/input_configs.yaml`

## Results

### Run 1: "AlphaFold", all categories (2 records)

| DOI | Version, date | Category | Published | Title |
|:---|:---|:---|:---|:---|
| 10.1101/2021.09.15.460468 | v2, 2021-10-02 | bioinformatics | 10.1038/s41467-022-28865-w | Improved prediction of protein-protein interactions using AlphaFold2 and extended multiple-sequence alignments |
| 10.1101/2021.10.04.463034 | v1, 2021-10-04 | bioinformatics | NA | Protein complex prediction with AlphaFold-Multimer |

### Run 2: "single-cell", category `cell-bio` (6 records)

| DOI | Version, date | Published | Title |
|:---|:---|:---|:---|
| 10.1101/2021.10.01.462521 | v1, 2021-10-01 | 10.1182/bloodadvances.2022006969 | Single-cell transcriptomics reveals the identity and regulators of human mast cell progenitors |
| 10.1101/2021.09.28.462199 | v2, 2021-10-03 | 10.1186/s12915-022-01372-6 | Cell-ACDC: a user-friendly toolset embedding state-of-the-art neural networks for segmentation, tracking and cell cycle annotations of live-cell imaging data |
| 10.1101/2021.05.14.443718 | v2, 2021-10-04 | 10.1093/nar/gkab1068 | Chromatin loading of MCM hexamers is associated with di-/tri-methylation of histone H4K20 toward S phase entry |
| 10.1101/2021.10.05.463175 | v1, 2021-10-05 | 10.7554/eLife.79519 | DetecDiv, a deep-learning platform for automated cell division tracking and replicative lifespan analysis |
| 10.1101/2021.10.06.463357 | v1, 2021-10-07 | 10.1186/s12915-022-01244-z | Hyaluronidase-1-mediated glycocalyx impairment underlies endothelial abnormalities in polypoidal choroidal vasculopathy |
| 10.1101/2021.10.07.463508 | v1, 2021-10-07 | 10.1242/jcs.259392 | Fluorescence exclusion: a rapid, accurate and powerful method for measuring yeast cell volume |

The keyword is a case-insensitive substring of title + abstract, so records match through their abstracts too
(e.g. Cell-ACDC, whose abstract mentions "single-cell segmentation").

## Comparison Against Ground Truth

### Completeness: independent recount

The whole window was downloaded again outside the script: all 1,027 records for Run 1, and for
Run 2 the 47 records returned by the API's own server-side category filter,
[`?category=cell_biology`](https://api.biorxiv.org/details/biorxiv/2021-10-01/2021-10-07/0/json?category=cell_biology).
The same substring test was then applied.

| Run | Independent recount | Script | Match |
|:---|:---|:---|:---|
| "AlphaFold" | 2 records | 2 records | Same DOIs, versions and order |
| "single-cell" + cell biology | 6 of the 47 cell-biology records | 6 records | Same DOIs, versions and order |

### Known record: AlphaFold-Multimer

Run 1 returns 10.1101/2021.10.04.463034 as **v1, 2021-10-04, bioinformatics**. That matches the
[Crossref record](https://api.crossref.org/works/10.1101/2021.10.04.463034), posted 2021-10-04
with group "Bioinformatics", and the [DOI lookup example](../doi_lookup/README.md).

### Spot-check 1: Bryant et al. (Run 1)

| Field | Script record | Ground truth ([Crossref preprint](https://api.crossref.org/works/10.1101/2021.09.15.460468), [Crossref article](https://api.crossref.org/works/10.1038/s41467-022-28865-w)) | Match |
|:---|:---|:---|:---|
| Authors | Bryant, P.; Pozzati, G.; Elofsson, A. | P. Bryant, G. Pozzati, A. Elofsson | Yes |
| Category | bioinformatics | group-title "Bioinformatics" | Yes |
| Version, date | v2, 2021-10-02 | First posted 2021-09-15 (Crossref); bioRxiv API versions: v1 2021-09-15, v2 2021-10-02, v3 2021-12-15 | Yes (v2 is the version posted in the window) |
| Published | 10.1038/s41467-022-28865-w | `is-preprint-of` 10.1038/s41467-022-28865-w = *Nature Communications* **13**, 1265, issued 2022-03-10 | Yes |
| Title | ...using AlphaFold2 and extended multiple-sequence alignments | Current title "Improved prediction of protein-protein interactions using AlphaFold2" | Expected difference: v3 shortened the title; v1 and v2 carry the long title |

### Spot-check 2: DetecDiv (Run 2)

| Field | Script record | Ground truth ([Crossref preprint](https://api.crossref.org/works/10.1101/2021.10.05.463175), [Crossref article](https://api.crossref.org/works/10.7554/eLife.79519)) | Match |
|:---|:---|:---|:---|
| Authors | Aspert, T.; Hentsch, D.; Charvin, G. | Théo Aspert, Didier Hentsch, Gilles Charvin | Yes |
| Category | cell biology | group-title "Cell Biology" | Yes |
| Version, date | v1, 2021-10-05 | Posted 2021-10-05 (Crossref) | Yes |
| Published | 10.7554/eLife.79519 | `is-preprint-of` 10.7554/eLife.79519 = *eLife* **11**, e79519, issued 2022-08-17 | Yes |
| Title | DetecDiv, a deep-learning platform ... replicative lifespan analysis | Current title "DetecDiv, a generalist deep-learning platform ... survival analysis" | Expected difference: the title changed in v4 (2022-04-15) |

A date-range record is a snapshot of the version posted in the window. For a paper's current
metadata, use `--doi`, which returns the latest version.

## Category Filter Fix

The API reports categories with spaces ("cell biology"), while the script's shortcuts, like the
API's query parameter, use underscores (`cell-bio` -> `cell_biology`). The client-side check compared
the two strings literally, so every multi-word category matched nothing. Before the fix, Run 2
returned **0 records**. It now normalizes underscores to spaces and returns the 6 records above.

## References

- Evans, R. et al., "Protein complex prediction with AlphaFold-Multimer", *bioRxiv*, 2021. [DOI](https://doi.org/10.1101/2021.10.04.463034)
- Bryant, P., Pozzati, G. & Elofsson, A., "Improved prediction of protein-protein interactions using AlphaFold2", *Nature Communications* 13, 1265, 2022. [DOI](https://doi.org/10.1038/s41467-022-28865-w)
- Aspert, T., Hentsch, D. & Charvin, G., "DetecDiv, a generalist deep-learning platform for automated cell division tracking and survival analysis", *eLife* 11, e79519, 2022. [DOI](https://doi.org/10.7554/eLife.79519)
- bioRxiv API documentation: https://api.biorxiv.org/
