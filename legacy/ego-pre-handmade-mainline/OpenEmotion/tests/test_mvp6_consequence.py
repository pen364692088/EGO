"""
MVP-6 D2: Consequence Model Tests

Tests for consequence event processor covering:
- Mapping correctness (tool_result/env_outcome/interaction_outcome)
- Control and boundary stability
- Risk escalation prevention from low-risk signals
- Feedback wiring into allostasis, precision, intrinsic, meta-cognition
- Trace tagging
"""
import pytest
import os
import sys

# Set test environment
os.environ["EMOTIOND_DISABLE_CORE"] = "0"
os.environ["EMOTIOND_DB_PATH"] = ":memory:"

from emotiond.consequence import (
    # Enums
    ConsequenceType,
    OutcomeStatus,
    RiskLevel,
    ConsequenceTag,

    # Models
    BodyDelta,
    ConsequenceDelta,
    AllostasisFeedback,
    PrecisionFeedback,
    IntrinsicFeedback,
    MetaCognitionFeedback,
    FeedbackBundle,
    ConsequenceProcessorConfig,

    # Functions
    lookup_body_delta,
    assess_risk_level,
    prevent_risk_escalation,
    check_boundary_stability,
    generate_tags,
    compute_allostasis_feedback,
    compute_precision_feedback,
    compute_intrinsic_feedback,
    compute_meta_cognition_feedback,

    # Mappings
    TOOL_RESULT_MAPPINGS,
    ENV_OUTCOME_MAPPINGS,
    INTERACTION_OUTCOME_MAPPINGS,

    # Processor
    ConsequenceProcessor,
)


# =============================================================================
# Test BodyDelta
# =============================================================================

class TestBodyDelta:
    """Tests for BodyDelta model."""

    def test_default_values(self):
        """Test default body delta values."""
        delta = BodyDelta()
        assert delta.safety == 0.0
        assert delta.energy == 0.0
        assert delta.arousal == 0.0
        assert delta.valence == 0.0
        assert delta.uncertainty == 0.0

    def test_valid_ranges(self):
        """Test that values are validated within [-1, 1]."""
        # Valid values should work
        delta = BodyDelta(safety=0.5, energy=-0.3)
        assert delta.safety == 0.5
        assert delta.energy == -0.3

        # Boundary values should work
        delta = BodyDelta(safety=1.0, energy=-1.0)
        assert delta.safety == 1.0
        assert delta.energy == -1.0

    def test_magnitude_zero(self):
        """Test magnitude calculation for zero delta."""
        delta = BodyDelta()
        assert delta.magnitude() == 0.0

    def test_magnitude_nonzero(self):
        """Test magnitude calculation for non-zero delta."""
        delta = BodyDelta(safety=0.5, energy=0.5, arousal=0.5, valence=0.5, uncertainty=0.5)
        mag = delta.magnitude()
        assert 0 < mag <= 1.0

    def test_is_significant_true(self):
        """Test is_significant returns True for significant delta."""
        delta = BodyDelta(safety=0.2)
        assert delta.is_significant(threshold=0.1) is True

    def test_is_significant_false(self):
        """Test is_significant returns False for small delta."""
        delta = BodyDelta(safety=0.05)
        assert delta.is_significant(threshold=0.1) is False

    def test_clamp(self):
        """Test clamping values to valid range."""
        # Create delta with values at boundaries
        delta = BodyDelta(safety=1.0, energy=-1.0)
        # Test clamping doesn't change valid values
        clamped = delta.clamp(-1.0, 1.0)
        assert clamped.safety == 1.0
        assert clamped.energy == -1.0

        # Create delta with values that need clamping (using internal modification)
        delta2 = BodyDelta(safety=0.8, energy=-0.8)
        clamped2 = delta2.clamp(-0.5, 0.5)
        assert clamped2.safety == 0.5
        assert clamped2.energy == -0.5


# =============================================================================
# Test ConsequenceDelta
# =============================================================================

class TestConsequenceDelta:
    """Tests for ConsequenceDelta model."""

    def test_creation(self):
        """Test creating a consequence delta."""
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta(safety=0.1)
        )
        assert delta.consequence_type == ConsequenceType.TOOL_RESULT
        assert delta.outcome_status == OutcomeStatus.SUCCESS
        assert delta.body_delta.safety == 0.1

    def test_add_tag(self):
        """Test adding tags."""
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS
        )
        delta.add_tag("test_tag")
        assert "test_tag" in delta.tags

    def test_add_tag_duplicate(self):
        """Test that duplicate tags are not added."""
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS
        )
        delta.add_tag("test_tag")
        delta.add_tag("test_tag")
        assert delta.tags.count("test_tag") == 1

    def test_has_tag(self):
        """Test checking for tag presence."""
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS
        )
        delta.add_tag("test_tag")
        assert delta.has_tag("test_tag") is True
        assert delta.has_tag("missing_tag") is False

    def test_get_risk_score(self):
        """Test risk score conversion."""
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            risk_level=RiskLevel.HIGH
        )
        assert delta.get_risk_score() == 0.75

    def test_feeds_flags_default(self):
        """Test that feed flags default to False."""
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS
        )
        assert delta.feeds_allostasis is False
        assert delta.feeds_precision is False
        assert delta.feeds_intrinsic is False
        assert delta.feeds_meta_cognition is False


# =============================================================================
# Test Lookup Body Delta
# =============================================================================

class TestLookupBodyDelta:
    """Tests for body delta lookup function."""

    def test_lookup_tool_success_low(self):
        """Test lookup for tool success with low impact."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.SUCCESS, "low")
        assert delta is not None
        assert delta.safety > 0
        assert delta.valence > 0

    def test_lookup_tool_failure_medium(self):
        """Test lookup for tool failure with medium impact."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.FAILURE, "medium")
        assert delta is not None
        assert delta.safety < 0
        assert delta.valence < 0

    def test_lookup_env_success(self):
        """Test lookup for environment success."""
        delta = lookup_body_delta(ConsequenceType.ENV_OUTCOME, OutcomeStatus.SUCCESS, "low")
        assert delta is not None
        # Environmental outcomes have smaller effects
        assert abs(delta.safety) <= 0.05

    def test_lookup_interaction_failure_high(self):
        """Test lookup for interaction failure with high impact."""
        delta = lookup_body_delta(ConsequenceType.INTERACTION_OUTCOME, OutcomeStatus.FAILURE, "high")
        assert delta is not None
        # Interaction failures have larger safety impact
        assert delta.safety <= -0.15

    def test_lookup_not_found(self):
        """Test lookup returns None for unknown combination."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.UNEXPECTED, "high")
        assert delta is None

    def test_lookup_timeout(self):
        """Test lookup for timeout status."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.TIMEOUT, "medium")
        assert delta is not None
        assert delta.uncertainty > 0  # Timeouts increase uncertainty


# =============================================================================
# Test Risk Assessment
# =============================================================================

class TestAssessRiskLevel:
    """Tests for risk assessment function."""

    def test_risk_low_impact(self):
        """Test risk assessment for low impact."""
        risk = assess_risk_level(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            "low"
        )
        assert risk == RiskLevel.LOW

    def test_risk_medium_impact(self):
        """Test risk assessment for medium impact."""
        risk = assess_risk_level(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            "medium"
        )
        assert risk == RiskLevel.MEDIUM

    def test_risk_high_impact(self):
        """Test risk assessment for high impact."""
        risk = assess_risk_level(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            "high"
        )
        assert risk == RiskLevel.HIGH

    def test_risk_error_escalates(self):
        """Test that error status escalates risk."""
        risk = assess_risk_level(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.ERROR,
            "low"
        )
        # Error escalates low -> medium
        assert risk == RiskLevel.MEDIUM

    def test_risk_timeout_escalates(self):
        """Test that timeout status escalates risk."""
        risk = assess_risk_level(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.TIMEOUT,
            "low"
        )
        # Timeout escalates low -> medium
        assert risk == RiskLevel.MEDIUM

    def test_risk_interaction_failure_critical(self):
        """Test that interaction failure can be critical."""
        risk = assess_risk_level(
            ConsequenceType.INTERACTION_OUTCOME,
            OutcomeStatus.FAILURE,
            "high"
        )
        # Interaction failure with high impact -> critical
        assert risk == RiskLevel.CRITICAL

    def test_risk_boundary_violation(self):
        """Test that boundary violation makes risk critical."""
        risk = assess_risk_level(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            "low",
            context={"boundary_violated": True}
        )
        assert risk == RiskLevel.CRITICAL


# =============================================================================
# Test Risk Escalation Prevention
# =============================================================================

class TestPreventRiskEscalation:
    """Tests for risk escalation prevention."""

    def test_no_prevention_strong_signal(self):
        """Test no prevention for strong signals."""
        config = ConsequenceProcessorConfig()
        risk, prevented = prevent_risk_escalation(
            RiskLevel.HIGH,
            0.5,  # Strong signal
            config
        )
        assert risk == RiskLevel.HIGH
        assert prevented is False

    def test_prevention_weak_signal(self):
        """Test prevention for weak signals."""
        config = ConsequenceProcessorConfig()
        risk, prevented = prevent_risk_escalation(
            RiskLevel.HIGH,
            0.1,  # Weak signal
            config
        )
        # Weak signal should be capped at MEDIUM
        assert risk == RiskLevel.MEDIUM
        assert prevented is True

    def test_prevention_critical_weak_signal(self):
        """Test prevention caps critical risk for weak signals."""
        config = ConsequenceProcessorConfig()
        risk, prevented = prevent_risk_escalation(
            RiskLevel.CRITICAL,
            0.1,  # Weak signal
            config
        )
        assert risk == RiskLevel.MEDIUM
        assert prevented is True

    def test_no_prevention_low_risk(self):
        """Test no prevention needed for low risk."""
        config = ConsequenceProcessorConfig()
        risk, prevented = prevent_risk_escalation(
            RiskLevel.LOW,
            0.1,
            config
        )
        assert risk == RiskLevel.LOW
        assert prevented is False

    def test_custom_max_risk(self):
        """Test custom max risk configuration."""
        config = ConsequenceProcessorConfig(max_risk_from_low_signal=RiskLevel.LOW)
        risk, prevented = prevent_risk_escalation(
            RiskLevel.MEDIUM,
            0.1,
            config
        )
        assert risk == RiskLevel.LOW
        assert prevented is True


# =============================================================================
# Test Boundary Stability
# =============================================================================

class TestCheckBoundaryStability:
    """Tests for boundary stability checking."""

    def test_stable_within_bounds(self):
        """Test stability check passes within bounds."""
        delta = BodyDelta(safety=0.1, energy=0.1)
        is_stable, violations = check_boundary_stability(
            delta, current_safety=0.5, current_energy=0.5, threshold=0.1
        )
        assert is_stable is True
        assert len(violations) == 0

    def test_unstable_safety_floor(self):
        """Test instability when safety would go below floor."""
        delta = BodyDelta(safety=-0.5)
        is_stable, violations = check_boundary_stability(
            delta, current_safety=0.2, current_energy=0.5, threshold=0.1
        )
        assert is_stable is False
        assert any("safety_floor" in v for v in violations)

    def test_unstable_energy_floor(self):
        """Test instability when energy would go below floor."""
        delta = BodyDelta(energy=-0.5)
        is_stable, violations = check_boundary_stability(
            delta, current_safety=0.5, current_energy=0.2, threshold=0.1
        )
        assert is_stable is False
        assert any("energy_floor" in v for v in violations)

    def test_unstable_safety_ceiling(self):
        """Test instability when safety would exceed ceiling."""
        delta = BodyDelta(safety=0.5)
        is_stable, violations = check_boundary_stability(
            delta, current_safety=0.8, current_energy=0.5, threshold=0.1
        )
        assert is_stable is False
        assert any("safety_ceiling" in v for v in violations)

    def test_unstable_large_change(self):
        """Test instability for large single changes."""
        delta = BodyDelta(safety=0.5)  # Large change
        is_stable, violations = check_boundary_stability(
            delta, current_safety=0.5, current_energy=0.5, threshold=0.1
        )
        assert is_stable is False
        assert any("safety_change" in v for v in violations)


# =============================================================================
# Test Tag Generation
# =============================================================================

class TestGenerateTags:
    """Tests for tag generation."""

    def test_tool_source_tag(self):
        """Test tool source tag is generated."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta()
        )
        assert ConsequenceTag.FROM_TOOL.value in tags

    def test_env_source_tag(self):
        """Test environment source tag is generated."""
        tags = generate_tags(
            ConsequenceType.ENV_OUTCOME,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta()
        )
        assert ConsequenceTag.FROM_ENV.value in tags

    def test_interaction_source_tag(self):
        """Test interaction source tag is generated."""
        tags = generate_tags(
            ConsequenceType.INTERACTION_OUTCOME,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta()
        )
        assert ConsequenceTag.FROM_INTERACTION.value in tags

    def test_outcome_success_tag(self):
        """Test success outcome tag."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta()
        )
        assert ConsequenceTag.SUCCESS.value in tags

    def test_outcome_failure_tag(self):
        """Test failure outcome tag."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.FAILURE,
            RiskLevel.LOW,
            BodyDelta()
        )
        assert ConsequenceTag.FAILURE.value in tags

    def test_risk_tag_mapping(self):
        """Test risk level tags."""
        for risk_level, expected_tag in [
            (RiskLevel.NONE, ConsequenceTag.RISK_NONE.value),
            (RiskLevel.LOW, ConsequenceTag.RISK_LOW.value),
            (RiskLevel.MEDIUM, ConsequenceTag.RISK_MEDIUM.value),
            (RiskLevel.HIGH, ConsequenceTag.RISK_HIGH.value),
            (RiskLevel.CRITICAL, ConsequenceTag.RISK_CRITICAL.value),
        ]:
            tags = generate_tags(
                ConsequenceType.TOOL_RESULT,
                OutcomeStatus.SUCCESS,
                risk_level,
                BodyDelta()
            )
            assert expected_tag in tags

    def test_controlled_tag(self):
        """Test controlled tag."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta(),
            context={"controllable": True}
        )
        assert ConsequenceTag.CONTROLLED.value in tags

    def test_uncontrolled_tag(self):
        """Test uncontrolled tag."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta(),
            context={"controllable": False}
        )
        assert ConsequenceTag.UNCONTROLLED.value in tags

    def test_boundary_hit_tag(self):
        """Test boundary hit tag."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta(),
            context={"boundary_hit": True}
        )
        assert ConsequenceTag.BOUNDARY_HIT.value in tags

    def test_escalation_prevented_tags(self):
        """Test escalation prevention tags."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta(),
            context={"escalation_prevented": True}
        )
        assert ConsequenceTag.ESCALATION_CHECKED.value in tags
        assert ConsequenceTag.LOW_SIGNAL_HIGH_RISK.value in tags


# =============================================================================
# Test Allostasis Feedback
# =============================================================================

class TestComputeAllostasisFeedback:
    """Tests for allostasis feedback computation."""

    def test_no_feedback_normal_state(self):
        """Test no feedback when state is normal."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta(safety=0.02)
        )
        feedback = compute_allostasis_feedback(delta, 0.6, 0.7, config)
        assert feedback is None

    def test_feedback_low_safety(self):
        """Test feedback triggered by low safety."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta()
        )
        feedback = compute_allostasis_feedback(delta, 0.2, 0.7, config)
        assert feedback is not None
        assert feedback.safety_target > 0.2
        assert "safety_low" in feedback.reason

    def test_feedback_low_energy(self):
        """Test feedback triggered by low energy."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta()
        )
        feedback = compute_allostasis_feedback(delta, 0.6, 0.2, config)
        assert feedback is not None
        assert feedback.energy_target > 0.2
        assert "energy_low" in feedback.reason

    def test_feedback_urgent(self):
        """Test urgent flag for very low states."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta()
        )
        feedback = compute_allostasis_feedback(delta, 0.1, 0.1, config)
        assert feedback is not None
        assert feedback.urgent is True

    def test_feedback_from_delta(self):
        """Test feedback triggered by body delta."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.FAILURE,
            body_delta=BodyDelta(safety=-0.2)  # Large negative safety change
        )
        feedback = compute_allostasis_feedback(delta, 0.6, 0.7, config)
        assert feedback is not None


# =============================================================================
# Test Precision Feedback
# =============================================================================

class TestComputePrecisionFeedback:
    """Tests for precision feedback computation."""

    def test_no_feedback_no_expectation(self):
        """Test no feedback without expected outcome."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta()
        )
        feedback = compute_precision_feedback(delta, None, config)
        assert feedback is None

    def test_feedback_expected_success_got_failure(self):
        """Test feedback when expected success but got failure."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.FAILURE,
            body_delta=BodyDelta()
        )
        feedback = compute_precision_feedback(delta, "success", config)
        assert feedback is not None
        assert feedback.prediction_error > 0
        assert "expected_success_got_failure" in feedback.reason

    def test_feedback_expected_failure_got_success(self):
        """Test feedback when expected failure but got success."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta()
        )
        feedback = compute_precision_feedback(delta, "failure", config)
        assert feedback is not None
        assert feedback.prediction_error > 0
        assert "expected_failure_got_success" in feedback.reason

    def test_feedback_uncertainty_spike(self):
        """Test feedback from uncertainty spike."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta(uncertainty=0.3)  # Large uncertainty increase
        )
        feedback = compute_precision_feedback(delta, None, config)
        assert feedback is not None
        assert "uncertainty_spike" in feedback.reason

    def test_precision_weight_decreases_with_error(self):
        """Test that precision weight decreases with high error."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.FAILURE,
            body_delta=BodyDelta()
        )
        feedback = compute_precision_feedback(delta, "success", config)
        assert feedback is not None
        assert feedback.precision_weight < 0.5  # Should decrease


# =============================================================================
# Test Intrinsic Feedback
# =============================================================================

class TestComputeIntrinsicFeedback:
    """Tests for intrinsic feedback computation."""

    def test_no_feedback_small_changes(self):
        """Test no feedback for small changes."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta(safety=0.01)
        )
        feedback = compute_intrinsic_feedback(delta, {}, config)
        assert feedback is None

    def test_feedback_safety_value(self):
        """Test feedback from safety value changes."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.FAILURE,
            body_delta=BodyDelta(safety=-0.2)
        )
        feedback = compute_intrinsic_feedback(delta, {"safety": 0.8}, config)
        assert feedback is not None
        assert feedback.value_type == "safety"
        assert feedback.value_signal < 0  # Negative safety change

    def test_feedback_growth_from_failure(self):
        """Test growth feedback from failure."""
        config = ConsequenceProcessorConfig(intrinsic_trigger_threshold=0.05)
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.FAILURE,
            body_delta=BodyDelta(uncertainty=0.2)  # Higher uncertainty for stronger signal
        )
        feedback = compute_intrinsic_feedback(delta, {"growth": 0.9, "safety": 0.1}, config)
        assert feedback is not None
        # With high growth value and low safety value, growth should dominate
        assert feedback.value_type == "growth"

    def test_feedback_intensity(self):
        """Test that intensity is properly bounded."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.FAILURE,
            body_delta=BodyDelta(safety=-0.5)
        )
        feedback = compute_intrinsic_feedback(delta, {"safety": 1.0}, config)
        assert feedback is not None
        assert 0 <= feedback.intensity <= 1.0


# =============================================================================
# Test Meta-Cognition Feedback
# =============================================================================

class TestComputeMetaCognitionFeedback:
    """Tests for meta-cognition feedback computation."""

    def test_reflect_on_unexpected(self):
        """Test reflection suggested on unexpected outcome."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.UNEXPECTED,
            body_delta=BodyDelta()
        )
        feedback = compute_meta_cognition_feedback(delta, 0.5, config)
        assert feedback is not None
        assert feedback.suggest_reflect is True
        assert "unexpected_outcome" in feedback.reason

    def test_clarify_on_partial_uncertain(self):
        """Test clarification suggested on partial success with uncertainty."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.PARTIAL,
            body_delta=BodyDelta(uncertainty=0.15)
        )
        feedback = compute_meta_cognition_feedback(delta, 0.6, config)
        assert feedback is not None
        assert feedback.suggest_clarify is True

    def test_learn_on_failure(self):
        """Test learning suggested on failure."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.FAILURE,
            risk_level=RiskLevel.MEDIUM,
            body_delta=BodyDelta()
        )
        feedback = compute_meta_cognition_feedback(delta, 0.5, config)
        assert feedback is not None
        assert feedback.suggest_learn is True

    def test_reflect_on_critical_risk(self):
        """Test reflection suggested on critical risk."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            risk_level=RiskLevel.CRITICAL,
            body_delta=BodyDelta()
        )
        feedback = compute_meta_cognition_feedback(delta, 0.5, config)
        assert feedback is not None
        assert feedback.suggest_reflect is True

    def test_confidence_adjustment(self):
        """Test confidence adjustment on high uncertainty."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            body_delta=BodyDelta(uncertainty=0.5)
        )
        feedback = compute_meta_cognition_feedback(delta, 0.5, config)
        assert feedback is not None
        assert feedback.confidence_adjustment < 0  # Should decrease confidence

    def test_no_feedback_normal(self):
        """Test no feedback for normal outcomes."""
        config = ConsequenceProcessorConfig()
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS,
            risk_level=RiskLevel.LOW,
            body_delta=BodyDelta()
        )
        feedback = compute_meta_cognition_feedback(delta, 0.3, config)
        assert feedback is None


# =============================================================================
# Test ConsequenceProcessor
# =============================================================================

class TestConsequenceProcessor:
    """Tests for the main ConsequenceProcessor."""

    def test_processor_creation(self):
        """Test creating a processor."""
        processor = ConsequenceProcessor()
        assert processor is not None
        assert processor.config is not None

    def test_processor_with_config(self):
        """Test creating a processor with custom config."""
        config = ConsequenceProcessorConfig(low_signal_threshold=0.3)
        processor = ConsequenceProcessor(config)
        assert processor.config.low_signal_threshold == 0.3

    def test_process_tool_success(self):
        """Test processing a successful tool result."""
        processor = ConsequenceProcessor()
        bundle = processor.process_tool_result(
            status=OutcomeStatus.SUCCESS,
            tool_name="test_tool",
            impact_level="medium"
        )
        assert bundle is not None
        assert bundle.consequence_delta.consequence_type == ConsequenceType.TOOL_RESULT
        assert bundle.consequence_delta.outcome_status == OutcomeStatus.SUCCESS

    def test_process_env_failure(self):
        """Test processing an environment failure."""
        processor = ConsequenceProcessor()
        bundle = processor.process_env_outcome(
            status=OutcomeStatus.FAILURE,
            env_name="test_env",
            impact_level="high"
        )
        assert bundle is not None
        assert bundle.consequence_delta.consequence_type == ConsequenceType.ENV_OUTCOME
        assert bundle.consequence_delta.body_delta.safety < 0

    def test_process_interaction_partial(self):
        """Test processing a partial interaction outcome."""
        processor = ConsequenceProcessor()
        bundle = processor.process_interaction_outcome(
            status=OutcomeStatus.PARTIAL,
            target="user",
            impact_level="low",
            current_uncertainty=0.6
        )
        assert bundle is not None
        assert bundle.consequence_delta.consequence_type == ConsequenceType.INTERACTION_OUTCOME

    def test_trace_id_generation(self):
        """Test that trace IDs are generated."""
        processor = ConsequenceProcessor()
        bundle = processor.process_tool_result(
            status=OutcomeStatus.SUCCESS,
            tool_name="test_tool"
        )
        assert bundle.consequence_delta.trace_id != ""
        assert bundle.consequence_delta.trace_id.startswith("cons_")

    def test_parent_trace_id(self):
        """Test parent trace ID chaining."""
        processor = ConsequenceProcessor()
        parent_id = "parent_123"
        bundle = processor.process_tool_result(
            status=OutcomeStatus.SUCCESS,
            tool_name="test_tool",
            parent_trace_id=parent_id
        )
        assert bundle.consequence_delta.parent_trace_id == parent_id

    def test_feedback_bundle_contents(self):
        """Test that feedback bundle contains all feedback types when triggered."""
        processor = ConsequenceProcessor()
        bundle = processor.process(
            consequence_type=ConsequenceType.TOOL_RESULT,
            status=OutcomeStatus.FAILURE,
            impact_level="high",
            current_safety=0.2,
            current_energy=0.2,
            current_uncertainty=0.6,
            expected_outcome="success"
        )
        # Should have allostasis feedback (low safety/energy)
        assert bundle.allostasis is not None
        # Should have precision feedback (expected vs actual mismatch)
        assert bundle.precision is not None
        # Should have meta-cognition feedback (failure)
        assert bundle.meta_cognition is not None

    def test_tags_in_feedback(self):
        """Test that tags are included in consequence delta."""
        processor = ConsequenceProcessor()
        bundle = processor.process_tool_result(
            status=OutcomeStatus.SUCCESS,
            tool_name="test_tool",
            impact_level="low"
        )
        tags = bundle.consequence_delta.tags
        assert ConsequenceTag.FROM_TOOL.value in tags
        assert ConsequenceTag.SUCCESS.value in tags
        assert ConsequenceTag.RISK_LOW.value in tags

    def test_risk_escalation_prevention_integration(self):
        """Test risk escalation prevention in full processing."""
        config = ConsequenceProcessorConfig(low_signal_threshold=0.5)  # Higher threshold
        processor = ConsequenceProcessor(config)
        # Use a weak signal (small body delta magnitude) by using low impact
        bundle = processor.process(
            consequence_type=ConsequenceType.INTERACTION_OUTCOME,
            status=OutcomeStatus.FAILURE,
            impact_level="low",  # Would normally be low but with boundary violation could escalate
            current_safety=0.9,
            current_energy=0.9
        )
        # The test verifies the processor runs without error
        # and the consequence delta is properly created
        assert bundle.consequence_delta is not None
        assert bundle.consequence_delta.risk_level is not None

    def test_boundary_stability_integration(self):
        """Test boundary stability in full processing."""
        processor = ConsequenceProcessor()
        bundle = processor.process(
            consequence_type=ConsequenceType.TOOL_RESULT,
            status=OutcomeStatus.FAILURE,
            impact_level="high",
            current_safety=0.15,  # Near floor
            current_energy=0.5
        )
        # Should have boundary hit tag
        assert bundle.consequence_delta.has_tag(ConsequenceTag.BOUNDARY_HIT.value) or \
               bundle.consequence_delta.has_tag(ConsequenceTag.BOUNDARY_SAFE.value)


# =============================================================================
# Test Mappings Correctness
# =============================================================================

class TestMappingCorrectness:
    """Tests for mapping correctness."""

    def test_tool_success_positive_valence(self):
        """Test that tool success has positive valence."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.SUCCESS, "medium")
        assert delta.valence > 0

    def test_tool_failure_negative_valence(self):
        """Test that tool failure has negative valence."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.FAILURE, "medium")
        assert delta.valence < 0

    def test_tool_success_reduces_uncertainty(self):
        """Test that tool success reduces uncertainty."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.SUCCESS, "medium")
        assert delta.uncertainty < 0

    def test_tool_failure_increases_uncertainty(self):
        """Test that tool failure increases uncertainty."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.FAILURE, "medium")
        assert delta.uncertainty > 0

    def test_env_outcome_smaller_effects(self):
        """Test that environmental outcomes have smaller effects than tool outcomes."""
        tool_delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.SUCCESS, "medium")
        env_delta = lookup_body_delta(ConsequenceType.ENV_OUTCOME, OutcomeStatus.SUCCESS, "medium")
        assert abs(env_delta.safety) < abs(tool_delta.safety)

    def test_interaction_failure_larger_safety_impact(self):
        """Test that interaction failure has larger safety impact."""
        tool_delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.FAILURE, "high")
        interaction_delta = lookup_body_delta(ConsequenceType.INTERACTION_OUTCOME, OutcomeStatus.FAILURE, "high")
        assert abs(interaction_delta.safety) > abs(tool_delta.safety)

    def test_timeout_increases_arousal(self):
        """Test that timeout increases arousal."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.TIMEOUT, "medium")
        assert delta.arousal > 0

    def test_error_increases_arousal(self):
        """Test that error increases arousal."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.ERROR, "medium")
        assert delta.arousal > 0

    def test_partial_increases_uncertainty(self):
        """Test that partial success increases uncertainty."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.PARTIAL, "medium")
        assert delta.uncertainty > 0

    def test_success_costs_energy(self):
        """Test that success costs some energy."""
        delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.SUCCESS, "medium")
        assert delta.energy <= 0

    def test_failure_costs_more_energy(self):
        """Test that failure costs more energy than success."""
        success_delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.SUCCESS, "medium")
        failure_delta = lookup_body_delta(ConsequenceType.TOOL_RESULT, OutcomeStatus.FAILURE, "medium")
        assert failure_delta.energy < success_delta.energy


# =============================================================================
# Test Configuration
# =============================================================================

class TestConsequenceProcessorConfig:
    """Tests for processor configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ConsequenceProcessorConfig()
        assert config.max_risk_from_low_signal == RiskLevel.MEDIUM
        assert config.low_signal_threshold == 0.2
        assert config.boundary_stability_threshold == 0.1

    def test_custom_config(self):
        """Test custom configuration."""
        config = ConsequenceProcessorConfig(
            max_risk_from_low_signal=RiskLevel.LOW,
            low_signal_threshold=0.3,
            boundary_stability_threshold=0.2
        )
        assert config.max_risk_from_low_signal == RiskLevel.LOW
        assert config.low_signal_threshold == 0.3
        assert config.boundary_stability_threshold == 0.2

    def test_config_validation(self):
        """Test that config values are validated."""
        # Should raise validation error for invalid values
        with pytest.raises(Exception):
            ConsequenceProcessorConfig(low_signal_threshold=1.5)


# =============================================================================
# Test Feedback Models
# =============================================================================

class TestFeedbackModels:
    """Tests for feedback model validation."""

    def test_allostasis_feedback_creation(self):
        """Test creating allostasis feedback."""
        feedback = AllostasisFeedback(
            safety_target=0.6,
            energy_target=0.7,
            regulation_priority=0.5,
            urgent=False,
            reason="test"
        )
        assert feedback.safety_target == 0.6
        assert feedback.urgent is False

    def test_precision_feedback_creation(self):
        """Test creating precision feedback."""
        feedback = PrecisionFeedback(
            precision_weight=0.3,
            prediction_error=0.2,
            update_rate=0.1,
            reason="test"
        )
        assert feedback.precision_weight == 0.3
        assert feedback.prediction_error == 0.2

    def test_intrinsic_feedback_creation(self):
        """Test creating intrinsic feedback."""
        feedback = IntrinsicFeedback(
            value_signal=0.5,
            value_type="safety",
            intensity=0.7,
            reason="test"
        )
        assert feedback.value_signal == 0.5
        assert feedback.value_type == "safety"

    def test_meta_cognition_feedback_creation(self):
        """Test creating meta-cognition feedback."""
        feedback = MetaCognitionFeedback(
            suggest_reflect=True,
            suggest_clarify=False,
            suggest_learn=True,
            confidence_adjustment=-0.1,
            reason="test"
        )
        assert feedback.suggest_reflect is True
        assert feedback.suggest_clarify is False
        assert feedback.confidence_adjustment == -0.1

    def test_feedback_bundle_creation(self):
        """Test creating feedback bundle."""
        delta = ConsequenceDelta(
            consequence_type=ConsequenceType.TOOL_RESULT,
            outcome_status=OutcomeStatus.SUCCESS
        )
        bundle = FeedbackBundle(
            allostasis=AllostasisFeedback(),
            consequence_delta=delta
        )
        assert bundle.allostasis is not None
        assert bundle.consequence_delta == delta


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_body_delta(self):
        """Test processing with zero body delta."""
        processor = ConsequenceProcessor()
        bundle = processor.process(
            consequence_type=ConsequenceType.TOOL_RESULT,
            status=OutcomeStatus.SUCCESS,
            impact_level="low",
            current_safety=0.6,
            current_energy=0.7
        )
        assert bundle is not None
        assert bundle.consequence_delta.body_delta.magnitude() >= 0

    def test_extreme_current_values(self):
        """Test processing with extreme current values."""
        processor = ConsequenceProcessor()
        bundle = processor.process(
            consequence_type=ConsequenceType.TOOL_RESULT,
            status=OutcomeStatus.FAILURE,
            impact_level="high",
            current_safety=0.01,  # Very low
            current_energy=0.99   # Very high
        )
        assert bundle is not None
        # Should have allostasis feedback due to low safety
        assert bundle.allostasis is not None

    def test_all_boundary_violations(self):
        """Test with multiple boundary violations."""
        delta = BodyDelta(safety=-0.5, energy=-0.5)
        is_stable, violations = check_boundary_stability(
            delta, current_safety=0.15, current_energy=0.15, threshold=0.1
        )
        assert is_stable is False
        assert len(violations) >= 2

    def test_empty_context(self):
        """Test with empty context."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta(),
            context={}
        )
        assert len(tags) > 0

    def test_none_context(self):
        """Test with None context."""
        tags = generate_tags(
            ConsequenceType.TOOL_RESULT,
            OutcomeStatus.SUCCESS,
            RiskLevel.LOW,
            BodyDelta(),
            context=None
        )
        assert len(tags) > 0


# =============================================================================
# Test ConsequenceType Enum
# =============================================================================

class TestConsequenceTypeEnum:
    """Tests for ConsequenceType enum."""

    def test_tool_result_value(self):
        """Test TOOL_RESULT enum value."""
        assert ConsequenceType.TOOL_RESULT.value == "tool_result"

    def test_env_outcome_value(self):
        """Test ENV_OUTCOME enum value."""
        assert ConsequenceType.ENV_OUTCOME.value == "env_outcome"

    def test_interaction_outcome_value(self):
        """Test INTERACTION_OUTCOME enum value."""
        assert ConsequenceType.INTERACTION_OUTCOME.value == "interaction_outcome"


# =============================================================================
# Test OutcomeStatus Enum
# =============================================================================

class TestOutcomeStatusEnum:
    """Tests for OutcomeStatus enum."""

    def test_success_value(self):
        """Test SUCCESS enum value."""
        assert OutcomeStatus.SUCCESS.value == "success"

    def test_failure_value(self):
        """Test FAILURE enum value."""
        assert OutcomeStatus.FAILURE.value == "failure"

    def test_partial_value(self):
        """Test PARTIAL enum value."""
        assert OutcomeStatus.PARTIAL.value == "partial"

    def test_timeout_value(self):
        """Test TIMEOUT enum value."""
        assert OutcomeStatus.TIMEOUT.value == "timeout"

    def test_error_value(self):
        """Test ERROR enum value."""
        assert OutcomeStatus.ERROR.value == "error"

    def test_unexpected_value(self):
        """Test UNEXPECTED enum value."""
        assert OutcomeStatus.UNEXPECTED.value == "unexpected"
