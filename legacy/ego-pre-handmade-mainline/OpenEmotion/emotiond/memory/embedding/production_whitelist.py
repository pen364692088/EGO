"""
Production Whitelist Registry.

Manages production whitelist scenarios with state transitions and audit trail.
Capability Owner: OpenEmotion

v6h: Production Whitelist Promotion + Post-Promotion Observation
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class WhitelistStatus(str, Enum):
    """Status of a scenario in the whitelist lifecycle."""
    PILOT_CANDIDATE = "pilot_candidate"
    PILOT_ACTIVE = "pilot_active"
    PROMOTED = "promoted"  # In production whitelist
    DEMOTED = "demoted"  # Removed from production whitelist
    ROLLED_BACK = "rolled_back"  # Emergency rollback


@dataclass
class PromotionReceipt:
    """Receipt for a promotion event."""
    promoted_scenario: str
    previous_state: str
    new_state: str
    approval_basis: str
    promotion_commit: str
    promotion_timestamp: float
    observation_window_days: int
    observation_window_rounds: int
    rollback_thresholds: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "promoted_scenario": self.promoted_scenario,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "approval_basis": self.approval_basis,
            "promotion_commit": self.promotion_commit,
            "promotion_timestamp": self.promotion_timestamp,
            "promotion_datetime": datetime.fromtimestamp(self.promotion_timestamp).isoformat(),
            "observation_window_days": self.observation_window_days,
            "observation_window_rounds": self.observation_window_rounds,
            "rollback_thresholds": self.rollback_thresholds,
        }


@dataclass
class WhitelistScenario:
    """A scenario in the production whitelist."""
    scenario_name: str
    status: WhitelistStatus = WhitelistStatus.PILOT_CANDIDATE
    promotion_receipt: Optional[PromotionReceipt] = None

    # Post-promotion observation metrics
    request_count: int = 0
    success_count: int = 0
    fallback_count: int = 0
    wrong_user_guard_trigger_count: int = 0
    latencies: List[float] = field(default_factory=list)
    quality_signal_samples: List[float] = field(default_factory=list)
    provider_health_success: int = 0
    provider_health_total: int = 0
    observation_rounds: int = 0

    @property
    def fallback_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.fallback_count / self.request_count

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)] * 1000

    @property
    def provider_health_rate(self) -> float:
        if self.provider_health_total == 0:
            return 0.0
        return self.provider_health_success / self.provider_health_total

    @property
    def avg_quality_signal(self) -> float:
        if not self.quality_signal_samples:
            return 0.0
        return sum(self.quality_signal_samples) / len(self.quality_signal_samples)


class ProductionWhitelistRegistry:
    """
    Manages production whitelist with state transitions.
    
    State Flow:
    pilot_candidate -> pilot_active -> promoted -> (demoted|rolled_back)
    """

    # Default rollback thresholds
    DEFAULT_ROLLBACK_THRESHOLDS = {
        "max_wrong_user_guard_trigger_count": 0,
        "max_fallback_rate": 0.10,  # 10%
        "min_provider_health_rate": 0.95,  # 95%
        "max_p95_latency_ms": 300,
        "min_avg_quality_signal": 0.0,
    }

    # Initial production whitelist (from v6d)
    INITIAL_PRODUCTION_WHITELIST = [
        "memory_search_hard_query",
        "narrative_recall_ambiguous_query",
        "long_context_semantic_lookup",
    ]

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("artifacts/eval/v6h")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.scenarios: Dict[str, WhitelistScenario] = {}
        self.promotion_history: List[PromotionReceipt] = []

        # Initialize with existing production whitelist
        for scenario_name in self.INITIAL_PRODUCTION_WHITELIST:
            self.scenarios[scenario_name] = WhitelistScenario(
                scenario_name=scenario_name,
                status=WhitelistStatus.PROMOTED,
            )

        # Load state if storage exists
        self._load_state()

    def _load_state(self) -> None:
        """Load state from storage."""
        state_file = self.storage_path / "whitelist_state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                for scenario_name, scenario_data in data.get("scenarios", {}).items():
                    self.scenarios[scenario_name] = WhitelistScenario(
                        scenario_name=scenario_name,
                        status=WhitelistStatus(scenario_data.get("status", "pilot_candidate")),
                        request_count=scenario_data.get("request_count", 0),
                        success_count=scenario_data.get("success_count", 0),
                        fallback_count=scenario_data.get("fallback_count", 0),
                        wrong_user_guard_trigger_count=scenario_data.get("wrong_user_guard_trigger_count", 0),
                        latencies=scenario_data.get("latencies", []),
                        quality_signal_samples=scenario_data.get("quality_signal_samples", []),
                        provider_health_success=scenario_data.get("provider_health_success", 0),
                        provider_health_total=scenario_data.get("provider_health_total", 0),
                        observation_rounds=scenario_data.get("observation_rounds", 0),
                    )
                self.promotion_history = [
                    PromotionReceipt(
                        promoted_scenario=r.get("promoted_scenario", ""),
                        previous_state=r.get("previous_state", ""),
                        new_state=r.get("new_state", ""),
                        approval_basis=r.get("approval_basis", ""),
                        promotion_commit=r.get("promotion_commit", ""),
                        promotion_timestamp=r.get("promotion_timestamp", 0.0),
                        observation_window_days=r.get("observation_window_days", 14),
                        observation_window_rounds=r.get("observation_window_rounds", 10),
                        rollback_thresholds=r.get("rollback_thresholds", {}),
                    )
                    for r in data.get("promotion_history", [])
                ]

                # Link promotion receipts to scenarios
                for receipt in self.promotion_history:
                    if receipt.promoted_scenario in self.scenarios:
                        self.scenarios[receipt.promoted_scenario].promotion_receipt = receipt

            except Exception:
                pass  # Use defaults

    def _save_state(self) -> None:
        """Save state to storage."""
        state_file = self.storage_path / "whitelist_state.json"
        data = {
            "scenarios": {
                name: {
                    "scenario_name": s.scenario_name,
                    "status": s.status.value,
                    "request_count": s.request_count,
                    "success_count": s.success_count,
                    "fallback_count": s.fallback_count,
                    "wrong_user_guard_trigger_count": s.wrong_user_guard_trigger_count,
                    "latencies": s.latencies,
                    "quality_signal_samples": s.quality_signal_samples,
                    "provider_health_success": s.provider_health_success,
                    "provider_health_total": s.provider_health_total,
                    "observation_rounds": s.observation_rounds,
                }
                for name, s in self.scenarios.items()
            },
            "promotion_history": [r.to_dict() for r in self.promotion_history],
        }
        state_file.write_text(json.dumps(data, indent=2))

    def get_production_whitelist(self) -> List[str]:
        """Get current production whitelist scenarios."""
        return [
            name for name, scenario in self.scenarios.items()
            if scenario.status == WhitelistStatus.PROMOTED
        ]

    def get_pilot_candidates(self) -> List[str]:
        """Get pilot candidate scenarios."""
        return [
            name for name, scenario in self.scenarios.items()
            if scenario.status in (WhitelistStatus.PILOT_CANDIDATE, WhitelistStatus.PILOT_ACTIVE)
        ]

    def promote_scenario(
        self,
        scenario_name: str,
        approval_basis: str,
        promotion_commit: str,
        observation_window_days: int = 14,
        observation_window_rounds: int = 10,
        rollback_thresholds: Optional[Dict[str, Any]] = None,
    ) -> PromotionReceipt:
        """
        Promote a scenario from pilot to production whitelist.
        
        Args:
            scenario_name: Scenario to promote
            approval_basis: Reason for promotion
            promotion_commit: Git commit hash
            observation_window_days: Days to observe after promotion
            observation_window_rounds: Rounds to observe after promotion
            rollback_thresholds: Custom rollback thresholds
            
        Returns:
            PromotionReceipt for audit
        """
        if scenario_name not in self.scenarios:
            self.scenarios[scenario_name] = WhitelistScenario(
                scenario_name=scenario_name,
                status=WhitelistStatus.PILOT_ACTIVE,
            )

        scenario = self.scenarios[scenario_name]
        previous_state = scenario.status.value

        # Create receipt
        receipt = PromotionReceipt(
            promoted_scenario=scenario_name,
            previous_state=previous_state,
            new_state=WhitelistStatus.PROMOTED.value,
            approval_basis=approval_basis,
            promotion_commit=promotion_commit,
            promotion_timestamp=time.time(),
            observation_window_days=observation_window_days,
            observation_window_rounds=observation_window_rounds,
            rollback_thresholds=rollback_thresholds or self.DEFAULT_ROLLBACK_THRESHOLDS,
        )

        # Update scenario
        scenario.status = WhitelistStatus.PROMOTED
        scenario.promotion_receipt = receipt
        self.promotion_history.append(receipt)

        self._save_state()
        self._save_receipt(receipt)

        return receipt

    def demote_scenario(self, scenario_name: str, reason: str) -> bool:
        """
        Demote a scenario from production whitelist to pilot.
        
        Args:
            scenario_name: Scenario to demote
            reason: Reason for demotion
            
        Returns:
            True if demotion successful
        """
        if scenario_name not in self.scenarios:
            return False

        scenario = self.scenarios[scenario_name]
        if scenario.status != WhitelistStatus.PROMOTED:
            return False

        scenario.status = WhitelistStatus.DEMOTED
        self._save_state()

        return True

    def rollback_scenario(self, scenario_name: str, reason: str) -> bool:
        """
        Emergency rollback - remove from production whitelist entirely.
        
        Args:
            scenario_name: Scenario to rollback
            reason: Reason for rollback
            
        Returns:
            True if rollback successful
        """
        if scenario_name not in self.scenarios:
            return False

        scenario = self.scenarios[scenario_name]
        if scenario.status != WhitelistStatus.PROMOTED:
            return False

        scenario.status = WhitelistStatus.ROLLED_BACK
        self._save_state()

        return True

    def record_observation(
        self,
        scenario_name: str,
        success: bool,
        latency_ms: float,
        fallback: bool = False,
        wrong_user_guard: bool = False,
        provider_health: bool = True,
        quality_signal: Optional[float] = None,
    ) -> None:
        """Record an observation for a promoted scenario."""
        if scenario_name not in self.scenarios:
            return

        scenario = self.scenarios[scenario_name]
        if scenario.status != WhitelistStatus.PROMOTED:
            return

        scenario.request_count += 1
        if success:
            scenario.success_count += 1
        if fallback:
            scenario.fallback_count += 1
        if wrong_user_guard:
            scenario.wrong_user_guard_trigger_count += 1
        if provider_health:
            scenario.provider_health_success += 1
        scenario.provider_health_total += 1
        scenario.latencies.append(latency_ms / 1000)  # Convert to seconds
        if quality_signal is not None:
            scenario.quality_signal_samples.append(quality_signal)

        self._save_state()

    def check_rollback_needed(self, scenario_name: str) -> Optional[str]:
        """
        Check if a promoted scenario needs rollback.
        
        Returns:
            Reason for rollback if needed, None otherwise
        """
        if scenario_name not in self.scenarios:
            return None

        scenario = self.scenarios[scenario_name]
        if scenario.status != WhitelistStatus.PROMOTED:
            return None

        receipt = scenario.promotion_receipt
        if not receipt:
            return None

        thresholds = receipt.rollback_thresholds

        # Check thresholds
        if scenario.wrong_user_guard_trigger_count > thresholds.get("max_wrong_user_guard_trigger_count", 0):
            return f"wrong_user_guard_trigger_count ({scenario.wrong_user_guard_trigger_count}) > threshold"

        if scenario.fallback_rate > thresholds.get("max_fallback_rate", 0.10):
            return f"fallback_rate ({scenario.fallback_rate:.2%}) > threshold"

        if scenario.provider_health_rate < thresholds.get("min_provider_health_rate", 0.95):
            return f"provider_health_rate ({scenario.provider_health_rate:.2%}) < threshold"

        if scenario.p95_latency_ms > thresholds.get("max_p95_latency_ms", 300):
            return f"p95_latency_ms ({scenario.p95_latency_ms:.1f}) > threshold"

        # Check quality signal over multiple rounds
        if len(scenario.quality_signal_samples) >= 2:
            recent_signals = scenario.quality_signal_samples[-3:]
            if all(s <= thresholds.get("min_avg_quality_signal", 0) for s in recent_signals):
                return f"quality_signal <= 0 for {len(recent_signals)} consecutive rounds"

        return None

    def get_observation_report(self, scenario_name: str) -> Dict[str, Any]:
        """Get observation report for a promoted scenario."""
        if scenario_name not in self.scenarios:
            return {}

        scenario = self.scenarios[scenario_name]
        receipt = scenario.promotion_receipt

        return {
            "scenario_name": scenario_name,
            "status": scenario.status.value,
            "request_count": scenario.request_count,
            "success_count": scenario.success_count,
            "fallback_count": scenario.fallback_count,
            "fallback_rate": scenario.fallback_rate,
            "p95_latency_ms": scenario.p95_latency_ms,
            "wrong_user_guard_trigger_count": scenario.wrong_user_guard_trigger_count,
            "provider_health_rate": scenario.provider_health_rate,
            "avg_quality_signal": scenario.avg_quality_signal,
            "observation_rounds": scenario.observation_rounds,
            "promotion_receipt": receipt.to_dict() if receipt else None,
            "rollback_needed": self.check_rollback_needed(scenario_name),
        }

    def _save_receipt(self, receipt: PromotionReceipt) -> None:
        """Save promotion receipt to file."""
        receipt_file = self.storage_path / "promotion_receipt.json"
        receipt_file.write_text(json.dumps(receipt.to_dict(), indent=2))

    def is_in_production_whitelist(self, scenario_name: str) -> bool:
        """Check if a scenario is in production whitelist."""
        if scenario_name not in self.scenarios:
            return False
        return self.scenarios[scenario_name].status == WhitelistStatus.PROMOTED
