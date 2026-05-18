"""
Periodic Receipts.

Automatic generation of periodic receipts for whitelist governance.
Capability Owner: OpenEmotion

v6k: Periodic Receipts + Daily/Round-based/Manual triggers
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .production_whitelist import ProductionWhitelistRegistry
from .whitelist_governance import (
    WhitelistGovernanceEvaluator,
    ScenarioVerdict,
    WhitelistVerdict,
    ExpansionReadiness,
)


class ReceiptMode(str, Enum):
    """Mode of receipt generation."""
    DAILY = "daily"
    ROUND_BASED = "round_based"
    MANUAL = "manual"


@dataclass
class WhitelistReceipt:
    """Periodic receipt for whitelist governance."""
    receipt_version: str = "v6k-v1"
    receipt_id: str = ""
    mode: ReceiptMode = ReceiptMode.MANUAL
    generated_at: str = ""
    generated_timestamp: float = 0.0
    period_start: str = ""
    period_end: str = ""
    generation_mode: str = ""

    # Whitelist-level fields
    active_scenario_count: int = 0
    healthy_scenario_count: int = 0
    observe_scenario_count: int = 0
    demote_candidate_count: int = 0
    rollback_candidate_count: int = 0
    whitelist_verdict: str = ""
    expansion_readiness: str = ""
    blockers: List[str] = field(default_factory=list)

    # Per-scenario metrics
    scenario_metrics: List[Dict[str, Any]] = field(default_factory=list)

    # Guard summary
    guard_summary: Dict[str, Any] = field(default_factory=dict)

    # Artifact references
    artifact_refs: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_version": self.receipt_version,
            "receipt_id": self.receipt_id,
            "mode": self.mode.value,
            "generated_at": self.generated_at,
            "generated_timestamp": self.generated_timestamp,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "generation_mode": self.generation_mode,
            "active_scenario_count": self.active_scenario_count,
            "healthy_scenario_count": self.healthy_scenario_count,
            "observe_scenario_count": self.observe_scenario_count,
            "demote_candidate_count": self.demote_candidate_count,
            "rollback_candidate_count": self.rollback_candidate_count,
            "whitelist_verdict": self.whitelist_verdict,
            "expansion_readiness": self.expansion_readiness,
            "blockers": self.blockers,
            "scenario_metrics": self.scenario_metrics,
            "guard_summary": self.guard_summary,
            "artifact_refs": self.artifact_refs,
        }


class PeriodicReceiptGenerator:
    """
    Generates periodic receipts for whitelist governance.
    
    v6k specific:
    - Daily receipts
    - Round-based receipts
    - Manual trigger receipts
    - Structured artifact generation
    """

    def __init__(
        self,
        registry: ProductionWhitelistRegistry,
        governance_evaluator: WhitelistGovernanceEvaluator,
        storage_path: Optional[Path] = None,
    ):
        self.registry = registry
        self.governance = governance_evaluator
        self.storage_path = storage_path or Path("artifacts/eval/v6k")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.receipts: List[WhitelistReceipt] = []
        self._load_receipts()

    def _load_receipts(self) -> None:
        """Load existing receipts from storage."""
        receipts_file = self.storage_path / "receipts_history.json"
        if receipts_file.exists():
            try:
                data = json.loads(receipts_file.read_text())
                self.receipts = [
                    WhitelistReceipt(
                        receipt_version=r.get("receipt_version", "v6k-v1"),
                        receipt_id=r.get("receipt_id", ""),
                        mode=ReceiptMode(r.get("mode", "manual")),
                        generated_at=r.get("generated_at", ""),
                        generated_timestamp=r.get("generated_timestamp", 0),
                        period_start=r.get("period_start", ""),
                        period_end=r.get("period_end", ""),
                        generation_mode=r.get("generation_mode", ""),
                        active_scenario_count=r.get("active_scenario_count", 0),
                        healthy_scenario_count=r.get("healthy_scenario_count", 0),
                        observe_scenario_count=r.get("observe_scenario_count", 0),
                        demote_candidate_count=r.get("demote_candidate_count", 0),
                        rollback_candidate_count=r.get("rollback_candidate_count", 0),
                        whitelist_verdict=r.get("whitelist_verdict", ""),
                        expansion_readiness=r.get("expansion_readiness", ""),
                        blockers=r.get("blockers", []),
                        scenario_metrics=r.get("scenario_metrics", []),
                        guard_summary=r.get("guard_summary", {}),
                        artifact_refs=r.get("artifact_refs", {}),
                    )
                    for r in data.get("receipts", [])
                ]
            except Exception:
                pass

    def _save_receipts(self) -> None:
        """Save receipts to storage."""
        receipts_file = self.storage_path / "receipts_history.json"
        data = {
            "receipts": [r.to_dict() for r in self.receipts[-100:]],  # Keep last 100
        }
        receipts_file.write_text(json.dumps(data, indent=2))

    def _generate_receipt_id(self, mode: ReceiptMode) -> str:
        """Generate unique receipt ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"whitelist-receipt-{mode.value}-{timestamp}"

    def generate_daily_receipt(self) -> WhitelistReceipt:
        """
        Generate daily receipt.
        
        Returns:
            WhitelistReceipt for the day
        """
        now = datetime.now()
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=1)

        receipt = self._generate_receipt(
            mode=ReceiptMode.DAILY,
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
        )

        # Save daily receipt
        receipt_file = self.storage_path / f"whitelist_receipt_daily_{now.strftime('%Y%m%d')}.json"
        receipt_file.write_text(json.dumps(receipt.to_dict(), indent=2))
        receipt.artifact_refs["daily_receipt"] = str(receipt_file)

        self.receipts.append(receipt)
        self._save_receipts()

        return receipt

    def generate_round_receipt(self, round_id: int) -> WhitelistReceipt:
        """
        Generate round-based receipt.
        
        Args:
            round_id: Observation round ID
            
        Returns:
            WhitelistReceipt for the round
        """
        now = datetime.now()

        receipt = self._generate_receipt(
            mode=ReceiptMode.ROUND_BASED,
            period_start=now.isoformat(),
            period_end=now.isoformat(),
            extra_data={"round_id": round_id},
        )

        # Save round receipt
        receipt_file = self.storage_path / f"whitelist_receipt_round_{round_id}.json"
        receipt_file.write_text(json.dumps(receipt.to_dict(), indent=2))
        receipt.artifact_refs["round_receipt"] = str(receipt_file)

        self.receipts.append(receipt)
        self._save_receipts()

        return receipt

    def generate_manual_receipt(self, reason: str = "") -> WhitelistReceipt:
        """
        Generate manual trigger receipt.
        
        Args:
            reason: Reason for manual generation
            
        Returns:
            WhitelistReceipt
        """
        now = datetime.now()

        receipt = self._generate_receipt(
            mode=ReceiptMode.MANUAL,
            period_start=now.isoformat(),
            period_end=now.isoformat(),
            extra_data={"manual_reason": reason},
        )

        # Save manual receipt
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        receipt_file = self.storage_path / f"whitelist_receipt_manual_{timestamp}.json"
        receipt_file.write_text(json.dumps(receipt.to_dict(), indent=2))
        receipt.artifact_refs["manual_receipt"] = str(receipt_file)

        self.receipts.append(receipt)
        self._save_receipts()

        return receipt

    def _generate_receipt(
        self,
        mode: ReceiptMode,
        period_start: str,
        period_end: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> WhitelistReceipt:
        """Generate receipt from current state."""
        now = datetime.now()
        governance_summary = self.governance.evaluate_whitelist()

        # Build scenario metrics
        scenario_metrics = []
        for state in governance_summary.scenario_states:
            scenario_metrics.append({
                "scenario_name": state.scenario_name,
                "request_count": state.request_count,
                "fallback_rate": state.fallback_rate,
                "p95_latency_ms": state.p95_latency_ms,
                "wrong_user_guard_trigger_count": state.wrong_user_guard_trigger_count,
                "provider_health_rate": state.provider_health_rate,
                "quality_gain_signal": state.quality_gain_signal,
                "scenario_verdict": state.verdict.value,
            })

        receipt = WhitelistReceipt(
            receipt_version="v6k-v1",
            receipt_id=self._generate_receipt_id(mode),
            mode=mode,
            generated_at=now.isoformat(),
            generated_timestamp=time.time(),
            period_start=period_start,
            period_end=period_end,
            generation_mode=mode.value,
            active_scenario_count=governance_summary.active_scenario_count,
            healthy_scenario_count=governance_summary.healthy_scenario_count,
            observe_scenario_count=governance_summary.observe_scenario_count,
            demote_candidate_count=governance_summary.demote_candidate_count,
            rollback_candidate_count=governance_summary.rollback_candidate_count,
            whitelist_verdict=governance_summary.whitelist_verdict.value,
            expansion_readiness=governance_summary.expansion_readiness.value,
            blockers=governance_summary.blockers,
            scenario_metrics=scenario_metrics,
        )

        if extra_data:
            receipt.guard_summary = extra_data

        return receipt

    def get_latest_receipt(self) -> Optional[WhitelistReceipt]:
        """Get the most recent receipt."""
        if not self.receipts:
            return None
        return self.receipts[-1]

    def get_receipts_by_mode(self, mode: ReceiptMode) -> List[WhitelistReceipt]:
        """Get all receipts of a specific mode."""
        return [r for r in self.receipts if r.mode == mode]

    def get_receipt_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get receipt history."""
        return [r.to_dict() for r in self.receipts[-limit:]]
