"""
MVP-10 T07: Test HOT State Structure and Update Rules

Tests:
1. HOT state field validation
2. Prediction → Result → Error → Update chain
3. State delta traceability
4. Confidence updates from prediction errors
"""
import pytest
import time

# Import from the actual project location
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from emotiond.hot_self_model import (
    HOTState,
    HOTStateField,
    HOTUpdate,
    PredictionRecord,
    HOTSelfModel,
    get_hot_self_model,
    reset_hot_self_model,
)


class TestHOTState:
    """Tests for HOTState dataclass."""
    
    def test_default_state(self):
        """Test default HOT state values."""
        state = HOTState()
        
        assert 0.0 <= state.self_confidence <= 1.0
        assert 0.0 <= state.conflict_level <= 1.0
        assert 0.0 <= state.control_estimate <= 1.0
        assert 0.0 <= state.predicted_success <= 1.0
        assert 0.0 <= state.prediction_error <= 1.0
    
    def test_state_clamping(self):
        """Test that values are clamped to [0, 1] range."""
        # Values above 1 should be clamped
        state = HOTState(
            self_confidence=1.5,
            conflict_level=-0.5,
            control_estimate=2.0,
            predicted_success=-0.1,
            prediction_error=3.0,
        )
        
        assert state.self_confidence == 1.0
        assert state.conflict_level == 0.0
        assert state.control_estimate == 1.0
        assert state.predicted_success == 0.0
        assert state.prediction_error == 1.0
    
    def test_state_serialization(self):
        """Test to_dict and from_dict roundtrip."""
        original = HOTState(
            self_confidence=0.75,
            conflict_level=0.3,
            control_estimate=0.6,
            predicted_success=0.8,
            prediction_error=0.1,
        )
        
        data = original.to_dict()
        restored = HOTState.from_dict(data)
        
        assert restored.self_confidence == original.self_confidence
        assert restored.conflict_level == original.conflict_level
        assert restored.control_estimate == original.control_estimate
        assert restored.predicted_success == original.predicted_success
        assert restored.prediction_error == original.prediction_error


class TestPredictionRecord:
    """Tests for PredictionRecord."""
    
    def test_prediction_creation(self):
        """Test creating a prediction record."""
        record = PredictionRecord(
            tick_id=1,
            predicted_success=0.7,
        )
        
        assert record.tick_id == 1
        assert record.predicted_success == 0.7
        assert record.actual_outcome is None
        assert record.prediction_error is None
        assert not record.resolved
    
    def test_prediction_resolution_success(self):
        """Test resolving a prediction with success."""
        record = PredictionRecord(
            tick_id=1,
            predicted_success=0.8,
        )
        
        error = record.resolve(actual_success=True)
        
        assert record.resolved
        assert record.actual_outcome == "success"
        # Error should be |0.8 - 1.0| = 0.2
        assert abs(error - 0.2) < 0.001
    
    def test_prediction_resolution_failure(self):
        """Test resolving a prediction with failure."""
        record = PredictionRecord(
            tick_id=1,
            predicted_success=0.8,
        )
        
        error = record.resolve(actual_success=False)
        
        assert record.resolved
        assert record.actual_outcome == "fail"
        # Error should be |0.8 - 0.0| = 0.8
        assert abs(error - 0.8) < 0.001


class TestHOTSelfModelPredictions:
    """Tests for prediction chain."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_make_prediction(self):
        """Test making a prediction."""
        hot = HOTSelfModel()
        
        record = hot.make_prediction(tick_id=1, predicted_success=0.7)
        
        assert record.tick_id == 1
        assert record.predicted_success == 0.7
        assert not record.resolved
        assert hot.state.predicted_success == 0.7
    
    def test_resolve_prediction_success(self):
        """Test resolving prediction with success."""
        hot = HOTSelfModel()
        hot.make_prediction(tick_id=1, predicted_success=0.8)
        
        error = hot.resolve_prediction(tick_id=1, actual_success=True)
        
        assert error is not None
        assert abs(error - 0.2) < 0.001  # |0.8 - 1.0|
    
    def test_resolve_prediction_failure(self):
        """Test resolving prediction with failure."""
        hot = HOTSelfModel()
        hot.make_prediction(tick_id=1, predicted_success=0.8)
        
        error = hot.resolve_prediction(tick_id=1, actual_success=False)
        
        assert error is not None
        assert abs(error - 0.8) < 0.001  # |0.8 - 0.0|
    
    def test_resolve_nonexistent_prediction(self):
        """Test resolving a prediction that doesn't exist."""
        hot = HOTSelfModel()
        
        error = hot.resolve_prediction(tick_id=999, actual_success=True)
        
        assert error is None
    
    def test_prediction_state_delta_logged(self):
        """Test that predictions are logged in state delta."""
        hot = HOTSelfModel()
        
        hot.make_prediction(tick_id=1, predicted_success=0.7)
        hot.resolve_prediction(tick_id=1, actual_success=True)
        
        log = hot.get_state_delta_log()
        
        # Should have at least: predicted_success update, prediction_error update
        assert len(log) >= 2
        
        # Check that prediction error was logged
        error_entries = [e for e in log if e["field"] == "prediction_error"]
        assert len(error_entries) > 0


class TestConfidenceUpdates:
    """Tests for confidence updates from prediction errors."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_low_error_increases_confidence(self):
        """Test that low prediction error increases confidence."""
        hot = HOTSelfModel()
        initial_confidence = hot.state.self_confidence
        
        # Make accurate prediction
        hot.make_prediction(tick_id=1, predicted_success=0.9)
        hot.resolve_prediction(tick_id=1, actual_success=True)  # Error = 0.1
        
        # Confidence should increase
        assert hot.state.self_confidence >= initial_confidence
    
    def test_high_error_decreases_confidence(self):
        """Test that high prediction error decreases confidence."""
        hot = HOTSelfModel()
        initial_confidence = hot.state.self_confidence
        
        # Make inaccurate prediction
        hot.make_prediction(tick_id=1, predicted_success=0.9)
        hot.resolve_prediction(tick_id=1, actual_success=False)  # Error = 0.9
        
        # Confidence should decrease
        assert hot.state.self_confidence < initial_confidence
    
    def test_multiple_predictions_accumulate(self):
        """Test that multiple predictions affect confidence."""
        hot = HOTSelfModel()
        
        # Series of very accurate predictions
        for i in range(5):
            hot.make_prediction(tick_id=i, predicted_success=0.95)
            hot.resolve_prediction(tick_id=i, actual_success=True)
        
        # Confidence should be higher than initial
        assert hot.state.self_confidence > 0.5


class TestConflictUpdates:
    """Tests for conflict level updates."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_conflict_from_sources(self):
        """Test updating conflict from competing sources."""
        hot = HOTSelfModel()
        
        conflicts = [
            {"weight": 0.7, "description": "goal_a vs goal_b"},
            {"weight": 0.5, "description": "belief_x vs belief_y"},
        ]
        
        new_conflict = hot.update_conflict_level(conflicts)
        
        assert new_conflict > 0
        assert hot.state.conflict_level > 0
    
    def test_conflict_decay(self):
        """Test that conflict decays over time without sources."""
        hot = HOTSelfModel()
        
        # Set high conflict
        hot.update_conflict_level([{"weight": 0.8, "description": "test"}])
        high_conflict = hot.state.conflict_level
        
        # Decay by updating with no sources
        hot.update_conflict_level([])
        
        assert hot.state.conflict_level < high_conflict


class TestControlUpdates:
    """Tests for control estimate updates."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_success_planned_increases_control(self):
        """Test that planned success increases control estimate."""
        hot = HOTSelfModel()
        initial_control = hot.state.control_estimate
        
        hot.update_control_estimate(
            outcome_status="success",
            was_planned=True,
            external_factors=0.0,
        )
        
        assert hot.state.control_estimate > initial_control
    
    def test_failure_planned_decreases_control(self):
        """Test that planned failure decreases control estimate."""
        hot = HOTSelfModel()
        initial_control = hot.state.control_estimate
        
        hot.update_control_estimate(
            outcome_status="fail",
            was_planned=True,
            external_factors=0.0,
        )
        
        assert hot.state.control_estimate < initial_control
    
    def test_external_factors_moderate_control(self):
        """Test that external factors moderate control updates."""
        hot = HOTSelfModel()
        
        # Failure with high external factors should have less impact
        hot.state.control_estimate = 0.5
        hot.update_control_estimate(
            outcome_status="fail",
            was_planned=True,
            external_factors=0.8,
        )
        control_with_external = hot.state.control_estimate
        
        # Reset
        hot.state.control_estimate = 0.5
        
        # Failure with no external factors
        hot.update_control_estimate(
            outcome_status="fail",
            was_planned=True,
            external_factors=0.0,
        )
        control_without_external = hot.state.control_estimate
        
        # With external factors, control should be higher (less penalty)
        assert control_with_external > control_without_external


class TestStateDeltaTraceability:
    """Tests for state delta logging and traceability."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_state_delta_records_all_changes(self):
        """Test that state delta records all changes."""
        hot = HOTSelfModel()
        
        # Make several changes
        hot.make_prediction(tick_id=1, predicted_success=0.7)
        hot.resolve_prediction(tick_id=1, actual_success=True)
        hot.update_conflict_level([{"weight": 0.6, "description": "test"}])
        hot.update_control_estimate("success", True, 0.0)
        
        log = hot.get_state_delta_log()
        
        # Should have multiple entries
        assert len(log) >= 3
        
        # Each entry should have required fields
        for entry in log:
            assert "field" in entry
            assert "before" in entry
            assert "after" in entry
            assert "reason" in entry
    
    def test_state_delta_includes_prediction_chain(self):
        """Test that state delta includes prediction chain data."""
        hot = HOTSelfModel()
        
        hot.make_prediction(tick_id=1, predicted_success=0.8)
        hot.resolve_prediction(tick_id=1, actual_success=False)
        
        log = hot.get_state_delta_log()
        
        # Find prediction_error entry
        error_entries = [e for e in log if e["field"] == "prediction_error"]
        assert len(error_entries) > 0
        
        # Should include predicted and actual values
        entry = error_entries[0]
        assert entry["predicted"] is not None
        assert entry["actual"] is not None


class TestGlobalInstance:
    """Tests for global instance management."""
    
    def test_get_hot_self_model(self):
        """Test getting global instance."""
        reset_hot_self_model()
        
        hot1 = get_hot_self_model()
        hot2 = get_hot_self_model()
        
        assert hot1 is hot2
    
    def test_reset_hot_self_model(self):
        """Test resetting global instance."""
        hot1 = get_hot_self_model()
        hot1.state.self_confidence = 0.9
        
        reset_hot_self_model()
        
        hot2 = get_hot_self_model()
        assert hot2.state.self_confidence == 0.5  # Default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
