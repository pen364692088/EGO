"""
Rollout Policy for High-Quality Retrieval Mode.

Implements limited rollout with whitelist, fallback, and observation.
Capability Owner: OpenEmotion

v6d: Limited Rollout for High-Quality Retrieval Mode
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from emotiond.memory.embedding.scenario_router import (
    RolloutConfig,
    RolloutTrace,
    ScenarioContext,
    ScenarioRouter,
    RetrievalScenario,
)
from emotiond.memory.embedding.selector import (
    ProviderSelector,
    RetrievalConfig,
    ProviderSelectionTrace,
)


class RolloutVerdict(str, Enum):
    """Verdict for rollout decision."""
    EXPAND_SAME_SCOPE = "expand_same_scope"
    EXPAND_MORE_SCENARIOS = "expand_more_scenarios"
    SHRINK_OR_ROLLBACK = "shrink_or_rollback"


@dataclass
class ShadowCompareResult:
    """Result of shadow comparison between providers."""
    primary_provider: str
    shadow_provider: str
    primary_latency_ms: float
    shadow_latency_ms: float
    top_k_overlap: float = 0.0
    top_1_match: bool = False
    difference_summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_provider": self.primary_provider,
            "shadow_provider": self.shadow_provider,
            "primary_latency_ms": round(self.primary_latency_ms, 2),
            "shadow_latency_ms": round(self.shadow_latency_ms, 2),
            "top_k_overlap": round(self.top_k_overlap, 4),
            "top_1_match": self.top_1_match,
            "difference_summary": self.difference_summary,
        }


@dataclass
class RolloutMetrics:
    """Aggregated metrics for rollout evaluation."""
    whitelist_requests: int = 0
    non_whitelist_requests: int = 0
    ollama_success_count: int = 0
    ollama_fallback_count: int = 0
    tfidf_count: int = 0
    p95_latency_ms: float = 0.0
    wrong_user_guard_trigger_count: int = 0
    latency_samples: List[float] = field(default_factory=list)
    
    @property
    def fallback_rate(self) -> float:
        total = self.ollama_success_count + self.ollama_fallback_count
        if total == 0:
            return 0.0
        return self.ollama_fallback_count / total
    
    @property
    def avg_latency_ms(self) -> Optional[float]:
        if not self.latency_samples:
            return None
        return sum(self.latency_samples) / len(self.latency_samples)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "whitelist_requests": self.whitelist_requests,
            "non_whitelist_requests": self.non_whitelist_requests,
            "ollama_success_count": self.ollama_success_count,
            "ollama_fallback_count": self.ollama_fallback_count,
            "tfidf_count": self.tfidf_count,
            "avg_latency_ms": round(self.avg_latency_ms, 2) if self.avg_latency_ms else None,
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "wrong_user_guard_trigger_count": self.wrong_user_guard_trigger_count,
            "fallback_rate": round(self.fallback_rate, 4),
        }


class RolloutPolicy:
    """Manages limited rollout of high-quality retrieval mode.
    
    Capability Owner: OpenEmotion
    
    Features:
    - Scenario whitelist
    - Rollout percentage control
    - Fallback handling
    - Shadow comparison (optional)
    - Per-scenario observation
    """
    
    def __init__(
        self,
        rollout_config: Optional[RolloutConfig] = None,
        retrieval_config: Optional[RetrievalConfig] = None,
    ):
        self.rollout_config = rollout_config or RolloutConfig()
        self.retrieval_config = retrieval_config or RetrievalConfig()
        self.scenario_router = ScenarioRouter(self.rollout_config)
        self.provider_selector = ProviderSelector(self.retrieval_config)
        self._shadow_results: List[ShadowCompareResult] = []
        
    async def execute_retrieval(
        self,
        context: ScenarioContext,
        requested_mode: Optional[str] = None,
    ) -> tuple[Any, RolloutTrace]:
        """Execute retrieval with rollout policy applied.
        
        Args:
            context: Request context
            requested_mode: Explicitly requested mode (optional)
            
        Returns:
            Tuple of (provider, rollout_trace)
        """
        start = time.time()
        
        # Resolve scenario
        scenario = self.scenario_router.resolve_scenario(context)
        
        # Determine rollout eligibility
        rollout_eligible = self.scenario_router.is_rollout_eligible(scenario)
        
        # Resolve mode
        resolved_mode = self.scenario_router.resolve_mode(scenario, requested_mode)
        
        # Select provider
        provider, selection_trace = await self.provider_selector.select_provider(resolved_mode)
        
        # Calculate latency
        latency_ms = (time.time() - start) * 1000
        
        # Determine rollout applied
        rollout_applied = (
            rollout_eligible and 
            selection_trace.provider_used == "ollama" and
            not selection_trace.fallback_triggered
        )
        
        # Create rollout trace
        rollout_trace = self.scenario_router.create_trace(
            scenario=scenario,
            requested_mode=requested_mode or self.rollout_config.default_mode,
            resolved_mode=resolved_mode,
            provider_used=selection_trace.provider_used,
            rollout_applied=rollout_applied,
            fallback_triggered=selection_trace.fallback_triggered,
            fallback_reason=selection_trace.fallback_reason,
            latency_ms=latency_ms,
        )
        
        return provider, rollout_trace
    
    async def execute_with_shadow(
        self,
        context: ScenarioContext,
        requested_mode: Optional[str] = None,
    ) -> tuple[Any, RolloutTrace, Optional[ShadowCompareResult]]:
        """Execute retrieval with shadow comparison.
        
        Runs both tfidf and ollama, returns primary result with shadow comparison.
        
        Args:
            context: Request context
            requested_mode: Explicitly requested mode
            
        Returns:
            Tuple of (provider, rollout_trace, shadow_result)
        """
        if not self.rollout_config.shadow_compare_enabled:
            provider, trace = await self.execute_retrieval(context, requested_mode)
            return provider, trace, None
        
        start = time.time()
        
        # Resolve scenario and mode
        scenario = self.scenario_router.resolve_scenario(context)
        resolved_mode = self.scenario_router.resolve_mode(scenario, requested_mode)
        
        # Execute primary
        primary_provider, primary_trace = await self.provider_selector.select_provider(resolved_mode)
        primary_latency = primary_trace.latency_ms
        
        # Execute shadow (the other provider)
        shadow_mode = "tfidf" if resolved_mode == "ollama" else "ollama"
        try:
            shadow_provider, shadow_trace = await self.provider_selector.select_provider(shadow_mode)
            shadow_latency = shadow_trace.latency_ms
            
            shadow_result = ShadowCompareResult(
                primary_provider=primary_trace.provider_used,
                shadow_provider=shadow_trace.provider_used,
                primary_latency_ms=primary_latency,
                shadow_latency_ms=shadow_latency,
                top_k_overlap=0.0,  # Would need actual retrieval results
                top_1_match=False,
                difference_summary=f"Latency diff: {shadow_latency - primary_latency:.2f}ms",
            )
            
            self._shadow_results.append(shadow_result)
            if len(self._shadow_results) > 100:
                self._shadow_results = self._shadow_results[-100:]
                
        except Exception as e:
            shadow_result = None
        
        # Calculate total latency
        total_latency = (time.time() - start) * 1000
        
        # Create rollout trace
        rollout_eligible = self.scenario_router.is_rollout_eligible(scenario)
        rollout_applied = (
            rollout_eligible and 
            primary_trace.provider_used == "ollama" and
            not primary_trace.fallback_triggered
        )
        
        rollout_trace = self.scenario_router.create_trace(
            scenario=scenario,
            requested_mode=requested_mode or self.rollout_config.default_mode,
            resolved_mode=resolved_mode,
            provider_used=primary_trace.provider_used,
            rollout_applied=rollout_applied,
            fallback_triggered=primary_trace.fallback_triggered,
            fallback_reason=primary_trace.fallback_reason,
            latency_ms=total_latency,
        )
        
        return primary_provider, rollout_trace, shadow_result
    
    def get_metrics(self) -> RolloutMetrics:
        """Get aggregated rollout metrics."""
        summary = self.scenario_router.get_summary()
        
        latencies = [t.latency_ms for t in self.scenario_router._traces]
        p95 = 0.0
        if latencies:
            sorted_latencies = sorted(latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p95 = sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else sorted_latencies[-1]
        
        return RolloutMetrics(
            whitelist_requests=summary["whitelist_requests"],
            non_whitelist_requests=summary["non_whitelist_requests"],
            ollama_success_count=summary["ollama_requests"],
            ollama_fallback_count=summary["fallback_count"],
            tfidf_count=summary["tfidf_requests"],
            p95_latency_ms=p95,
            latency_samples=latencies,
        )
    
    def get_verdict(self) -> RolloutVerdict:
        """Determine rollout verdict based on metrics."""
        metrics = self.get_metrics()
        
        # Check for issues
        if metrics.wrong_user_guard_trigger_count > 0:
            return RolloutVerdict.SHRINK_OR_ROLLBACK
        
        if metrics.fallback_rate > 0.10:
            return RolloutVerdict.SHRINK_OR_ROLLBACK
        
        if metrics.p95_latency_ms > 300:
            return RolloutVerdict.SHRINK_OR_ROLLBACK
        
        # Check for stability
        if metrics.whitelist_requests < 20:
            return RolloutVerdict.EXPAND_SAME_SCOPE
        
        # Stable - continue with same scope
        return RolloutVerdict.EXPAND_SAME_SCOPE
    
    def export_report(self, path: Optional[str] = None) -> str:
        """Export rollout report to JSON."""
        metrics = self.get_metrics()
        verdict = self.get_verdict()
        summary = self.scenario_router.get_summary()
        scenario_stats = self.scenario_router.get_scenario_stats()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "config": self.rollout_config.to_dict(),
            "metrics": metrics.to_dict(),
            "verdict": verdict.value,
            "summary": summary,
            "scenario_stats": scenario_stats,
        }
        
        output_path = Path(path) if path else None
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"rollout_report_{timestamp}.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return str(output_path)
