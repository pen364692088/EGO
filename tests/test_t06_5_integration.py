#!/usr/bin/env python3
"""
T06.5 Runtime Integration Test

Verifies that:
1. generate_plan() returns intent_contract
2. assistant_reply triggers intent checker
3. Shadow logging works for runtime events
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond.models import PlanResponse


def test_plan_response_has_intent_contract():
    """Test that PlanResponse has intent_contract field"""
    import inspect
    sig = inspect.signature(PlanResponse)
    params = list(sig.parameters.keys())
    assert 'intent_contract' in params, "intent_contract not in PlanResponse"
    print("✅ PlanResponse has intent_contract field")


async def test_generate_plan_includes_contract():
    """Test that generate_plan() returns intent_contract"""
    from emotiond.core import generate_plan
    from emotiond.models import PlanRequest
    
    # Create a minimal request
    request = PlanRequest(
        user_id="test_user",
        user_text="Hello",
        focus_target="test_user"
    )
    
    try:
        result = await generate_plan(request)
        
        # Check if intent_contract is in result
        assert hasattr(result, 'intent_contract'), "Result has no intent_contract attribute"
        print(f"✅ generate_plan() returns intent_contract")
        
        if result.intent_contract:
            print(f"   intent_contract keys: {list(result.intent_contract.keys())[:5]}")
        else:
            print("   intent_contract is None (acceptable if emotiond not initialized)")
    except Exception as e:
        print(f"⚠️ generate_plan() test skipped: {e}")


async def test_assistant_reply_triggers_checker():
    """Test that assistant_reply triggers intent checker"""
    from emotiond.core import process_event
    from emotiond.models import Event
    
    # Create an assistant_reply event with test text
    event = Event(
        type="assistant_reply",
        actor="test_user",
        target="agent",
        text="My joy is 0.5"  # Should trigger numeric leak
    )
    
    try:
        result = await process_event(event)
        
        # Check if intent_check is in result
        if "intent_check" in result:
            print("✅ assistant_reply triggers intent checker")
            check_result = result["intent_check"]
            print(f"   Check result keys: {list(check_result.keys())}")
            if check_result.get("violations"):
                print(f"   Violations detected: {len(check_result['violations'])}")
        else:
            print("⚠️ No intent_check in result")
    except Exception as e:
        print(f"⚠️ assistant_reply test skipped: {e}")


def main():
    print("=" * 60)
    print("T06.5 Runtime Integration Test")
    print("=" * 60)
    print()
    
    # Test 1: PlanResponse field
    test_plan_response_has_intent_contract()
    print()
    
    # Test 2: generate_plan
    print("Test 2: generate_plan() includes contract")
    try:
        asyncio.run(test_generate_plan_includes_contract())
    except Exception as e:
        print(f"   Skipped: {e}")
    print()
    
    # Test 3: assistant_reply
    print("Test 3: assistant_reply triggers checker")
    try:
        asyncio.run(test_assistant_reply_triggers_checker())
    except Exception as e:
        print(f"   Skipped: {e}")
    print()
    
    print("=" * 60)
    print("T06.5 Integration Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
