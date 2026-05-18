"""
MVP-10 T21: Science Mode Switch Tests

Tests for science_mode.py:
- ScienceMode class: enable/disable interventions, inject parameters
- All interventions through unified interface
- Log interventions to run header
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.science.science_mode import (
    ScienceMode,
    ScienceModeState,
    InterventionSpec,
    RunHeader,
    create_science_mode,
)
from emotiond.science.interventions import InterventionType


class TestScienceModeState:
    """Test ScienceModeState enum."""
    
    def test_states_exist(self):
        """Test that required states exist."""
        assert ScienceModeState.DISABLED.value == "disabled"
        assert ScienceModeState.ENABLED.value == "enabled"
        assert ScienceModeState.PAUSED.value == "paused"


class TestInterventionSpec:
    """Test InterventionSpec dataclass."""
    
    def test_spec_creation(self):
        """Test creating an InterventionSpec."""
        spec = InterventionSpec(
            intervention_type=InterventionType.FREEZE_VALENCE,
            params={"valence": 0.5},
            reason="test",
            priority=1,
        )
        
        assert spec.intervention_type == InterventionType.FREEZE_VALENCE
        assert spec.params == {"valence": 0.5}
        assert spec.reason == "test"
        assert spec.priority == 1


class TestRunHeader:
    """Test RunHeader dataclass."""
    
    def test_header_creation(self):
        """Test creating a RunHeader."""
        header = RunHeader(
            run_id="test_run",
            seed=42,
            science_mode=ScienceModeState.ENABLED,
            interventions=[],
            config_hash="",
        )
        
        assert header.run_id == "test_run"
        assert header.seed == 42
        assert header.science_mode == ScienceModeState.ENABLED
    
    def test_header_compute_hash(self):
        """Test config hash computation."""
        header = RunHeader(
            run_id="test",
            seed=0,
            science_mode=ScienceModeState.ENABLED,
            interventions=[
                {"type": "freeze_valence", "params": {"valence": 0.5}}
            ],
            config_hash="",
        )
        
        hash1 = header.compute_config_hash()
        assert len(hash1) == 16
        
        # Same interventions should produce same hash
        hash2 = header.compute_config_hash()
        assert hash1 == hash2
    
    def test_header_to_dict(self):
        """Test RunHeader serialization."""
        header = RunHeader(
            run_id="test",
            seed=0,
            science_mode=ScienceModeState.ENABLED,
            interventions=[],
            config_hash="abc123",
        )
        
        d = header.to_dict()
        
        assert d["run_id"] == "test"
        assert d["seed"] == 0
        assert d["science_mode"] == "enabled"


class TestScienceMode:
    """Test ScienceMode class."""
    
    def test_initialization(self):
        """Test default initialization."""
        science = ScienceMode()
        
        assert science.state == ScienceModeState.DISABLED
        assert science.is_enabled == False
    
    def test_start_run(self):
        """Test starting a science run."""
        science = ScienceMode()
        
        run_id = science.start_run(seed=42)
        
        assert run_id is not None
        assert science.is_enabled == True
        assert science.run_id == run_id
    
    def test_start_run_with_id(self):
        """Test starting a run with custom ID."""
        science = ScienceMode()
        
        run_id = science.start_run(seed=42, run_id="custom_run")
        
        assert run_id == "custom_run"
    
    def test_enable_intervention(self):
        """Test enabling an intervention."""
        science = ScienceMode()
        science.start_run(seed=42)
        
        result = science.enable_intervention(
            InterventionType.FREEZE_VALENCE,
            params={"valence": 0.5},
            reason="test",
        )
        
        assert result.success == True
        assert science.is_intervention_active(InterventionType.FREEZE_VALENCE)
    
    def test_enable_without_run_raises(self):
        """Test that enabling without starting run raises error."""
        science = ScienceMode()
        
        with pytest.raises(RuntimeError):
            science.enable_intervention(InterventionType.FREEZE_VALENCE)
    
    def test_disable_intervention(self):
        """Test disabling an intervention."""
        science = ScienceMode()
        science.start_run(seed=42)
        science.enable_intervention(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        
        result = science.disable_intervention(InterventionType.FREEZE_VALENCE)
        
        assert result.success == True
        assert not science.is_intervention_active(InterventionType.FREEZE_VALENCE)
    
    def test_get_intervention_param(self):
        """Test getting intervention parameter."""
        science = ScienceMode()
        science.start_run(seed=42)
        science.enable_intervention(
            InterventionType.FREEZE_VALENCE,
            params={"valence": 0.7},
        )
        
        valence = science.get_intervention_param(
            InterventionType.FREEZE_VALENCE, "valence"
        )
        
        assert valence == 0.7
    
    def test_get_intervention_param_default(self):
        """Test getting parameter with default."""
        science = ScienceMode()
        science.start_run(seed=42)
        
        valence = science.get_intervention_param(
            InterventionType.FREEZE_VALENCE, "valence", default=0.0
        )
        
        assert valence == 0.0
    
    def test_get_all_active_interventions(self):
        """Test getting all active interventions."""
        science = ScienceMode()
        science.start_run(seed=42)
        science.enable_intervention(InterventionType.FREEZE_VALENCE)
        science.enable_intervention(InterventionType.DISABLE_HOT)
        
        active = science.get_all_active_interventions()
        
        assert InterventionType.FREEZE_VALENCE in active
        assert InterventionType.DISABLE_HOT in active
        assert len(active) == 2
    
    def test_apply_to_state(self):
        """Test applying interventions to state."""
        science = ScienceMode()
        science.start_run(seed=42)
        science.enable_intervention(
            InterventionType.FREEZE_VALENCE,
            params={"valence": 0.8},
        )
        
        result = science.apply_to_state(valence=0.0)
        
        assert result["valence"] == 0.8
        assert "freeze_valence" in result["interventions_applied"]
    
    def test_pause_resume(self):
        """Test pausing and resuming."""
        science = ScienceMode()
        science.start_run(seed=42)
        
        science.pause()
        assert science.state == ScienceModeState.PAUSED
        
        science.resume()
        assert science.state == ScienceModeState.ENABLED
    
    def test_end_run(self):
        """Test ending a run."""
        science = ScienceMode()
        science.start_run(seed=42)
        science.enable_intervention(InterventionType.FREEZE_VALENCE)
        
        header = science.end_run()
        
        assert header is not None
        assert len(header.interventions) > 0
        assert science.state == ScienceModeState.DISABLED
    
    def test_end_run_without_active_raises(self):
        """Test that ending without active run raises error."""
        science = ScienceMode()
        
        with pytest.raises(RuntimeError):
            science.end_run()
    
    def test_intervention_log(self):
        """Test intervention logging."""
        science = ScienceMode()
        science.start_run(seed=42)
        science.enable_intervention(InterventionType.FREEZE_VALENCE)
        science.disable_intervention(InterventionType.FREEZE_VALENCE)
        
        log = science.get_intervention_log()
        
        assert len(log) == 2
        assert log[0]["action"] == "enable"
        assert log[1]["action"] == "disable"
    
    def test_inject_parameters(self):
        """Test bulk parameter injection."""
        science = ScienceMode()
        science.start_run(seed=42)
        
        results = science.inject_parameters({
            InterventionType.FREEZE_VALENCE: {"valence": 0.5},
            InterventionType.DISABLE_HOT: {},
        })
        
        assert len(results) == 2
        assert science.is_intervention_active(InterventionType.FREEZE_VALENCE)
        assert science.is_intervention_active(InterventionType.DISABLE_HOT)
    
    def test_to_dict(self):
        """Test serialization."""
        science = ScienceMode()
        science.start_run(seed=42)
        science.enable_intervention(InterventionType.FREEZE_VALENCE)
        
        d = science.to_dict()
        
        assert d["state"] == "enabled"
        assert "freeze_valence" in d["active_interventions"]


class TestScienceModeWithArtifacts:
    """Test ScienceMode with artifacts directory."""
    
    def test_save_run_header(self):
        """Test saving run header to artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            science = ScienceMode(artifacts_dir=tmpdir)
            science.start_run(seed=42, run_id="test_save")
            science.enable_intervention(InterventionType.FREEZE_VALENCE)
            
            header = science.end_run()
            
            # Check file was created
            header_file = Path(tmpdir) / "header_test_save.json"
            assert header_file.exists()
    
    def test_header_file_content(self):
        """Test header file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            science = ScienceMode(artifacts_dir=tmpdir)
            science.start_run(seed=42, run_id="content_test")
            science.enable_intervention(
                InterventionType.FREEZE_VALENCE,
                params={"valence": 0.5},
                reason="test_reason",
            )
            
            header = science.end_run()
            
            # Read and verify
            import json
            header_file = Path(tmpdir) / "header_content_test.json"
            with open(header_file) as f:
                data = json.load(f)
            
            assert data["run_id"] == "content_test"
            assert data["seed"] == 42
            assert len(data["interventions"]) == 1


class TestScienceModeMatrix:
    """Matrix tests for multiple intervention combinations."""
    
    @pytest.mark.parametrize("intervention_type", [
        InterventionType.FREEZE_VALENCE,
        InterventionType.FREEZE_DRIVES,
        InterventionType.FREEZE_POLICY,
        InterventionType.INJECT_VALENCE,
        InterventionType.INJECT_DRIVE,
        InterventionType.DISABLE_HOT,
        InterventionType.DISABLE_BROADCAST,
    ])
    def test_enable_each_intervention_type(self, intervention_type):
        """Test enabling each intervention type."""
        science = ScienceMode()
        science.start_run(seed=42)
        
        result = science.enable_intervention(intervention_type)
        
        assert result.success == True
        assert science.is_intervention_active(intervention_type)
    
    @pytest.mark.parametrize("intervention_types", [
        [InterventionType.FREEZE_VALENCE],
        [InterventionType.FREEZE_VALENCE, InterventionType.DISABLE_HOT],
        [InterventionType.DISABLE_HOT, InterventionType.DISABLE_BROADCAST],
        [InterventionType.FREEZE_VALENCE, InterventionType.DISABLE_HOT, InterventionType.DISABLE_BROADCAST],
    ])
    def test_multiple_interventions(self, intervention_types):
        """Test enabling multiple interventions."""
        science = ScienceMode()
        science.start_run(seed=42)
        
        for it in intervention_types:
            science.enable_intervention(it)
        
        active = science.get_all_active_interventions()
        assert len(active) == len(intervention_types)
        for it in intervention_types:
            assert it in active


class TestFactoryFunction:
    """Test factory function."""
    
    def test_create_science_mode(self):
        """Test factory function."""
        science = create_science_mode()
        
        assert isinstance(science, ScienceMode)
    
    def test_create_with_artifacts_dir(self):
        """Test factory with artifacts directory."""
        science = create_science_mode(artifacts_dir="/tmp/test")
        
        assert isinstance(science, ScienceMode)
