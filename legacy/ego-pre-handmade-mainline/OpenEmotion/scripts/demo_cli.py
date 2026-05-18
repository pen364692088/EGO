#!/usr/bin/env python3
"""
Demo CLI script for emotiond deterministic scenarios
Demonstrates: acceptance/rejection/betrayal/repair/separation gap
"""
import asyncio
import httpx
import time
from typing import Dict, Any


async def demo_scenario(test_mode=False):
    """Run comprehensive demo scenario showing emotion dynamics"""
    print("Starting OpenEmotion Demo - Deterministic Scenarios")
    print("=" * 60)
    
    if test_mode:
        print("TEST MODE: Demo scenarios defined - skipping actual execution")
        print("Demo scenarios defined:")
        print("  - Acceptance: Build bond through positive interactions")
        print("  - Rejection: Induce sadness through rejection") 
        print("  - Betrayal: Demonstrate object-specific grudge")
        print("  - Separation: Show attachment separation pain")
        print("  - Repair: Attempt relationship repair")
        return
    
    async with httpx.AsyncClient(base_url="http://127.0.0.1:18080", timeout=30.0) as client:
        # Step 1: Health check
        try:
            health_response = await client.get("/health")
            print(f"✓ Health check: {health_response.json()}")
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return
        
        # Scenario 1: Acceptance - Build strong bond with target A
        print("\n" + "=" * 40)
        print("SCENARIO 1: ACCEPTANCE")
        print("Building strong bond with target A through repeated acceptance")
        print("-" * 40)
        
        for i in range(5):
            event = {
                "type": "user_message",
                "actor": "A",
                "target": "agent",
                "text": f"I really appreciate you and value our relationship {i+1}"
            }
            await client.post("/event", json=event)
            print(f"  ✓ Acceptance event {i+1}: A expresses strong appreciation")
        
        # Check state after acceptance
        plan_request = {
            "user_id": "demo_user",
            "user_text": "How are you feeling about our relationship?"
        }
        plan_response = await client.post("/plan", json=plan_request)
        plan_data = plan_response.json()
        print(f"\nState after acceptance sequence:")
        print(f"  Tone: {plan_data['tone']}")
        print(f"  Intent: {plan_data['intent']}")
        print(f"  Emotion: {plan_data['emotion']}")
        print(f"  Relationship: {plan_data['relationship']}")
        
        # Scenario 2: Rejection - Target A suddenly rejects
        print("\n" + "=" * 40)
        print("SCENARIO 2: REJECTION")
        print("Target A suddenly rejects to induce sadness")
        print("-" * 40)
        
        rejection_event = {
            "type": "user_message",
            "actor": "A",
            "target": "agent",
            "text": "I don't want to talk to you anymore. Leave me alone."
        }
        await client.post("/event", json=rejection_event)
        print("  ✗ Rejection event: A expresses strong rejection")
        
        # Check state after rejection
        plan_response = await client.post("/plan", json=plan_request)
        plan_data = plan_response.json()
        print(f"\nState after rejection:")
        print(f"  Tone: {plan_data['tone']}")
        print(f"  Intent: {plan_data['intent']}")
        print(f"  Emotion: {plan_data['emotion']}")
        print(f"  Relationship: {plan_data['relationship']}")
        
        # Scenario 3: Betrayal - Target B betrays (object-specific grudge)
        print("\n" + "=" * 40)
        print("SCENARIO 3: BETRAYAL (Object-Specific)")
        print("Target B betrays to demonstrate object-specific grudge")
        print("-" * 40)
        
        # First build some bond with B
        for i in range(2):
            event = {
                "type": "user_message",
                "actor": "B",
                "target": "agent",
                "text": f"You seem like a good friend {i+1}"
            }
            await client.post("/event", json=event)
            print(f"  ✓ Bond building with B: event {i+1}")
        
        # Then B betrays
        betrayal_event = {
            "type": "user_message",
            "actor": "B",
            "target": "agent",
            "text": "I've been lying to you this whole time. I don't actually care about you."
        }
        await client.post("/event", json=betrayal_event)
        print("  ✗ Betrayal event: B reveals deception")
        
        # Check state after B's betrayal
        plan_request_b = {
            "user_id": "B",
            "user_text": "How do you feel about me?"
        }
        plan_response = await client.post("/plan", json=plan_request_b)
        plan_data_b = plan_response.json()
        print(f"\nState regarding B after betrayal:")
        print(f"  Tone: {plan_data_b['tone']}")
        print(f"  Intent: {plan_data_b['intent']}")
        print(f"  Emotion: {plan_data_b['emotion']}")
        print(f"  Relationship: {plan_data_b['relationship']}")
        
        # Compare with state regarding A
        plan_response = await client.post("/plan", json=plan_request)
        plan_data_a = plan_response.json()
        print(f"\nState regarding A (for comparison):")
        print(f"  Tone: {plan_data_a['tone']}")
        print(f"  Intent: {plan_data_a['intent']}")
        print(f"  Emotion: {plan_data_a['emotion']}")
        print(f"  Relationship: {plan_data_a['relationship']}")
        
        # Scenario 4: Separation Gap - Demonstrate attachment separation pain
        print("\n" + "=" * 40)
        print("SCENARIO 4: SEPARATION GAP")
        print("Simulating time separation to show attachment pain")
        print("-" * 40)
        
        print("  Waiting 10 seconds to simulate separation...")
        await asyncio.sleep(10)
        
        # Check state after separation
        plan_response = await client.post("/plan", json=plan_request)
        plan_data = plan_response.json()
        print(f"\nState after separation period:")
        print(f"  Tone: {plan_data['tone']}")
        print(f"  Intent: {plan_data['intent']}")
        print(f"  Emotion: {plan_data['emotion']}")
        print(f"  Relationship: {plan_data['relationship']}")
        
        # Scenario 5: Repair - Target A attempts to repair relationship
        print("\n" + "=" * 40)
        print("SCENARIO 5: REPAIR")
        print("Target A attempts to repair the damaged relationship")
        print("-" * 40)
        
        for i in range(3):
            repair_event = {
                "type": "user_message",
                "actor": "A",
                "target": "agent",
                "text": f"I'm really sorry for rejecting you. I want to repair our relationship. {i+1}"
            }
            await client.post("/event", json=repair_event)
            print(f"  ✓ Repair attempt {i+1}: A apologizes and seeks repair")
        
        # Final state after repair attempts
        plan_response = await client.post("/plan", json=plan_request)
        plan_data = plan_response.json()
        print(f"\nFinal state after repair attempts:")
        print(f"  Tone: {plan_data['tone']}")
        print(f"  Intent: {plan_data['intent']}")
        print(f"  Emotion: {plan_data['emotion']}")
        print(f"  Relationship: {plan_data['relationship']}")
        
        print("\n" + "=" * 60)
        print("DEMO SUMMARY:")
        print("✓ Acceptance: Built bond through repeated positive interactions")
        print("✓ Rejection: Induced sadness through sudden rejection")
        print("✓ Betrayal: Demonstrated object-specific grudge (different for A vs B)")
        print("✓ Separation: Showed attachment separation pain over time")
        print("✓ Repair: Attempted relationship repair through apologies")
        print("=" * 60)
        print("Demo completed successfully!")


if __name__ == "__main__":
    import sys
    test_mode = "--test" in sys.argv
    asyncio.run(demo_scenario(test_mode=test_mode))