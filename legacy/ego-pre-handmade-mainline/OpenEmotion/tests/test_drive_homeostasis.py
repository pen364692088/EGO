"""
Tests for Homeostasis Drive system - US-651
"""

import pytest
import time
import math
from core.drive_homeostasis import (
    HomeostasisDrive, DriveState, DriveType, get_drive, reset_drive
)


class TestDriveState:
    """Test DriveState functionality."""
    
    def test_drive_state_initialization(self):
        """Test that DriveState initializes with correct defaults."""
        state = DriveState()
        
        # Check initial values are in valid range
        assert 0.0 <= state.energy <= 1.0
        assert 0.0 <= state.uncertainty <= 1.0
        assert 0.0 <= state.social <= 1.0
        assert 0.0 <= state.safety <= 1.0
        assert 0.0 <= state.fatigue <= 1.0
        
        # Check setpoints are reasonable
        for drive_type in DriveType:
            min_sp, max_sp = state.get_setpoint(drive_type)
            assert 0.0 <= min_sp <= max_sp <= 1.0
    
    def test_update_value_validation(self):
        """Test that drive value updates are validated."""
        state = DriveState()
        
        # Valid updates
        state.update_value(DriveType.ENERGY, 0.5)
        assert state.energy == 0.5
        
        state.update_value(DriveType.UNCERTAINTY, 0.0)
        assert state.uncertainty == 0.0
        
        state.update_value(DriveType.SOCIAL, 1.0)
        assert state.social == 1.0
        
        # Invalid updates should raise error
        with pytest.raises(ValueError):
            state.update_value(DriveType.ENERGY, -0.1)
        
        with pytest.raises(ValueError):
            state.update_value(DriveType.ENERGY, 1.1)
    
    def test_timestamp_updates(self):
        """Test that updates modify timestamps."""
        state = DriveState()
        original_time = state.last_update
        
        time.sleep(0.01)  # Small delay
        state.update_value(DriveType.ENERGY, 0.5)
        
        assert state.last_update > original_time


class TestHomeostasisDrive:
    """Test HomeostasisDrive functionality."""
    
    def test_drive_computation_in_setpoint(self):
        """Test that drive error is zero when in setpoint."""
        state = DriveState()
        drive = HomeostasisDrive(state)
        
        # Set energy to be within setpoint
        state.update_value(DriveType.ENERGY, 0.8)  # Within (0.7, 0.9)
        
        error = drive._compute_drive_error(DriveType.ENERGY)
        assert error == 0.0
    
    def test_drive_computation_outside_setpoint(self):
        """Test that drive error is positive when outside setpoint."""
        state = DriveState()
        drive = HomeostasisDrive(state)
        
        # Set energy below setpoint
        state.update_value(DriveType.ENERGY, 0.5)  # Below (0.7, 0.9)
        
        error = drive._compute_drive_error(DriveType.ENERGY)
        assert error > 0.0
        
        # Set energy above setpoint
        state.update_value(DriveType.ENERGY, 0.95)  # Above (0.7, 0.9)
        
        error = drive._compute_drive_error(DriveType.ENERGY)
        assert error > 0.0
    
    def test_overall_drive_error(self):
        """Test overall drive error computation."""
        drive = HomeostasisDrive()
        
        # All drives at optimal values should give zero error
        for drive_type in DriveType:
            min_sp, max_sp = drive.state.get_setpoint(drive_type)
            optimal_value = (min_sp + max_sp) / 2
            drive.state.update_value(drive_type, optimal_value)
        
        assert drive.drive_error() == 0.0
        
        # All drives at worst values should give high error
        for drive_type in DriveType:
            drive.state.update_value(drive_type, 0.0)  # Worst case
        
        assert drive.drive_error() > 0.5
    
    def test_emotion_from_drive(self):
        """Test emotion mapping from drive states."""
        drive = HomeostasisDrive()
        
        emotions = drive.emotion_from_drive()
        
        # Check all expected emotions are present
        expected_emotions = ["confidence", "curiosity", "affiliation", "caution", "rest_need"]
        for emotion in expected_emotions:
            assert emotion in emotions
            assert 0.0 <= emotions[emotion] <= 1.0
        
        # Test logical relationships
        # High energy + safety + low uncertainty should increase confidence
        drive.state.update_value(DriveType.ENERGY, 0.9)
        drive.state.update_value(DriveType.SAFETY, 0.9)
        drive.state.update_value(DriveType.UNCERTAINTY, 0.1)
        
        emotions = drive.emotion_from_drive()
        assert emotions["confidence"] > 0.7
    
    def test_drive_modulations(self):
        """Test drive modulation factors."""
        drive = HomeostasisDrive()
        
        modulations = drive.get_drive_modulations()
        
        # Check all expected modulations are present
        expected_keys = [
            "rollout_drive_bias", "conservatism_factor", "clarification倾向",
            "social_engagement", "response_length_factor", "risk_tolerance",
            "temperature_modulation", "top_p_modulation"
        ]
        
        for key in expected_keys:
            assert key in modulations
            assert 0.0 <= modulations[key] <= 1.0 or modulations[key] >= 0.0
    
    def test_decision_application(self):
        """Test drive application to decision contexts."""
        drive = HomeostasisDrive()
        
        # Test rollout selection
        context = {"strategy": "rollout_selection"}
        modified = drive.apply_drive_to_decision("rollout_selection", context)
        
        assert "drive_state" in modified
        assert "drive_bias" in modified
        assert modified["drive_bias"] >= 0.0
        
        # Test response generation
        context = {}
        modified = drive.apply_drive_to_decision("response_generation", context)
        
        assert "drive_state" in modified
        assert "response_factors" in modified
        assert "length_bias" in modified["response_factors"]
    
    def test_feedback_update(self):
        """Test updating drives from feedback."""
        drive = HomeostasisDrive()
        
        original_energy = drive.state.get_value(DriveType.ENERGY)
        
        # Apply feedback
        feedback = {"energy": -0.1, "uncertainty": 0.2}
        drive.update_from_feedback(feedback)
        
        # Check updates were applied
        assert drive.state.get_value(DriveType.ENERGY) == original_energy - 0.1
        assert drive.state.get_value(DriveType.UNCERTAINTY) == 0.2 + 0.3  # Base + feedback
        
        # Test invalid drive type is ignored
        feedback = {"invalid_drive": 0.5}
        drive.update_from_feedback(feedback)  # Should not raise error
    
    def test_drive_summary(self):
        """Test comprehensive drive summary."""
        drive = HomeostasisDrive()
        
        summary = drive.get_drive_summary()
        
        # Check summary structure
        required_keys = ["overall_error", "individual_drives", "emotions", "modulations", "last_update"]
        for key in required_keys:
            assert key in summary
        
        # Check individual drives structure
        for drive_type in DriveType:
            assert drive_type.value in summary["individual_drives"]
            drive_info = summary["individual_drives"][drive_type.value]
            assert "value" in drive_info
            assert "setpoint" in drive_info
            assert "error" in drive_info


class TestGlobalDriveInstance:
    """Test global drive instance management."""
    
    def test_get_drive_singleton(self):
        """Test that get_drive returns singleton instance."""
        reset_drive()
        
        drive1 = get_drive()
        drive2 = get_drive()
        
        assert drive1 is drive2
    
    def test_reset_drive(self):
        """Test drive instance reset."""
        drive1 = get_drive()
        reset_drive()
        drive2 = get_drive()
        
        assert drive1 is not drive2


class TestDriveModulationEffects:
    """Test that drive modulation produces expected effects."""
    
    def test_high_uncertainty_increases_clarification(self):
        """Test that high uncertainty increases clarification tendency."""
        drive = HomeostasisDrive()
        
        # Set high uncertainty, low fatigue
        drive.state.update_value(DriveType.UNCERTAINTY, 0.8)
        drive.state.update_value(DriveType.FATIGUE, 0.1)
        
        modulations = drive.get_drive_modulations()
        
        # Should increase clarification tendency
        assert modulations["clarification倾向"] > 0.6
    
    def test_high_fatigue_increases_conservatism(self):
        """Test that high fatigue increases conservatism."""
        drive = HomeostasisDrive()
        
        # Set high fatigue, low safety
        drive.state.update_value(DriveType.FATIGUE, 0.8)
        drive.state.update_value(DriveType.SAFETY, 0.2)
        
        modulations = drive.get_drive_modulations()
        
        # Should increase conservatism
        assert modulations["conservatism_factor"] > 0.8
    
    def test_low_safety_reduces_risk_tolerance(self):
        """Test that low safety reduces risk tolerance."""
        drive = HomeostasisDrive()
        
        # Set low safety, high uncertainty
        drive.state.update_value(DriveType.SAFETY, 0.2)
        drive.state.update_value(DriveType.UNCERTAINTY, 0.7)
        
        modulations = drive.get_drive_modulations()
        
        # Should reduce risk tolerance
        assert modulations["risk_tolerance"] < 0.5


if __name__ == "__main__":
    pytest.main([__file__])
