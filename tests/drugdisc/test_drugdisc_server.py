import pytest
from src.mcp_server import drugdisc_server

def test_parse_smiles_input(skip_if_wrong_env):
    res = drugdisc_server.parse_smiles_input(smiles="CC")
    assert "error" not in res
    assert "smiles" in res

def test_standardize_molecule(skip_if_wrong_env):
    res = drugdisc_server.standardize_molecule(smiles="CC")
    assert "error" not in res
    assert "standardized_smiles" in res

def test_convert_to_pdbqt(skip_if_wrong_env):
    res = drugdisc_server.convert_to_pdbqt(input_data="CC", input_type="smiles", output_path="test.pdbqt")
    assert "error" not in res

def test_compute_molecular_descriptors(skip_if_wrong_env):
    res = drugdisc_server.compute_molecular_descriptors(smiles="CC", output_file="test_desc.json")
    assert "error" not in res

def test_compute_molecular_fingerprints(tmp_path, skip_if_wrong_env):
    smiles_file = tmp_path / "test.smi"
    smiles_file.write_text("CC\nCCO\n")
    res = drugdisc_server.compute_molecular_fingerprints(smiles_file=str(smiles_file), output_file="test_fp.json")
    assert "error" not in res
