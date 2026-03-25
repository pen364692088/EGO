"""
Tests for Whitelist Governance.

v6k: Whitelist Governance + Periodic Receipts + Alerts
"""

import pytest
from pathlib import Path

from emotiond.memory.embedding.production_whitelist import (
    ProductionWhitelistRegistry,
    WhitelistStatus,
)
from emotiond.memory.embedding.whitelist_governance import (
    WhitelistGovernanceEvaluator,
    ScenarioVerdict,
    WhitelistVerdict,
    ExpansionReadiness,
    ScenarioGovernanceState,
    WhitelistGovernanceSummary,
)


class TestWhitelistGovernanceEvaluator:
    """Tests for WhitelistGovernanceEvaluator."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def governance(self, registry, tmp_path):
        return WhitelistGovernanceEvaluator(registry, storage_path=tmp_path)

    def test_evaluate_healthy_scenario(self, registry, governance):
        """evaluate_scenario returns HEALTHY for stable scenario."""
        # Add observation data to first scenario
        scenario_name = "memory_search_hard_query"
        registry.record_observation(scenario_name, True, 50, quality_signal=0.4)
        registry.record_observation(scenario_name, True, 55, quality_signal=0.4)
        registry.record_observation(scenario_name, True, 60, quality_signal=0.4)

        state = governance.evaluate_scenario(scenario_name)

        assert state.verdict == ScenarioVerdict.HEALTHY
        assert len(state.blockers) == 0

    def test_evaluate_observe_scenario(self, registry, governance):
        """evaluate_scenario returns OBSERVE for borderline metrics."""
        scenario_name = "memory_search_hard_query"

        # Add observation with slightly elevated fallback rate
        for _ in range(20):
            registry.record_observation(scenario_name, True, 50, fallback=False)
        for _ in range(2):
            registry.record_observation(scenario_name, True, 50, fallback=True)  # 9% fallback

        state = governance.evaluate_scenario(scenario_name)

        assert state.verdict == ScenarioVerdict.OBSERVE
        assert any("fallback_rate" in b for b in state.blockers)

    def test_evaluate_demote_candidate(self, registry, governance):
        """evaluate_scenario returns DEMOTE_CANDIDATE for high fallback."""
        scenario_name = "memory_search_hard_query"

        # Add observation with high fallback rate
        for _ in range(20):
            registry.record_observation(scenario_name, True, 50, fallback=False)
        for _ in range(5):
            registry.record_observation(scenario_name, True, 50, fallback=True)  # 20%

        state = governance.evaluate_scenario(scenario_name)

        assert state.verdict == ScenarioVerdict.DEMOTE_CANDIDATE
        assert any("fallback_rate" in b for b in state.blockers)

    def test_evaluate_rollback_candidate(self, registry, governance):
        """evaluate_scenario returns ROLLBACK_CANDIDATE for wrong_user_guard."""
        scenario_name = "memory_search_hard_query"

        # Add observation with wrong_user_guard
        registry.record_observation(scenario_name, True, 50, wrong_user_guard=True)

        state = governance.evaluate_scenario(scenario_name)

        assert state.verdict == ScenarioVerdict.ROLLBACK_CANDIDATE

    def test_evaluate_whitelist_all_healthy(self, registry, governance):
        """evaluate_whitelist returns STABLE when all healthy."""
        # Add healthy data to all 3 initial scenarios
        for scenario_name in ["memory_search_hard_query", "narrative_recall_ambiguous_query", "long_context_semantic_lookup"]:
            for _ in range(10):
                registry.record_observation(scenario_name, True, 50, quality_signal=0.4)

        summary = governance.evaluate_whitelist()

        assert summary.whitelist_verdict == WhitelistVerdict.STABLE
        assert summary.healthy_scenario_count == 3

    def test_evaluate_whitelist_with_demote(self, registry, governance):
        """evaluate_whitelist returns OBSERVE when demote candidate exists."""
        scenario_name = "memory_search_hard_query"

        # Add high fallback to one scenario
        for _ in range(20):
            registry.record_observation(scenario_name, True, 50, fallback=False)
        for _ in range(5):
            registry.record_observation(scenario_name, True, 50, fallback=True)

        summary = governance.evaluate_whitelist()

        assert summary.demote_candidate_count > 0
        assert summary.whitelist_verdict == WhitelistVerdict.OBSERVE

    def test_evaluate_whitelist_with_rollback(self, registry, governance):
        """evaluate_whitelist returns EXPANSION_BLOCKED when rollback exists."""
        scenario_name = "memory_search_hard_query"

        # Trigger wrong_user_guard
        registry.record_observation(scenario_name, True, 50, wrong_user_guard=True)

        summary = governance.evaluate_whitelist()

        assert summary.rollback_candidate_count > 0
        assert summary.whitelist_verdict == WhitelistVerdict.EXPANSION_BLOCKED
        assert summary.expansion_readiness == ExpansionReadiness.BLOCKED

    def test_expansion_readiness(self, registry, governance):
        """expansion_readiness is READY when all healthy."""
        # Add healthy data to all scenarios
        for scenario_name in ["memory_search_hard_query", "narrative_recall_ambiguous_query", "long_context_semantic_lookup"]:
            for _ in range(10):
                registry.record_observation(scenario_name, True, 50, quality_signal=0.4)

        summary = governance.evaluate_whitelist()

        assert summary.expansion_readiness == ExpansionReadiness.READY

    def test_generate_governance_report(self, registry, governance):
        """generate_governance_report creates full report."""
        # Add data to scenarios
        for scenario_name in ["memory_search_hard_query", "narrative_recall_ambiguous_query"]:
            for _ in range(10):
                registry.record_observation(scenario_name, True, 50, quality_signal=0.4)

        report = governance.generate_governance_report()

        assert "snapshot" in report
        assert "governance" in report
        assert "generated_at" in report
        assert report["snapshot"]["scenario_count"] == 3

    def test_save_governance_report(self, registry, governance, tmp_path):
        """save_governance_report persists to file."""
        report_path = governance.save_governance_report()

        assert report_path.exists()
        import json
        data = json.loads(report_path.read_text())
        assert "governance" in data


class TestScenarioGovernanceState:
    """Tests for ScenarioGovernanceState."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        state = ScenarioGovernanceState(
            scenario_name="test",
            request_count=100,
            fallback_rate=0.05,
            p95_latency_ms=75.0,
            wrong_user_guard_trigger_count=0,
            provider_health_rate=0.99,
            quality_gain_signal=0.4,
            verdict=ScenarioVerdict.HEALTHY,
        )

        d = state.to_dict()

        assert d["scenario_name"] == "test"
        assert d["request_count"] == 100
        assert d["verdict"] == "healthy"


class TestWhitelistGovernanceSummary:
    """Tests for WhitelistGovernanceSummary."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        summary = WhitelistGovernanceSummary(
            active_scenario_count=4,
            healthy_scenario_count=3,
            observe_scenario_count=1,
            demote_candidate_count=0,
            rollback_candidate_count=0,
            whitelist_verdict=WhitelistVerdict.STABLE,
            expansion_readiness=ExpansionReadiness.READY,
            rationale="All scenarios healthy",
        )

        d = summary.to_dict()

        assert d["active_scenario_count"] == 4
        assert d["whitelist_verdict"] == "stable"
        assert d["expansion_readiness"] == "ready"


class TestScenarioVerdict:
    """Tests for ScenarioVerdict enum."""

    def test_all_verdicts_exist(self):
        """All expected verdicts exist."""
        assert ScenarioVerdict.HEALTHY.value == "healthy"
        assert ScenarioVerdict.OBSERVE.value == "observe"
        assert ScenarioVerdict.DEMOTE_CANDIDATE.value == "demote_candidate"
        assert ScenarioVerdict.ROLLBACK_CANDIDATE.value == "rollback_candidate"


class TestWhitelistVerdict:
    """Tests for WhitelistVerdict enum."""

    def test_all_verdicts_exist(self):
        """All expected verdicts exist."""
        assert WhitelistVerdict.STABLE.value == "stable"
        assert WhitelistVerdict.OBSERVE.value == "observe"
        assert WhitelistVerdict.EXPANSION_BLOCKED.value == "expansion_blocked"
        assert WhitelistVerdict.EXPANSION_READY_CANDIDATE.value == "expansion_ready_candidate"


class TestExpansionReadiness:
    """Tests for ExpansionReadiness enum."""

    def test_all_states_exist(self):
        """All expected states exist."""
        assert ExpansionReadiness.READY.value == "ready"
        assert ExpansionReadiness.NOT_READY.value == "not_ready"
        assert ExpansionReadiness.BLOCKED.value == "blocked"
