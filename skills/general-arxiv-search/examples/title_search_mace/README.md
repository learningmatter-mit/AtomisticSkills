# Title Search: the MACE Paper

## Goal

Find a known paper by words from its title, then check the returned metadata against the
paper's official arXiv record: Batatia et al., "MACE: Higher Order Equivariant Message Passing
Neural Networks for Fast and Accurate Force Fields",
[arXiv:2206.07697](https://arxiv.org/abs/2206.07697).

## Command

Run from the repository root:

```bash
venv/run cpu python skills/general-arxiv-search/scripts/arxiv_search.py \
    --title "MACE higher order equivariant message passing" --max_results 5 \
    --output skills/general-arxiv-search/examples/title_search_mace/results.json --verbose
```

The script sends this `search_query`, which `--verbose` logs:

```
(ti:MACE AND ti:higher AND ti:order AND ti:equivariant AND ti:message AND ti:passing)
```

Every word carries its own `ti:` prefix, so all six must occur in the title.

## Output Files

- `results.json` holds the single matching record.
- `input_configs.yaml` holds the arguments.

## Results vs. Ground Truth

Ground truth is the arXiv abstract page, https://arxiv.org/abs/2206.07697 (citation metadata and submission history).

| Field | Script output | arXiv abstract page | Match |
|:---|:---|:---|:---|
| Results | 1 record (of `--max_results 5`) | The paper above; no other arXiv title contains all six words | Yes |
| ID | 2206.07697v2 | arXiv:2206.07697, latest version v2 | Yes |
| Title | MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields | Same | Yes |
| Authors | Ilyes Batatia, Dávid Péter Kovács, Gregor N. C. Simm, Christoph Ortner, Gábor Csányi | Batatia, Ilyes; Kovács, Dávid Péter; Simm, Gregor N. C.; Ortner, Christoph; Csányi, Gábor | Yes, same order |
| First submission (`published`) | 2022-06-15T17:46:05Z | [v1] Wed, 15 Jun 2022 17:46:05 UTC | Yes |
| Last revision (`updated`) | 2023-01-26T10:07:20Z | [v2] Thu, 26 Jan 2023 10:07:20 UTC | Yes |
| Primary category | stat.ML | Machine Learning (stat.ML), listed first | Yes |
| Categories | stat.ML, cond-mat.mtrl-sci, cs.LG, physics.chem-ph | stat.ML; cond-mat.mtrl-sci; cs.LG; physics.chem-ph | Yes |
| `doi` | `null` | No publisher DOI on the record (only the arXiv-issued DOI [10.48550/arXiv.2206.07697](https://doi.org/10.48550/arXiv.2206.07697)) | Yes |
| `journal_ref` | `null` | No journal reference; the venue is given only in Comments: "Advances in Neural Information Processing Systems, 2022" | Yes |

`doi` and `journal_ref` carry only what the authors entered on arXiv. For MACE, the NeurIPS 2022
venue sits in the free-text Comments field, which the script does not export.

## References

- Batatia, I., Kovács, D. P., Simm, G. N. C., Ortner, C. & Csányi, G., "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields", *Advances in Neural Information Processing Systems* 35 (NeurIPS 2022). [arXiv:2206.07697](https://arxiv.org/abs/2206.07697)
- arXiv API User's Manual, query construction: https://info.arxiv.org/help/api/user-manual.html
