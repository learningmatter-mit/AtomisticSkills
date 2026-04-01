# ADiT Molecule Generation Example

10 molecules generated unconditionally using the ADiT (All-atom Diffusion Transformer) model trained on QM9.

## Generation Parameters

| Parameter | Value |
|---|---|
| Model | ADiT (HuggingFace: `chaitjo/all-atom-diffusion-transformer`) |
| Generation type | Molecules (QM9 distribution) |
| CFG scale | 2.0 |
| Batch size | 100 |
| Device | CUDA |

## Output Files

- `molecule_0000.xyz` – `molecule_0009.xyz`: Generated molecular structures in XYZ format
- `generation_metadata.json`: Generation parameters and statistics

## How to Reproduce

Use the ADiT MCP tool:

```
generate_structures(
    generation_type="molecules",
    num_structures=10,
    cfg_scale=2.0,
    output_dir="<output_path>",
)
```

## Notes

- ADiT generates molecules from the QM9 learned distribution (~5–29 atoms, C/H/N/O/F elements)
- No composition conditioning is available; structures are sampled unconditionally
- Spacegroup conditioning applies to crystal generation only
