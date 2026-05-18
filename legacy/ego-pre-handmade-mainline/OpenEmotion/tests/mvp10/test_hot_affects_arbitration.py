"""
MVP-10 T08: Test HOT Affects Workspace Arbitration

Tests:
1. High conflict → bias toward reflection/info-gathering candidates
2. Low control → lower risk-taking candidate scores
3. should_reflect trigger conditions
4. Candidate score modifications
"""
import pytest
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from emotiond.hot_self_model import (
    HOTState,
    HOTSelfModel,
    reset_hot_self_model,
)


class TestArbitrationModifiers:
    """Tests for arbitration modifier calculation."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_normal_state_no_modifiers(self):
        """Test that normal state produces no significant modifiers."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            self_confidence=0.5,
            conflict_level=0.1,  # Low conflict
            control_estimate=0.7,  # Good control
        )
        
        modifiers = hot.get_arbitration_modifiers()
        
        assert modifiers["conflict_bias"] < 0.1
        assert modifiers["control_penalty"] < 0.1
        assert not modifiers["should_reflect"]
        assert not modifiers["high_conflict"]
        assert not modifiers["low_control"]
    
    def test_high_conflict_triggers_reflection(self):
        """Test that high conflict triggers reflection bias."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            self_confidence=0.5,
            conflict_level=0.7,  # High conflict
            control_estimate=0.5,
        )
        
        modifiers = hot.get_arbitration_modifiers()
        
        assert modifiers["high_conflict"]
        assert modifiers["should_reflect"]
        assert modifiers["conflict_bias"] > 0.0
        assert modifiers["info_seeking_bonus"] > 0.0
    
    def test_low_control_penalizes_risky_actions(self):
        """Test that low control penalizes risky actions."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            self_confidence=0.5,
            conflict_level=0.1,
            control_estimate=0.2,  # Low control
        )
        
        modifiers = hot.get_arbitration_modifiers()
        
        assert modifiers["low_control"]
        assert modifiers["control_penalty"] > 0.0
    
    def test_both_high_conflict_and_low_control(self):
        """Test combined high conflict and low control scenario."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            self_confidence=0.3,
            conflict_level=0.8,  # High conflict
            control_estimate=0.1,  # Low control
        )
        
        modifiers = hot.get_arbitration_modifiers()
        
        assert modifiers["high_conflict"]
        assert modifiers["low_control"]
        assert modifiers["should_reflect"]
        assert modifiers["conflict_bias"] > 0.0
        assert modifiers["control_penalty"] > 0.0


class TestCandidateModification:
    """Tests for applying HOT modifiers to candidates."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_normal_state_preserves_scores(self):
        """Test that normal state doesn't significantly change scores."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            conflict_level=0.1,
            control_estimate=0.7,
        )
        
        candidates = [
            {"id": "action_1", "score": 0.8, "type": "act"},
            {"id": "reflect_1", "score": 0.6, "type": "reflect"},
        ]
        
        modified = hot.apply_to_candidates(candidates)
        
        # Scores should be mostly preserved
        for orig, mod in zip(candidates, modified):
            assert abs(orig["score"] - mod["score"]) < 0.1
    
    def test_high_conflict_boosts_reflection_candidates(self):
        """Test that high conflict boosts reflection candidate scores."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            conflict_level=0.8,
            control_estimate=0.5,
        )
        
        candidates = [
            {"id": "action_1", "score": 0.7, "type": "act"},
            {"id": "reflect_1", "score": 0.5, "type": "reflect"},
            {"id": "info_1", "score": 0.5, "type": "info_seek"},
        ]
        
        modified = hot.apply_to_candidates(candidates)
        
        # Find modified candidates
        action_mod = next(c for c in modified if c["id"] == "action_1")
        reflect_mod = next(c for c in modified if c["id"] == "reflect_1")
        info_mod = next(c for c in modified if c["id"] == "info_1")
        
        # Reflection should be boosted
        assert reflect_mod["score"] >= candidates[1]["score"]
        
        # Info seeking should be boosted
        assert info_mod["score"] >= candidates[2]["score"]
        
        # Action might be slightly penalized
        # (depends on conflict_bias implementation)
    
    def test_low_control_penalizes_risky_candidates(self):
        """Test that low control penalizes high-risk candidates."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            conflict_level=0.1,
            control_estimate=0.2,  # Low control
        )
        
        candidates = [
            {"id": "safe_1", "score": 0.7, "type": "act", "meta": {"risk_level": 0.2}},
            {"id": "risky_1", "score": 0.7, "type": "act", "meta": {"risk_level": 0.8}},
        ]
        
        modified = hot.apply_to_candidates(candidates)
        
        safe_mod = next(c for c in modified if c["id"] == "safe_1")
        risky_mod = next(c for c in modified if c["id"] == "risky_1")
        
        # Risky candidate should be penalized
        assert risky_mod["score"] < candidates[1]["score"]
        
        # Safe candidate should not be penalized (or less)
        assert safe_mod["score"] >= risky_mod["score"]
    
    def test_scores_clamped_to_valid_range(self):
        """Test that modified scores stay in [0, 1] range."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            conflict_level=1.0,
            control_estimate=0.0,
        )
        
        candidates = [
            {"id": "test_1", "score": 0.95, "type": "act", "meta": {"risk_level": 1.0}},
            {"id": "test_2", "score": 0.05, "type": "reflect"},
        ]
        
        modified = hot.apply_to_candidates(candidates)
        
        for c in modified:
            assert 0.0 <= c["score"] <= 1.0
    
    def test_hot_applied_flag_set(self):
        """Test that hot_applied flag is set on modified candidates."""
        hot = HOTSelfModel()
        hot.state = HOTState(conflict_level=0.5)
        
        candidates = [{"id": "test", "score": 0.5, "type": "act"}]
        modified = hot.apply_to_candidates(candidates)
        
        assert modified[0]["hot_applied"]


class TestReflectionTrigger:
    """Tests for reflection trigger conditions."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_high_conflict_triggers_reflection(self):
        """Test that high conflict triggers reflection."""
        hot = HOTSelfModel()
        hot.state = HOTState(conflict_level=0.7)
        
        should, reason = hot.should_trigger_reflection()
        
        assert should
        assert "conflict" in reason.lower()
    
    def test_low_confidence_high_error_triggers_reflection(self):
        """Test that low confidence + high error triggers reflection."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            self_confidence=0.2,
            prediction_error=0.5,
        )
        
        should, reason = hot.should_trigger_reflection()
        
        assert should
    
    def test_low_control_triggers_reflection(self):
        """Test that low control triggers reflection."""
        hot = HOTSelfModel()
        hot.state = HOTState(control_estimate=0.1)
        
        should, reason = hot.should_trigger_reflection()
        
        assert should
        assert "control" in reason.lower()
    
    def test_stable_state_no_reflection(self):
        """Test that stable state doesn't trigger reflection."""
        hot = HOTSelfModel()
        hot.state = HOTState(
            self_confidence=0.7,
            conflict_level=0.1,
            control_estimate=0.7,
            prediction_error=0.1,
        )
        
        should, reason = hot.should_trigger_reflection()
        
        assert not should
        assert reason == ""


class TestArbitrationIntegration:
    """Integration tests for HOT affecting arbitration."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_conflict_scenario_selects_reflection(self):
        """Test that in conflict scenario, reflection is selected."""
        hot = HOTSelfModel()
        
        # Set high conflict directly (simulating accumulated conflict)
        hot.state.conflict_level = 0.7
        
        # Make the scores closer so HOT can tip the balance
        candidates = [
            {"id": "act_now", "score": 0.55, "type": "act"},
            {"id": "reflect_on_situation", "score": 0.5, "type": "reflect"},
            {"id": "gather_info", "score": 0.5, "type": "info_seek"},
        ]
        
        modified = hot.apply_to_candidates(candidates)
        
        # Get highest scoring candidate
        best = max(modified, key=lambda c: c["score"])
        
        # With high conflict and close scores, should prefer reflection/info-seeking
        assert best["type"] in ("reflect", "info_seek")
    
    def test_low_control_scenario_reduces_risk(self):
        """Test that low control reduces risk-taking in candidate selection."""
        hot = HOTSelfModel()
        
        # Set low control directly
        hot.state.control_estimate = 0.1  # Very low control
        
        candidates = [
            {"id": "safe_option", "score": 0.6, "type": "act", "meta": {"risk_level": 0.1}},
            {"id": "risky_option", "score": 0.65, "type": "act", "meta": {"risk_level": 0.9}},
        ]
        
        modified = hot.apply_to_candidates(candidates)
        
        safe = next(c for c in modified if c["id"] == "safe_option")
        risky = next(c for c in modified if c["id"] == "risky_option")
        
        # With low control, risky option should be penalized
        # Safe option should now score higher or equal to risky
        assert safe["score"] >= risky["score"]
    
    def test_prediction_error_triggers_behavior_change(self):
        """Test that prediction errors lead to behavioral adjustments."""
        hot = HOTSelfModel()
        
        # Make and fail predictions
        hot.make_prediction(tick_id=1, predicted_success=0.9)
        hot.resolve_prediction(tick_id=1, actual_success=False)
        
        hot.make_prediction(tick_id=2, predicted_success=0.8)
        hot.resolve_prediction(tick_id=2, actual_success=False)
        
        # Check that reflection is now triggered
        should, _ = hot.should_trigger_reflection()
        
        # After prediction errors, should want to reflect
        # (either due to low confidence or high error)
        # This tests that prediction errors causally affect behavior
        modifiers = hot.get_arbitration_modifiers()
        
        # Either should_reflect is true, or confidence is low
        assert should or hot.state.self_confidence < 0.5


class TestEdgeCases:
    """Edge case tests."""
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_empty_candidates(self):
        """Test applying to empty candidate list."""
        hot = HOTSelfModel()
        hot.state = HOTState(conflict_level=0.8)
        
        modified = hot.apply_to_candidates([])
        
        assert modified == []
    
    def test_candidate_without_meta(self):
        """Test candidate without meta field."""
        hot = HOTSelfModel()
        hot.state = HOTState(control_estimate=0.1)
        
        candidates = [
            {"id": "test", "score": 0.7, "type": "act"},  # No meta
        ]
        
        # Should not crash
        modified = hot.apply_to_candidates(candidates)
        
        assert len(modified) == 1
        assert modified[0]["hot_applied"]
    
    def test_extreme_conflict_values(self):
        """Test with extreme conflict values."""
        hot = HOTSelfModel()
        hot.state = HOTState(conflict_level=1.0, control_estimate=0.0)
        
        modifiers = hot.get_arbitration_modifiers()
        
        # Should have maximum modifiers
        assert modifiers["conflict_bias"] > 0
        assert modifiers["control_penalty"] > 0
        assert modifiers["should_reflect"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
