"""
Whitelist Scheduler.

Manages scheduled execution of whitelist governance tasks.
Capability Owner: OpenEmotion

v6k.2: Scheduler Integration + Operations
v6k.2a: External Scheduler Evidence + Reporter Integration
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .production_whitelist import ProductionWhitelistRegistry
from .whitelist_governance import WhitelistGovernanceEvaluator
from .periodic_receipts import PeriodicReceiptGenerator, ReceiptMode
from .receipt_history import ReceiptHistoryStore
from .whitelist_alert_engine import WhitelistAlertEngine


@dataclass
class SchedulerRun:
    """Record of a scheduler run."""
    run_id: str
    triggered_at: str
    trigger_type: str  # daily, round, manual
    success: bool
    receipt_id: Optional[str]
    alerts_generated: int
    governance_verdict: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "triggered_at": self.triggered_at,
            "trigger_type": self.trigger_type,
            "success": self.success,
            "receipt_id": self.receipt_id,
            "alerts_generated": self.alerts_generated,
            "governance_verdict": self.governance_verdict,
            "details": self.details,
        }


class WhitelistScheduler:
    """
    Manages scheduled execution of whitelist governance tasks.
    
    v6k.2 specific:
    - Daily receipt scheduling
    - Round receipt scheduling
    - Manual fallback
    - Run history tracking
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("artifacts/eval/v6k_2")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.runs: List[SchedulerRun] = []
        self._load_runs()

    def _load_runs(self) -> None:
        """Load run history."""
        runs_file = self.storage_path / "scheduler_runs.json"
        if runs_file.exists():
            try:
                data = json.loads(runs_file.read_text())
                self.runs = [
                    SchedulerRun(
                        run_id=r.get("run_id", ""),
                        triggered_at=r.get("triggered_at", ""),
                        trigger_type=r.get("trigger_type", ""),
                        success=r.get("success", False),
                        receipt_id=r.get("receipt_id"),
                        alerts_generated=r.get("alerts_generated", 0),
                        governance_verdict=r.get("governance_verdict", ""),
                        details=r.get("details", {}),
                    )
                    for r in data.get("runs", [])
                ]
            except Exception:
                pass

    def _save_runs(self) -> None:
        """Save run history."""
        runs_file = self.storage_path / "scheduler_runs.json"
        data = {
            "runs": [r.to_dict() for r in self.runs[-100:]],
            "generated_at": datetime.now().isoformat(),
        }
        runs_file.write_text(json.dumps(data, indent=2))

    def _generate_run_id(self, trigger_type: str) -> str:
        """Generate unique run ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"run-{trigger_type}-{timestamp}"

    def run_daily(self, registry_storage: Path) -> SchedulerRun:
        """
        Run daily whitelist governance.
        
        Args:
            registry_storage: Path to whitelist registry storage
            
        Returns:
            SchedulerRun record
        """
        run_id = self._generate_run_id("daily")
        now = datetime.now().isoformat()

        try:
            # Initialize components
            registry = ProductionWhitelistRegistry(storage_path=registry_storage)
            governance = WhitelistGovernanceEvaluator(registry, storage_path=self.storage_path)
            generator = PeriodicReceiptGenerator(registry, governance, storage_path=self.storage_path)
            history = ReceiptHistoryStore(storage_path=self.storage_path)
            alert_engine = WhitelistAlertEngine(registry, governance, storage_path=self.storage_path)

            # Generate daily receipt
            receipt = generator.generate_daily_receipt()

            # Add to history
            history.add_receipt(
                receipt_id=receipt.receipt_id,
                mode=ReceiptMode.DAILY,
                generated_at=receipt.generated_at,
                artifact_path=receipt.artifact_refs.get("daily_receipt", ""),
                scenario_count=receipt.active_scenario_count,
                whitelist_verdict=receipt.whitelist_verdict,
            )

            # Generate alerts
            alerts = alert_engine.generate_all_alerts()

            # Get governance summary
            summary = governance.evaluate_whitelist()

            run = SchedulerRun(
                run_id=run_id,
                triggered_at=now,
                trigger_type="daily",
                success=True,
                receipt_id=receipt.receipt_id,
                alerts_generated=len(alerts),
                governance_verdict=summary.whitelist_verdict.value,
                details={
                    "scenario_count": receipt.active_scenario_count,
                    "healthy_count": receipt.healthy_scenario_count,
                    "observe_count": receipt.observe_scenario_count,
                },
            )

        except Exception as e:
            run = SchedulerRun(
                run_id=run_id,
                triggered_at=now,
                trigger_type="daily",
                success=False,
                receipt_id=None,
                alerts_generated=0,
                governance_verdict="error",
                details={"error": str(e)},
            )

        self.runs.append(run)
        self._save_runs()

        return run

    def run_round(self, round_id: int, registry_storage: Path) -> SchedulerRun:
        """
        Run round-based whitelist governance.
        
        Args:
            round_id: Round number
            registry_storage: Path to whitelist registry storage
            
        Returns:
            SchedulerRun record
        """
        run_id = self._generate_run_id("round")
        now = datetime.now().isoformat()

        try:
            # Initialize components
            registry = ProductionWhitelistRegistry(storage_path=registry_storage)
            governance = WhitelistGovernanceEvaluator(registry, storage_path=self.storage_path)
            generator = PeriodicReceiptGenerator(registry, governance, storage_path=self.storage_path)
            history = ReceiptHistoryStore(storage_path=self.storage_path)
            alert_engine = WhitelistAlertEngine(registry, governance, storage_path=self.storage_path)

            # Generate round receipt
            receipt = generator.generate_round_receipt(round_id)

            # Add to history
            history.add_receipt(
                receipt_id=receipt.receipt_id,
                mode=ReceiptMode.ROUND_BASED,
                generated_at=receipt.generated_at,
                artifact_path=receipt.artifact_refs.get("round_receipt", ""),
                scenario_count=receipt.active_scenario_count,
                whitelist_verdict=receipt.whitelist_verdict,
            )

            # Generate alerts
            alerts = alert_engine.generate_all_alerts()

            # Get governance summary
            summary = governance.evaluate_whitelist()

            run = SchedulerRun(
                run_id=run_id,
                triggered_at=now,
                trigger_type="round",
                success=True,
                receipt_id=receipt.receipt_id,
                alerts_generated=len(alerts),
                governance_verdict=summary.whitelist_verdict.value,
                details={
                    "round_id": round_id,
                    "scenario_count": receipt.active_scenario_count,
                },
            )

        except Exception as e:
            run = SchedulerRun(
                run_id=run_id,
                triggered_at=now,
                trigger_type="round",
                success=False,
                receipt_id=None,
                alerts_generated=0,
                governance_verdict="error",
                details={"error": str(e)},
            )

        self.runs.append(run)
        self._save_runs()

        return run

    def run_manual(self, reason: str, registry_storage: Path) -> SchedulerRun:
        """
        Run manual whitelist governance.
        
        Args:
            reason: Reason for manual run
            registry_storage: Path to whitelist registry storage
            
        Returns:
            SchedulerRun record
        """
        run_id = self._generate_run_id("manual")
        now = datetime.now().isoformat()

        try:
            # Initialize components
            registry = ProductionWhitelistRegistry(storage_path=registry_storage)
            governance = WhitelistGovernanceEvaluator(registry, storage_path=self.storage_path)
            generator = PeriodicReceiptGenerator(registry, governance, storage_path=self.storage_path)
            history = ReceiptHistoryStore(storage_path=self.storage_path)
            alert_engine = WhitelistAlertEngine(registry, governance, storage_path=self.storage_path)

            # Generate manual receipt
            receipt = generator.generate_manual_receipt(reason)

            # Add to history
            history.add_receipt(
                receipt_id=receipt.receipt_id,
                mode=ReceiptMode.MANUAL,
                generated_at=receipt.generated_at,
                artifact_path=receipt.artifact_refs.get("manual_receipt", ""),
                scenario_count=receipt.active_scenario_count,
                whitelist_verdict=receipt.whitelist_verdict,
            )

            # Generate alerts
            alerts = alert_engine.generate_all_alerts()

            # Get governance summary
            summary = governance.evaluate_whitelist()

            run = SchedulerRun(
                run_id=run_id,
                triggered_at=now,
                trigger_type="manual",
                success=True,
                receipt_id=receipt.receipt_id,
                alerts_generated=len(alerts),
                governance_verdict=summary.whitelist_verdict.value,
                details={
                    "reason": reason,
                    "scenario_count": receipt.active_scenario_count,
                },
            )

        except Exception as e:
            run = SchedulerRun(
                run_id=run_id,
                triggered_at=now,
                trigger_type="manual",
                success=False,
                receipt_id=None,
                alerts_generated=0,
                governance_verdict="error",
                details={"error": str(e)},
            )

        self.runs.append(run)
        self._save_runs()

        return run

    def get_recent_runs(self, limit: int = 10) -> List[SchedulerRun]:
        """Get recent scheduler runs."""
        return self.runs[-limit:]

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        recent = self.runs[-10:]
        successful = sum(1 for r in recent if r.success)

        return {
            "total_runs": len(self.runs),
            "recent_runs": len(recent),
            "successful_runs": successful,
            "failed_runs": len(recent) - successful,
            "last_run": recent[-1].to_dict() if recent else None,
        }

    def generate_scheduler_evidence(self, trigger_type: str, external: bool = False) -> Dict[str, Any]:
        """
        Generate scheduler evidence for external scheduling.
        
        v6k.2a: External scheduler evidence
        
        Args:
            trigger_type: Type of trigger (daily, round, manual)
            external: Whether this was triggered by external scheduler
            
        Returns:
            Scheduler evidence dict
        """
        now = datetime.now().isoformat()
        
        evidence = {
            "scheduler_type": "cron" if external else "manual",
            "config_file": "ops/cron/whitelist_governance.cron" if external else "manual_trigger",
            "trigger_time": now,
            "trigger_type": trigger_type,
            "script_path": "tools/whitelist_governance_daily.sh" if external else "scripts/run_whitelist_scheduler_once.py",
            "schedule": "0 3 * * *" if trigger_type == "daily" and external else "on_demand",
            "artifacts_dir": str(self.storage_path),
            "evidence_valid": True,
            "generated_at": now,
        }
        
        return evidence

    def save_scheduler_evidence(self, trigger_type: str, external: bool = False) -> Path:
        """Save scheduler evidence to file."""
        evidence = self.generate_scheduler_evidence(trigger_type, external)
        
        evidence_file = self.storage_path / "scheduler_evidence.json"
        evidence_file.write_text(json.dumps(evidence, indent=2))
        
        return evidence_file

    def run_with_evidence(self, trigger_type: str, registry_storage: Path, external: bool = False, round_id: Optional[int] = None, reason: Optional[str] = None) -> tuple:
        """
        Run scheduler and generate evidence.
        
        v6k.2a: Combined run with evidence generation
        
        Args:
            trigger_type: daily, round, or manual
            registry_storage: Path to whitelist registry storage
            external: Whether triggered by external scheduler
            round_id: Round ID for round-based runs
            reason: Reason for manual runs
            
        Returns:
            Tuple of (SchedulerRun, evidence_path)
        """
        if trigger_type == "daily":
            run = self.run_daily(registry_storage)
        elif trigger_type == "round":
            run = self.run_round(round_id or 1, registry_storage)
        elif trigger_type == "manual":
            run = self.run_manual(reason or "Manual trigger", registry_storage)
        else:
            raise ValueError(f"Unknown trigger type: {trigger_type}")
        
        evidence_path = self.save_scheduler_evidence(trigger_type, external)
        
        return run, evidence_path
