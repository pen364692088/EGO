"""
MVP14 T02: Drive Integration Tests
"""
import pytest
import tempfile

from emotiond.drives import (
    DriveManager,
    get_drive_manager,
    reset_drive_manager,
    DriveType,
)
from emotiond.drives.integration import DriveIntegrator, get_drive_integrator
from emotiond.self_model import SelfModelState


class TestDriveIntegration:
    """Tests for drive integration."""
    
    def test_sync_with_self_model(self):
        """Should sync drives with self-model."""
        reset_drive_manager()
        integrator = get_drive_integrator()
        self_model = SelfModelState()
        
        result = integrator.sync_with_self_model(self_model)
        
        assert "drives_updated" in result
        assert "signals_updated" in result
    
    def test_get_candidate_bias(self):
        """Should return candidate scoring bias."""
        reset_drive_manager()
        integrator = get_drive_integrator()
        
        bias = integrator.get_candidate_bias()
        
        assert "stability_weight" in bias
        assert "coherence_weight" in bias
        assert "completion_weight" in bias
    
    def test_get_maintenance_priority(self):
        """Should return maintenance priority."""
        reset_drive_manager()
        integrator = get_drive_integrator()
        
        priority = integrator.get_maintenance_priority()
        
        assert "urgent_maintenance" in priority
        assert "homeostatic_issues" in priority
        assert "repair_drive" in priority
        assert "should_maintain" in priority
    
    def test_compute_cycle_influence(self):
        """Should compute cycle influence."""
        reset_drive_manager()
        integrator = get_drive_integrator()
        
        influence = integrator.compute_cycle_influence()
        
        assert 0.0 <= influence <= 1.0
    
    def test_check_intervention_needed(self):
        """Should check intervention status."""
        reset_drive_manager()
        integrator = get_drive_integrator()
        
        intervention = integrator.check_intervention_needed()
        
        assert "needed" in intervention
        assert "reasons" in intervention
        assert "dominant_drive" in intervention
