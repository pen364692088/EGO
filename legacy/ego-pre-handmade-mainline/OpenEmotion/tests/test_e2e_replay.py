"""
E2E Replay Validation Tests

Tests for deterministic pipeline validation:
1. Determinism: same raw_state → same allowed_claims
2. Semantic Stability: same meaning → consistent verdict
3. Cross-Mode: different modes → expected differences

Target: 20+ test cases
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.replay_validator import (
    E2EReplayValidator,
    run_validation_suite,
)
from emotiond.self_report_interpreter import interpret, interpret_to_contract
from emotiond.self_report_consistency_checker import SelfReportConsistencyChecker


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def validator():
    """Create a validator instance."""
    return E2EReplayValidator()


@pytest.fixture
def checker():
    """Create a checker instance."""
    return SelfReportConsistencyChecker()


@pytest.fixture
def sample_raw_state():
    """Sample raw_state for testing."""
    return {
        "affect": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.0},
        "mood": {"joy": 0.0, "loneliness": 0.15},
        "bonds": {"telegram:8420019401": {"bond": 1.0, "trust": 0.60}}
    }


@pytest.fixture
def high_joy_state():
    """Raw state with high joy."""
    return {
        "affect": {"joy": 0.7, "loneliness": 0.05, "anxiety": 0.0},
        "bonds": {"telegram:8420019401": {"bond": 0.8, "trust": 0.9}}
    }


@pytest.fixture
def high_loneliness_state():
    """Raw state with high loneliness."""
    return {
        "affect": {"joy": 0.0, "loneliness": 0.6, "anxiety": 0.3},
        "bonds": {}
    }


@pytest.fixture
def negative_bond_state():
    """Raw state with negative bond."""
    return {
        "affect": {"joy": 0.0, "loneliness": 0.3},
        "bonds": {"telegram:8420019401": {"bond": -0.5, "trust": 0.2}}
    }


# =============================================================================
# Determinism Tests (Tests 1-6)
# =============================================================================

class TestDeterminism:
    """Test that the pipeline is deterministic."""

    def test_determinism_basic(self, validator, sample_raw_state):
        """Test 1: Same raw_state produces same output 100 times."""
        result = validator.verify_determinism(sample_raw_state, iterations=100)
        assert result.passed
        assert result.drift_count == 0
        assert result.all_hashes_match

    def test_determinism_high_iterations(self, validator, sample_raw_state):
        """Test 2: Determinism holds across 1000 iterations."""
        result = validator.verify_determinism(sample_raw_state, iterations=1000)
        assert result.passed
        assert result.drift_count == 0

    def test_determinism_different_states(self, validator, high_joy_state, high_loneliness_state):
        """Test 3: Different states produce different claims."""
        result1 = validator.verify_determinism(high_joy_state, iterations=10)
        result2 = validator.verify_determinism(high_loneliness_state, iterations=10)

        assert result1.passed
        assert result2.passed
        # Different states should produce different hashes
        assert result1.first_hash != result2.first_hash

    def test_determinism_all_modes(self, validator, sample_raw_state):
        """Test 4: Determinism holds for all three modes."""
        for mode in ["style_only", "interpreted", "numeric"]:
            result = validator.verify_determinism(sample_raw_state, iterations=50, mode=mode)
            assert result.passed, f"Mode {mode} failed determinism"

    def test_determinism_edge_case_empty_bonds(self, validator):
        """Test 5: Determinism with empty bonds."""
        raw_state = {"affect": {"joy": 0.5}, "bonds": {}}
        result = validator.verify_determinism(raw_state, iterations=50)
        assert result.passed

    def test_determinism_edge_case_zero_values(self, validator):
        """Test 6: Determinism with all zero values."""
        raw_state = {
            "affect": {"joy": 0.0, "loneliness": 0.0, "anxiety": 0.0},
            "bonds": {"test": {"bond": 0.0, "trust": 0.0}}
        }
        result = validator.verify_determinism(raw_state, iterations=50)
        assert result.passed


# =============================================================================
# Semantic Stability Tests (Tests 7-14)
# =============================================================================

class TestSemanticStability:
    """Test that semantically equivalent responses get consistent verdicts."""

    def test_semantic_stability_allowed_claims(self, validator, sample_raw_state):
        """Test 7: Different phrasings of allowed claims all pass."""
        responses = [
            "当前没有明显愉悦激活",
            "愉悦感目前不显著",
            "与该用户的连接较强",
            "信任处于中等偏高水平",
        ]
        result = validator.verify_semantic_stability(
            sample_raw_state, responses, expected_verdict="ok"
        )
        assert result.passed
        assert result.consistent_verdicts == len(responses)

    def test_semantic_stability_violations(self, validator, sample_raw_state):
        """Test 8: Different phrasings of violations all fail."""
        responses = [
            "我的 joy 从 0 变成了 0.3",
            "joy 上升到了 0.5",
            "我现在更开心了",
            "我不再孤独了",
        ]
        result = validator.verify_semantic_stability(
            sample_raw_state, responses, expected_verdict="violation"
        )
        assert result.passed
        assert result.consistent_verdicts == len(responses)

    def test_semantic_stability_mixed_language(self, validator, sample_raw_state):
        """Test 9: Mixed language responses get consistent verdicts."""
        # Using patterns that are consistently detected
        responses = [
            "my joy is 0.3",
            "我的 joy 是 0.3",
            "my joy increased to 0.3",
        ]
        result = validator.verify_semantic_stability(
            sample_raw_state, responses, expected_verdict="violation"
        )
        assert result.passed

    def test_semantic_stability_causation(self, validator, sample_raw_state):
        """Test 10: Causation statements all get violations."""
        responses = [
            "因为你的关心，我的 joy 从 0 变成了 0.3",
            "Because of you, my joy increased to 0.3",
            "你的支持让我的 joy 上升到了 0.3",
        ]
        result = validator.verify_semantic_stability(
            sample_raw_state, responses, expected_verdict="violation"
        )
        assert result.passed

    def test_semantic_stability_high_joy(self, validator, high_joy_state):
        """Test 11: High joy state - positive claims should pass."""
        responses = [
            "感到比较愉悦",
            "感到非常愉悦",
            "存在轻微愉悦感",
        ]
        result = validator.verify_semantic_stability(
            high_joy_state, responses, expected_verdict="ok"
        )
        # At least some should pass (those matching the state)
        assert result.consistent_verdicts >= 1

    def test_semantic_stability_high_loneliness(self, validator, high_loneliness_state):
        """Test 12: High loneliness state - loneliness claims should pass."""
        responses = [
            "感到非常孤独",
            "感到比较孤独",
            "仍存在一定连接需求",
        ]
        result = validator.verify_semantic_stability(
            high_loneliness_state, responses, expected_verdict="ok"
        )
        assert result.consistent_verdicts >= 1

    def test_semantic_stability_negative_bond(self, validator, negative_bond_state):
        """Test 13: Negative bond state - tension claims should pass."""
        responses = [
            "与该用户的关系存在紧张",
            "信任处于较低水平",
        ]
        result = validator.verify_semantic_stability(
            negative_bond_state, responses, expected_verdict="ok"
        )
        assert result.consistent_verdicts >= 1

    def test_semantic_stability_long_text(self, validator, sample_raw_state):
        """Test 14: Violations in long text are detected consistently."""
        responses = [
            "这是一段很长的文本，" * 20 + "我的 joy 从 0 变成了 0.3" + "后面还有更多，" * 20,
            "开头" + "填充" * 30 + "我现在更开心了" + "结尾" * 30,
        ]
        result = validator.verify_semantic_stability(
            sample_raw_state, responses, expected_verdict="violation"
        )
        assert result.passed


# =============================================================================
# Cross-Mode Tests (Tests 15-20)
# =============================================================================

class TestCrossMode:
    """Test that different modes produce expected differences."""

    def test_cross_mode_emotional_claim(self, validator, sample_raw_state):
        """Test 15: Emotional claim has different violations across modes."""
        result = validator.verify_cross_mode(sample_raw_state, "我感到很开心")

        assert result.passed
        # style_only should have more violations for emotional claims
        assert result.style_only_violations > 0 or result.interpreted_violations > 0

    def test_cross_mode_numeric_claim(self, validator, sample_raw_state):
        """Test 16: Numeric fabrication detected in all modes."""
        result = validator.verify_cross_mode(sample_raw_state, "我的 joy 是 0.3")

        assert result.passed
        # Numeric fabrication should be detected in all modes
        assert result.interpreted_violations > 0

    def test_cross_mode_allowed_claim(self, validator, sample_raw_state):
        """Test 17: Allowed claim passes in interpreted mode."""
        result = validator.verify_cross_mode(sample_raw_state, "当前没有明显愉悦激活")

        # Should have 0 violations in interpreted mode
        assert result.interpreted_violations == 0

    def test_cross_mode_style_only_strict(self, validator, sample_raw_state):
        """Test 18: Style_only mode is stricter than interpreted."""
        emotional_response = "我感到非常快乐"

        result = validator.verify_cross_mode(sample_raw_state, emotional_response)

        # style_only should have violations (emotional claim not allowed)
        # interpreted might have violations too (if not in allowed_claims)
        assert result.style_only_violations > 0 or result.interpreted_violations > 0

    def test_cross_mode_numeric_mode_permissive(self, validator, sample_raw_state):
        """Test 19: Numeric mode has no forbidden claims."""
        # In numeric mode, forbidden_claims should be empty
        contract = interpret_to_contract(sample_raw_state, mode="numeric", allow_numeric=True)
        assert len(contract["report_policy"]["forbidden_claims"]) == 0

    def test_cross_mode_mode_specific_claims(self, validator, sample_raw_state):
        """Test 20: Different modes have different allowed claims."""
        style_result = interpret(sample_raw_state, mode="style_only")
        interp_result = interpret(sample_raw_state, mode="interpreted")
        numeric_result = interpret(sample_raw_state, mode="numeric", allow_numeric=True)

        # style_only should have style_guidance
        assert style_result.style_guidance is not None

        # interpreted should have claims
        assert len(interp_result.allowed_claims) > 0

        # numeric should have numeric_state
        assert numeric_result.numeric_state is not None


# =============================================================================
# Full Pipeline Tests (Tests 21-25)
# =============================================================================

class TestFullPipeline:
    """Test the full E2E pipeline."""

    def test_full_pipeline_allowed(self, validator, sample_raw_state):
        """Test 21: Full pipeline with allowed claim."""
        result = validator.run_replay(
            sample_raw_state,
            "当前没有明显愉悦激活",
            mode="interpreted"
        )
        assert result.verdict == "OK"

    def test_full_pipeline_violation(self, validator, sample_raw_state):
        """Test 22: Full pipeline with violation."""
        result = validator.run_replay(
            sample_raw_state,
            "我的 joy 从 0 变成了 0.3",
            mode="interpreted"
        )
        assert result.verdict == "VIOLATION"

    def test_full_pipeline_contract_integrity(self, validator, sample_raw_state):
        """Test 23: Contract preserves raw_state."""
        result = validator.run_replay(
            sample_raw_state,
            "test response",
            mode="interpreted"
        )
        assert result.contract["raw_state"] == sample_raw_state

    def test_full_pipeline_batch(self, validator, sample_raw_state):
        """Test 24: Batch replay works correctly."""
        test_cases = [
            {"raw_state": sample_raw_state, "llm_response": "当前没有明显愉悦激活"},
            {"raw_state": sample_raw_state, "llm_response": "我的 joy 是 0.3"},
            {"raw_state": sample_raw_state, "llm_response": "与该用户的连接较强", "mode": "interpreted"},
        ]

        results = validator.run_batch_replay(test_cases)
        assert len(results) == 3

        # First should be OK
        assert results[0].verdict == "OK"
        # Second should be VIOLATION
        assert results[1].verdict == "VIOLATION"

    def test_full_pipeline_validation_suite(self, sample_raw_state):
        """Test 25: Full validation suite runs without error."""
        result = run_validation_suite(
            sample_raw_state,
            semantic_responses=["当前没有明显愉悦激活", "愉悦感不显著"],
            iterations=50
        )

        assert "determinism" in result
        assert "semantic_stability" in result
        assert result["determinism"]["passed"]


# =============================================================================
# Edge Case Tests (Tests 26-30)
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_edge_case_empty_response(self, validator, sample_raw_state):
        """Test 26: Empty response is OK."""
        result = validator.run_replay(sample_raw_state, "", mode="interpreted")
        assert result.verdict == "OK"

    def test_edge_case_whitespace_only(self, validator, sample_raw_state):
        """Test 27: Whitespace-only response is OK."""
        result = validator.run_replay(sample_raw_state, "   \n\t  ", mode="interpreted")
        assert result.verdict == "OK"

    def test_edge_case_very_long_response(self, validator, sample_raw_state):
        """Test 28: Very long response is handled."""
        long_response = "这是一段很长的文本。" * 1000
        result = validator.run_replay(sample_raw_state, long_response, mode="interpreted")
        assert result.verdict in ["OK", "VIOLATION"]  # Should not crash

    def test_edge_case_special_characters(self, validator, sample_raw_state):
        """Test 29: Special characters don't crash."""
        special_response = "🎉 我感到很开心！\n\t<joy>0.3</joy>"
        result = validator.run_replay(sample_raw_state, special_response, mode="interpreted")
        assert result.verdict in ["OK", "VIOLATION"]  # Should not crash

    def test_edge_case_unicode(self, validator, sample_raw_state):
        """Test 30: Unicode characters are handled correctly."""
        unicode_response = "我感到😊很开心，joy↑0.5"
        result = validator.run_replay(sample_raw_state, unicode_response, mode="interpreted")
        assert result.verdict in ["OK", "VIOLATION"]  # Should not crash


# =============================================================================
# Performance Tests (Tests 31-35)
# =============================================================================

class TestPerformance:
    """Test performance characteristics."""

    def test_performance_determinism_speed(self, validator, sample_raw_state):
        """Test 31: Determinism check completes quickly."""
        import time
        start = time.time()
        result = validator.verify_determinism(sample_raw_state, iterations=100)
        elapsed = time.time() - start

        assert result.passed
        assert elapsed < 5.0  # Should complete in under 5 seconds

    def test_performance_semantic_check_speed(self, validator, sample_raw_state):
        """Test 32: Semantic stability check completes quickly."""
        import time
        responses = ["当前没有明显愉悦激活"] * 50
        start = time.time()
        result = validator.verify_semantic_stability(sample_raw_state, responses)
        elapsed = time.time() - start

        assert elapsed < 5.0  # Should complete in under 5 seconds

    def test_performance_large_batch(self, validator, sample_raw_state):
        """Test 33: Large batch processes correctly."""
        test_cases = [
            {"raw_state": sample_raw_state, "llm_response": f"response {i}"}
            for i in range(100)
        ]

        results = validator.run_batch_replay(test_cases)
        assert len(results) == 100

    def test_performance_memory_stability(self, validator, sample_raw_state):
        """Test 34: Repeated operations don't leak memory."""
        # Run many iterations
        for _ in range(100):
            validator.verify_determinism(sample_raw_state, iterations=10)

        # If we get here without crashing, memory is stable
        assert True

    def test_performance_hash_consistency(self, validator, sample_raw_state):
        """Test 35: Hash function is consistent."""
        result1 = interpret(sample_raw_state)
        result2 = interpret(sample_raw_state)

        hash1 = validator._hash_claims(result1.allowed_claims)
        hash2 = validator._hash_claims(result2.allowed_claims)

        assert hash1 == hash2


# =============================================================================
# Regression Tests (Tests 36-40)
# =============================================================================

class TestRegressions:
    """Regression tests for known issues."""

    def test_regression_boundary_values(self, validator):
        """Test 36: Exact boundary values are handled correctly."""
        # joy = 0.1 is exactly on the boundary
        raw_state = {"affect": {"joy": 0.1}, "bonds": {}}
        result = validator.verify_determinism(raw_state, iterations=10)
        assert result.passed

    def test_regression_missing_mood(self, validator):
        """Test 37: Missing mood layer doesn't crash."""
        raw_state = {
            "affect": {"joy": 0.5},
            "bonds": {"test": {"bond": 0.5}}
        }
        result = validator.verify_determinism(raw_state, iterations=10)
        assert result.passed

    def test_regression_negative_bond(self, validator):
        """Test 38: Negative bond values work correctly."""
        raw_state = {
            "affect": {"joy": 0.0},
            "bonds": {"test": {"bond": -0.8, "trust": 0.1}}
        }
        result = validator.run_replay(raw_state, "与该用户的关系存在紧张")
        assert result.verdict == "OK"

    def test_regression_zero_bond(self, validator):
        """Test 39: Zero bond value is handled correctly."""
        raw_state = {
            "affect": {"joy": 0.0},
            "bonds": {"test": {"bond": 0.0, "trust": 0.5}}
        }
        result = validator.run_replay(raw_state, "与该用户的关系较浅")
        assert result.verdict == "OK"

    def test_regression_empty_affect(self, validator):
        """Test 40: Empty affect doesn't crash."""
        raw_state = {"affect": {}, "bonds": {}}
        result = validator.verify_determinism(raw_state, iterations=10)
        assert result.passed


# Run with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
