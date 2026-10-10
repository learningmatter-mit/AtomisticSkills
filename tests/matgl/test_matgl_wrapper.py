"""
Tests for MatGL wrapper functionality

These tests validate:
- predict_atomic_features() for CHGNet and M3GNet
- MatGL calculator creation
- MatGL model loading

Run in: matgl-agent conda environment
Command: conda activate matgl-agent && pytest -m matgl
"""

import pytest
import numpy as np
from ase import Atoms


@pytest.mark.matgl
class TestMatGLPredictAtomicFeatures:
    """Test MatGL atomic feature extraction"""

    def test_predict_atomic_features_chgnet(self, sample_ase_atoms, skip_if_wrong_env):
        """Test atomic feature extraction with CHGNet model"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(
            model_name="CHGNet-PES-MatPES-PBE-2025.2.10", device="cpu"
        )
        wrapper.load()

        result = wrapper.predict_atomic_features(sample_ase_atoms)

        # Should not have error
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

        # Check required keys
        assert "atomic_features" in result
        assert "feature_dim" in result
        assert "num_atoms" in result

        # Validate shapes
        features = np.array(result["atomic_features"])
        assert features.shape[0] == result["num_atoms"]
        assert features.shape[1] == result["feature_dim"]
        assert features.shape[0] == len(sample_ase_atoms)

    def test_predict_atomic_features_m3gnet(self, sample_ase_atoms, skip_if_wrong_env):
        """Test atomic feature extraction with M3GNet model"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(model_name="M3GNet-PES-MatPES-PBE-2025.2", device="cpu")
        wrapper.load()

        result = wrapper.predict_atomic_features(sample_ase_atoms)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "atomic_features" in result
        assert result["num_atoms"] == len(sample_ase_atoms)

    def test_feature_extraction_with_file_path(self, tmp_cif_file, skip_if_wrong_env):
        """Test feature extraction from file path"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(
            model_name="CHGNet-PES-MatPES-PBE-2025.2.10", device="cpu"
        )
        wrapper.load()

        result = wrapper.predict_atomic_features(str(tmp_cif_file))

        assert "error" not in result
        assert "atomic_features" in result
        assert result["num_atoms"] == 2  # Si2 structure

    def test_feature_dimensions_consistent_chgnet(self, skip_if_wrong_env):
        """Test that CHGNet feature dimensions are consistent"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(
            model_name="CHGNet-PES-MatPES-PBE-2025.2.10", device="cpu"
        )
        wrapper.load()

        atoms1 = Atoms(
            "Si2", positions=[[0, 0, 0], [1.35, 1.35, 1.35]], cell=[5.43] * 3, pbc=True
        )
        atoms2 = Atoms(
            "Si4",
            positions=[[0, 0, 0], [1.35, 1.35, 1.35], [2.7, 0, 0], [0, 2.7, 0]],
            cell=[5.43] * 3,
            pbc=True,
        )

        result1 = wrapper.predict_atomic_features(atoms1)
        result2 = wrapper.predict_atomic_features(atoms2)

        # Feature dimension should be same for same model
        assert result1["feature_dim"] == result2["feature_dim"]
        assert result1["num_atoms"] == 2
        assert result2["num_atoms"] == 4


@pytest.mark.matgl
class TestMatGLCalculator:
    """Test MatGL calculator creation and functionality"""

    def test_create_calculator_chgnet(self, skip_if_wrong_env):
        """Test calculator creation with CHGNet"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
        from ase.calculators.calculator import Calculator

        wrapper = MatGLWrapper(
            model_name="CHGNet-PES-MatPES-PBE-2025.2.10", device="cpu"
        )
        wrapper.load()

        calc = wrapper.create_calculator()

        assert calc is not None
        assert isinstance(calc, Calculator)

    def test_create_calculator_m3gnet(self, skip_if_wrong_env):
        """Test calculator creation with M3GNet"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
        from ase.calculators.calculator import Calculator

        wrapper = MatGLWrapper(model_name="M3GNet-PES-MatPES-PBE-2025.2", device="cpu")
        wrapper.load()

        calc = wrapper.create_calculator()

        assert calc is not None
        assert isinstance(calc, Calculator)

    def test_calculator_computes_energy_forces_stress(
        self, sample_ase_atoms, skip_if_wrong_env
    ):
        """Test that calculator computes energy, forces, and stress"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(
            model_name="CHGNet-PES-MatPES-PBE-2025.2.10", device="cpu"
        )
        wrapper.load()

        calc = wrapper.create_calculator()
        sample_ase_atoms.calc = calc

        energy = sample_ase_atoms.get_potential_energy()
        forces = sample_ase_atoms.get_forces()
        stress = sample_ase_atoms.get_stress()

        assert isinstance(energy, (float, np.floating))
        assert forces.shape == (len(sample_ase_atoms), 3)
        assert stress.shape == (6,)  # Voigt notation


@pytest.mark.matgl
class TestMatGLModelLoading:
    """Test MatGL model loading"""

    def test_load_chgnet(self, skip_if_wrong_env):
        """Test loading CHGNet model"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(
            model_name="CHGNet-PES-MatPES-PBE-2025.2.10", device="cpu"
        )
        wrapper.load()

        assert wrapper.is_loaded
        assert wrapper.model is not None

    def test_load_m3gnet(self, skip_if_wrong_env):
        """Test loading M3GNet model"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(model_name="M3GNet-PES-MatPES-PBE-2025.2", device="cpu")
        wrapper.load()

        assert wrapper.is_loaded
        assert wrapper.model is not None

    def test_tensornet_pbe_v2025_1_alias(self, skip_if_wrong_env):
        """The v2025.1 TensorNet PBE name resolves like the other v2025.1 aliases."""
        from src.utils.mlips.matgl.matgl_wrapper import AVAILABLE_MATGL_MODELS

        assert (
            AVAILABLE_MATGL_MODELS["TensorNet-MatPES-PBE-v2025.1-PES"]
            == "TensorNet-PES-MatPES-PBE-2025.2"
        )

    def test_static_calculation(self, sample_ase_atoms, skip_if_wrong_env):
        """Test static_calculation returns energy, forces, and stress"""
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(
            model_name="CHGNet-PES-MatPES-PBE-2025.2.10", device="cpu"
        )
        wrapper.load()

        result = wrapper.static_calculation(sample_ase_atoms)

        assert "error" not in result
        assert "energy" in result
        assert "forces" in result
        assert "stress" in result

        # Validate types
        assert isinstance(result["energy"], (float, np.floating))
        forces = np.array(result["forces"])
        assert forces.shape == (len(sample_ase_atoms), 3)


@pytest.mark.matgl
class TestMatGLBandgapFunctionals:
    """Test MEGNet-BandGap-mfi bandgap prediction across DFT functionals."""

    @pytest.fixture(scope="class")
    def si_atoms(self):
        from ase import Atoms

        return Atoms(
            "Si2",
            positions=[[0, 0, 0], [1.3575, 1.3575, 1.3575]],
            cell=[5.43] * 3,
            pbc=True,
        )

    def _predict(self, task_name, si_atoms):
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper

        wrapper = MatGLWrapper(
            model_name="MEGNet-BandGap-mfi-MP-2019.4.1",
            device="auto",
            task_name=task_name,
        )
        wrapper.load()
        return wrapper.static_calculation(si_atoms)

    def test_pbe_bandgap(self, si_atoms, skip_if_wrong_env):
        result = self._predict("PBE", si_atoms)
        assert "error" not in result, result.get("error")
        assert "bandgap" in result
        assert isinstance(result["bandgap"], float)
        assert result["bandgap"] > 0

    def test_hse_bandgap(self, si_atoms, skip_if_wrong_env):
        result = self._predict("HSE", si_atoms)
        assert "error" not in result, result.get("error")
        assert "bandgap" in result
        assert isinstance(result["bandgap"], float)
        assert result["bandgap"] > 0

    def test_functionals_give_different_values(self, si_atoms, skip_if_wrong_env):
        """HSE should predict a larger bandgap than PBE for Si (consistent with DFT literature)."""
        pbe = self._predict("PBE", si_atoms)["bandgap"]
        hse = self._predict("HSE", si_atoms)["bandgap"]
        gllb = self._predict("GLLB-SC", si_atoms)["bandgap"]
        scan = self._predict("SCAN", si_atoms)["bandgap"]

        # All four must be distinct predictions
        values = {pbe, hse, gllb, scan}
        assert len(values) > 1, f"All functionals returned the same bandgap: {values}"

    def test_invalid_task_name_defaults_to_pbe(self, si_atoms, skip_if_wrong_env):
        """Unknown task_name should silently fall back to PBE (index 0)."""
        result_default = self._predict(None, si_atoms)
        result_unknown = self._predict("UNKNOWN", si_atoms)
        assert result_default["bandgap"] == pytest.approx(
            result_unknown["bandgap"], rel=1e-4
        )
