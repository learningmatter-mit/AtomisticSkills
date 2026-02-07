# Testing Guide

## Overview

This project uses **pytest** with a multi-environment testing strategy. Different MCP servers require different conda environments, so tests are organized by environment.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and environment detection
├── base/                    # Tests for base utilities (base-agent env)
│   ├── conftest.py
│   ├── test_structure_utils.py
│   └── test_base_mlip.py
├── mace/                    # Tests for MACE wrapper (mace-agent env)
│   ├── conftest.py
│   ├── test_mace_wrapper.py
│   └── test_mace_server.py
├── matgl/                   # Tests for MatGL wrapper (matgl-agent env)
│   ├── conftest.py
│   ├── test_matgl_wrapper.py
│   └── test_matgl_server.py
├── fairchem/                # Tests for FairChem wrapper (fairchem-agent env)
│   ├── conftest.py
│   └── test_fairchem_server.py
├── atomate2/                # Tests for Atomate2 integration (atomate2-agent env)
│   ├── conftest.py
│   ├── test_atomate2_local.py
│   └── test_atomate2_remote.py
├── integration/             # Integration tests (various envs)
│   ├── conftest.py
│   ├── test_remote_submission_check.py
│   └── submit_perlmutter_test.py
└── README.md                # Testing guide
```

## Running Tests

### 1. Run Base Tests (base-agent)

```bash
conda activate base-agent
pytest tests/base/ -v
```

Or using markers:
```bash
conda activate base-agent
pytest -m base -v
```

### 2. Run MACE Tests (mace-agent)

```bash
conda activate mace-agent
pytest tests/mace/ -v
```

Or using markers:
```bash
conda activate mace-agent
pytest -m mace -v
```

### 3. Run MatGL Tests (matgl-agent)

```bash
conda activate matgl-agent
pytest tests/matgl/ -v
```

Or using markers:
```bash
conda activate matgl-agent
pytest -m matgl -v
```

### 4. Run All Tests (Sequential Multi-Environment)

Create a script `run_all_tests.sh`:

```bash
#!/bin/bash

echo "Running base tests..."
conda activate base-agent
pytest tests/base/ -v

echo "Running MACE tests..."
conda activate mace-agent
pytest tests/mace/ -v

echo "Running MatGL tests..."
conda activate matgl-agent
pytest tests/matgl/ -v

echo "Running FairChem tests..."
conda activate fairchem-agent
pytest tests/fairchem/ -v

echo "Running Atomate2 tests..."
conda activate atomate2-agent
pytest tests/atomate2/ -v

echo "All tests complete!"
```

### 5. Run Integration Tests

```bash
# Integration tests may require specific environment setup
pytest tests/integration/ -v
```

## Test Markers

Tests are marked by required environment:

- `@pytest.mark.base` - Base utilities (base-agent)
- `@pytest.mark.mace` - MACE-specific tests (mace-agent)
- `@pytest.mark.matgl` - MatGL-specific tests (matgl-agent)
- `@pytest.mark.fairchem` - FairChem-specific tests (fairchem-agent)
- `@pytest.mark.integration` - Integration tests (may require multiple envs)

## Auto-Skip Behavior

Tests automatically skip if run in the wrong environment:

```python
@pytest.mark.mace
def test_mace_feature(skip_if_wrong_env):
    # Will skip if not in mace-agent environment
    ...
```

## Breaking Changes Tested

### 1. `load_structure_from_file()` Returns Pymatgen Structure

**Old behavior**: Returned ASE Atoms  
**New behavior**: Returns Pymatgen Structure

**Test**: `tests/base/test_structure_utils.py::TestLoadStructureFromFile`

### 2. `save_structure()` Standardization

**New function**: Handles both ASE Atoms and Pymatgen Structures

**Test**: `tests/base/test_structure_utils.py::TestSaveStructure`

### 3. Materials Project Query Simplification

**Changed functions**: `get_structure_by_formula`, `get_structure_by_chemsys`, `get_structure_by_id`

**Test**: `tests/base/test_structure_utils.py::TestMaterialsProjectQueries`

## New Features Tested

### 1. Atomic Feature Extraction

**MACE**: `tests/mace/test_mace_wrapper.py::TestMACEPredictAtomicFeatures`  
**MatGL**: `tests/matgl/test_matgl_wrapper.py::TestMatGLPredictAtomicFeatures`

### 2. Base Relax Structure Implementation

**Test**: `tests/base/test_base_mlip.py::TestRelaxStructureBase`

## Common Fixtures

Available in all tests via `conftest.py`:

- `current_env` - Current conda environment name
- `skip_if_wrong_env` - Auto-skip if wrong environment
- `tmp_cif_file` - Temporary Si2 CIF structure
- `sample_structure` - Pymatgen Structure (Si2)
- `sample_ase_atoms` - ASE Atoms (Si2)
- `tmp_research_dir` - Temporary research directory
- `mock_mp_api_key` - Mock Materials Project API key

## Troubleshooting

### Test fails with import error

**Problem**: Wrong conda environment activated

**Solution**: Check you're in the correct environment:
```bash
conda info --envs
conda activate <correct-env>
```

### Test skips unexpectedly

**Problem**: Auto-skip triggered

**Solution**: This is expected behavior. Tests skip gracefully in wrong environments.

## CI/CD Considerations

For automated testing, you'll need:

1. **Multi-stage CI** with separate jobs per environment
2. **Docker containers** with pre-built conda environments
3. **GitHub Actions matrix** strategy

Currently, tests are designed for **local manual execution** in the appropriate conda environment.
