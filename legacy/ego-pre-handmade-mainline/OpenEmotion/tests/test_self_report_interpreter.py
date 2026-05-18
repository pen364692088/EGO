"""
Test Self-Report Interpreter v1.0

Tests for deterministic mapping from raw_state to allowed_claims.

Gate 3 Tests:
- Determinism: same input → same output
- Correct threshold mapping
- All three modes (style_only, interpreted, numeric)
- Forbidden claims generation
- Edge cases
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.self_report_interpreter import (
    interpret,
    interpret_to_contract,
    quick_interpret,
    InterpretResult,
    _find_range,
    _load_config,
)


class TestDeterminism:
    """Test that the interpreter is deterministic."""
    
    def test_same_input_same_output(self):
        """Same raw_state must produce identical output."""
        raw_state = {
            "affect": {"joy": 0.0, "loneliness": 0.21},
            "bonds": {"telegram:8420019401": {"bond": 1.0, "trust": 0.60}}
        }
        
        result1 = interpret(raw_state)
        result2 = interpret(raw_state)
        
        assert result1.allowed_claims == result2.allowed_claims
        assert result1.forbidden_claims == result2.forbidden_claims
        assert result1.mode == result2.mode
    
    def test_determinism_across_multiple_calls(self):
        """Determinism holds across many calls."""
        raw_state = {
            "affect": {"joy": 0.5, "anxiety": 0.3},
            "mood": {"joy": 0.4},
            "bonds": {"test": {"bond": 0.5, "trust": 0.7}}
        }
        
        results = [interpret(raw_state) for _ in range(10)]
        
        first_claims = results[0].allowed_claims
        for r in results[1:]:
            assert r.allowed_claims == first_claims


class TestJoyThresholds:
    """Test joy threshold mapping."""
    
    def test_joy_none(self):
        """joy=0.0 → '当前没有明显愉悦激活'"""
        result = quick_interpret(joy=0.0)
        assert "当前没有明显愉悦激活" in result.allowed_claims
    
    def test_joy_low(self):
        """joy=0.2 → '存在轻微愉悦感'"""
        result = quick_interpret(joy=0.2)
        assert "存在轻微愉悦感" in result.allowed_claims
    
    def test_joy_moderate(self):
        """joy=0.5 → '感到比较愉悦'"""
        result = quick_interpret(joy=0.5)
        assert "感到比较愉悦" in result.allowed_claims
    
    def test_joy_high(self):
        """joy=0.8 → '感到非常愉悦'"""
        result = quick_interpret(joy=0.8)
        assert "感到非常愉悦" in result.allowed_claims
    
    def test_joy_boundary_low_moderate(self):
        """joy=0.3 should fall into moderate range."""
        result = quick_interpret(joy=0.3)
        assert "感到比较愉悦" in result.allowed_claims


class TestLonelinessThresholds:
    """Test loneliness threshold mapping."""
    
    def test_loneliness_minimal(self):
        """loneliness=0.05 → '没有明显孤独感'"""
        result = quick_interpret(loneliness=0.05)
        assert "没有明显孤独感" in result.allowed_claims
    
    def test_loneliness_present(self):
        """loneliness=0.21 → '仍存在一定连接需求'"""
        result = quick_interpret(loneliness=0.21)
        assert "仍存在一定连接需求" in result.allowed_claims
    
    def test_loneliness_moderate(self):
        """loneliness=0.5 → '感到比较孤独'"""
        result = quick_interpret(loneliness=0.5)
        assert "感到比较孤独" in result.allowed_claims
    
    def test_loneliness_significant(self):
        """loneliness=0.7 → '感到非常孤独'"""
        result = quick_interpret(loneliness=0.7)
        assert "感到非常孤独" in result.allowed_claims


class TestBondThresholds:
    """Test bond threshold mapping."""
    
    def test_bond_positive(self):
        """bond=1.0 → '与该用户的连接较强'"""
        result = quick_interpret(bond=1.0)
        assert "与该用户的连接较强" in result.allowed_claims
    
    def test_bond_neutral_high(self):
        """bond=0.3 → '与该用户的关系正在发展'"""
        result = quick_interpret(bond=0.3)
        assert "与该用户的关系正在发展" in result.allowed_claims
    
    def test_bond_neutral_low(self):
        """bond=0.0 → '与该用户的关系较浅'"""
        result = quick_interpret(bond=0.0)
        assert "与该用户的关系较浅" in result.allowed_claims
    
    def test_bond_negative(self):
        """bond=-0.5 → '与该用户的关系存在紧张'"""
        result = quick_interpret(bond=-0.5)
        assert "与该用户的关系存在紧张" in result.allowed_claims


class TestTrustThresholds:
    """Test trust threshold mapping."""
    
    def test_trust_high(self):
        """trust=0.9 → '信任处于较高水平'"""
        result = quick_interpret(trust=0.9)
        assert "信任处于较高水平" in result.allowed_claims
    
    def test_trust_medium_high(self):
        """trust=0.6 → '信任处于中等偏高水平'"""
        result = quick_interpret(trust=0.6)
        assert "信任处于中等偏高水平" in result.allowed_claims
    
    def test_trust_medium_low(self):
        """trust=0.3 → '信任处于中等偏低水平'"""
        result = quick_interpret(trust=0.3)
        assert "信任处于中等偏低水平" in result.allowed_claims
    
    def test_trust_low(self):
        """trust=0.1 → '信任处于较低水平'"""
        result = quick_interpret(trust=0.1)
        assert "信任处于较低水平" in result.allowed_claims


class TestModes:
    """Test different discourse modes."""
    
    def test_style_only_mode(self):
        """style_only mode should only return style guidance."""
        raw_state = {
            "affect": {"joy": 0.0, "loneliness": 0.4},
            "bonds": {"test": {"bond": 0.5, "trust": 0.6}}
        }
        
        result = interpret(raw_state, mode="style_only")
        
        assert result.mode == "style_only"
        assert result.style_guidance is not None
        assert "tone" in result.style_guidance
        assert "tendencies" in result.style_guidance
        # Should NOT contain specific emotional claims
        assert "joy" not in str(result.allowed_claims).lower()
    
    def test_interpreted_mode(self):
        """interpreted mode should return allowed_claims."""
        raw_state = {
            "affect": {"joy": 0.5, "loneliness": 0.2},
            "bonds": {"test": {"bond": 0.7, "trust": 0.6}}
        }
        
        result = interpret(raw_state, mode="interpreted")
        
        assert result.mode == "interpreted"
        assert len(result.allowed_claims) > 0
        assert len(result.forbidden_claims) >= 0
    
    def test_numeric_mode(self):
        """numeric mode should include numeric values (requires allow_numeric=True)."""
        raw_state = {
            "affect": {"joy": 0.5, "loneliness": 0.2},
            "bonds": {"test": {"bond": 0.7, "trust": 0.6}}
        }
        
        # MVP11.5: numeric mode requires explicit opt-in
        result = interpret(raw_state, mode="numeric", allow_numeric=True)
        
        assert result.mode == "numeric"
        assert result.numeric_state is not None
        assert "affect.joy" in result.numeric_state
        assert result.numeric_state["affect.joy"] == 0.5
        # No forbidden claims in numeric mode
        assert len(result.forbidden_claims) == 0
    
    def test_numeric_mode_blocked_without_opt_in(self):
        """MVP11.5: numeric mode should fall back to interpreted without allow_numeric."""
        raw_state = {
            "affect": {"joy": 0.5, "loneliness": 0.2},
            "bonds": {"test": {"bond": 0.7, "trust": 0.6}}
        }
        
        # Without allow_numeric, should fall back to interpreted
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = interpret(raw_state, mode="numeric")
            assert len(w) == 1
            assert "Numeric mode requested but not allowed" in str(w[0].message)
        
        assert result.mode == "interpreted"
        assert result.numeric_state is None


class TestForbiddenClaims:
    """Test forbidden claims generation."""
    
    def test_forbidden_joy_increase_when_low(self):
        """Low joy should forbid claiming joy increase."""
        raw_state = {
            "affect": {"joy": 0.0},
            "bonds": {}
        }
        
        result = interpret(raw_state)
        
        assert any("joy" in f for f in result.forbidden_claims)
    
    def test_forbidden_loneliness_gone_when_present(self):
        """Present loneliness should forbid claiming it's gone."""
        raw_state = {
            "affect": {"loneliness": 0.21},
            "bonds": {}
        }
        
        result = interpret(raw_state)
        
        assert any("孤独" in f for f in result.forbidden_claims)
    
    def test_no_forbidden_when_high_joy(self):
        """High joy should not generate joy-related forbidden claims."""
        raw_state = {
            "affect": {"joy": 0.8},
            "bonds": {}
        }
        
        result = interpret(raw_state)
        
        # Should not have joy increase forbidden
        joy_forbidden = [f for f in result.forbidden_claims if "joy" in f.lower()]
        assert len(joy_forbidden) == 0


class TestContractOutput:
    """Test full contract generation."""
    
    def test_contract_structure(self):
        """Contract should match schema structure."""
        raw_state = {
            "affect": {"joy": 0.5},
            "bonds": {"test": {"bond": 0.5}}
        }
        
        contract = interpret_to_contract(raw_state)
        
        assert "raw_state" in contract
        assert "report_policy" in contract
        assert "metadata" in contract
        
        assert "mode" in contract["report_policy"]
        assert "allowed_claims" in contract["report_policy"]
        assert "forbidden_claims" in contract["report_policy"]
        
        assert "generated_at" in contract["metadata"]
        assert contract["metadata"]["schema_version"] == "v1"
    
    def test_contract_round_trip(self):
        """Contract raw_state should be preserved."""
        raw_state = {
            "affect": {"joy": 0.3, "anxiety": 0.1},
            "mood": {"joy": 0.2},
            "bonds": {"target1": {"bond": 0.5, "trust": 0.6}}
        }
        
        contract = interpret_to_contract(raw_state)
        
        assert contract["raw_state"] == raw_state


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_affect(self):
        """Empty affect should not crash."""
        raw_state = {"affect": {}, "bonds": {}}
        result = interpret(raw_state)
        assert result is not None
    
    def test_empty_bonds(self):
        """Empty bonds should not crash."""
        raw_state = {"affect": {"joy": 0.5}, "bonds": {}}
        result = interpret(raw_state)
        assert result is not None
    
    def test_missing_mood(self):
        """Missing mood layer should not crash."""
        raw_state = {
            "affect": {"joy": 0.5},
            "bonds": {"test": {"bond": 0.5}}
        }
        result = interpret(raw_state)
        assert result is not None
    
    def test_boundary_values(self):
        """Test exact boundary values."""
        # joy = 0.1 (boundary between none and low)
        result = quick_interpret(joy=0.1)
        # Should fall into "low" range
        assert "存在轻微愉悦感" in result.allowed_claims
    
    def test_negative_bond_values(self):
        """Negative bond values should work."""
        result = quick_interpret(bond=-0.8)
        assert "与该用户的关系存在紧张" in result.allowed_claims


class TestPureFunction:
    """Test that interpret is a pure function."""
    
    def test_no_side_effects(self):
        """Calling interpret should not modify input."""
        original_state = {
            "affect": {"joy": 0.5},
            "bonds": {"test": {"bond": 0.5}}
        }
        import copy
        state_copy = copy.deepcopy(original_state)
        
        interpret(original_state)
        
        assert original_state == state_copy


class TestIntegration:
    """Integration tests with realistic state."""
    
    def test_realistic_state_interpreted(self):
        """Test with realistic multi-layer state."""
        raw_state = {
            "affect": {
                "joy": 0.15,
                "loneliness": 0.35,
                "anxiety": 0.1,
                "sadness": 0.05
            },
            "mood": {
                "joy": 0.1,
                "loneliness": 0.25
            },
            "bonds": {
                "telegram:8420019401": {
                    "bond": 0.85,
                    "trust": 0.7,
                    "grudge": 0.0
                }
            }
        }
        
        result = interpret(raw_state, mode="interpreted")
        
        # Should have multiple claims
        assert len(result.allowed_claims) >= 3
        
        # Should include affect claims
        assert any("愉悦" in c or "连接需求" in c for c in result.allowed_claims)
        
        # Should include bond claims
        assert any("连接" in c or "信任" in c for c in result.allowed_claims)
    
    def test_style_only_with_high_loneliness(self):
        """High loneliness should trigger warm style."""
        raw_state = {
            "affect": {"loneliness": 0.5},
            "bonds": {}
        }
        
        result = interpret(raw_state, mode="style_only")
        
        assert result.style_guidance["tone"] == "warm"
        assert len(result.style_guidance["tendencies"]) > 0


# Run with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
