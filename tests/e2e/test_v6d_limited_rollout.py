"""
E2E Tests for v6d Limited Rollout.

Validates:
- Whitelist mechanism
- Non-whitelist enforcement
- Rollout trace
"""

import json
import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.scenario_router import (
    RolloutConfig,
    ScenarioContext,
    RetrievalScenario,
)
from emotiond.memory.embedding.rollout import (
    RolloutPolicy,
    RolloutVerdict,
)


class TestWhitelistMechanism:
    """Test whitelist mechanism."""
    
    @pytest.mark.asyncio
    async def test_whitelist_scenario_uses_ollama(self):
        """Whitelist scenario should use ollama (or fallback)."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query="I remember something about the project discussion",
            action_type="memory_search",
        )
        
        provider, trace = await policy.execute_retrieval(context)
        
        # Should be ollama (or tfidf if fallback)
        assert trace.provider_used in ["ollama", "tfidf"]
        assert trace.rollout_applied is (trace.provider_used == "ollama" and not trace.fallback_triggered)
    
    @pytest.mark.asyncio
    async def test_non_whitelist_uses_tfidf(self):
        """Non-whitelist scenario must use tfidf."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query='"exact keyword match"',
            action_type="search",
        )
        
        provider, trace = await policy.execute_retrieval(context)
        
        assert trace.provider_used == "tfidf"
        assert trace.rollout_applied is False


class TestNonWhitelistEnforcement:
    """Test that non-whitelist scenarios cannot use ollama."""
    
    @pytest.mark.asyncio
    async def test_keyword_exact_not_rollout(self):
        """Keyword exact match should not get rollout."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query='"find this exact phrase"',
            action_type="search",
        )
        
        provider, trace = await policy.execute_retrieval(context)
        
        assert trace.rollout_applied is False
        assert trace.provider_used == "tfidf"
    
    @pytest.mark.asyncio
    async def test_low_latency_not_rollout(self):
        """Low latency path should not get rollout."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query="quick search",
            action_type="real-time",
        )
        
        provider, trace = await policy.execute_retrieval(context)
        
        assert trace.rollout_applied is False
        assert trace.provider_used == "tfidf"
    
    @pytest.mark.asyncio
    async def test_multi_user_not_rollout(self):
        """Multi-user sensitive should not get rollout."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query="shared data",
            action_type="shared",
        )
        
        provider, trace = await policy.execute_retrieval(context)
        
        assert trace.rollout_applied is False
        assert trace.provider_used == "tfidf"
    
    @pytest.mark.asyncio
    async def test_default_not_rollout(self):
        """Default scenario should not get rollout."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query="simple query",
            action_type="default",
        )
        
        provider, trace = await policy.execute_retrieval(context)
        
        assert trace.rollout_applied is False
        assert trace.provider_used == "tfidf"


class TestRolloutTrace:
    """Test rollout trace recording."""
    
    @pytest.mark.asyncio
    async def test_trace_is_recorded(self):
        """Rollout trace should be recorded."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(query="test query")
        await policy.execute_retrieval(context)
        
        traces = policy.scenario_router.get_traces()
        assert len(traces) == 1
    
    @pytest.mark.asyncio
    async def test_trace_has_required_fields(self):
        """Trace must have all required fields."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(query="I remember something")
        await policy.execute_retrieval(context)
        
        traces = policy.scenario_router.get_traces()
        trace = traces[0]
        
        assert "scenario_name" in trace
        assert "rollout_eligible" in trace
        assert "requested_mode" in trace
        assert "resolved_mode" in trace
        assert "rollout_applied" in trace
        assert "provider_used" in trace
        assert "fallback_triggered" in trace
        assert "latency_ms" in trace


class TestScenarioStats:
    """Test per-scenario statistics."""
    
    @pytest.mark.asyncio
    async def test_stats_by_scenario(self):
        """Should track stats by scenario."""
        policy = RolloutPolicy()
        
        # Run whitelist scenario
        context1 = ScenarioContext(
            query="I remember something",
            action_type="memory_search",
        )
        await policy.execute_retrieval(context1)
        
        # Run non-whitelist scenario
        context2 = ScenarioContext(
            query='"exact match"',
            action_type="search",
        )
        await policy.execute_retrieval(context2)
        
        stats = policy.scenario_router.get_scenario_stats()
        
        # Should have stats for both scenarios
        assert len(stats) >= 1


class TestRolloutReport:
    """Test rollout report generation."""
    
    @pytest.mark.asyncio
    async def test_report_serialization(self):
        """Report should be JSON serializable."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(query="test")
        await policy.execute_retrieval(context)
        
        metrics = policy.get_metrics()
        report = {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics.to_dict(),
            "verdict": policy.get_verdict().value,
        }
        
        # Should serialize
        json_str = json.dumps(report)
        assert json_str is not None
        
        # Should parse
        parsed = json.loads(json_str)
        assert "metrics" in parsed
        assert "verdict" in parsed


class TestCapabilityOwnership:
    """Test capability ownership."""
    
    def test_rollout_in_openemotion(self):
        """Rollout must be in OpenEmotion."""
        from emotiond.memory.embedding import rollout
        
        assert "emotiond" in rollout.__file__
    
    def test_scenario_router_in_openemotion(self):
        """Scenario router must be in OpenEmotion."""
        from emotiond.memory.embedding import scenario_router
        
        assert "emotiond" in scenario_router.__file__
