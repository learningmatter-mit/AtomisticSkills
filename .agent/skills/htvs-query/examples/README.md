# HTVS Query Examples

This directory contains examples and documentation for querying data from the HTVS database using the tools in the `scripts/` directory.

## Querying Perovskite Surface IDs (Light Version)

To query IDs of surfaces generated for the `perovskite` group using the `clean_surface_cut` configuration, you can use the `query_surfaces.py` script with the `--light-output` flag.

### Command

```bash
conda activate htvs-agent
python .agent/skills/htvs-query/scripts/query_surfaces.py \
    --group "perovskite" \
    --config "clean_surface_cut" \
    --light-output "perovskite_ids.json"
```

### Explanation

- `--group "perovskite"`: Specifies the HTVS project group.
- `--config "clean_surface_cut"`: Filters surfaces cut from bulk using this specific job configuration.
- `--light-output "perovskite_ids.json"`: Saves only the numerical `surface_id`s to a JSON list, omitting detailed structure and metadata. By not providing `--output`, the full version is not saved to a file.
