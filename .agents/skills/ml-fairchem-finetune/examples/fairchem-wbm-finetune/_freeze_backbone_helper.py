import torch
from fairchem.core.units.mlip_unit.mlip_unit import initialize_finetuning_model

def initialize_finetuning_model_frozen(checkpoint_location, overrides=None, heads=None, strict=True):
    model = initialize_finetuning_model(
        checkpoint_location=checkpoint_location, overrides=overrides, heads=heads, strict=strict
    )
    for param in model.backbone.parameters():
        param.requires_grad = False
    return model
