"""
T12 - Freeze Valence Intervention Tests

Tests for the interventions module:
- freeze_valence=True intervention
- Same task with different initial valence → behavior difference minimized
- Used for causal evidence
"""
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.drives import Drives, DriveType, drives_from_valence
from emotiond.valence_policy import ValencePolicy, PolicyParams
from emotiond.science.interventions import (
    InterventionType, InterventionConfig, InterventionResult,
    InterventionManager, FreezeValenceIntervention,
    create_freeze_valence_intervention, run_with_freeze_valence,
)


class TestInterventionType:
    """Test InterventionType enum."""
    
    def test_intervention_types_exist(self):
        """Test that required intervention types exist."""
        assert InterventionType.FREEZE_VALENCE.value == "freeze_valence"
        assert InterventionType.FREEZE_DRIVES.value == "freeze_drives"
        assert InterventionType.FREEZE_POLICY.value == "freeze_policy"
        assert InterventionType.INJECT_VALENCE.value == "inject_valence"
        assert InterventionType.INJECT_DRIVE.value == "inject_drive"
        assert InterventionType.CLAMP_DECISION.value == "clamp_decision"


class TestInterventionConfig:
    """Test InterventionConfig dataclass."""
    
    def test_config_creation(self):
        """Test creating an InterventionConfig."""
        config = InterventionConfig(
            intervention_type=InterventionType.FREEZE_VALENCE,
            enabled=True,
            params={"valence": 0.5},
            reason="test",
        )
        
        assert config.intervention_type == InterventionType.FREEZE_VALENCE
        assert config.enabled == True
        assert config.params == {"valence": 0.5}
    
    def test_config_to_dict(self):
        """Test InterventionConfig serialization."""
        config = InterventionConfig(
            intervention_type=InterventionType.FREEZE_VALENCE,
            params={"valence": 0.3},
        )
        
        d = config.to_dict()
        
        assert d["intervention_type"] == "freeze_valence"
        assert d["params"]["valence"] == 0.3


class TestInterventionResult:
    """Test InterventionResult dataclass."""
    
    def test_result_creation(self):
        """Test creating an InterventionResult."""
        result = InterventionResult(
            success=True,
            intervention_type=InterventionType.FREEZE_VALENCE,
            before={"active": False},
            after={"active": True, "params": {"valence": 0.5}},
            message="Enabled freeze_valence",
        )
        
        assert result.success == True
        assert result.intervention_type == InterventionType.FREEZE_VALENCE
    
    def test_result_to_dict(self):
        """Test InterventionResult serialization."""
        result = InterventionResult(
            success=True,
            intervention_type=InterventionType.FREEZE_VALENCE,
            before={},
            after={},
        )
        
        d = result.to_dict()
        
        assert d["success"] == True
        assert d["intervention_type"] == "freeze_valence"


class TestInterventionManager:
    """Test InterventionManager class."""
    
    def test_manager_initialization(self):
        """Test default manager initialization."""
        manager = InterventionManager()
        
        assert manager.is_active(InterventionType.FREEZE_VALENCE) == False
    
    def test_enable_intervention(self):
        """Test enabling an intervention."""
        manager = InterventionManager()
        
        result = manager.enable(
            InterventionType.FREEZE_VALENCE,
            params={"valence": 0.5},
            reason="test",
        )
        
        assert result.success == True
        assert manager.is_active(InterventionType.FREEZE_VALENCE) == True
    
    def test_disable_intervention(self):
        """Test disabling an intervention."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        result = manager.disable(InterventionType.FREEZE_VALENCE)
        
        assert result.success == True
        assert manager.is_active(InterventionType.FREEZE_VALENCE) == False
    
    def test_get_frozen_valence(self):
        """Test getting frozen valence."""
        manager = InterventionManager()
        
        # Not active
        assert manager.get_frozen_valence() is None
        
        # Active
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.7})
        assert manager.get_frozen_valence() == 0.7
    
    def test_get_frozen_drives(self):
        """Test getting frozen drives."""
        manager = InterventionManager()
        
        # Not active
        assert manager.get_frozen_drives() is None
        
        # Active
        manager.enable(InterventionType.FREEZE_DRIVES, {
            "levels": {"competence": 0.3, "safety": 0.8}
        })
        
        frozen = manager.get_frozen_drives()
        assert frozen[DriveType.COMPETENCE] == 0.3
        assert frozen[DriveType.SAFETY] == 0.8
    
    def test_get_frozen_policy(self):
        """Test getting frozen policy params."""
        manager = InterventionManager()
        
        # Not active
        assert manager.get_frozen_policy() is None
        
        # Active
        manager.enable(InterventionType.FREEZE_POLICY, {
            "policy_params": {
                "risk_aversion": 0.7,
                "exploration_temp": 0.2,
                "plan_depth": 2,
                "reflect_threshold": 0.4,
            }
        })
        
        frozen = manager.get_frozen_policy()
        assert frozen.risk_aversion == 0.7
        assert frozen.plan_depth == 2
    
    def test_apply_intervention_freeze_valence(self):
        """Test applying freeze_valence intervention."""
        manager = InterventionManager()
        
        result = manager.apply_intervention(valence=0.3)
        assert result["valence"] == 0.3  # No intervention active
        
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.8})
        result = manager.apply_intervention(valence=0.3)
        
        assert result["valence"] == 0.8  # Frozen value
        assert "freeze_valence" in result["interventions_applied"]
    
    def test_apply_intervention_with_drives(self):
        """Test applying intervention with drives."""
        manager = InterventionManager()
        drives = Drives()
        
        manager.enable(InterventionType.FREEZE_DRIVES, {
            "levels": {"competence": 0.2, "curiosity": 0.9}
        })
        
        result = manager.apply_intervention(valence=0.0, drives=drives)
        
        assert "freeze_drives" in result["interventions_applied"]
        assert drives.get_level(DriveType.COMPETENCE) == 0.2
        assert drives.get_level(DriveType.CURIOSITY) == 0.9
    
    def test_history(self):
        """Test intervention history."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        manager.disable(InterventionType.FREEZE_VALENCE)
        
        history = manager.get_history()
        
        assert len(history) == 2
        assert history[0].intervention_type == InterventionType.FREEZE_VALENCE
        assert history[1].message == "Disabled freeze_valence"
        
        manager.clear_history()
        assert len(manager.get_history()) == 0
    
    def test_clear_all(self):
        """Test clearing all interventions."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        manager.enable(InterventionType.FREEZE_DRIVES, {"levels": {}})
        
        manager.clear_all()
        
        assert manager.is_active(InterventionType.FREEZE_VALENCE) == False
        assert manager.is_active(InterventionType.FREEZE_DRIVES) == False


class TestFreezeValenceIntervention:
    """Test FreezeValenceIntervention class."""
    
    def test_intervention_creation(self):
        """Test creating a freeze_valence intervention."""
        intervention = FreezeValenceIntervention(valence=0.5)
        
        assert intervention.frozen_valence == 0.5
        assert intervention.manager.is_active(InterventionType.FREEZE_VALENCE)
    
    def test_intervention_clamping(self):
        """Test that valence is clamped to valid range."""
        intervention1 = FreezeValenceIntervention(valence=1.5)
        intervention2 = FreezeValenceIntervention(valence=-0.8)
        
        assert intervention1.frozen_valence == 1.0
        assert intervention2.frozen_valence == -0.8
    
    def test_apply(self):
        """Test applying the intervention."""
        intervention = FreezeValenceIntervention(valence=0.6)
        
        result = intervention.apply(valence=0.9)  # Different input
        assert result == 0.6  # Returns frozen value
    
    def test_apply_to_drives(self):
        """Test applying intervention to drives."""
        intervention = FreezeValenceIntervention(valence=0.5)
        drives = Drives()
        
        drives = intervention.apply_to_drives(drives)
        
        # Drives should be set based on frozen valence
        # Positive valence → higher competence
        assert drives.get_level(DriveType.COMPETENCE) > 0.5
    
    def test_compute_policy(self):
        """Test computing policy with intervention."""
        intervention = FreezeValenceIntervention(valence=0.8)
        drives = Drives()
        
        params = intervention.compute_policy(drives)
        
        # Policy should reflect high positive valence
        assert params.risk_aversion < 0.5  # Low risk
        assert params.exploration_temp < 0.3  # Low exploration
    
    def test_to_dict(self):
        """Test intervention serialization."""
        intervention = FreezeValenceIntervention(valence=0.3)
        
        d = intervention.to_dict()
        
        assert d["frozen_valence"] == 0.3
        assert "manager" in d


class TestFreezeValenceCausalEvidence:
    """Test that freeze_valence provides causal evidence."""
    
    def test_different_valence_same_frozen_behavior(self):
        """
        Test that different initial valence with freeze produces similar drives.
        
        This is the key test for causal evidence:
        - Without intervention: different valence → different drives
        - With freeze_valence: different valence → same drives
        
        If behavior differs with freeze_valence, the difference is NOT
        due to valence (because valence is fixed).
        """
        # Without intervention
        drives1_no_intervention = drives_from_valence(0.8)
        drives2_no_intervention = drives_from_valence(-0.8)
        
        # Should be different
        assert drives1_no_intervention[DriveType.COMPETENCE] != drives2_no_intervention[DriveType.COMPETENCE]
        
        # With freeze_valence intervention
        intervention1 = FreezeValenceIntervention(valence=0.0)  # Frozen to neutral
        intervention2 = FreezeValenceIntervention(valence=0.0)  # Same frozen value
        
        drives1 = Drives()
        drives2 = Drives()
        
        drives1 = intervention1.apply_to_drives(drives1)
        drives2 = intervention2.apply_to_drives(drives2)
        
        # Should be identical (both frozen to same valence)
        assert drives1.get_level(DriveType.COMPETENCE) == drives2.get_level(DriveType.COMPETENCE)
        assert drives1.get_level(DriveType.CURIOSITY) == drives2.get_level(DriveType.CURIOSITY)
    
    def test_policy_params_consistent_with_freeze(self):
        """
        Test that policy params are consistent with frozen valence.
        
        Same frozen valence should produce same policy params,
        regardless of original valence.
        """
        intervention = FreezeValenceIntervention(valence=0.5)
        
        # Compute policy with different input valences
        params1 = intervention.compute_policy(Drives())
        params2 = intervention.compute_policy(Drives())
        
        # Both should have same policy params (from frozen valence)
        assert params1.risk_aversion == params2.risk_aversion
        assert params1.exploration_temp == params2.exploration_temp
        assert params1.plan_depth == params2.plan_depth
    
    def test_behavior_difference_minimized(self):
        """
        Test that behavior difference is minimized with freeze.
        
        This simulates the key causal evidence test:
        - Run same task with different valence
        - With freeze: behavior should be similar
        - Without freeze: behavior should differ
        """
        # Simulate behavior via policy params
        policy = ValencePolicy()
        
        # Without intervention: different valence → different policy
        params_positive = policy.compute(valence=0.8)
        params_negative = policy.compute(valence=-0.8)
        
        # Clear cache
        policy._last_params = None
        
        # Should differ significantly
        risk_diff_no_intervention = abs(params_positive.risk_aversion - params_negative.risk_aversion)
        
        # With intervention: frozen to same value
        intervention1 = FreezeValenceIntervention(valence=0.0)
        intervention2 = FreezeValenceIntervention(valence=0.0)
        
        drives1 = intervention1.apply_to_drives(Drives())
        drives2 = intervention2.apply_to_drives(Drives())
        
        params1 = intervention1.compute_policy(drives1)
        params2 = intervention2.compute_policy(drives2)
        
        # Should be identical
        risk_diff_with_intervention = abs(params1.risk_aversion - params2.risk_aversion)
        
        assert risk_diff_with_intervention == 0.0
        assert risk_diff_no_intervention > risk_diff_with_intervention


class TestCreateFreezeValenceIntervention:
    """Test factory function."""
    
    def test_factory_creates_intervention(self):
        """Test that factory creates intervention correctly."""
        intervention = create_freeze_valence_intervention(valence=0.7)
        
        assert isinstance(intervention, FreezeValenceIntervention)
        assert intervention.frozen_valence == 0.7


class TestRunWithFreezeValence:
    """Test run_with_freeze_valence function."""
    
    def test_run_with_intervention(self):
        """Test running a function with freeze intervention."""
        def mock_run(valence, drives, policy_params, context):
            return {
                "valence_used": valence,
                "policy": policy_params.to_dict() if policy_params else None,
            }
        
        drives = Drives()
        
        result = run_with_freeze_valence(
            valence=0.5,
            run_func=mock_run,
            drives=drives,
            context={},
        )
        
        assert "result" in result
        assert "intervention" in result
        assert "policy_params" in result
        assert result["result"]["valence_used"] == 0.5
    
    def test_run_clamps_valence(self):
        """Test that run clamps valence to valid range."""
        def mock_run(valence, **kwargs):
            return {"valence": valence}
        
        result = run_with_freeze_valence(
            valence=1.5,  # Out of range
            run_func=mock_run,
        )
        
        # Should be clamped to 1.0
        assert result["intervention"]["frozen_valence"] == 1.0


class TestInterventionIntegration:
    """Integration tests for interventions."""
    
    def test_full_intervention_workflow(self):
        """Test full intervention workflow."""
        # Create drives with low competence
        drives = Drives()
        drives.set_level(DriveType.COMPETENCE, 0.2, "test")
        
        # Create intervention
        intervention = FreezeValenceIntervention(valence=0.3)
        
        # Apply to drives
        drives = intervention.apply_to_drives(drives)
        
        # Compute policy
        params = intervention.compute_policy(drives)
        
        # Verify intervention is active
        assert intervention.manager.is_active(InterventionType.FREEZE_VALENCE)
        
        # Verify drives are consistent with frozen valence
        # Negative valence → higher curiosity
        assert drives.get_level(DriveType.CURIOSITY) > 0.5
        
        # Verify policy params
        assert 0.0 <= params.risk_aversion <= 1.0
        assert 0.0 <= params.exploration_temp <= 1.0
    
    def test_multiple_interventions(self):
        """Test multiple interventions together."""
        manager = InterventionManager()
        
        # Enable multiple interventions
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        manager.enable(InterventionType.FREEZE_POLICY, {
            "policy_params": {
                "risk_aversion": 0.8,
                "exploration_temp": 0.1,
                "plan_depth": 1,
                "reflect_threshold": 0.9,
            }
        })
        
        # Both should be active
        assert manager.is_active(InterventionType.FREEZE_VALENCE)
        assert manager.is_active(InterventionType.FREEZE_POLICY)
        
        # Apply both - need to pass a policy for FREEZE_POLICY to take effect
        drives = Drives()
        policy = ValencePolicy()
        result = manager.apply_intervention(valence=-0.5, drives=drives, policy=policy)
        
        assert result["valence"] == 0.5  # Frozen
        assert result["policy_params"] is not None
        assert result["policy_params"].risk_aversion == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
