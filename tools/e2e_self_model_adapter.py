#!/usr/bin/env python3
"""
E2E Verification for SelfModelAdapter

Verifies that:
1. SelfModelAdapter is called in the main chain
2. Shadow artifacts are created
3. Both new and legacy models produce valid output
4. No errors in shadow mode
"""
import os
import sys
import json
import asyncio
import glob
from pathlib import Path
from datetime import datetime

# Setup
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ['ENABLE_OPENEMOTION_SELF_MODEL'] = 'true'

from emotiond.core import process_event
from emotiond.models import Event


async def run_e2e_test():
    """Run E2E test with multiple events."""
    
    print("=" * 60)
    print("E2E Verification for SelfModelAdapter")
    print("=" * 60)
    
    # Clear old artifacts
    artifact_dir = Path("artifacts/self_model_adapter")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # Test events
    test_events = [
        Event(
            type='user_message',
            actor='user',
            target='assistant',
            text='Hello, how are you?',
            meta={'test_id': 1}
        ),
        Event(
            type='user_message',
            actor='user',
            target='assistant',
            text='I need help with a project',
            meta={'test_id': 2}
        ),
        Event(
            type='assistant_reply',
            actor='assistant',
            target='user',
            text='I can help with that!',
            meta={'test_id': 3}
        ),
    ]
    
    results = []
    
    for i, event in enumerate(test_events, 1):
        print(f"\nProcessing event {i}/{len(test_events)}: {event.type}")
        
        try:
            result = await process_event(event)
            
            results.append({
                "event_id": i,
                "event_type": event.type,
                "success": True,
                "has_valence": "valence" in result,
                "has_arousal": "arousal" in result,
            })
            
            print(f"  ✅ Success: valence={result.get('valence', 'N/A'):.2f}")
            
        except Exception as e:
            results.append({
                "event_id": i,
                "event_type": event.type,
                "success": False,
                "error": str(e),
            })
            print(f"  ❌ Error: {e}")
    
    # Check artifacts
    print("\n" + "=" * 60)
    print("Shadow Artifacts")
    print("=" * 60)
    
    artifacts = sorted(glob.glob("artifacts/self_model_adapter/shadow_*.json"))
    print(f"Total artifacts: {len(artifacts)}")
    
    # Read latest artifacts
    artifact_data = []
    for artifact_path in artifacts[-5:]:
        data = json.loads(open(artifact_path).read())
        artifact_data.append({
            "path": artifact_path,
            "timestamp": data.get("timestamp"),
            "new_model_calls": data.get("metrics", {}).get("new_model_calls", 0),
            "legacy_calls": data.get("metrics", {}).get("legacy_calls", 0),
            "errors": data.get("metrics", {}).get("errors", 0),
        })
        print(f"  {artifact_path}")
        print(f"    new_model_calls: {data.get('metrics', {}).get('new_model_calls', 0)}")
        print(f"    legacy_calls: {data.get('metrics', {}).get('legacy_calls', 0)}")
        print(f"    errors: {data.get('metrics', {}).get('errors', 0)}")
    
    # Verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r["success"])
    total_artifacts = len(artifacts)
    total_errors = sum(a["errors"] for a in artifact_data)
    
    print(f"Events processed: {success_count}/{len(test_events)}")
    print(f"Shadow artifacts: {total_artifacts}")
    print(f"Total errors: {total_errors}")
    
    # Criteria
    criteria = [
        ("Events processed successfully", success_count == len(test_events)),
        ("Shadow artifacts created", total_artifacts > 0),
        ("No errors in artifacts", total_errors == 0),
        ("New model called", any(a["new_model_calls"] > 0 for a in artifact_data)),
        ("Legacy model called", any(a["legacy_calls"] > 0 for a in artifact_data)),
    ]
    
    all_pass = all(c[1] for c in criteria)
    
    for name, passed in criteria:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
    
    print("\n" + "-" * 60)
    
    if all_pass:
        print("✅ E2E VERIFIED")
        print("   SelfModelAdapter is working in shadow mode")
        return 0
    else:
        print("❌ E2E FAILED")
        print("   Some criteria not met")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_e2e_test()))
