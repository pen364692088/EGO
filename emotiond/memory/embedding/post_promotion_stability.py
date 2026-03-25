"""
Post-Promotion Stability Evaluator.

Evaluates stability of promoted scenarios and outputs verdict.
Capability Owner: OpenEmotion

v6i: Post-Promotion Observation Window + Stability Verdict
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .production_whitelist import ProductionWhitelistRegistry, WhitelistStatus
from .post_promotion_guard import PostPromotionGuard


class StabilityVerdict(str, Enum):
    """Stability verdict for promoted scenario."""
    STABLE_KEEP_PROMOTED = "stable_keep_promoted"
    KEEP_UNDER_OBSERVATION = "keep_under_observation"
    DEMOTE_TO_PILOT = "demote_to_pilot"
    ROLLBACK_TO_TFIDF_ONLY = "rollback_to_tfidf_only"


@dataclass
class ObservationRoundReceipt:
    """Receipt for a single observation round."""
    round_id: int
    scenario_name: str
    sample_count: int
    fallback_rate: float
    p95_latency_ms: float
    wrong_user_guard_trigger_count: int
    provider_health_rate: float
    quality_gain_signal: float
    guard_status: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_id": self.round_id,
            "scenario_name": self.scenario_name,
            "sample_count": self.sample_count,
            "fallback_rate": self.fallback_rate,
            "p95_latency_ms": self.p95_latency_ms,
            "wrong_user_guard_trigger_count": self.wrong_user_guard_trigger_count,
            "provider_health_rate": self.provider_health_rate,
            "quality_gain_signal": self.quality_gain_signal,
            "guard_status": self.guard_status,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


@dataclass
class StabilityEvaluation:
    """Result of stability evaluation."""
    scenario_name: str
    verdict: StabilityVerdict
    blockers: List[str]
    rationale: str
    next_allowed_action: str
    metrics_summary: Dict[str, Any]
    observation_rounds: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "verdict": self.verdict.value,
            "blockers": self.blockers,
            "rationale": self.rationale,
            "next_allowed_action": self.next_allowed_action,
            "metrics_summary": self.metrics_summary,
            "observation_rounds": self.observation_rounds,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


class PostPromotionStabilityEvaluator:
    """
    Evaluates stability of promoted scenarios.
    
    v6i specific:
    - Evaluates complex_semantic_reasoning after v6h promotion
    - Outputs stability verdict with blockers and rationale
    - Supports drill mode for testing rollback/demotion
    """

    # Minimum requirements for stable verdict
    MIN_REQUEST_COUNT = 50
    MIN_OBSERVATION_ROUNDS = 3

    # Stability thresholds
    MAX_FALLBACK_RATE = 0.05  # 5%
    MAX_P95_LATENCY_MS = 100
    MAX_WRONG_USER_GUARD = 0
    MIN_PROVIDER_HEALTH_RATE = 0.98  # 98%
    MIN_QUALITY_SIGNAL = 0.0

    # Demotion thresholds
    DEMOTION_FALLBACK_RATE = 0.10  # 10%
    DEMOTION_PROVIDER_HEALTH_RATE = 0.95  # 95%

    def __init__(
        self,
        registry: ProductionWhitelistRegistry,
        guard: PostPromotionGuard,
        storage_path: Optional[Path] = None,
    ):
        self.registry = registry
        self.guard = guard
        self.storage_path = storage_path or Path("artifacts/eval/v6i")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.round_receipts: List[ObservationRoundReceipt] = []
        self._load_receipts()

    def _load_receipts(self) -> None:
        """Load round receipts from storage."""
        receipts_file = self.storage_path / "round_receipts.json"
        if receipts_file.exists():
            try:
                data = json.loads(receipts_file.read_text())
                self.round_receipts = [
                    ObservationRoundReceipt(
                        round_id=r["round_id"],
                        scenario_name=r["scenario_name"],
                        sample_count=r["sample_count"],
                        fallback_rate=r["fallback_rate"],
                        p95_latency_ms=r["p95_latency_ms"],
                        wrong_user_guard_trigger_count=r["wrong_user_guard_trigger_count"],
                        provider_health_rate=r["provider_health_rate"],
                        quality_gain_signal=r["quality_gain_signal"],
                        guard_status=r["guard_status"],
                        timestamp=r.get("timestamp", time.time()),
                    )
                    for r in data.get("rounds", [])
                ]
            except Exception:
                pass

    def _save_receipts(self) -> None:
        """Save round receipts to storage."""
        receipts_file = self.storage_path / "round_receipts.json"
        data = {
            "rounds": [r.to_dict() for r in self.round_receipts],
        }
        receipts_file.write_text(json.dumps(data, indent=2))

    def record_observation_round(
        self,
        scenario_name: str,
        observations: List[Dict[str, Any]],
    ) -> ObservationRoundReceipt:
        """
        Record an observation round for a promoted scenario.
        
        Args:
            scenario_name: Scenario being observed
            observations: List of observation dicts
            
        Returns:
            ObservationRoundReceipt
        """
        if not self.registry.is_in_production_whitelist(scenario_name):
            raise ValueError(f"{scenario_name} is not in production whitelist")

        round_id = len(self.round_receipts) + 1

        # Run observations through guard
        decision = self.guard.run_observation_round(scenario_name, observations)

        # Get metrics from registry
        report = self.registry.get_observation_report(scenario_name)

        receipt = ObservationRoundReceipt(
            round_id=round_id,
            scenario_name=scenario_name,
            sample_count=len(observations),
            fallback_rate=report.get("fallback_rate", 0),
            p95_latency_ms=report.get("p95_latency_ms", 0),
            wrong_user_guard_trigger_count=report.get("wrong_user_guard_trigger_count", 0),
            provider_health_rate=report.get("provider_health_rate", 0),
            quality_gain_signal=report.get("avg_quality_signal", 0),
            guard_status=decision.action.value if decision else "none",
        )

        self.round_receipts.append(receipt)
        self._save_receipts()

        return receipt

    def evaluate_stability(self, scenario_name: str) -> StabilityEvaluation:
        """
        Evaluate stability of a promoted scenario.
        
        Args:
            scenario_name: Scenario to evaluate
            
        Returns:
            StabilityEvaluation with verdict
        """
        if scenario_name not in self.registry.scenarios:
            return StabilityEvaluation(
                scenario_name=scenario_name,
                verdict=StabilityVerdict.ROLLBACK_TO_TFIDF_ONLY,
                blockers=["Scenario not in registry"],
                rationale="Scenario does not exist in whitelist registry",
                next_allowed_action="Investigate scenario registration",
                metrics_summary={},
                observation_rounds=0,
            )

        scenario = self.registry.scenarios[scenario_name]
        if scenario.status != WhitelistStatus.PROMOTED:
            return StabilityEvaluation(
                scenario_name=scenario_name,
                verdict=StabilityVerdict.ROLLBACK_TO_TFIDF_ONLY,
                blockers=[f"Scenario status is {scenario.status.value}, not promoted"],
                rationale="Scenario is not currently in promoted state",
                next_allowed_action="Check scenario status history",
                metrics_summary={},
                observation_rounds=0,
            )

        # Get current metrics
        report = self.registry.get_observation_report(scenario_name)

        # Count observation rounds for this scenario
        scenario_rounds = [r for r in self.round_receipts if r.scenario_name == scenario_name]
        observation_rounds = len(scenario_rounds)

        metrics_summary = {
            "request_count": report.get("request_count", 0),
            "fallback_rate": report.get("fallback_rate", 0),
            "p95_latency_ms": report.get("p95_latency_ms", 0),
            "wrong_user_guard_trigger_count": report.get("wrong_user_guard_trigger_count", 0),
            "provider_health_rate": report.get("provider_health_rate", 0),
            "quality_gain_signal": report.get("avg_quality_signal", 0),
            "observation_rounds": observation_rounds,
        }

        blockers = []

        # Check minimum requirements FIRST (before demotion thresholds)
        if report.get("request_count", 0) < self.MIN_REQUEST_COUNT:
            blockers.append(f"request_count ({report.get('request_count', 0)}) < {self.MIN_REQUEST_COUNT}")

        if observation_rounds < self.MIN_OBSERVATION_ROUNDS:
            blockers.append(f"observation_rounds ({observation_rounds}) < {self.MIN_OBSERVATION_ROUNDS}")

        # Check critical issues (rollback) - highest priority
        if report.get("wrong_user_guard_trigger_count", 0) > self.MAX_WRONG_USER_GUARD:
            return StabilityEvaluation(
                scenario_name=scenario_name,
                verdict=StabilityVerdict.ROLLBACK_TO_TFIDF_ONLY,
                blockers=[f"wrong_user_guard_trigger_count ({report.get('wrong_user_guard_trigger_count', 0)}) > 0"],
                rationale="Critical: wrong_user_guard triggered, immediate rollback required",
                next_allowed_action="Execute rollback and investigate root cause",
                metrics_summary=metrics_summary,
                observation_rounds=observation_rounds,
            )

        # If data is insufficient, return early with KEEP_UNDER_OBSERVATION
        if blockers:
            return StabilityEvaluation(
                scenario_name=scenario_name,
                verdict=StabilityVerdict.KEEP_UNDER_OBSERVATION,
                blockers=blockers,
                rationale="Insufficient observation data, continue monitoring",
                next_allowed_action="Continue accumulating observation samples",
                metrics_summary=metrics_summary,
                observation_rounds=observation_rounds,
            )

        # Check demotion thresholds
        if report.get("fallback_rate", 0) > self.DEMOTION_FALLBACK_RATE:
            return StabilityEvaluation(
                scenario_name=scenario_name,
                verdict=StabilityVerdict.DEMOTE_TO_PILOT,
                blockers=[f"fallback_rate ({report['fallback_rate']:.1%}) > {self.DEMOTION_FALLBACK_RATE:.0%}"],
                rationale="High fallback rate requires demotion to pilot for further observation",
                next_allowed_action="Demote to pilot and investigate fallback causes",
                metrics_summary=metrics_summary,
                observation_rounds=observation_rounds,
            )

        if report.get("provider_health_rate", 1) < self.DEMOTION_PROVIDER_HEALTH_RATE:
            return StabilityEvaluation(
                scenario_name=scenario_name,
                verdict=StabilityVerdict.DEMOTE_TO_PILOT,
                blockers=[f"provider_health_rate ({report['provider_health_rate']:.1%}) < {self.DEMOTION_PROVIDER_HEALTH_RATE:.0%}"],
                rationale="Low provider health rate requires demotion to pilot",
                next_allowed_action="Demote to pilot and investigate provider issues",
                metrics_summary=metrics_summary,
                observation_rounds=observation_rounds,
            )

        # Check stability thresholds
        if report.get("fallback_rate", 0) > self.MAX_FALLBACK_RATE:
            blockers.append(f"fallback_rate ({report['fallback_rate']:.1%}) > {self.MAX_FALLBACK_RATE:.0%}")

        if report.get("p95_latency_ms", 0) > self.MAX_P95_LATENCY_MS:
            blockers.append(f"p95_latency_ms ({report['p95_latency_ms']:.0f}) > {self.MAX_P95_LATENCY_MS}")

        if report.get("provider_health_rate", 1) < self.MIN_PROVIDER_HEALTH_RATE:
            blockers.append(f"provider_health_rate ({report['provider_health_rate']:.1%}) < {self.MIN_PROVIDER_HEALTH_RATE:.0%}")

        if report.get("avg_quality_signal", 0) <= self.MIN_QUALITY_SIGNAL:
            blockers.append(f"quality_gain_signal ({report.get('avg_quality_signal', 0):.2f}) <= {self.MIN_QUALITY_SIGNAL}")

        # Determine verdict
        if blockers:
            # Check if just insufficient data or actual stability issues
            has_data_issues = any("request_count" in b or "observation_rounds" in b for b in blockers)
            has_stability_issues = any(
                "fallback_rate" in b or "p95_latency" in b or "provider_health" in b or "quality_gain" in b
                for b in blockers
            )

            if has_stability_issues:
                verdict = StabilityVerdict.KEEP_UNDER_OBSERVATION
                rationale = "Stability thresholds not met, continue observation"
                next_action = "Continue observation window, address stability issues"
            elif has_data_issues:
                verdict = StabilityVerdict.KEEP_UNDER_OBSERVATION
                rationale = "Insufficient observation data, continue monitoring"
                next_action = "Continue accumulating observation samples"
            else:
                verdict = StabilityVerdict.KEEP_UNDER_OBSERVATION
                rationale = "Minor issues detected, continue observation"
                next_action = "Address blockers and continue observation"

            return StabilityEvaluation(
                scenario_name=scenario_name,
                verdict=verdict,
                blockers=blockers,
                rationale=rationale,
                next_allowed_action=next_action,
                metrics_summary=metrics_summary,
                observation_rounds=observation_rounds,
            )

        # All checks passed - stable
        return StabilityEvaluation(
            scenario_name=scenario_name,
            verdict=StabilityVerdict.STABLE_KEEP_PROMOTED,
            blockers=[],
            rationale="All stability criteria met, scenario remains in production whitelist",
            next_allowed_action="Continue monitoring, consider reducing observation frequency",
            metrics_summary=metrics_summary,
            observation_rounds=observation_rounds,
        )

    def get_stability_report(self, scenario_name: str) -> Dict[str, Any]:
        """Get full stability report for a scenario."""
        evaluation = self.evaluate_stability(scenario_name)
        scenario_rounds = [r for r in self.round_receipts if r.scenario_name == scenario_name]

        return {
            "scenario_name": scenario_name,
            "evaluation": evaluation.to_dict(),
            "round_receipts": [r.to_dict() for r in scenario_rounds],
            "total_rounds": len(scenario_rounds),
            "generated_at": datetime.now().isoformat(),
        }

    def save_stability_report(self, scenario_name: str) -> Path:
        """Save stability report to file."""
        report = self.get_stability_report(scenario_name)
        report_file = self.storage_path / "post_promotion_stability_report.json"
        report_file.write_text(json.dumps(report, indent=2))
        return report_file
