"""
Scenario Router for High-Quality Retrieval Rollout.

Routes requests to appropriate retrieval mode based on scenario whitelist.
Capability Owner: OpenEmotion

v6d: Limited Rollout for High-Quality Retrieval Mode
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RetrievalScenario(str, Enum):
    """Retrieval scenarios for routing decisions."""
    # Whitelist scenarios - eligible for high-quality mode
    MEMORY_SEARCH_HARD_QUERY = "memory_search_hard_query"
    NARRATIVE_RECALL_AMBIGUOUS_QUERY = "narrative_recall_ambiguous_query"
    LONG_CONTEXT_SEMANTIC_LOOKUP = "long_context_semantic_lookup"
    
    # Non-rollout scenarios - always use TF-IDF
    KEYWORD_EXACT_MATCH = "keyword_exact_match"
    LOW_LATENCY_PATH = "low_latency_path"
    MULTI_USER_SENSITIVE = "multi_user_sensitive"
    DEFAULT = "default"


@dataclass
class RolloutConfig:
    """Configuration for limited rollout."""
    enabled: bool = True
    default_mode: str = "tfidf"
    allowed_scenarios: List[str] = field(default_factory=lambda: [
        RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value,
        RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value,
        RetrievalScenario.LONG_CONTEXT_SEMANTIC_LOOKUP.value,
    ])
    rollout_percentage: int = 100
    fallback_to_tfidf: bool = True
    shadow_compare_enabled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "default_mode": self.default_mode,
            "allowed_scenarios": self.allowed_scenarios,
            "rollout_percentage": self.rollout_percentage,
            "fallback_to_tfidf": self.fallback_to_tfidf,
            "shadow_compare_enabled": self.shadow_compare_enabled,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RolloutConfig":
        return cls(
            enabled=data.get("enabled", True),
            default_mode=data.get("default_mode", "tfidf"),
            allowed_scenarios=data.get("allowed_scenarios", [
                RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value,
                RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value,
                RetrievalScenario.LONG_CONTEXT_SEMANTIC_LOOKUP.value,
            ]),
            rollout_percentage=data.get("rollout_percentage", 100),
            fallback_to_tfidf=data.get("fallback_to_tfidf", True),
            shadow_compare_enabled=data.get("shadow_compare_enabled", False),
        )


@dataclass
class ScenarioContext:
    """Context for scenario resolution."""
    query: str
    action_type: str = "default"
    memory_action: str = ""
    user_id: str = ""
    request_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "action_type": self.action_type,
            "memory_action": self.memory_action,
            "user_id": self.user_id,
            "request_metadata": self.request_metadata,
        }


@dataclass
class RolloutTrace:
    """Trace record for rollout decisions."""
    scenario_name: str
    rollout_eligible: bool
    requested_mode: str
    resolved_mode: str
    rollout_applied: bool
    provider_used: str
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "rollout_eligible": self.rollout_eligible,
            "requested_mode": self.requested_mode,
            "resolved_mode": self.resolved_mode,
            "rollout_applied": self.rollout_applied,
            "provider_used": self.provider_used,
            "fallback_triggered": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
        }


class ScenarioRouter:
    """Routes retrieval requests based on scenario whitelist.
    
    Capability Owner: OpenEmotion
    
    Determines which retrieval mode to use based on:
    - Scenario identification
    - Whitelist membership
    - Rollout percentage
    - Fallback configuration
    """
    
    def __init__(self, config: Optional[RolloutConfig] = None):
        self.config = config or RolloutConfig()
        self._traces: List[RolloutTrace] = []
        self._scenario_stats: Dict[str, Dict[str, Any]] = {}
        
    def resolve_scenario(self, context: ScenarioContext) -> str:
        """Resolve the retrieval scenario from context.
        
        Args:
            context: Request context with query and metadata
            
        Returns:
            Scenario name
        """
        query = context.query.lower()
        action_type = context.action_type.lower()
        memory_action = context.memory_action.lower()
        
        # Hard query indicators
        hard_query_indicators = [
            "i think", "i remember", "something about", "i'm not sure",
            "what was that", "can you find", "looking for",
        ]
        
        # Ambiguous query indicators
        ambiguous_indicators = [
            "something like", "kind of", "sort of", "maybe",
            "i guess", "approximately",
        ]
        
        # Long context indicators
        long_context_indicators = [
            len(query) > 100,
            "long" in query and "context" in query,
            "conversation" in query and "history" in query,
        ]
        
        # Keyword exact match indicators
        exact_match_indicators = [
            '"' in query,  # Quoted search
            "exact" in query,
            "keyword" in action_type,
        ]
        
        # Low latency path indicators
        low_latency_indicators = [
            context.request_metadata.get("low_latency_required", False),
            "real-time" in action_type,
            "quick" in query,
        ]
        
        # Multi-user sensitive
        multi_user_indicators = [
            context.request_metadata.get("multi_user_context", False),
            "shared" in action_type,
        ]
        
        # Priority decision logic
        if any(multi_user_indicators):
            return RetrievalScenario.MULTI_USER_SENSITIVE.value
        
        if any(low_latency_indicators):
            return RetrievalScenario.LOW_LATENCY_PATH.value
        
        if any(exact_match_indicators):
            return RetrievalScenario.KEYWORD_EXACT_MATCH.value
        
        # Check for hard query
        if any(ind in query for ind in hard_query_indicators):
            return RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value
        
        # Check for ambiguous query
        if any(ind in query for ind in ambiguous_indicators):
            return RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value
        
        # Check for long context
        if any(long_context_indicators):
            return RetrievalScenario.LONG_CONTEXT_SEMANTIC_LOOKUP.value
        
        return RetrievalScenario.DEFAULT.value
    
    def is_rollout_eligible(self, scenario: str) -> bool:
        """Check if scenario is eligible for high-quality rollout.
        
        Args:
            scenario: Scenario name
            
        Returns:
            True if eligible for rollout
        """
        if not self.config.enabled:
            return False
        
        if scenario not in self.config.allowed_scenarios:
            return False
        
        # Check rollout percentage
        import random
        if self.config.rollout_percentage < 100:
            return random.randint(1, 100) <= self.config.rollout_percentage
        
        return True
    
    def resolve_mode(
        self, 
        scenario: str,
        requested_mode: Optional[str] = None,
    ) -> str:
        """Resolve the retrieval mode for a scenario.
        
        Args:
            scenario: Scenario name
            requested_mode: Explicitly requested mode (optional)
            
        Returns:
            Resolved mode
        """
        # Explicit request takes priority
        if requested_mode:
            return requested_mode.lower()
        
        # Check if rollout is enabled for this scenario
        if self.is_rollout_eligible(scenario):
            return "ollama"
        
        # Default to tfidf
        return self.config.default_mode
    
    def create_trace(
        self,
        scenario: str,
        requested_mode: str,
        resolved_mode: str,
        provider_used: str,
        rollout_applied: bool,
        fallback_triggered: bool = False,
        fallback_reason: Optional[str] = None,
        latency_ms: float = 0.0,
    ) -> RolloutTrace:
        """Create and record a rollout trace."""
        trace = RolloutTrace(
            scenario_name=scenario,
            rollout_eligible=self.is_rollout_eligible(scenario),
            requested_mode=requested_mode,
            resolved_mode=resolved_mode,
            rollout_applied=rollout_applied,
            provider_used=provider_used,
            fallback_triggered=fallback_triggered,
            fallback_reason=fallback_reason,
            latency_ms=latency_ms,
        )
        
        self._traces.append(trace)
        self._update_stats(trace)
        
        # Keep traces bounded
        if len(self._traces) > 1000:
            self._traces = self._traces[-1000:]
        
        return trace
    
    def _update_stats(self, trace: RolloutTrace) -> None:
        """Update scenario statistics."""
        scenario = trace.scenario_name
        
        if scenario not in self._scenario_stats:
            self._scenario_stats[scenario] = {
                "request_count": 0,
                "rollout_count": 0,
                "tfidf_count": 0,
                "ollama_count": 0,
                "fallback_count": 0,
                "total_latency_ms": 0.0,
            }
        
        stats = self._scenario_stats[scenario]
        stats["request_count"] += 1
        stats["total_latency_ms"] += trace.latency_ms
        
        if trace.rollout_applied:
            stats["rollout_count"] += 1
        
        if trace.provider_used == "tfidf":
            stats["tfidf_count"] += 1
        elif trace.provider_used == "ollama":
            stats["ollama_count"] += 1
        
        if trace.fallback_triggered:
            stats["fallback_count"] += 1
    
    def get_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent traces."""
        traces = self._traces[-limit:]
        return [t.to_dict() for t in traces]
    
    def get_scenario_stats(self) -> Dict[str, Any]:
        """Get statistics by scenario."""
        result = {}
        for scenario, stats in self._scenario_stats.items():
            avg_latency = (
                stats["total_latency_ms"] / stats["request_count"]
                if stats["request_count"] > 0 else 0
            )
            result[scenario] = {
                **stats,
                "avg_latency_ms": round(avg_latency, 2),
            }
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get overall rollout summary."""
        total_requests = len(self._traces)
        rollout_requests = sum(1 for t in self._traces if t.rollout_applied)
        ollama_requests = sum(1 for t in self._traces if t.provider_used == "ollama")
        tfidf_requests = sum(1 for t in self._traces if t.provider_used == "tfidf")
        fallbacks = sum(1 for t in self._traces if t.fallback_triggered)
        
        # Whitelist vs non-whitelist
        whitelist_requests = sum(
            1 for t in self._traces 
            if t.scenario_name in self.config.allowed_scenarios
        )
        non_whitelist_requests = total_requests - whitelist_requests
        
        return {
            "total_requests": total_requests,
            "whitelist_requests": whitelist_requests,
            "non_whitelist_requests": non_whitelist_requests,
            "rollout_requests": rollout_requests,
            "ollama_requests": ollama_requests,
            "tfidf_requests": tfidf_requests,
            "fallback_count": fallbacks,
            "rollout_rate": round(rollout_requests / total_requests, 4) if total_requests > 0 else 0,
            "fallback_rate": round(fallbacks / total_requests, 4) if total_requests > 0 else 0,
        }


def resolve_retrieval_scenario(
    context: ScenarioContext,
    config: Optional[RolloutConfig] = None,
) -> str:
    """Convenience function to resolve scenario.
    
    Args:
        context: Request context
        config: Rollout configuration
        
    Returns:
        Scenario name
    """
    router = ScenarioRouter(config)
    return router.resolve_scenario(context)
