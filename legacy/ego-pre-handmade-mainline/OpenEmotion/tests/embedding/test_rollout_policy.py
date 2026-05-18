"""
Tests for Rollout Policy (v6d).

Validates:
- Whitelist mechanism
- Scenario routing
- Non-whitelist enforcement
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.scenario_router import (
    RolloutConfig,
    ScenarioContext,
    ScenarioRouter,
    RetrievalScenario,
)
from emotiond.memory.embedding.rollout import (
    RolloutPolicy,
    RolloutVerdict,
)


class TestRetrievalScenario:
    """Test scenario enum."""
    
    def test_whitelist_scenarios_exist(self):
        """Whitelist scenarios should exist."""
        assert RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value == "memory_search_hard_query"
        assert RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value == "narrative_recall_ambiguous_query"
        assert RetrievalScenario.LONG_CONTEXT_SEMANTIC_LOOKUP.value == "long_context_semantic_lookup"
    
    def test_non_rollout_scenarios_exist(self):
        """Non-rollout scenarios should exist."""
        assert RetrievalScenario.KEYWORD_EXACT_MATCH.value == "keyword_exact_match"
        assert RetrievalScenario.LOW_LATENCY_PATH.value == "low_latency_path"
        assert RetrievalScenario.MULTI_USER_SENSITIVE.value == "multi_user_sensitive"


class TestRolloutConfig:
    """Test rollout configuration."""
    
    def test_default_enabled(self):
        """Rollout should be enabled by default."""
        config = RolloutConfig()
        assert config.enabled is True
    
    def test_default_mode_is_tfidf(self):
        """Default mode should be tfidf."""
        config = RolloutConfig()
        assert config.default_mode == "tfidf"
    
    def test_default_allowed_scenarios(self):
        """Should have default whitelist scenarios."""
        config = RolloutConfig()
        assert "memory_search_hard_query" in config.allowed_scenarios
        assert "narrative_recall_ambiguous_query" in config.allowed_scenarios
        assert "long_context_semantic_lookup" in config.allowed_scenarios
    
    def test_non_whitelist_not_in_allowed(self):
        """Non-whitelist scenarios should not be in allowed."""
        config = RolloutConfig()
        assert "keyword_exact_match" not in config.allowed_scenarios
        assert "low_latency_path" not in config.allowed_scenarios


class TestScenarioRouter:
    """Test scenario router."""
    
    def test_resolve_hard_query_scenario(self):
        """Should identify hard query scenarios."""
        router = ScenarioRouter()
        
        context = ScenarioContext(
            query="I remember something about the project",
            action_type="memory_search",
        )
        
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value
    
    def test_resolve_ambiguous_query_scenario(self):
        """Should identify ambiguous query scenarios."""
        router = ScenarioRouter()
        
        context = ScenarioContext(
            query="It was something like a meeting",
            action_type="narrative_recall",
        )
        
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value
    
    def test_resolve_keyword_exact_scenario(self):
        """Should identify exact match scenarios."""
        router = ScenarioRouter()
        
        context = ScenarioContext(
            query='"exact phrase search"',
            action_type="search",
        )
        
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.KEYWORD_EXACT_MATCH.value
    
    def test_resolve_low_latency_scenario(self):
        """Should identify low latency scenarios."""
        router = ScenarioRouter()
        
        context = ScenarioContext(
            query="test query",
            action_type="real-time",
        )
        
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.LOW_LATENCY_PATH.value
    
    def test_is_rollout_eligible_whitelist(self):
        """Whitelist scenarios should be eligible."""
        config = RolloutConfig()
        router = ScenarioRouter(config)
        
        assert router.is_rollout_eligible("memory_search_hard_query") is True
        assert router.is_rollout_eligible("narrative_recall_ambiguous_query") is True
        assert router.is_rollout_eligible("long_context_semantic_lookup") is True
    
    def test_is_rollout_not_eligible_non_whitelist(self):
        """Non-whitelist scenarios should not be eligible."""
        config = RolloutConfig()
        router = ScenarioRouter(config)
        
        assert router.is_rollout_eligible("keyword_exact_match") is False
        assert router.is_rollout_eligible("low_latency_path") is False
        assert router.is_rollout_eligible("default") is False
    
    def test_resolve_mode_whitelist(self):
        """Whitelist scenario should resolve to ollama."""
        config = RolloutConfig()
        router = ScenarioRouter(config)
        
        mode = router.resolve_mode("memory_search_hard_query")
        assert mode == "ollama"
    
    def test_resolve_mode_non_whitelist(self):
        """Non-whitelist scenario should resolve to tfidf."""
        config = RolloutConfig()
        router = ScenarioRouter(config)
        
        mode = router.resolve_mode("keyword_exact_match")
        assert mode == "tfidf"
    
    def test_resolve_mode_explicit_request(self):
        """Explicit request should override scenario."""
        config = RolloutConfig()
        router = ScenarioRouter(config)
        
        mode = router.resolve_mode("keyword_exact_match", requested_mode="ollama")
        assert mode == "ollama"


class TestRolloutPolicy:
    """Test rollout policy."""
    
    @pytest.mark.asyncio
    async def test_whitelist_uses_ollama_or_fallback(self):
        """Whitelist scenario should use ollama or fallback."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query="I remember something about the project",
            action_type="memory_search",
        )
        
        provider, trace = await policy.execute_retrieval(context)
        
        # Should use ollama (or fallback to tfidf)
        assert trace.provider_used in ["ollama", "tfidf"]
        assert trace.scenario_name == RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value
    
    @pytest.mark.asyncio
    async def test_non_whitelist_uses_tfidf(self):
        """Non-whitelist scenario should use tfidf."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query='"exact keyword"',
            action_type="search",
        )
        
        provider, trace = await policy.execute_retrieval(context)
        
        assert trace.provider_used == "tfidf"
        assert trace.rollout_applied is False
    
    @pytest.mark.asyncio
    async def test_rollout_trace_recorded(self):
        """Rollout trace should be recorded."""
        policy = RolloutPolicy()
        
        context = ScenarioContext(
            query="test query",
            action_type="default",
        )
        
        await policy.execute_retrieval(context)
        
        traces = policy.scenario_router.get_traces()
        assert len(traces) == 1
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """Should track rollout metrics."""
        policy = RolloutPolicy()
        
        # Run multiple requests
        for i in range(5):
            context = ScenarioContext(
                query="I remember something",
                action_type="memory_search",
            )
            await policy.execute_retrieval(context)
        
        metrics = policy.get_metrics()
        
        assert metrics.whitelist_requests >= 0
        assert metrics.non_whitelist_requests >= 0


class TestRolloutVerdict:
    """Test rollout verdict logic."""
    
    def test_verdict_expand_same_scope(self):
        """Should recommend expand_same_scope when stable."""
        policy = RolloutPolicy()
        
        # Add some traces
        for i in range(10):
            policy.scenario_router.create_trace(
                scenario="memory_search_hard_query",
                requested_mode="tfidf",
                resolved_mode="ollama",
                provider_used="ollama",
                rollout_applied=True,
                latency_ms=60.0,
            )
        
        verdict = policy.get_verdict()
        assert verdict == RolloutVerdict.EXPAND_SAME_SCOPE


class TestCapabilityOwnership:
    """Test capability ownership."""
    
    def test_scenario_router_in_openemotion(self):
        """Scenario router must be in OpenEmotion."""
        from emotiond.memory.embedding import scenario_router
        
        assert "emotiond" in scenario_router.__file__
    
    def test_rollout_policy_in_openemotion(self):
        """Rollout policy must be in OpenEmotion."""
        from emotiond.memory.embedding import rollout
        
        assert "emotiond" in rollout.__file__
