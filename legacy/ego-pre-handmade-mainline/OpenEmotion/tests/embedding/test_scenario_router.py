"""
Tests for Scenario Router (v6d).

Validates scenario identification and routing.
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


class TestScenarioResolution:
    """Test scenario resolution from context."""
    
    @pytest.fixture
    def router(self):
        return ScenarioRouter()
    
    def test_hard_query_i_remember(self, router):
        """'I remember' should indicate hard query."""
        context = ScenarioContext(query="I remember something about the project")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value
    
    def test_hard_query_i_think(self, router):
        """'I think' should indicate hard query."""
        context = ScenarioContext(query="I think there was a meeting")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value
    
    def test_hard_query_looking_for(self, router):
        """'looking for' should indicate hard query."""
        context = ScenarioContext(query="I'm looking for that document")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value
    
    def test_ambiguous_something_like(self, router):
        """'something like' should indicate ambiguous query."""
        context = ScenarioContext(query="It was something like a plan")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value
    
    def test_ambiguous_kind_of(self, router):
        """'kind of' should indicate ambiguous query."""
        context = ScenarioContext(query="It was kind of important")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value
    
    def test_long_context_long_query(self, router):
        """Long query should indicate long context."""
        long_query = "This is a very long query about conversation history and context that spans multiple topics and requires semantic understanding to find the relevant information in the memory system"
        context = ScenarioContext(query=long_query)
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.LONG_CONTEXT_SEMANTIC_LOOKUP.value
    
    def test_keyword_exact_quotes(self, router):
        """Quoted search should indicate exact match."""
        context = ScenarioContext(query='"exact phrase"')
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.KEYWORD_EXACT_MATCH.value
    
    def test_keyword_exact_keyword_action(self, router):
        """'keyword' action type should indicate exact match."""
        context = ScenarioContext(query="search term", action_type="keyword")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.KEYWORD_EXACT_MATCH.value
    
    def test_low_latency_realtime_action(self, router):
        """'real-time' action should indicate low latency."""
        context = ScenarioContext(query="search", action_type="real-time")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.LOW_LATENCY_PATH.value
    
    def test_multi_user_shared_action(self, router):
        """'shared' action should indicate multi-user."""
        context = ScenarioContext(query="search", action_type="shared")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.MULTI_USER_SENSITIVE.value
    
    def test_default_simple_query(self, router):
        """Simple query should default."""
        context = ScenarioContext(query="hello world")
        scenario = router.resolve_scenario(context)
        assert scenario == RetrievalScenario.DEFAULT.value


class TestRolloutEligibility:
    """Test rollout eligibility checking."""
    
    def test_whitelist_eligible(self):
        """Whitelist scenarios should be eligible."""
        config = RolloutConfig()
        router = ScenarioRouter(config)
        
        assert router.is_rollout_eligible("memory_search_hard_query") is True
    
    def test_non_whitelist_not_eligible(self):
        """Non-whitelist should not be eligible."""
        config = RolloutConfig()
        router = ScenarioRouter(config)
        
        assert router.is_rollout_eligible("keyword_exact_match") is False
    
    def test_disabled_rollout(self):
        """Disabled rollout should not be eligible."""
        config = RolloutConfig(enabled=False)
        router = ScenarioRouter(config)
        
        assert router.is_rollout_eligible("memory_search_hard_query") is False
    
    def test_custom_whitelist(self):
        """Custom whitelist should work."""
        config = RolloutConfig(
            allowed_scenarios=["custom_scenario"]
        )
        router = ScenarioRouter(config)
        
        assert router.is_rollout_eligible("custom_scenario") is True
        assert router.is_rollout_eligible("memory_search_hard_query") is False


class TestScenarioStats:
    """Test scenario statistics."""
    
    def test_stats_tracking(self):
        """Should track statistics per scenario."""
        router = ScenarioRouter()
        
        # Create some traces
        router.create_trace(
            scenario="test_scenario",
            requested_mode="tfidf",
            resolved_mode="ollama",
            provider_used="ollama",
            rollout_applied=True,
            latency_ms=60.0,
        )
        
        stats = router.get_scenario_stats()
        assert "test_scenario" in stats
        assert stats["test_scenario"]["request_count"] == 1
        assert stats["test_scenario"]["ollama_count"] == 1
    
    def test_summary(self):
        """Should provide summary statistics."""
        router = ScenarioRouter()
        
        # Create traces
        for i in range(5):
            router.create_trace(
                scenario="memory_search_hard_query",
                requested_mode="tfidf",
                resolved_mode="ollama",
                provider_used="ollama",
                rollout_applied=True,
                latency_ms=60.0,
            )
        
        summary = router.get_summary()
        
        assert summary["total_requests"] == 5
        assert summary["rollout_requests"] == 5
        assert summary["ollama_requests"] == 5
