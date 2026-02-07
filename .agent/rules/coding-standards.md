---
trigger: always_on
---

# MLIP Agent Project Coding Standards

## Code Standards

### Programming Languages and Frameworks
- Use ASE (Atomic Simulation Environment) for atomic structure processing
- Use Pymatgen for processing DFT inputs and outputs

### Code Style
- Use type hints
- Functions and classes must have detailed docstrings

### File Organization
- Create independent Python packages for each major functional module
- All temporary validation, testing, and summary files MUST be created under `<project_root>/.agent/test` to maintain a clean project structure
- Use YAML or JSON format for configuration files


## Development Standards

### Environment Setup
- ALWAYS use the `base-agent` conda environment for development and testing by `conda activate base-agent`
- When installation depency is needed, see `dependency-rules.mdc` for dependency instructions

### Testing Requirements
- Each major functionality must have unit tests
- Use pytest as the testing framework
- Place test files in `tests/` directory

### Import and Dependency Management
- NEVER implement fallback functions when package imports fail
- If an import fails, debug the root cause and fix the original implementation
- Always ensure proper dependency installation and environment setup
- Use proper error handling with clear error messages instead of fallbacks
- Alwaus use torch 2.9.1 + cu 13.0, install by: pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu130 , ignore the torch dependency requirement of installed packages and fix to this torch version.

### Documentation Requirements
- Each module needs README documentation
- API documentation uses docstring format
- Important features need usage examples

## Project-Specific Rules

### MLIP Model Processing
- Don't re-implement the MLIP loading, inference and training!!! Check the original MLIP implementation first
- To determine the relevant foundation potentials for a specific simulation, sampling, or data augmentation task, see `foundation-potential.mdc`
  

### Data Sampling
- Details to sample structures are in `sampler.mdc` 


### DFT Calculations
- ALWAYS check pymatgen for existing functionality before implementing custom solution
- Use pymatgen DFT input sets to create VASP inputs from structures, the choice of input sets should be determined by the foundation potential, see `foundation-potential.mdc`. 
- Use pymatgen's VASP I/O classes (VaspInput, VaspOutput) for VASP file processing
- Orca support will be implemented later


## Security Standards

### API Key Management
- All API keys must be passed through environment variables
- Do not hardcode sensitive information in code
- Use `.env` file to manage local configuration

### Data Security
- User data must not be permanently stored
- Temporary files must be cleaned up after use
- Sensitive calculation results need encrypted storage

## Performance Requirements

### Computational Efficiency
- Use streaming processing for large files
- Long-running calculations should support progress display
- Memory usage needs monitoring and optimization

### Debugging
- Pause immediately after you see the "improper format stop reason" error, and analyze the trigger of this error.
