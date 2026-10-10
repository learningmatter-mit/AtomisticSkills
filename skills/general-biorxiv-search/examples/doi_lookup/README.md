# DOI Lookup: AlphaFold-Multimer and ESM-2

## Goal

Retrieve a bioRxiv preprint's metadata from its DOI, then check each field (title,
authors, posting date, version, category, published-journal DOI) against the official record.
Two well-known preprints cover both outcomes of the `published` field:

| Preprint | DOI | Versions | Journal version |
|:---|:---|:---|:---|
| Evans et al., "Protein complex prediction with AlphaFold-Multimer" | [10.1101/2021.10.04.463034](https://doi.org/10.1101/2021.10.04.463034) | 2 | none |
| Lin et al., "Evolutionary-scale prediction of atomic level protein structure with a language model" (ESM-2) | [10.1101/2022.07.20.500902](https://doi.org/10.1101/2022.07.20.500902) | 3, title and author list changed after v1 | *Science* 2023 |

## Commands

Run from the repository root:

```bash
venv/run cpu python skills/general-biorxiv-search/scripts/biorxiv_search.py \
    --doi 10.1101/2021.10.04.463034 \
    --output skills/general-biorxiv-search/examples/doi_lookup/alphafold_multimer/paper.json

venv/run cpu python skills/general-biorxiv-search/scripts/biorxiv_search.py \
    --doi 10.1101/2022.07.20.500902 \
    --output skills/general-biorxiv-search/examples/doi_lookup/esm2/paper.json
```

Each run makes one API request and writes a one-element JSON list, plus the
`input_configs.yaml` holding the arguments.

## Output Files

- `alphafold_multimer/paper.json`, `alphafold_multimer/input_configs.yaml`
- `esm2/paper.json`, `esm2/input_configs.yaml`

## Ground Truth Sources

The bioRxiv website (`www.biorxiv.org`) answers scripted requests with HTTP 429 (bot
protection), so its landing pages could not be fetched. The record was taken from three sources instead:

1. **bioRxiv API, all versions**: the official bioRxiv record, one entry per posted version
   ([AlphaFold-Multimer](https://api.biorxiv.org/details/biorxiv/10.1101/2021.10.04.463034/na/json),
   [ESM-2](https://api.biorxiv.org/details/biorxiv/10.1101/2022.07.20.500902/na/json)), and its
   published-article endpoint
   ([AlphaFold-Multimer](https://api.biorxiv.org/pubs/biorxiv/10.1101/2021.10.04.463034/na/json),
   [ESM-2](https://api.biorxiv.org/pubs/biorxiv/10.1101/2022.07.20.500902/na/json)).
2. **Crossref**: the DOI registration bioRxiv deposits, which is independent of the API
   ([AlphaFold-Multimer](https://api.crossref.org/works/10.1101/2021.10.04.463034),
   [ESM-2 preprint](https://api.crossref.org/works/10.1101/2022.07.20.500902),
   [ESM-2 Science article](https://api.crossref.org/works/10.1126/science.ade2574)).
3. **Europe PMC** preprint record PPR403752 for AlphaFold-Multimer
   ([REST record](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:PPR403752%20AND%20SRC:PPR&format=json&resultType=core)).

Every DOI above resolves through doi.org (HTTP 302). The bioRxiv and *Science* landing pages it
redirects to refuse scripted clients (HTTP 429 and 403), so the Crossref records stand in for them.

## Results vs. Ground Truth

### AlphaFold-Multimer

| Field | Script output | Ground truth | Match |
|:---|:---|:---|:---|
| Title | Protein complex prediction with AlphaFold-Multimer | Same title (Crossref, Europe PMC) | Yes |
| Authors | 22, from "Evans, R.; O'Neill, M.; Pritzel, A." to "Jumper, J.; Hassabis, D." | 22, from Richard Evans to Demis Hassabis, same order (Crossref, Europe PMC) | Yes |
| Version, date | v2, 2022-03-10 | v1 posted 2021-10-04 (Crossref `posted`, Europe PMC first publication); v2 posted 2022-03-10 (bioRxiv API version list) | Yes, latest version |
| Category | bioinformatics | Crossref `group-title` "Bioinformatics" | Yes |
| Published | `NA` | No `is-preprint-of` relation in Crossref; bioRxiv pubs endpoint: "no articles found for published version"; Europe PMC lists no journal version | Yes |
| URL | https://www.biorxiv.org/content/10.1101/2021.10.04.463034v2 | DOI resolves via doi.org to the bioRxiv lookup page | Yes |

### ESM-2

| Field | Script output | Ground truth | Match |
|:---|:---|:---|:---|
| Title | Evolutionary-scale prediction of atomic level protein structure with a language model | Same title (Crossref preprint record) | Yes |
| Authors | 15, from "Lin, Z.; Akin, H.; Rao, R." to "Candido, S.; Rives, A." | 15, from Zeming Lin to Alexander Rives, same order (Crossref) | Yes |
| Version, date | v3, 2022-12-21 | v1 2022-07-21 (Crossref `posted`), v2 2022-10-31, v3 2022-12-21 (bioRxiv API version list) | Yes, latest version |
| Category | synthetic biology | Crossref `group-title` "Synthetic Biology" | Yes |
| Published | `10.1126/science.ade2574` | Crossref `is-preprint-of` 10.1126/science.ade2574 = Lin et al., *Science* **379**(6637), 1123-1130, published 2023-03-17; bioRxiv pubs endpoint: journal "Science", published 2023-03-17 | Yes |

The `date` field is the posting date of the version returned. The first posting date is
the v1 date in the API's version list (also Crossref's `posted` date).

## Latest-Version Selection

The API returns one entry per version, oldest first. Before this example was added, the
script returned the first entry. For ESM-2 that meant the superseded v1 record: version 1, dated
2022-07-21, under the original title *"Language models of protein sequences at the scale of
evolution enable accurate structure prediction"*, with 11 of the 15 authors. The script now returns
the highest version, the one the DOI resolves to.

| ESM-2 version | Date | Title | Authors |
|:---|:---|:---|:---|
| v1 | 2022-07-21 | Language models of protein sequences at the scale of evolution enable accurate structure prediction | 11 |
| v2 | 2022-10-31 | Evolutionary-scale prediction of atomic level protein structure with a language model | 15 |
| v3 | 2022-12-21 | Evolutionary-scale prediction of atomic level protein structure with a language model | 15 |

## Notes

- The API writes author names as "Surname, Initials" in ASCII ("Zidek, A."), whereas Crossref keeps
  the full names and diacritics ("Augustin Žídek").
- The `published` field is filled in only once bioRxiv links the preprint to a journal article,
  so re-running the lookup later can change it from `NA` to a DOI.

## References

- Evans, R. et al., "Protein complex prediction with AlphaFold-Multimer", *bioRxiv*, 2021. [DOI](https://doi.org/10.1101/2021.10.04.463034)
- Lin, Z. et al., "Evolutionary-scale prediction of atomic-level protein structure with a language model", *Science* 379, 1123-1130, 2023. [DOI](https://doi.org/10.1126/science.ade2574)
- bioRxiv API documentation: https://api.biorxiv.org/
