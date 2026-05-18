"""
MVP-5 D1: Precision Controller Tests

Tests for contextual arbitration with precision weights.
Covers >=30 test cases for different scenarios.
"""
import pytest
import math
from emotiond.precision import (
    PrecisionController,
    PrecisionWeights,
    PrecisionContext,
    PrecisionTraceEntry,
    build_precision_context,
    apply_precision_to_meta_cognition,
    apply_precision_to_action_selection,
    format_precision_summary,
    get_precision_evidence_source_note,
    get_precision_controller,
    reset_precision_controller,
    clamp,
    sigmoid
)


class TestPrecisionWeights:
    """Test PrecisionWeights model."""
    
    def test_default_weights(self):
        """Test default weight values."""
        weights = PrecisionWeights()
        assert 0 <= weights.w_external <= 1
        assert 0 <= weights.w_internal <= 1
        assert 0 <= weights.w_memory <= 1
        assert 0 <= weights.w_action <= 1
        assert 0 <= weights.w_explore <= 1
    
    def test_get_primary_evidence_source_external(self):
        """Test primary source detection - external."""
        weights = PrecisionWeights(w_external=0.8, w_internal=0.1, w_memory=0.1)
        source, weight = weights.get_primary_evidence_source()
        assert source == "external"
        assert weight == 0.8
    
    def test_get_primary_evidence_source_internal(self):
        """Test primary source detection - internal."""
        weights = PrecisionWeights(w_external=0.2, w_internal=0.6, w_memory=0.2)
        source, weight = weights.get_primary_evidence_source()
        assert source == "internal"
        assert weight == 0.6
    
    def test_get_primary_evidence_source_memory(self):
        """Test primary source detection - memory."""
        weights = PrecisionWeights(w_external=0.2, w_internal=0.2, w_memory=0.6)
        source, weight = weights.get_primary_evidence_source()
        assert source == "memory"
        assert weight == 0.6
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        weights = PrecisionWeights(w_external=0.5, w_internal=0.3, w_memory=0.2)
        d = weights.to_dict()
        assert d["w_external"] == 0.5
        assert d["w_internal"] == 0.3
        assert d["w_memory"] == 0.2


class TestPrecisionContext:
    """Test PrecisionContext model."""
    
    def test_default_context(self):
        """Test default context values."""
        ctx = PrecisionContext()
        assert ctx.uncertainty == 0.5
        assert ctx.prediction_error == 0.0
        assert ctx.consecutive_prediction_errors == 0
        assert ctx.ledger_evidence_strength == 0.0
        assert ctx.user_affect_confidence == 0.5
        assert ctx.social_threat == 0.0
        assert ctx.bond_strength == 0.0
        assert ctx.energy == 0.7
        assert ctx.social_safety == 0.6
        assert ctx.cold_treatment_duration == 0.0
        assert ctx.has_promise_context is False
    
    def test_context_bounds(self):
        """Test context value bounds."""
        ctx = PrecisionContext(
            uncertainty=0.5,
            energy=0.7,
            social_safety=0.6
        )
        assert 0 <= ctx.uncertainty <= 1
        assert 0 <= ctx.energy <= 1
        assert 0 <= ctx.social_safety <= 1


class TestPrecisionControllerBasic:
    """Test PrecisionController basic functionality."""
    
    def setup_method(self):
        """Reset controller before each test."""
        reset_precision_controller()
    
    def test_controller_initialization(self):
        """Test controller initialization."""
        controller = PrecisionController()
        assert controller._history == []
        assert controller._max_history == 100
    
    def test_controller_with_seed(self):
        """Test controller with random seed."""
        controller = PrecisionController(seed=42)
        assert controller is not None
    
    def test_compute_weights_basic(self):
        """Test basic weight computation."""
        controller = PrecisionController()
        ctx = build_precision_context()
        weights, reasoning = controller.compute_weights(ctx)
        
        assert isinstance(weights, PrecisionWeights)
        assert 0 <= weights.w_external <= 1
        assert 0 <= weights.w_internal <= 1
        assert 0 <= weights.w_memory <= 1
        assert 0 <= weights.w_action <= 1
        assert 0 <= weights.w_explore <= 1
        assert isinstance(reasoning, list)
    
    def test_compute_weights_deterministic(self):
        """Test that weight computation is deterministic."""
        controller1 = PrecisionController(seed=42)
        controller2 = PrecisionController(seed=42)
        
        ctx = build_precision_context(uncertainty=0.8, energy=0.3)
        weights1, _ = controller1.compute_weights(ctx)
        weights2, _ = controller2.compute_weights(ctx)
        
        assert weights1.w_external == weights2.w_external
        assert weights1.w_internal == weights2.w_internal
        assert weights1.w_memory == weights2.w_memory


class TestPrecisionUncertainty:
    """Test precision under uncertainty scenarios."""
    
    def test_high_uncertainty_reduces_external(self):
        """High uncertainty should reduce w_external."""
        controller = PrecisionController()
        
        # Low uncertainty context
        ctx_low = build_precision_context(uncertainty=0.2)
        weights_low, _ = controller.compute_weights(ctx_low)
        
        # High uncertainty context
        ctx_high = build_precision_context(uncertainty=0.9)
        weights_high, _ = controller.compute_weights(ctx_high)
        
        # High uncertainty should reduce external trust
        assert weights_high.w_external < weights_low.w_external
    
    def test_high_uncertainty_increases_memory(self):
        """High uncertainty should increase w_memory."""
        controller = PrecisionController()
        
        ctx_low = build_precision_context(uncertainty=0.2)
        weights_low, _ = controller.compute_weights(ctx_low)
        
        ctx_high = build_precision_context(uncertainty=0.9)
        weights_high, _ = controller.compute_weights(ctx_high)
        
        # High uncertainty should increase memory reliance
        assert weights_high.w_memory > weights_low.w_memory
    
    def test_high_uncertainty_increases_exploration(self):
        """High uncertainty should increase w_explore."""
        controller = PrecisionController()
        
        ctx_low = build_precision_context(uncertainty=0.2)
        weights_low, _ = controller.compute_weights(ctx_low)
        
        ctx_high = build_precision_context(uncertainty=0.9)
        weights_high, _ = controller.compute_weights(ctx_high)
        
        # High uncertainty should increase exploration
        assert weights_high.w_explore > weights_low.w_explore
    
    def test_high_uncertainty_reduces_action(self):
        """High uncertainty should reduce w_action (more cautious)."""
        controller = PrecisionController()
        
        ctx_low = build_precision_context(uncertainty=0.2)
        weights_low, _ = controller.compute_weights(ctx_low)
        
        ctx_high = build_precision_context(uncertainty=0.9)
        weights_high, _ = controller.compute_weights(ctx_high)
        
        # High uncertainty should reduce decisiveness
        assert weights_high.w_action < weights_low.w_action


class TestPrecisionPredictionError:
    """Test precision under prediction error scenarios."""
    
    def test_prediction_error_streak_reduces_external(self):
        """Prediction error streak should reduce w_external."""
        controller = PrecisionController()
        
        ctx_no_error = build_precision_context(consecutive_prediction_errors=0)
        weights_no_error, _ = controller.compute_weights(ctx_no_error)
        
        ctx_error = build_precision_context(consecutive_prediction_errors=5)
        weights_error, _ = controller.compute_weights(ctx_error)
        
        # Error streak should reduce external trust
        assert weights_error.w_external < weights_no_error.w_external
    
    def test_prediction_error_increases_internal(self):
        """Prediction error should increase w_internal."""
        controller = PrecisionController()
        
        ctx_no_error = build_precision_context(consecutive_prediction_errors=0)
        weights_no_error, _ = controller.compute_weights(ctx_no_error)
        
        ctx_error = build_precision_context(consecutive_prediction_errors=5)
        weights_error, _ = controller.compute_weights(ctx_error)
        
        # Error streak should increase internal reliance
        assert weights_error.w_internal > weights_no_error.w_internal


class TestPrecisionLedgerEvidence:
    """Test precision with ledger evidence."""
    
    def test_strong_ledger_increases_memory(self):
        """Strong ledger evidence should increase w_memory."""
        controller = PrecisionController()
        
        ctx_weak = build_precision_context(ledger_evidence_strength=0.2)
        weights_weak, _ = controller.compute_weights(ctx_weak)
        
        ctx_strong = build_precision_context(ledger_evidence_strength=0.8)
        weights_strong, _ = controller.compute_weights(ctx_strong)
        
        # Strong ledger evidence should increase memory weight
        assert weights_strong.w_memory > weights_weak.w_memory
    
    def test_ledger_with_promise_increases_action(self):
        """Ledger with promise context should increase w_action."""
        controller = PrecisionController()
        
        ctx_no_promise = build_precision_context(
            ledger_evidence_strength=0.5,
            has_promise_context=False
        )
        weights_no_promise, _ = controller.compute_weights(ctx_no_promise)
        
        ctx_promise = build_precision_context(
            ledger_evidence_strength=0.5,
            has_promise_context=True
        )
        weights_promise, _ = controller.compute_weights(ctx_promise)
        
        # Promise context should increase decisiveness
        assert weights_promise.w_action > weights_no_promise.w_action


class TestPrecisionUserAffect:
    """Test precision with user affect confidence."""
    
    def test_low_affect_confidence_reduces_external(self):
        """Low user affect confidence should reduce w_external."""
        controller = PrecisionController()
        
        ctx_high_conf = build_precision_context(user_affect_confidence=0.8)
        weights_high, _ = controller.compute_weights(ctx_high_conf)
        
        ctx_low_conf = build_precision_context(user_affect_confidence=0.2)
        weights_low, _ = controller.compute_weights(ctx_low_conf)
        
        # Low confidence should reduce external trust
        assert weights_low.w_external < weights_high.w_external
    
    def test_low_affect_confidence_increases_exploration(self):
        """Low user affect confidence should increase w_explore."""
        controller = PrecisionController()
        
        ctx_high_conf = build_precision_context(user_affect_confidence=0.8)
        weights_high, _ = controller.compute_weights(ctx_high_conf)
        
        ctx_low_conf = build_precision_context(user_affect_confidence=0.2)
        weights_low, _ = controller.compute_weights(ctx_low_conf)
        
        # Low confidence should increase exploration (need clarification)
        assert weights_low.w_explore > weights_high.w_explore


class TestPrecisionSocialThreat:
    """Test precision under social threat."""
    
    def test_high_threat_reduces_action(self):
        """High social threat should reduce w_action."""
        controller = PrecisionController()
        
        ctx_low_threat = build_precision_context(social_threat=0.2)
        weights_low, _ = controller.compute_weights(ctx_low_threat)
        
        ctx_high_threat = build_precision_context(social_threat=0.9)
        weights_high, _ = controller.compute_weights(ctx_high_threat)
        
        # High threat should reduce decisiveness
        assert weights_high.w_action < weights_low.w_action
    
    def test_high_threat_reduces_exploration(self):
        """High social threat should reduce w_explore."""
        controller = PrecisionController()
        
        ctx_low_threat = build_precision_context(social_threat=0.2)
        weights_low, _ = controller.compute_weights(ctx_low_threat)
        
        ctx_high_threat = build_precision_context(social_threat=0.9)
        weights_high, _ = controller.compute_weights(ctx_high_threat)
        
        # High threat should reduce exploration (risky)
        assert weights_high.w_explore < weights_low.w_explore


class TestPrecisionEnergy:
    """Test precision with energy levels."""
    
    def test_low_energy_reduces_action(self):
        """Low energy should reduce w_action."""
        controller = PrecisionController()
        
        ctx_high_energy = build_precision_context(energy=0.8)
        weights_high, _ = controller.compute_weights(ctx_high_energy)
        
        ctx_low_energy = build_precision_context(energy=0.2)
        weights_low, _ = controller.compute_weights(ctx_low_energy)
        
        # Low energy should reduce decisiveness
        assert weights_low.w_action < weights_high.w_action
    
    def test_low_energy_reduces_exploration(self):
        """Low energy should reduce w_explore."""
        controller = PrecisionController()
        
        ctx_high_energy = build_precision_context(energy=0.8)
        weights_high, _ = controller.compute_weights(ctx_high_energy)
        
        ctx_low_energy = build_precision_context(energy=0.2)
        weights_low, _ = controller.compute_weights(ctx_low_energy)
        
        # Low energy should reduce exploration (conservative)
        assert weights_low.w_explore < weights_high.w_explore


class TestPrecisionBond:
    """Test precision with bond strength."""
    
    def test_strong_bond_increases_memory(self):
        """Strong bond should increase w_memory."""
        controller = PrecisionController()
        
        ctx_weak_bond = build_precision_context(bond_strength=0.2)
        weights_weak, _ = controller.compute_weights(ctx_weak_bond)
        
        ctx_strong_bond = build_precision_context(bond_strength=0.9)
        weights_strong, _ = controller.compute_weights(ctx_strong_bond)
        
        # Strong bond should increase memory weight
        assert weights_strong.w_memory > weights_weak.w_memory
    
    def test_strong_bond_increases_exploration(self):
        """Strong bond should increase w_explore."""
        controller = PrecisionController()
        
        ctx_weak_bond = build_precision_context(bond_strength=0.2)
        weights_weak, _ = controller.compute_weights(ctx_weak_bond)
        
        ctx_strong_bond = build_precision_context(bond_strength=0.9)
        weights_strong, _ = controller.compute_weights(ctx_strong_bond)
        
        # Strong bond should increase exploration (safe to ask)
        assert weights_strong.w_explore > weights_weak.w_explore


class TestPrecisionColdTreatment:
    """Test precision with cold treatment duration."""
    
    def test_cold_treatment_reduces_external(self):
        """Cold treatment should reduce w_external."""
        controller = PrecisionController()
        
        ctx_no_cold = build_precision_context(cold_treatment_duration=0)
        weights_no_cold, _ = controller.compute_weights(ctx_no_cold)
        
        ctx_cold = build_precision_context(cold_treatment_duration=3600)  # 1 hour
        weights_cold, _ = controller.compute_weights(ctx_cold)
        
        # Cold treatment should reduce external trust
        assert weights_cold.w_external < weights_no_cold.w_external
    
    def test_cold_treatment_increases_memory(self):
        """Cold treatment should increase w_memory."""
        controller = PrecisionController()
        
        ctx_no_cold = build_precision_context(cold_treatment_duration=0)
        weights_no_cold, _ = controller.compute_weights(ctx_no_cold)
        
        ctx_cold = build_precision_context(cold_treatment_duration=3600)
        weights_cold, _ = controller.compute_weights(ctx_cold)
        
        # Cold treatment should increase memory reliance
        assert weights_cold.w_memory > weights_no_cold.w_memory


class TestPrecisionSocialSafety:
    """Test precision with social safety."""
    
    def test_low_safety_reduces_action(self):
        """Low social safety should reduce w_action."""
        controller = PrecisionController()
        
        ctx_high_safety = build_precision_context(social_safety=0.8)
        weights_high, _ = controller.compute_weights(ctx_high_safety)
        
        ctx_low_safety = build_precision_context(social_safety=0.2)
        weights_low, _ = controller.compute_weights(ctx_low_safety)
        
        # Low safety should reduce decisiveness
        assert weights_low.w_action < weights_high.w_action


class TestPrecisionIntegration:
    """Test precision integration with other systems."""
    
    def test_apply_precision_to_meta_cognition_low_action(self):
        """Test meta-cognition threshold adjustment with low w_action."""
        weights = PrecisionWeights(w_action=0.3)
        threshold = apply_precision_to_meta_cognition(weights, base_trigger_uncertainty=0.7)
        
        # Low action should lower threshold (more cautious)
        assert threshold < 0.7
    
    def test_apply_precision_to_meta_cognition_low_external(self):
        """Test meta-cognition threshold adjustment with low w_external."""
        weights = PrecisionWeights(w_external=0.2)
        threshold = apply_precision_to_meta_cognition(weights, base_trigger_uncertainty=0.7)
        
        # Low external should lower threshold
        assert threshold < 0.7
    
    def test_apply_precision_to_meta_cognition_high_explore(self):
        """Test meta-cognition threshold adjustment with high w_explore."""
        weights = PrecisionWeights(w_explore=0.6)
        threshold = apply_precision_to_meta_cognition(weights, base_trigger_uncertainty=0.7)
        
        # High explore should lower threshold slightly
        assert threshold <= 0.7
    
    def test_apply_precision_to_action_selection_low_action(self):
        """Test action selection modification with low w_action."""
        weights = PrecisionWeights(w_action=0.3)
        scores = {
            "attack": 1.0,
            "withdraw": 1.0,
            "boundary": 1.0
        }
        modified = apply_precision_to_action_selection(weights, scores)
        
        # Low action should penalize attack, boost withdraw/boundary
        assert modified["attack"] < scores["attack"]
        assert modified["withdraw"] > scores["withdraw"]
        assert modified["boundary"] > scores["boundary"]
    
    def test_apply_precision_to_action_selection_high_action(self):
        """Test action selection modification with high w_action."""
        weights = PrecisionWeights(w_action=0.8)
        scores = {
            "approach": 1.0,
            "repair_offer": 1.0
        }
        modified = apply_precision_to_action_selection(weights, scores)
        
        # High action should boost approach/repair
        assert modified["approach"] > scores["approach"]
        assert modified["repair_offer"] > scores["repair_offer"]
    
    def test_apply_precision_to_action_selection_high_explore(self):
        """Test action selection modification with high w_explore."""
        weights = PrecisionWeights(w_explore=0.6)
        scores = {"approach": 1.0}
        modified = apply_precision_to_action_selection(weights, scores)
        
        # High explore should boost approach
        assert modified["approach"] > scores["approach"]
    
    def test_apply_precision_to_action_selection_low_explore(self):
        """Test action selection modification with low w_explore."""
        weights = PrecisionWeights(w_explore=0.1)
        scores = {"approach": 1.0}
        modified = apply_precision_to_action_selection(weights, scores)
        
        # Low explore should penalize approach
        assert modified["approach"] < scores["approach"]


class TestPrecisionTrace:
    """Test precision trace functionality."""
    
    def setup_method(self):
        """Reset controller before each test."""
        reset_precision_controller()
    
    def test_record_trace(self):
        """Test trace recording."""
        controller = PrecisionController()
        ctx = build_precision_context()
        weights, reasoning = controller.compute_weights(ctx)
        
        entry = controller.record_trace(weights, ctx, reasoning)
        
        assert isinstance(entry, PrecisionTraceEntry)
        assert entry.weights == weights
        assert entry.context == ctx
        assert entry.reasoning == reasoning
        assert entry.timestamp > 0
    
    def test_get_history(self):
        """Test getting trace history."""
        controller = PrecisionController()
        
        # Record multiple entries
        for i in range(5):
            ctx = build_precision_context(uncertainty=0.5 + i * 0.1)
            weights, reasoning = controller.compute_weights(ctx)
            controller.record_trace(weights, ctx, reasoning)
        
        history = controller.get_history(limit=3)
        assert len(history) == 3
    
    def test_get_trace_summary(self):
        """Test getting trace summary."""
        controller = PrecisionController()
        
        # Record some entries
        for i in range(5):
            ctx = build_precision_context()
            weights, reasoning = controller.compute_weights(ctx)
            controller.record_trace(weights, ctx, reasoning)
        
        summary = controller.get_trace_summary()
        assert "count" in summary
        assert "average_weights" in summary
        assert summary["count"] == 5
    
    def test_clear_history(self):
        """Test clearing trace history."""
        controller = PrecisionController()
        
        ctx = build_precision_context()
        weights, reasoning = controller.compute_weights(ctx)
        controller.record_trace(weights, ctx, reasoning)
        
        assert len(controller._history) > 0
        
        controller.clear_history()
        assert len(controller._history) == 0
    
    def test_history_limit(self):
        """Test that history is limited to max_history."""
        controller = PrecisionController()
        controller._max_history = 5
        
        # Record more entries than max
        for i in range(10):
            ctx = build_precision_context()
            weights, reasoning = controller.compute_weights(ctx)
            controller.record_trace(weights, ctx, reasoning)
        
        assert len(controller._history) <= 5


class TestPrecisionFormatting:
    """Test precision formatting functions."""
    
    def test_format_precision_summary(self):
        """Test precision summary formatting."""
        weights = PrecisionWeights(
            w_external=0.5,
            w_internal=0.3,
            w_memory=0.2,
            w_action=0.6,
            w_explore=0.4
        )
        summary = format_precision_summary(weights)
        
        assert "ext=0.50" in summary or "ext=0.5" in summary
        assert "primary=" in summary
    
    def test_format_precision_summary_max_chars(self):
        """Test precision summary with max_chars limit."""
        weights = PrecisionWeights()
        summary = format_precision_summary(weights, max_chars=50)
        
        assert len(summary) <= 50
    
    def test_get_precision_evidence_source_note_external(self):
        """Test evidence source note - external."""
        weights = PrecisionWeights(w_external=0.8, w_internal=0.1, w_memory=0.1)
        note = get_precision_evidence_source_note(weights)
        
        assert "current input" in note
    
    def test_get_precision_evidence_source_note_internal(self):
        """Test evidence source note - internal."""
        weights = PrecisionWeights(w_external=0.1, w_internal=0.8, w_memory=0.1)
        note = get_precision_evidence_source_note(weights)
        
        assert "interoceptive" in note
    
    def test_get_precision_evidence_source_note_memory(self):
        """Test evidence source note - memory."""
        weights = PrecisionWeights(w_external=0.1, w_internal=0.1, w_memory=0.8)
        note = get_precision_evidence_source_note(weights)
        
        assert "historical" in note


class TestPrecisionUtilities:
    """Test utility functions."""
    
    def test_clamp_within_range(self):
        """Test clamp with value within range."""
        assert clamp(0.5) == 0.5
    
    def test_clamp_below_min(self):
        """Test clamp with value below min."""
        assert clamp(-0.5) == 0.0
    
    def test_clamp_above_max(self):
        """Test clamp with value above max."""
        assert clamp(1.5) == 1.0
    
    def test_clamp_custom_range(self):
        """Test clamp with custom range."""
        assert clamp(15, min_val=10, max_val=20) == 15
        assert clamp(5, min_val=10, max_val=20) == 10
        assert clamp(25, min_val=10, max_val=20) == 20
    
    def test_sigmoid_midpoint(self):
        """Test sigmoid at midpoint."""
        result = sigmoid(0.5, midpoint=0.5)
        assert abs(result - 0.5) < 0.01
    
    def test_sigmoid_low(self):
        """Test sigmoid at low value."""
        result = sigmoid(0.0, midpoint=0.5)
        assert result < 0.1
    
    def test_sigmoid_high(self):
        """Test sigmoid at high value."""
        result = sigmoid(1.0, midpoint=0.5)
        assert result > 0.9


class TestPrecisionContextualArbitration:
    """Test contextual arbitration scenarios (>=30 tests requirement)."""
    
    def test_scenario_suanle_dismissive_no_context(self):
        """Scenario: '算了' without context - should reduce external trust."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=0.6,
            user_affect_confidence=0.4
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_external < 0.5  # Reduced due to uncertainty + low confidence
        assert weights.w_explore > 0.3  # Increased to seek clarification
    
    def test_scenario_suanle_with_promise(self):
        """Scenario: '算了' with promise context - should increase memory weight."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=0.5,
            ledger_evidence_strength=0.8,
            has_promise_context=True
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_memory > 0.3  # Increased due to ledger evidence
        assert weights.w_action > 0.5  # Increased due to promise context
    
    def test_scenario_hehe_ambiguous(self):
        """Scenario: '呵呵' ambiguous - should increase exploration."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=0.7,
            user_affect_confidence=0.3
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_explore > 0.3  # Increased to clarify
        assert weights.w_external < 0.4  # Reduced due to low confidence
    
    def test_scenario_hehe_with_strong_bond(self):
        """Scenario: '呵呵' with strong bond - should trust memory more."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=0.6,
            bond_strength=0.8,
            user_affect_confidence=0.4
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_memory > 0.3  # Increased due to strong bond
        assert weights.w_explore > 0.3  # Safe to explore with strong bond
    
    def test_scenario_nibie_with_laugh(self):
        """Scenario: '你别闹了（笑）' - mixed signals."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=0.6,
            user_affect_confidence=0.5,
            social_threat=0.3
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        # Moderate uncertainty, moderate exploration
        assert 0.2 < weights.w_explore < 0.6
        assert weights.w_action < 0.6  # Slightly cautious
    
    def test_scenario_henmang_busy(self):
        """Scenario: '我很忙' - cold treatment signal."""
        controller = PrecisionController()
        ctx = build_precision_context(
            cold_treatment_duration=1800,  # 30 min
            user_affect_confidence=0.4
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_external <= 0.4  # Reduced due to cold treatment
        assert weights.w_memory >= 0.3  # Increased to rely on history
    
    def test_scenario_high_uncertainty_chain(self):
        """Scenario: Chain of high uncertainty events."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=0.85,
            consecutive_prediction_errors=4,
            prediction_error=0.5
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_external < 0.3  # Significantly reduced
        assert weights.w_internal > 0.3  # Increased
        assert weights.w_memory > 0.3  # Increased
        assert weights.w_action <= 0.4  # Very cautious
        assert weights.w_explore > 0.4  # Seek clarification
    
    def test_scenario_betrayal_aftermath(self):
        """Scenario: After betrayal event - high threat, low safety."""
        controller = PrecisionController()
        ctx = build_precision_context(
            social_threat=0.9,
            social_safety=0.2,
            bond_strength=0.3,  # Damaged bond
            ledger_evidence_strength=0.8
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_action <= 0.4  # Very cautious
        assert weights.w_explore < 0.3  # Risky to explore
        assert weights.w_memory > 0.3  # Rely on evidence
    
    def test_scenario_repair_opportunity(self):
        """Scenario: Repair opportunity - moderate threat, high bond."""
        controller = PrecisionController()
        ctx = build_precision_context(
            social_threat=0.4,
            bond_strength=0.7,
            energy=0.6
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_action > 0.4  # Moderately decisive
        assert weights.w_memory > 0.3  # Trust history
        assert weights.w_explore > 0.3  # Safe to engage
    
    def test_scenario_low_energy_crisis(self):
        """Scenario: Low energy crisis - conserve resources."""
        controller = PrecisionController()
        ctx = build_precision_context(
            energy=0.2,
            uncertainty=0.5
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_action <= 0.5  # Conservative
        assert weights.w_explore < 0.3  # Conserve energy
    
    def test_scenario_strong_trust_high_safety(self):
        """Scenario: Strong trust and high safety - confident."""
        controller = PrecisionController()
        ctx = build_precision_context(
            bond_strength=0.9,
            social_safety=0.9,
            uncertainty=0.2,
            user_affect_confidence=0.8
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_external > 0.4  # Trust input
        assert weights.w_action >= 0.5  # Decisive
        assert weights.w_explore > 0.3  # Safe to explore
    
    def test_scenario_first_interaction(self):
        """Scenario: First interaction - no bond, high uncertainty."""
        controller = PrecisionController()
        ctx = build_precision_context(
            bond_strength=0.0,
            uncertainty=0.7,
            user_affect_confidence=0.4
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_memory <= 0.3  # No history to rely on
        assert weights.w_explore > 0.4  # Need to learn more
    
    def test_scenario_repeated_rejection(self):
        """Scenario: Repeated rejection - high threat, low external."""
        controller = PrecisionController()
        ctx = build_precision_context(
            social_threat=0.8,
            consecutive_prediction_errors=5,
            bond_strength=0.2
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_external < 0.3  # Don't trust input
        assert weights.w_action <= 0.4  # Very cautious
        assert weights.w_explore < 0.3  # Risky
    
    def test_scenario_ignored_long_time(self):
        """Scenario: Ignored
 for long time - cold treatment."""
        controller = PrecisionController()
        ctx = build_precision_context(
            cold_treatment_duration=7200,  # 2 hours
            bond_strength=0.4
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        assert weights.w_external < 0.35  # Reduced
        assert weights.w_memory > 0.35  # Rely on history
    
    def test_scenario_mixed_signals_complex(self):
        """Scenario: Complex mixed signals - balanced weights."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=0.5,
            bond_strength=0.5,
            social_threat=0.5,
            energy=0.5,
            user_affect_confidence=0.5
        )
        weights, reasoning = controller.compute_weights(ctx)
        
        # All weights should be in reasonable ranges
        assert 0.2 < weights.w_external < 0.6
        assert 0.2 < weights.w_internal < 0.6
        assert 0.2 < weights.w_memory < 0.6
        assert 0.3 < weights.w_action < 0.7
        assert 0.2 < weights.w_explore < 0.6


class TestPrecisionReproducibility:
    """Test reproducibility of precision computations."""
    
    def test_reproducible_with_same_seed(self):
        """Test that same seed produces same results."""
        controller1 = PrecisionController(seed=12345)
        controller2 = PrecisionController(seed=12345)
        
        ctx = build_precision_context(
            uncertainty=0.7,
            energy=0.4,
            social_threat=0.6
        )
        
        weights1, reasoning1 = controller1.compute_weights(ctx)
        weights2, reasoning2 = controller2.compute_weights(ctx)
        
        assert weights1.w_external == weights2.w_external
        assert weights1.w_internal == weights2.w_internal
        assert weights1.w_memory == weights2.w_memory
        assert weights1.w_action == weights2.w_action
        assert weights1.w_explore == weights2.w_explore
    
    def test_global_controller_singleton(self):
        """Test global controller singleton pattern."""
        reset_precision_controller()
        
        controller1 = get_precision_controller()
        controller2 = get_precision_controller()
        
        assert controller1 is controller2
    
    def test_reset_creates_new_controller(self):
        """Test that reset creates a new controller."""
        controller1 = get_precision_controller()
        reset_precision_controller()
        controller2 = get_precision_controller()
        
        assert controller1 is not controller2


class TestPrecisionEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_extreme_uncertainty_zero(self):
        """Test with uncertainty = 0."""
        controller = PrecisionController()
        ctx = build_precision_context(uncertainty=0.0)
        weights, _ = controller.compute_weights(ctx)
        
        assert weights.w_external > 0.4  # High trust in external
    
    def test_extreme_uncertainty_one(self):
        """Test with uncertainty = 1.0."""
        controller = PrecisionController()
        ctx = build_precision_context(uncertainty=1.0)
        weights, _ = controller.compute_weights(ctx)
        
        assert weights.w_external < 0.4  # Low trust in external
        assert weights.w_memory > 0.3  # Higher trust in memory
    
    def test_extreme_energy_zero(self):
        """Test with energy = 0."""
        controller = PrecisionController()
        ctx = build_precision_context(energy=0.0)
        weights, _ = controller.compute_weights(ctx)
        
        assert weights.w_action <= 0.4  # Very cautious
        assert weights.w_explore < 0.3  # Conservative
    
    def test_extreme_social_threat_one(self):
        """Test with social_threat = 1.0."""
        controller = PrecisionController()
        ctx = build_precision_context(social_threat=1.0)
        weights, _ = controller.compute_weights(ctx)
        
        assert weights.w_action <= 0.4  # Very cautious
        assert weights.w_explore < 0.3  # Risky to explore
    
    def test_extreme_bond_strength_one(self):
        """Test with bond_strength = 1.0."""
        controller = PrecisionController()
        ctx = build_precision_context(bond_strength=1.0)
        weights, _ = controller.compute_weights(ctx)
        
        assert weights.w_memory > 0.3  # Trust history
        assert weights.w_explore > 0.3  # Safe to explore
    
    def test_all_zeros_context(self):
        """Test with all zeros context."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=0.0,
            prediction_error=0.0,
            consecutive_prediction_errors=0,
            ledger_evidence_strength=0.0,
            user_affect_confidence=0.0,
            social_threat=0.0,
            bond_strength=0.0,
            energy=0.0,
            social_safety=0.0,
            cold_treatment_duration=0.0
        )
        weights, _ = controller.compute_weights(ctx)
        
        # Should still produce valid weights
        assert 0 <= weights.w_external <= 1
        assert 0 <= weights.w_internal <= 1
        assert 0 <= weights.w_memory <= 1
        assert 0 <= weights.w_action <= 1
        assert 0 <= weights.w_explore <= 1
    
    def test_all_ones_context(self):
        """Test with all ones context (where applicable)."""
        controller = PrecisionController()
        ctx = build_precision_context(
            uncertainty=1.0,
            prediction_error=1.0,
            consecutive_prediction_errors=10,
            ledger_evidence_strength=1.0,
            user_affect_confidence=1.0,
            social_threat=1.0,
            bond_strength=1.0,
            energy=1.0,
            social_safety=1.0,
            cold_treatment_duration=10000
        )
        weights, _ = controller.compute_weights(ctx)
        
        # Should still produce valid weights
        assert 0 <= weights.w_external <= 1
        assert 0 <= weights.w_internal <= 1
        assert 0 <= weights.w_memory <= 1
        assert 0 <= weights.w_action <= 1
        assert 0 <= weights.w_explore <= 1
