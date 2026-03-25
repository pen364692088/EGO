#!/usr/bin/env python3
"""
MVP16 Anomaly Handler

Called when daily check detects an anomaly.
Generates blocker package and escalation report.
"""
import sys
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.developmental import get_developmental_manager, reset_developmental_manager


def generate_blocker_package(anomaly_type: str, details: dict) -> str:
    """Generate a blocker package for the anomaly."""
    timestamp = datetime.now().isoformat()
    day_num = (datetime.now() - datetime(2026, 3, 12)).days + 1
    
    report = f"""# MVP16 Anomaly Report

**Timestamp**: {timestamp}
**Day**: {day_num}
**Type**: {anomaly_type}

## Summary
{details.get('summary', 'Anomaly detected during observation check')}

## Metrics at Detection
"""
    
    for key, value in details.get('metrics', {}).items():
        status = "⚠️" if value.get('alert') else "✅"
        report += f"- {status} {key}: {value.get('value')}\n"
    
    report += f"""
## Root Cause Analysis
- **Primary Cause**: {details.get('root_cause', 'Unknown - requires investigation')}
- **Contributing Factors**: {details.get('factors', ['TBD'])}
- **Evidence**: {details.get('evidence', ['TBD'])}

## Impact Assessment
- **Scope**: {details.get('scope', 'TBD')}
- **Severity**: {details.get('severity', 'TBD')}
- **Trend**: {details.get('trend', 'TBD')}

## Rollback Assessment
- **Need Rollback**: {details.get('need_rollback', 'TBD')}
- **Rollback Target**: {details.get('rollback_target', 'N/A')}
- **Rollback Risk**: {details.get('rollback_risk', 'TBD')}

## Minimal Fix Chain
"""
    
    for i, step in enumerate(details.get('fix_chain', ['TBD']), 1):
        report += f"{i}. {step}\n"
    
    report += f"""
## Next Actions
1. Review this report
2. Investigate root cause
3. Apply minimal fix or rollback
4. Re-run daily check
5. Resume observation if stable

---
**Status**: BLOCKER - Requires human review
"""
    
    return report


def check_and_handle_anomaly() -> dict:
    """Check for anomalies and generate blocker if needed."""
    reset_developmental_manager()
    manager = get_developmental_manager()
    
    anomalies = []
    details = {
        'metrics': {},
        'summary': '',
        'root_cause': 'Unknown',
        'factors': [],
        'evidence': [],
        'scope': '',
        'severity': 'warning',
        'trend': 'stable',
        'need_rollback': 'TBD',
        'rollback_target': 'N/A',
        'rollback_risk': 'low',
        'fix_chain': ['Investigate', 'Fix', 'Verify']
    }
    
    # Check each metric
    for name, metric in manager.state.metrics.items():
        value = metric.value
        alert = False
        
        if name == 'continuity_score' and value < 0.8:
            alert = True
            anomalies.append(f"continuity_score ({value:.2f}) < 0.8")
        if name == 'identity_stability' and value < 0.95:
            alert = True
            anomalies.append(f"identity_stability ({value:.2f}) < 0.95")
        if name == 'governance_compliance' and value < 1.0:
            alert = True
            anomalies.append(f"governance_compliance ({value:.2f}) < 1.0")
        
        details['metrics'][name] = {'value': value, 'alert': alert}
    
    # Check invariants
    if not manager.check_identity_preservation():
        anomalies.append("identity_preserved = False")
        details['metrics']['identity_preserved'] = {'value': False, 'alert': True}
    
    if anomalies:
        details['summary'] = "; ".join(anomalies)
        
        if len(anomalies) > 1:
            details['severity'] = 'critical'
        if any('governance' in a for a in anomalies):
            details['severity'] = 'emergency'
        
        # Generate blocker package
        report = generate_blocker_package(
            anomaly_type=details['severity'].upper(),
            details=details
        )
        
        # Save blocker
        day_num = (datetime.now() - datetime(2026, 3, 12)).days + 1
        output_dir = Path(__file__).parent.parent / "artifacts" / "mvp16-observation"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        blocker_path = output_dir / f"blocker_day{day_num}.md"
        blocker_path.write_text(report)
        
        # Write ALERT file
        alert_path = output_dir / "ALERT.txt"
        alert_path.write_text(f"[{datetime.now().isoformat()}] {details['severity'].upper()}: {details['summary']}\n")
        
        return {
            'status': 'BLOCKER',
            'anomalies': anomalies,
            'severity': details['severity'],
            'blocker_path': str(blocker_path)
        }
    
    return {'status': 'OK', 'anomalies': [], 'severity': 'none'}


def main():
    result = check_and_handle_anomaly()
    print(json.dumps(result, indent=2))
    
    if result['status'] == 'BLOCKER':
        print(f"\n⚠️ BLOCKER DETECTED")
        print(f"Severity: {result['severity']}")
        print(f"Blocker: {result['blocker_path']}")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
