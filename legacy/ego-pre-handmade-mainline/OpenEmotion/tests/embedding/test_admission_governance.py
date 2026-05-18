"""
Tests for Admission Governance (v6c).

Validates:
- Admission states
- Gate evaluation
- Decision logic
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.admission import (
    AdmissionState,
    AdmissionGateStatus,
    AdmissionThresholds,
    AdmissionMetrics,
    AdmissionGovernor,
    AdmissionDecision,
    AdmissionGateResult,
)


class TestAdmissionStates:
    """Test admission state enum."""
    
    def test_manual_only_exists(self):
        """MANUAL_ONLY state should exist."""
        assert AdmissionState.MANUAL_ONLY.value == "manual_only"
    
    def test_limited_rollout_candidate_exists(self):
        """LIMITED_ROLLOUT_CANDIDATE state should exist."""
        assert AdmissionState.LIMITED_ROLLOUT_CANDIDATE.value == "limited_rollout_candidate"
    
    def test_auto_mode_candidate_exists(self):
        """AUTO_MODE_CANDIDATE state should exist."""
        assert AdmissionState.AUTO_MODE_CANDIDATE.value == "auto_mode_candidate"
    
    def test_rollback_required_exists(self):
        """ROLLBACK_REQUIRED state should exist."""
        assert AdmissionState.ROLLBACK_REQUIRED.value == "rollback_required"


class TestAdmissionThresholds:
    """Test admission thresholds."""
    
    def test_default_thresholds(self):
        """Should have sensible defaults."""
        thresholds = AdmissionThresholds()
        assert thresholds.min_sample_size == 20
        assert thresholds.max_wrong_user_recall_count == 0
        assert thresholds.max_fallback_rate == 0.10
        assert thresholds.min_provider_health_rate == 0.95
        assert thresholds.max_p95_latency_ms == 300.0


class TestAdmissionMetrics:
    """Test admission metrics."""
    
    def test_fallback_rate_calculation(self):
        """Should calculate fallback rate correctly."""
        metrics = AdmissionMetrics(
            request_count=100,
            fallback_count=5,
        )
        assert metrics.fallback_rate == 0.05
    
    def test_fallback_rate_zero_requests(self):
        """Should return 0 when no requests."""
        metrics = AdmissionMetrics()
        assert metrics.fallback_rate == 0.0
    
    def test_provider_health_rate(self):
        """Should calculate health rate correctly."""
        metrics = AdmissionMetrics(
            health_check_success_count=95,
            health_check_total_count=100,
        )
        assert metrics.provider_health_rate == 0.95
    
    def test_p95_latency(self):
        """Should calculate p95 latency."""
        metrics = AdmissionMetrics(
            latencies=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        )
        # p95 of 10 samples is index 9
        assert metrics.p95_latency_ms == 100
    
    def test_avg_latency(self):
        """Should calculate average latency."""
        metrics = AdmissionMetrics(
            latencies=[10, 20, 30, 40, 50]
        )
        assert metrics.avg_latency_ms == 30


class TestAdmissionGovernor:
    """Test admission governor."""
    
    def test_insufficient_samples_returns_manual_only(self):
        """Insufficient samples should return MANUAL_ONLY."""
        metrics = AdmissionMetrics(
            sample_size=5,  # Less than threshold
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.MANUAL_ONLY
    
    def test_zero_samples_returns_manual_only(self):
        """Zero samples should return MANUAL_ONLY."""
        metrics = AdmissionMetrics()
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.MANUAL_ONLY
    
    def test_wrong_user_recall_returns_rollback(self):
        """Wrong user recall should return ROLLBACK_REQUIRED."""
        metrics = AdmissionMetrics(
            sample_size=100,
            wrong_user_recall_count=1,  # Above threshold (0)
            request_count=100,
            success_count=100,
            fallback_count=0,
            health_check_success_count=100,
            health_check_total_count=100,
            latencies=[50] * 100,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.ROLLBACK_REQUIRED
    
    def test_high_fallback_returns_manual_only(self):
        """High fallback rate should return MANUAL_ONLY."""
        metrics = AdmissionMetrics(
            sample_size=100,
            request_count=100,
            success_count=100,
            fallback_count=20,  # 20% > 10% threshold
            health_check_success_count=100,
            health_check_total_count=100,
            latencies=[50] * 100,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.MANUAL_ONLY
    
    def test_all_gates_pass_returns_limited_rollout(self):
        """All gates passing should return LIMITED_ROLLOUT_CANDIDATE."""
        metrics = AdmissionMetrics(
            sample_size=100,
            request_count=100,
            success_count=100,
            fallback_count=5,  # 5% < 10%
            wrong_user_recall_count=0,
            health_check_success_count=100,
            health_check_total_count=100,
            latencies=[50] * 100,
            tfidf_hit_at_1=0.4,
            ollama_hit_at_1=0.6,
            quality_gain=0.2,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.LIMITED_ROLLOUT_CANDIDATE
        assert decision.all_gates_passed is True
    
    def test_low_provider_health_returns_manual_only(self):
        """Low provider health should return MANUAL_ONLY."""
        metrics = AdmissionMetrics(
            sample_size=100,
            request_count=100,
            success_count=100,
            fallback_count=0,
            health_check_success_count=80,  # 80% < 95%
            health_check_total_count=100,
            latencies=[50] * 100,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.MANUAL_ONLY
    
    def test_high_p95_latency_returns_manual_only(self):
        """High p95 latency should return MANUAL_ONLY."""
        latencies = [50] * 95 + [400] * 5  # p95 = 400ms > 300ms
        metrics = AdmissionMetrics(
            sample_size=100,
            request_count=100,
            success_count=100,
            fallback_count=0,
            health_check_success_count=100,
            health_check_total_count=100,
            latencies=latencies,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.MANUAL_ONLY


class TestAdmissionDecision:
    """Test admission decision."""
    
    def test_to_dict(self):
        """Should serialize to dict."""
        metrics = AdmissionMetrics(
            sample_size=50,
            request_count=50,
            success_count=50,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        d = decision.to_dict()
        
        assert "state" in d
        assert "gates" in d
        assert "blockers" in d
        assert "recommendations" in d
        assert "metrics" in d
    
    def test_all_gates_passed_property(self):
        """Should correctly report all gates passed."""
        pass_gate = AdmissionGateResult(
            gate_name="test",
            status=AdmissionGateStatus.PASS,
            threshold=0,
            actual=0,
            message="ok",
        )
        fail_gate = AdmissionGateResult(
            gate_name="test2",
            status=AdmissionGateStatus.FAIL,
            threshold=0,
            actual=1,
            message="fail",
        )
        
        decision_pass = AdmissionDecision(
            state=AdmissionState.MANUAL_ONLY,
            gates=[pass_gate],
        )
        decision_fail = AdmissionDecision(
            state=AdmissionState.MANUAL_ONLY,
            gates=[pass_gate, fail_gate],
        )
        
        assert decision_pass.all_gates_passed is True
        assert decision_fail.all_gates_passed is False


class TestCapabilityOwnership:
    """Test capability ownership."""
    
    def test_admission_in_openemotion(self):
        """Admission module must be in OpenEmotion."""
        from emotiond.memory.embedding import admission
        
        # Should be under emotiond (OpenEmotion)
        assert "emotiond" in admission.__file__
