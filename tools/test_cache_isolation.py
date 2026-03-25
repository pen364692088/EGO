#!/usr/bin/env python3
"""Test to verify _target_predictions cache isolation issue"""

import asyncio
import json
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond.core import _target_predictions, load_initial_state

async def test_cache_pollution():
    print("=== Cache Pollution Test ===")
    
    # Reset cache first
    _target_predictions.clear()
    print(f"Initial cache size: {len(_target_predictions)}")
    
    # Simulate test 1: counterparty_a gets care
    print("\n1. Processing care event for counterparty_a...")
    await load_initial_state()
    
    # This will populate _target_predictions for counterparty_a
    from emotiond.core import process_event
    event1 = {
        "type": "world_event",
        "actor": "counterparty_a",
        "target": "testbot",
        "text": "care event",
        "meta": {"subtype": "care", "severity": 0.8},
        "agent_id": "testbot",
        "counterparty_id": "counterparty_a"
    }
    
    result1 = await process_event(event1)
    print(f"Event 1 processed: {result1.get('status', 'unknown')}")
    print(f"Cache size after event 1: {len(_target_predictions)}")
    if "counterparty_a" in _target_predictions:
        print(f"counterparty_a cache keys: {list(_target_predictions['counterparty_a'].keys())}")
    
    # Simulate test 2: counterparty_b gets betrayal
    print("\n2. Processing betrayal event for counterparty_b...")
    event2 = {
        "type": "world_event",
        "actor": "counterparty_b", 
        "target": "testbot",
        "text": "betrayal event",
        "meta": {"subtype": "betrayal", "severity": 0.9},
        "agent_id": "testbot",
        "counterparty_id": "counterparty_b"
    }
    
    result2 = await process_event(event2)
    print(f"Event 2 processed: {result2.get('status', 'unknown')}")
    print(f"Cache size after event 2: {len(_target_predictions)}")
    if "counterparty_b" in _target_predictions:
        print(f"counterparty_b cache keys: {list(_target_predictions['counterparty_b'].keys())}")
    
    # Check if cache has both entries
    print(f"\nFinal cache contents:")
    for target_id, actions in _target_predictions.items():
        print(f"  {target_id}: {list(actions.keys())}")
    
    # The problem: cache persists and grows
    print(f"\n⚠️  Cache pollution detected: {len(_target_predictions)} targets in cache")
    print("This cache persists between test runs and affects decisions!")

if __name__ == "__main__":
    asyncio.run(test_cache_pollution())
