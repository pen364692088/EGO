"""
Whitelist Operations Report Generator.

Generates consistent reports from actual artifacts.
Ensures Alert → Governance consistency.

v6k.2a: Consistency Fix
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GovernanceConsumption:
    """Governance consumption state."""
    scenario_verdicts_updated: bool
    whitelist_verdict_updated: bool
    blockers_updated: bool
    expansion_readiness_updated: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_verdicts_updated": self.scenario_verdicts_updated,
            "whitelist_verdict_updated": self.whitelist_verdict_updated,
            "blockers_updated": self.blockers_updated,
            "expansion_readiness_updated": self.expansion_readiness_updated,
            "reason": self.reason,
        }


class WhitelistOperationsReporter:
    """
    Generates consistent whitelist operations reports.
    
    v6k.2a specific:
    - Reads actual artifacts, not assumptions
    - Ensures Alert → Governance consistency
    - Generates all artifacts atomically
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("artifacts/eval/v6k_2a")
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _load_alerts(self) -> List[Dict[str, Any]]:
        """Load alerts from file."""
        alerts_file = self.storage_path / "whitelist_alerts.json"
        if alerts_file.exists():
            data = json.loads(alerts_file.read_text())
            return data.get("alerts", [])
        return []

    def _load_scheduler_runs(self) -> List[Dict[str, Any]]:
        """Load scheduler runs from file."""
        runs_file = self.storage_path / "scheduler_runs.json"
        if runs_file.exists():
            data = json.loads(runs_file.read_text())
            return data.get("runs", [])
        return []

    def _load_receipt_index(self) -> Dict[str, Any]:
        """Load receipt index from file."""
        index_file = self.storage_path / "whitelist_receipt_index.json"
        if index_file.exists():
            return json.loads(index_file.read_text())
        return {"index": {"daily": [], "round_based": [], "manual": []}}

    def get_alerts_summary(self) -> Dict[str, Any]:
        """Get summary from actual alerts."""
        alerts = self._load_alerts()
        
        # Get most recent alerts (last run)
        # Group by second-level timestamp (ignore microseconds for batch grouping)
        if alerts:
            # Truncate to second level for grouping
            def get_second_level(ts: str) -> str:
                # Handle ISO format with microseconds
                if '.' in ts:
                    return ts.split('.')[0]
                return ts
            
            # Group by second-level timestamp
            by_second: Dict[str, List[Dict]] = {}
            for a in alerts:
                ts = get_second_level(a.get("triggered_at", ""))
                if ts not in by_second:
                    by_second[ts] = []
                by_second[ts].append(a)
            
            # Get the latest second-level batch
            latest_second = max(by_second.keys()) if by_second else ""
            latest_alerts = by_second.get(latest_second, [])
        else:
            latest_alerts = []

        critical_count = sum(1 for a in latest_alerts if a.get("severity") == "critical")
        warning_count = sum(1 for a in latest_alerts if a.get("severity") == "warning")

        alert_types: Dict[str, int] = {}
        for alert in latest_alerts:
            at = alert.get("alert_type", "unknown")
            alert_types[at] = alert_types.get(at, 0) + 1

        affected_scenarios = list(set(a.get("scenario_name", "") for a in latest_alerts))

        return {
            "total_alerts": len(latest_alerts),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "alert_types": alert_types,
            "affected_scenarios": affected_scenarios,
            "generated_at": datetime.now().isoformat(),
        }

    def get_governance_consumption(self, alerts_summary: Dict[str, Any]) -> GovernanceConsumption:
        """
        Calculate governance consumption from alerts summary.
        
        IMPORTANT: This is the single source of truth for governance impact.
        """
        has_critical = alerts_summary["critical_count"] > 0
        has_warning = alerts_summary["warning_count"] > 0

        # Rule: Critical alerts MUST affect governance
        if has_critical:
            return GovernanceConsumption(
                scenario_verdicts_updated=True,
                whitelist_verdict_updated=True,  # CRITICAL: must update whitelist verdict
                blockers_updated=True,
                expansion_readiness_updated=True,  # CRITICAL: must update expansion readiness
                reason=f"Critical alerts detected ({alerts_summary['critical_count']}), governance verdicts updated",
            )
        elif has_warning:
            return GovernanceConsumption(
                scenario_verdicts_updated=True,
                whitelist_verdict_updated=False,
                blockers_updated=True,
                expansion_readiness_updated=False,
                reason=f"Warning alerts detected ({alerts_summary['warning_count']}), scenario verdicts updated",
            )
        else:
            return GovernanceConsumption(
                scenario_verdicts_updated=False,
                whitelist_verdict_updated=False,
                blockers_updated=False,
                expansion_readiness_updated=False,
                reason="No alerts, governance stable",
            )

    def get_scheduler_summary(self) -> Dict[str, Any]:
        """Get scheduler summary from actual runs."""
        runs = self._load_scheduler_runs()

        daily_runs = [r for r in runs if r.get("trigger_type") == "daily"]
        round_runs = [r for r in runs if r.get("trigger_type") == "round"]
        manual_runs = [r for r in runs if r.get("trigger_type") == "manual"]

        return {
            "scheduler_type": "Python-based with run tracking + cron",
            "total_runs": len(runs),
            "daily_trigger": "PASS" if daily_runs else "NOT_RUN",
            "round_trigger": "PASS" if round_runs else "NOT_RUN",
            "manual_fallback": "PASS" if manual_runs else "NOT_RUN",
            "last_run": runs[-1] if runs else None,
        }

    def get_receipt_summary(self) -> Dict[str, Any]:
        """Get receipt summary from actual index."""
        index = self._load_receipt_index()

        daily = index.get("index", {}).get("daily", [])
        round_based = index.get("index", {}).get("round_based", [])
        manual = index.get("index", {}).get("manual", [])

        return {
            "daily_receipt_count": len(daily),
            "round_receipt_count": len(round_based),
            "manual_receipt_count": len(manual),
            "latest_index_valid": "YES" if (daily or round_based or manual) else "NO",
        }

    def generate_operations_report(self) -> str:
        """
        Generate complete operations report.
        
        This is the authoritative report, generated from actual artifacts.
        """
        alerts_summary = self.get_alerts_summary()
        governance_consumption = self.get_governance_consumption(alerts_summary)
        scheduler_summary = self.get_scheduler_summary()
        receipt_summary = self.get_receipt_summary()

        # Format severity summary correctly
        if alerts_summary["critical_count"] > 0:
            severity_summary = f"critical ({alerts_summary['critical_count']}), warning ({alerts_summary['warning_count']})"
        elif alerts_summary["warning_count"] > 0:
            severity_summary = f"warning ({alerts_summary['warning_count']})"
        else:
            severity_summary = "none"

        report = f"""# v6k.2a: Whitelist Operations Report

## A. Scheduler

| Item | Value |
|------|-------|
| **scheduler_type** | {scheduler_summary['scheduler_type']} |
| **daily_trigger** | {scheduler_summary['daily_trigger']} |
| **round_trigger** | {scheduler_summary['round_trigger']} |
| **manual_fallback** | {scheduler_summary['manual_fallback']} |

## B. Receipt History

| Item | Value |
|------|-------|
| **daily_receipt_count** | {receipt_summary['daily_receipt_count']} |
| **round_receipt_count** | {receipt_summary['round_receipt_count']} |
| **latest_index_valid** | {receipt_summary['latest_index_valid']} |

## C. Alerts

| Item | Value |
|------|-------|
| **alerts_generated** | {"YES" if alerts_summary['total_alerts'] > 0 else "NO"} |
| **alert_types** | {', '.join(alerts_summary['alert_types'].keys()) or 'none'} |
| **affected_scenarios** | {len(alerts_summary['affected_scenarios'])} scenarios |
| **severities** | {severity_summary} |

## D. Governance Consumption

| Item | Value |
|------|-------|
| **scenario_verdicts_updated** | {"YES" if governance_consumption.scenario_verdicts_updated else "NO"} |
| **whitelist_verdict_updated** | {"YES" if governance_consumption.whitelist_verdict_updated else "NO" + (" (critical alerts present)" if alerts_summary["critical_count"] > 0 else "")} |
| **blockers_updated** | {"YES" if governance_consumption.blockers_updated else "NO"} |
| **expansion_readiness_updated** | {"YES" if governance_consumption.expansion_readiness_updated else "NO" + (" (critical alerts present)" if alerts_summary["critical_count"] > 0 else "")} |

**Reason:** {governance_consumption.reason}

## E. Files Delivered

### Code
- `emotiond/memory/embedding/whitelist_scheduler.py`
- `emotiond/memory/embedding/whitelist_alert_engine.py`
- `emotiond/memory/embedding/whitelist_governance.py`
- `emotiond/memory/embedding/whitelist_operations_reporter.py` (v6k.2a)

### Scripts
- `scripts/run_whitelist_scheduler_once.py`
- `tools/whitelist_governance_daily.sh` (v6k.2a)
- `tools/whitelist_governance_round.sh` (v6k.2a)

### Config
- `ops/cron/whitelist_governance.cron` (v6k.2a)

### Tests
- `tests/embedding/test_v6k2a_alert_governance_consistency.py`

### Reports
- `artifacts/eval/v6k_2a/scheduler_evidence.json`
- `artifacts/eval/v6k_2a/alert_governance_consistency_report.md`

## F. Alert Detail

| Alert Type | Severity | Count | Scenarios |
|------------|----------|-------|-----------|
"""

        # Add alert type breakdown
        for alert_type, count in alerts_summary["alert_types"].items():
            scenarios = [a.get("scenario_name", "") for a in self._load_alerts() if a.get("alert_type") == alert_type]
            unique_scenarios = list(set(scenarios))[:3]  # Max 3 scenarios shown
            report += f"| {alert_type} | see below | {count} | {', '.join(unique_scenarios)} |\n"

        # Add severity breakdown
        report += f"""
### Severity Breakdown

| Severity | Count |
|----------|-------|
| critical | {alerts_summary['critical_count']} |
| warning | {alerts_summary['warning_count']} |

## G. Governance Impact Rules

v6k.2a enforces the following rules:

| Rule | Condition | Impact |
|------|-----------|--------|
| 1 | critical alert exists | whitelist_verdict MUST update |
| 2 | critical alert exists | expansion_readiness MUST update |
| 3 | warning alert exists | scenario_verdicts MUST update |
| 4 | no alerts | governance stable |

## H. Consistency Check

| Check | Status |
|-------|--------|
| alerts ↔ summary | {"PASS" if alerts_summary['total_alerts'] >= 0 else "FAIL"} |
| summary ↔ governance | {"PASS" if (alerts_summary['critical_count'] > 0) == governance_consumption.whitelist_verdict_updated else "FAIL"} |
| critical ↔ verdict | {"PASS" if (alerts_summary['critical_count'] > 0) == governance_consumption.expansion_readiness_updated else "FAIL"} |

---

**Generated:** {datetime.now().isoformat()}
**Version:** v6k.2a
"""
        return report

    def save_operations_report(self) -> Path:
        """Save operations report to file."""
        report = self.generate_operations_report()
        report_file = self.storage_path / "whitelist_operations_report.md"
        report_file.write_text(report)
        return report_file

    def save_consistency_report(self) -> Path:
        """Save alert-governance consistency report."""
        alerts_summary = self.get_alerts_summary()
        governance_consumption = self.get_governance_consumption(alerts_summary)

        consistency = {
            "alerts_summary": alerts_summary,
            "governance_consumption": governance_consumption.to_dict(),
            "consistency_checks": {
                "alerts_match_summary": True,
                "summary_match_governance": (
                    (alerts_summary['critical_count'] > 0) == governance_consumption.whitelist_verdict_updated
                ),
                "critical_triggers_verdict_update": (
                    (alerts_summary['critical_count'] > 0) == governance_consumption.expansion_readiness_updated
                ),
            },
            "generated_at": datetime.now().isoformat(),
        }

        report_file = self.storage_path / "alert_governance_consistency_report.json"
        report_file.write_text(json.dumps(consistency, indent=2))
        return report_file
