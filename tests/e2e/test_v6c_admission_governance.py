"""
E2E Tests for v6c Admission Governance.

Validates:
- Real observation flow
- Decision generation
- Report output
"""

import json
import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.admission import (
    AdmissionGovernor,
    AdmissionMetrics,
    AdmissionState,
)


class TestRealObservation:
    """Test real observation flow."""
    
    def test_metrics_collection(self):
        """Should collect metrics correctly."""
        metrics = AdmissionMetrics(
            sample_size=20,
            request_count=20,
            success_count=18,
            fallback_count=2,
            latencies=[60, 65, 70, 75, 80] * 4,  # 20 samples
            health_check_success_count=18,
            health_check_total_count=20,
        )
        
        assert metrics.sample_size == 20
        assert metrics.fallback_rate == 0.10
        assert metrics.success_rate == 0.9
        assert metrics.provider_health_rate == 0.9
    
    def test_decision_with_collected_metrics(self):
        """Should make decision from collected metrics."""
        metrics = AdmissionMetrics(
            sample_size=20,
            request_count=20,
            success_count=20,
            fallback_count=1,  # 5% < 10%
            latencies=[60] * 20,
            health_check_success_count=20,
            health_check_total_count=20,
            tfidf_hit_at_1=0.4,
            ollama_hit_at_1=0.6,
            quality_gain=0.2,
        )
        
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state in [
            AdmissionState.MANUAL_ONLY,
            AdmissionState.LIMITED_ROLLOUT_CANDIDATE,
        ]
    
    def test_report_serialization(self):
        """Should serialize report to JSON."""
        metrics = AdmissionMetrics(
            sample_size=20,
            request_count=20,
            success_count=20,
            fallback_count=0,
            latencies=[60] * 20,
            health_check_success_count=20,
            health_check_total_count=20,
        )
        
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        # Should be JSON serializable
        report = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision.to_dict(),
        }
        
        json_str = json.dumps(report)
        assert json_str is not None
        
        # Should be parseable
        parsed = json.loads(json_str)
        assert "decision" in parsed
        assert "state" in parsed["decision"]


class TestAdmissionStatesScenarios:
    """Test various admission state scenarios."""
    
    def test_scenario_manual_only_insufficient_data(self):
        """Scenario: Insufficient data → MANUAL_ONLY."""
        metrics = AdmissionMetrics(sample_size=5)
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.MANUAL_ONLY
        assert any("Insufficient" in b for b in decision.blockers)
    
    def test_scenario_rollback_wrong_user(self):
        """Scenario: Wrong user recall → ROLLBACK_REQUIRED."""
        metrics = AdmissionMetrics(
            sample_size=100,
            wrong_user_recall_count=1,
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
        assert any("recall" in b.lower() for b in decision.blockers)
    
    def test_scenario_limited_rollout_all_pass(self):
        """Scenario: All gates pass → LIMITED_ROLLOUT_CANDIDATE."""
        metrics = AdmissionMetrics(
            sample_size=50,
            request_count=50,
            success_count=50,
            fallback_count=2,  # 4% < 10%
            wrong_user_recall_count=0,
            health_check_success_count=50,
            health_check_total_count=50,
            latencies=[60] * 50,
            tfidf_hit_at_1=0.4,
            ollama_hit_at_1=0.6,
            quality_gain=0.2,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        assert decision.state == AdmissionState.LIMITED_ROLLOUT_CANDIDATE
        assert decision.all_gates_passed is True


class TestAdmissionReport:
    """Test admission report generation."""
    
    def test_report_has_required_fields(self):
        """Report must have all required fields."""
        metrics = AdmissionMetrics(
            sample_size=20,
            request_count=20,
            success_count=20,
            latencies=[50] * 20,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        report = decision.to_dict()
        
        # Required top-level fields
        assert "state" in report
        assert "gates" in report
        assert "blockers" in report
        assert "recommendations" in report
        assert "metrics" in report
        
        # Required metrics fields
        m = report["metrics"]
        assert "sample_size" in m
        assert "request_count" in m
        assert "fallback_count" in m
        assert "fallback_rate" in m
        assert "p95_latency_ms" in m
        assert "provider_health_rate" in m
    
    def test_report_gates_have_required_fields(self):
        """Each gate must have required fields."""
        metrics = AdmissionMetrics(
            sample_size=20,
            request_count=20,
            success_count=20,
            latencies=[50] * 20,
        )
        governor = AdmissionGovernor(metrics=metrics)
        decision = governor.decide()
        
        for gate in decision.gates:
            g = gate.to_dict()
            assert "gate_name" in g
            assert "status" in g
            assert "threshold" in g
            assert "actual" in g
            assert "message" in g
