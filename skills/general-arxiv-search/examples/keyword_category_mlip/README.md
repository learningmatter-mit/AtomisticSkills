# Keyword + Category Search: Machine Learning Interatomic Potentials in cond-mat.mtrl-sci

## Goal

Search for "machine learning interatomic potential" within Materials Science
(`cond-mat.mtrl-sci`), and confirm that every top result is on-topic, which the
query-construction fix below makes possible.

## Command

Run from the repository root:

```bash
venv/run cpu python skills/general-arxiv-search/scripts/arxiv_search.py \
    "machine learning interatomic potential" --categories mtrl-sci --max_results 10 \
    --output skills/general-arxiv-search/examples/keyword_category_mlip/results.json --verbose
```

The script sends this `search_query`, which `--verbose` logs:

```
(all:machine AND all:learning AND all:interatomic AND all:potential) AND (cat:cond-mat.mtrl-sci)
```

The API echoes the query it ran in the feed `<title>`. For this query the echo is unchanged,
and 950 records match.

## Output Files

- `results.json` holds the 10 records, ranked by relevance.
- `input_configs.yaml` holds the arguments.

## Results (run 2026-10-10)

| # | arXiv ID | First submitted | Primary | Title |
|:---|:---|:---|:---|:---|
| 1 | 2602.04861v2 | 2026-02-04 | cs.LG | From Evaluation to Design: Using Potential Energy Surface Smoothness Metrics to Guide Machine Learning Interatomic Potential Architectures |
| 2 | 2509.02927v2 | 2025-09-03 | cs.LG | P-DRUM: Post-hoc Descriptor-based Residual Uncertainty Modeling for Machine Learning Potentials |
| 3 | 2506.08818v1 | 2025-06-10 | cond-mat.mtrl-sci | Crystal Nucleation in Eutectic Al-Si Alloys by Machine-Learned Molecular Dynamics |
| 4 | 2402.11383v1 | 2024-02-17 | cond-mat.mtrl-sci | Machine Learning a Universal Harmonic Interatomic Potential for Predicting Phonons in Crystalline Solids |
| 5 | 2203.01117v1 | 2022-03-02 | cond-mat.mtrl-sci | Machine-learning interatomic potential for molecular dynamics simulation of ferroelectric KNbO3 perovskite |
| 6 | 2602.08849v1 | 2026-02-09 | stat.ML | Cutting Through the Noise: On-the-fly Outlier Detection for Robust Training of Machine Learning Interatomic Potentials |
| 7 | 2209.12322v1 | 2022-09-21 | cond-mat.mtrl-sci | Classical and Machine Learning Interatomic Potentials for BCC Vanadium |
| 8 | 2312.11708v1 | 2023-12-18 | cond-mat.mtrl-sci | Accelerating the prediction of inorganic surfaces with machine learning interatomic potentials |
| 9 | 2504.05565v1 | 2025-04-07 | cond-mat.mtrl-sci | Cross-functional transferability in universal machine learning interatomic potentials |
| 10 | 2512.15952v3 | 2025-12-17 | cond-mat.mtrl-sci | Machine-Learned Interatomic Potential for Predictive Simulation of MoS2 Epitaxy |

The ranking is by relevance over a growing corpus, so a later re-run can return different
IDs. The checks below are therefore criteria, not a fixed ID list.

## Comparison Against Ground Truth

| Check | Result |
|:---|:---|
| All 10 records list `cond-mat.mtrl-sci` among their categories | 10/10; three are cross-lists with another primary (cs.LG, stat.ML) |
| All 10 titles + abstracts contain machine, learn(ed/ing), interatomic, potential | 10/10 |
| All 10 are about machine-learned interatomic potentials | 10/10 by title |

Two records were spot-checked against their arXiv abstract pages:

| Field | Script: 2203.01117v1 | [arxiv.org/abs/2203.01117](https://arxiv.org/abs/2203.01117) | Script: 2209.12322v1 | [arxiv.org/abs/2209.12322](https://arxiv.org/abs/2209.12322) |
|:---|:---|:---|:---|:---|
| Authors | Hao-Cheng Thong, XiaoYang Wang, Han Wang, Linfeng Zhang, Ke Wang, Ben Xu | Same 6, same order | Rui Wang, Xiaoxiao Ma, Linfeng Zhang, Han Wang, David J. Srolovitz, Tongqi Wen, Zhaoxuan Wu | Same 7, same order |
| First submission | 2022-03-02 | 2022/03/02 | 2022-09-21 | 2022/09/21 |
| Categories | cond-mat.mtrl-sci | Materials Science (cond-mat.mtrl-sci) | cond-mat.mtrl-sci | Materials Science (cond-mat.mtrl-sci) |
| DOI | 10.1103/PhysRevB.107.014101 | [10.1103/PhysRevB.107.014101](https://doi.org/10.1103/PhysRevB.107.014101) | 10.1103/PhysRevMaterials.6.113603 | [10.1103/PhysRevMaterials.6.113603](https://doi.org/10.1103/PhysRevMaterials.6.113603) |

Both DOIs resolve via doi.org to link.aps.org, which refuses scripted clients (HTTP 403). Crossref
lists them as *Phys. Rev. B* 107, 014101 (2023) and *Phys. Rev. Materials* 6, 113603 (2022).

## Query-Construction Fix

Per the arXiv API manual, a field prefix applies only to the term right after it. Bare spaces
separate terms, and phrases must be double-quoted (`%22`). The previous script sent the whole
keyword string after a single prefix, `all:machine learning interatomic potential`.
The API's feed title shows how it read that string:

```
arXiv Query: search_query=all:machine OR all:learning OR all:interatomic OR all:potential
```

That OR query matches 806,447 records, any paper containing "machine", "learning" or
"potential". Its top hits were "Changing Data Sources in the Age of Machine Learning for Official
Statistics" (2306.04338) and "DOME: Recommendations for supervised machine learning validation in
biology" (2006.16189), the same records stored in the removed `mlip_search_example.json`.
The fixed script prefixes every term, ANDs the words and keeps "double-quoted phrases" intact,
for 950 records here. The same fix applies to `--title`, `--authors` (each name sent as a
phrase, e.g. `au:"Boris Kozinsky"`) and to several `--categories` (`cat:A OR cat:B`).

## References

- arXiv API User's Manual, Appendix 5.1 "Details of Query Construction": https://info.arxiv.org/help/api/user-manual.html
- Thong, H.-C. et al., "Machine learning interatomic potential for molecular dynamics simulation of the ferroelectric KNbO3 perovskite", *Phys. Rev. B* 107, 014101 (2023). [DOI](https://doi.org/10.1103/PhysRevB.107.014101)
- Wang, R. et al., "Classical and machine learning interatomic potentials for BCC vanadium", *Phys. Rev. Materials* 6, 113603 (2022). [DOI](https://doi.org/10.1103/PhysRevMaterials.6.113603)
