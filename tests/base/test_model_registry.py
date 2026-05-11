import os
import pytest
from pathlib import Path

from src.utils import model_registry

@pytest.fixture
def mock_registry(tmp_path, monkeypatch):
    registry_file = tmp_path / "model_registry.yaml"
    monkeypatch.setattr(model_registry, "REGISTRY_PATH", registry_file)
    return registry_file

@pytest.mark.base
def test_normalise_chemsys():
    assert model_registry._normalise_chemsys("Li-Fe-P-O") == "Fe-Li-O-P"
    assert model_registry._normalise_chemsys("O-Li") == "Li-O"
    assert model_registry._normalise_chemsys(" Fe -  Li") == "Fe-Li"

@pytest.mark.base
def test_register_and_search_model(mock_registry, tmp_path):
    # Dummy checkpoint path
    ckpt = tmp_path / "dummy.pt"
    ckpt.touch()
    
    model_id = model_registry.register_model(
        checkpoint_path=str(ckpt),
        chemical_system="Li-O",
        backend="mace",
        base_model="MACE-MH-1",
        description="Test model",
        energy_mae=5.0,
        tags=["test", "battery"]
    )
    
    assert model_id == "mace-LiO-v1"
    
    # Search
    res = model_registry.search_models(chemical_system="Li", backend="mace")
    assert len(res) == 1
    assert res[0]["id"] == model_id
    assert res[0]["checkpoint_exists"] is True
    
    # Negative search
    res2 = model_registry.search_models(chemical_system="Fe")
    assert len(res2) == 0

    # Search with performance constraint
    res3 = model_registry.search_models(max_energy_mae=4.0)
    assert len(res3) == 0

    res4 = model_registry.search_models(max_energy_mae=6.0)
    assert len(res4) == 1

@pytest.mark.base
def test_delete_model(mock_registry, tmp_path):
    ckpt = tmp_path / "dummy.pt"
    ckpt.touch()
    model_id = model_registry.register_model(
        checkpoint_path=str(ckpt),
        chemical_system="Li",
        backend="mace",
        base_model="MACE-MH-1",
    )
    assert len(model_registry.list_models()) == 1
    
    deleted = model_registry.delete_model(model_id)
    assert deleted is True
    assert len(model_registry.list_models()) == 0
