# Tetrafluoropropene Refrigerant Patents

**Query:** `tetrafluoropropene OR HFO-1234yf`
**Topic:** IP landscape for low-GWP hydrofluoroolefin (HFO) refrigerant alternatives

HFO-1234yf (2,3,3,3-tetrafluoropropene) is a next-generation refrigerant replacing R-134a in automotive AC systems due to its low global warming potential (GWP = 4). This example maps the key patent holders around this compound.

## Files

- `results.json`: 5 matching patents from Google Patents (captured 2026-03-12)

## How to reproduce

```bash
conda activate base-agent
python .agents/skills/general-patent-search/scripts/query_google_patents.py \
    "tetrafluoropropene OR HFO-1234yf" --limit 5 \
    --output .agents/skills/general-patent-search/examples/tetrafluoropropene_refrigerants/results.json
```

## Results Summary

| # | Patent | Assignee | Priority Date | Title |
|---|--------|----------|---------------|-------|
| 1 | MX370935B | Du Pont | 2008-05-07 | …comprising pentafluoropropane or tetrafluoropropene |
| 2 | US8252198B2 | Arkema France | 2008-06-11 | Hydrofluoroolefin compositions |
| 3 | US20080121837A1 | Honeywell International | 2003-10-27 | Compositions containing fluorine substituted olefins |
| 4 | US8246850B2 | Arkema France | 2008-06-11 | Hydrofluoroolefin compositions |
| 5 | ES2951493T3 | Chemours Co Fc Llc | 2007-05-24 | Compositions comprising 2,3,3,3-tetrafluoropropene |

**Key finding:** The IP landscape is dominated by Honeywell, DuPont/Chemours, and Arkema, reflecting the real-world oligopoly that controls HFO refrigerant production. Priority dates cluster 2003–2008, consistent with the industry transition from HFCs to HFOs.
