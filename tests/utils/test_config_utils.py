import os
import yaml
import pytest
from pathlib import Path
from argparse import Namespace

from src.utils.config_utils import save_skill_inputs

def test_save_skill_inputs_namespace(tmp_path):
    # Test with argparse Namespace
    args = Namespace(
        input_file=Path("/path/to/input.cif"),
        max_steps=100,
        verbose=True
    )
    output_dir = tmp_path / "output_dir"
    
    save_skill_inputs(args, str(output_dir))
    
    yaml_path = output_dir / "input_configs.yaml"
    assert yaml_path.exists()
    
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
        
    assert data["input_file"] == "/path/to/input.cif"
    assert data["max_steps"] == 100
    assert data["verbose"] is True

def test_save_skill_inputs_dict(tmp_path):
    # Test with dict
    args = {
        "model_name": "MACE",
        "checkpoint": Path("/path/to/ckpt.pt")
    }
    output_dir = tmp_path / "results"
    
    save_skill_inputs(args, str(output_dir))
    
    yaml_path = output_dir / "input_configs.yaml"
    assert yaml_path.exists()
    
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
        
    assert data["model_name"] == "MACE"
    assert data["checkpoint"] == "/path/to/ckpt.pt"

def test_save_skill_inputs_file_path(tmp_path):
    # Test with output path being a file
    args = {"test": 123}
    # Output path is a file (has suffix)
    output_file = tmp_path / "data" / "output.json"
    
    save_skill_inputs(args, str(output_file))
    
    # It should save in the parent directory
    yaml_path = tmp_path / "data" / "input_configs.yaml"
    assert yaml_path.exists()
    
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    assert data["test"] == 123

def test_save_skill_inputs_no_output():
    # Test early return when output_path is empty
    # This shouldn't raise any errors
    save_skill_inputs({"a": 1}, "")
    save_skill_inputs({"a": 1}, None)

def test_save_skill_inputs_string(tmp_path):
    # Test fallback for non-dict/non-namespace
    output_dir = tmp_path / "string_out"
    save_skill_inputs("just a string", str(output_dir))
    
    yaml_path = output_dir / "input_configs.yaml"
    assert yaml_path.exists()
    
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    assert data["arguments"] == "just a string"
