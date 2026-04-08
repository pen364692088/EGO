#!/usr/bin/env python3
"""
MVP15 Trigger Funnel Check

Historical archive/reference-only check for the MVP15 reflection trigger funnel.

Funnel stages:
    events_seen → eligible_for_reflection → reflection_invoked → artifact_generated → artifact_persisted
"""
import json
from pathlib import Path
from datetime import datetime

TRACKER_DIR = Path("artifacts/mvp15/tracker")


def _load_archive_records():
    records = []
    if not TRACKER_DIR.exists():
        return records
    for path in sorted(TRACKER_DIR.glob("day_*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return records


def _aggregate_metrics(records):
    if not records:
        empty_funnel = {
            "events_seen": 0,
            "eligible_for_reflection": 0,
            "reflection_invoked": 0,
            "artifact_generated": 0,
            "artifact_persisted": 0,
        }
        empty_rates = {
            "eligibility_rate": 0.0,
            "invocation_rate": 0.0,
            "generation_rate": 0.0,
            "persistence_rate": 0.0,
            "end_to_end_rate": 0.0,
        }
        return {
            "enable": False,
            "call_count": 0,
            "error_count": 0,
            "funnel": empty_funnel,
            "funnel_rates": empty_rates,
            "artifacts_path": str(TRACKER_DIR),
            "artifacts_generated": 0,
        }

    latest = records[-1]
    funnel = dict(latest.get("funnel") or {})
    rates = dict(latest.get("funnel_rates") or {})
    return {
        "enable": False,
        "call_count": len(records),
        "error_count": sum(int(record.get("error_count", 0) or 0) for record in records),
        "funnel": {
            "events_seen": int(funnel.get("events_seen") or 0),
            "eligible_for_reflection": int(funnel.get("eligible_for_reflection") or 0),
            "reflection_invoked": int(funnel.get("reflection_invoked") or 0),
            "artifact_generated": int(funnel.get("artifact_generated") or 0),
            "artifact_persisted": int(funnel.get("artifact_persisted") or 0),
        },
        "funnel_rates": {
            "eligibility_rate": float(rates.get("eligibility_rate") or 0.0),
            "invocation_rate": float(rates.get("invocation_rate") or 0.0),
            "generation_rate": float(rates.get("generation_rate") or 0.0),
            "persistence_rate": float(rates.get("persistence_rate") or 0.0),
            "end_to_end_rate": float(rates.get("end_to_end_rate") or 0.0),
        },
        "artifacts_path": str(TRACKER_DIR),
        "artifacts_generated": sum(1 for _ in TRACKER_DIR.glob("*.json")) if TRACKER_DIR.exists() else 0,
    }


def check_funnel():
    """Check MVP15 funnel metrics."""
    print("=== MVP15 Trigger Funnel Check ===")
    print("Historical archive/reference-only surface\n")

    metrics = _aggregate_metrics(_load_archive_records())

    print("1. Shadow Status")
    print(f"   Enabled: {metrics['enable']}")
    print(f"   Call count: {metrics['call_count']}")
    print(f"   Error count: {metrics['error_count']}")
    print()

    print("2. Funnel Statistics")
    funnel = metrics["funnel"]
    rates = metrics["funnel_rates"]

    print(f"   events_seen:              {funnel['events_seen']}")
    print(f"   eligible_for_reflection:  {funnel['eligible_for_reflection']}")
    print(f"   reflection_invoked:       {funnel['reflection_invoked']}")
    print(f"   artifact_generated:       {funnel['artifact_generated']}")
    print(f"   artifact_persisted:       {funnel['artifact_persisted']}")
    print()

    print("3. Conversion Rates")
    print(f"   Eligibility rate:    {rates['eligibility_rate']:.1%}")
    print(f"   Invocation rate:     {rates['invocation_rate']:.1%}")
    print(f"   Generation rate:     {rates['generation_rate']:.1%}")
    print(f"   Persistence rate:    {rates['persistence_rate']:.1%}")
    print(f"   End-to-end rate:     {rates['end_to_end_rate']:.1%}")
    print()

    print("4. Artifact Files")
    artifacts_path = Path(metrics["artifacts_path"])
    if artifacts_path.exists():
        artifacts = list(artifacts_path.glob("*.json"))
        print(f"   Total files: {len(artifacts)}")
        for artifact in sorted(artifacts)[-5:]:
            stat = artifact.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"   - {artifact.name} ({stat.st_size} bytes, {mtime})")
    else:
        print("   Artifacts directory not found")
    print()

    print("5. Diagnosis")
    if funnel["events_seen"] == 0:
        print("   ⚠️ No events seen - archive tracker is empty")
    elif funnel["artifact_persisted"] == 0:
        print("   ⚠️ No artifacts persisted - check archive tracker data")
    else:
        print("   ✅ Funnel archive snapshot loaded")

    return metrics


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    metrics = check_funnel()

    if args.json and metrics:
        print("\n--- JSON Output ---")
        print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
