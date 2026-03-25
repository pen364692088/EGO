#!/usr/bin/env python
"""
MVP15 Funnel Trend Tracker

Tracks MVP15 reflection funnel metrics over multiple days for post-fix validation.

Funnel stages:
    events_seen → eligible_for_reflection → reflection_invoked → artifact_generated → artifact_persisted

Usage:
    python tools/mvp15_funnel_tracker.py --day 1 --record
    python tools/mvp15_funnel_tracker.py --day 2 --record
    python tools/mvp15_funnel_tracker.py --report
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


TRACKER_DIR = Path("artifacts/mvp15/tracker")
TRACKER_DIR.mkdir(parents=True, exist_ok=True)


def record_day_metrics(day: int, notes: str = "") -> Dict[str, Any]:
    """Record funnel metrics for a specific day."""
    
    try:
        from emotiond.reflection_shadow import get_reflection_shadow
        
        shadow = get_reflection_shadow()
        metrics = shadow.get_metrics()
        
        record = {
            "day": day,
            "timestamp": datetime.now().isoformat(),
            "notes": notes,
            "funnel": metrics["funnel"],
            "funnel_rates": metrics["funnel_rates"],
            "artifacts_generated": metrics["artifacts_generated"],
            "call_count": metrics["call_count"],
            "error_count": metrics["error_count"],
        }
        
        # Save record
        record_path = TRACKER_DIR / f"day_{day}.json"
        with open(record_path, "w") as f:
            json.dump(record, f, indent=2)
        
        print(f"✅ Day {day} metrics recorded to {record_path}")
        return record
        
    except Exception as e:
        print(f"❌ Error recording metrics: {e}")
        return {"error": str(e)}


def load_day_metrics(day: int) -> Optional[Dict[str, Any]]:
    """Load metrics for a specific day."""
    record_path = TRACKER_DIR / f"day_{day}.json"
    if not record_path.exists():
        return None
    
    with open(record_path) as f:
        return json.load(f)


def load_all_metrics() -> List[Dict[str, Any]]:
    """Load all recorded metrics."""
    records = []
    for i in range(1, 8):
        record = load_day_metrics(i)
        if record:
            records.append(record)
    return records


def generate_trend_report() -> str:
    """Generate 3-day funnel trend report."""
    
    records = load_all_metrics()
    
    if not records:
        return "# MVP15 Funnel Trend Report\n\nNo data recorded yet.\n"
    
    report = f"""# MVP15 Funnel Trend Report - 3 Day Validation

> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> Validation Period: Day 1-3 post-fix

---

## 1. Funnel Metrics Summary

| Day | events_seen | eligible | invoked | generated | persisted | Timestamp |
|-----|-------------|----------|---------|-----------|-----------|-----------|
"""
    
    for r in records:
        f = r["funnel"]
        report += f"| {r['day']} | {f['events_seen']} | {f['eligible_for_reflection']} | {f['reflection_invoked']} | {f['artifact_generated']} | {f['artifact_persisted']} | {r['timestamp'][:10]} |\n"
    
    report += """
---

## 2. Conversion Rates by Day

| Day | Eligibility | Invocation | Generation | Persistence | E2E Rate |
|-----|-------------|------------|------------|-------------|----------|
"""
    
    for r in records:
        rates = r["funnel_rates"]
        report += f"| {r['day']} | {rates['eligibility_rate']:.1%} | {rates['invocation_rate']:.1%} | {rates['generation_rate']:.1%} | {rates['persistence_rate']:.1%} | {rates['end_to_end_rate']:.1%} |\n"
    
    # Calculate trends
    if len(records) >= 2:
        report += """
---

## 3. Trend Analysis

### 3.1 Daily Change

"""
        for i in range(1, len(records)):
            prev = records[i-1]["funnel"]
            curr = records[i]["funnel"]
            
            events_delta = curr["events_seen"] - prev["events_seen"]
            persisted_delta = curr["artifact_persisted"] - prev["artifact_persisted"]
            
            report += f"**Day {i} → Day {i+1}:**\n"
            report += f"- Events seen: +{events_delta}\n"
            report += f"- Artifacts persisted: +{persisted_delta}\n\n"
    
    # Aggregate stats
    total_events = sum(r["funnel"]["events_seen"] for r in records)
    total_persisted = sum(r["funnel"]["artifact_persisted"] for r in records)
    
    report += f"""
---

## 4. Aggregate Statistics

| Metric | Value |
|--------|-------|
| Total days recorded | {len(records)} |
| Total events seen | {total_events} |
| Total artifacts persisted | {total_persisted} |
| Aggregate E2E rate | {total_persisted / max(1, total_events):.1%} |

---

## 5. Validation Status

"""
    
    # Check validation criteria
    issues = []
    
    if total_events == 0:
        issues.append("⚠️ No events recorded - shadow not receiving events")
    
    if total_persisted == 0:
        issues.append("❌ No artifacts persisted - persistence may be failing")
    
    # Check for anomalies
    for r in records:
        if r["error_count"] > 0:
            issues.append(f"⚠️ Day {r['day']}: {r['error_count']} errors recorded")
    
    if issues:
        report += "**Issues Found:**\n\n"
        for issue in issues:
            report += f"- {issue}\n"
    else:
        report += "✅ No issues detected. Funnel operating normally.\n"
    
    report += """
---

## 6. Notes

"""
    for r in records:
        if r.get("notes"):
            report += f"- Day {r['day']}: {r['notes']}\n"
    
    return report


def main():
    parser = argparse.ArgumentParser(description="MVP15 Funnel Trend Tracker")
    parser.add_argument("--day", type=int, help="Day number to record")
    parser.add_argument("--record", action="store_true", help="Record metrics for the day")
    parser.add_argument("--report", action="store_true", help="Generate trend report")
    parser.add_argument("--notes", type=str, default="", help="Notes for the day")
    args = parser.parse_args()
    
    if args.record and args.day:
        record = record_day_metrics(args.day, args.notes)
        print("\nRecorded metrics:")
        print(json.dumps(record, indent=2))
    
    elif args.report:
        report = generate_trend_report()
        print(report)
        
        # Save report
        report_path = TRACKER_DIR / "MVP15_FUNNEL_TREND_3D.md"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")
    
    else:
        # Default: show current metrics
        try:
            from emotiond.reflection_shadow import get_reflection_shadow
            shadow = get_reflection_shadow()
            metrics = shadow.get_metrics()
            
            print("=== Current MVP15 Funnel Metrics ===\n")
            print(f"Events seen: {metrics['funnel']['events_seen']}")
            print(f"Eligible: {metrics['funnel']['eligible_for_reflection']}")
            print(f"Invoked: {metrics['funnel']['reflection_invoked']}")
            print(f"Generated: {metrics['funnel']['artifact_generated']}")
            print(f"Persisted: {metrics['funnel']['artifact_persisted']}")
            print(f"\nArtifacts on disk: {metrics['artifacts_generated']}")
            
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
