#!/usr/bin/env python3
"""
Simple typecheck verification
"""
import sys

def verify_imports():
    """Verify that all modules can be imported"""
    try:
        # Try to import all modules
        import emotiond.api
        import emotiond.core
        import emotiond.db
        import emotiond.models
        import emotiond.config
        print("✓ All emotiond modules import successfully")
        
        # Verify models can be instantiated
        from emotiond.models import Event, PlanRequest, PlanResponse
        
        # Test Event model
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello"
        )
        print("✓ Event model instantiated successfully")
        
        # Test PlanRequest model
        plan_request = PlanRequest(
            user_id="test",
            user_text="How are you?"
        )
        print("✓ PlanRequest model instantiated successfully")
        
        # Test PlanResponse model
        plan_response = PlanResponse(
            tone="warm",
            intent="seek",
            focus_target="user",
            key_points=["test"],
            constraints=["test"],
            emotion={"valence": 0.5, "arousal": 0.3},
            relationship={"bond": 0.7, "grudge": 0.1}
        )
        print("✓ PlanResponse model instantiated successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import/type check failed: {e}")
        return False

def main():
    """Run typecheck verification"""
    print("Running typecheck verification...")
    print("=" * 50)
    
    if verify_imports():
        print("=" * 50)
        print("✓ All typecheck verifications passed!")
        sys.exit(0)
    else:
        print("=" * 50)
        print("✗ Typecheck verifications failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()