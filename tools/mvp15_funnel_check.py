#!/usr/bin/env python
"""
MVP15 Trigger Funnel Check

Checks the MVP15 reflection trigger funnel and generates diagnostic report.

Funnel stages:
    events_seen → eligible_for_reflection → reflection_invoked → artifact_generated → artifact_persisted
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_funnel():
    """Check MVP15 funnel metrics."""
    print("=== MVP15 Trigger Funnel Check ===\n")
    
    try:
        from emotiond.reflection_shadow import get_reflection_shadow
        
        shadow = get_reflection_shadow()
        metrics = shadow.get_metrics()
        
        print("1. Shadow Status")
        print(f"   Enabled: {metrics['enable']}")
        print(f"   Call count: {metrics['call_count']}")
        print(f"   Error count: {metrics['error_count']}")
        print()
        
        print("2. Funnel Statistics")
        funnel = metrics['funnel']
        rates = metrics['funnel_rates']
        
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
        artifacts_path = Path(metrics['artifacts_path'])
        if artifacts_path.exists():
            artifacts = list(artifacts_path.glob("*.json"))
            print(f"   Total files: {len(artifacts)}")
            for artifact in sorted(artifacts)[-5:]:
                stat = artifact.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                print(f"   - {artifact.name} ({stat.st_size} bytes, {mtime})")
        else:
            print("   Artifacts directory not found")
        print()
        
        print("5. Diagnosis")
        if funnel['events_seen'] == 0:
            print("   ⚠️ No events seen - shadow not receiving events")
        elif funnel['artifact_persisted'] == 0:
            print("   ⚠️ No artifacts persisted - check persistence logic")
        else:
            print("   ✅ Funnel working correctly")
        
        return metrics
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


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
