#!/usr/bin/env python3
"""
Smoke test for the complete emotiond system
"""
import subprocess
import time
import requests
import sys
from pathlib import Path

def test_daemon_startup():
    """Test that the daemon starts and health endpoint works"""
    print("Testing daemon startup...")
    
    # Start daemon
    process = subprocess.Popen(
        [".venv/bin/python", "scripts/run_daemon.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent
    )
    
    try:
        # Wait for startup
        time.sleep(5)
        
        # Test health endpoint
        response = requests.get("http://127.0.0.1:18080/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "emotiond" in data
        print("✓ Health endpoint works")
        
        # Test event endpoint
        event_data = {
            "type": "user_message",
            "actor": "test_user",
            "target": "assistant",
            "text": "Hello, smoke test"
        }
        response = requests.post("http://127.0.0.1:18080/event", json=event_data)
        assert response.status_code == 200
        print("✓ Event endpoint works")
        
        # Test plan endpoint
        plan_data = {
            "user_id": "test_user",
            "user_text": "How are you feeling?"
        }
        response = requests.post("http://127.0.0.1:18080/plan", json=plan_data)
        assert response.status_code == 200
        plan = response.json()
        
        # Verify plan structure
        required_fields = ["tone", "intent", "focus_target", "key_points", 
                         "constraints", "emotion", "relationship"]
        for field in required_fields:
            assert field in plan
        
        # Verify emotion ranges
        assert -1 <= plan["emotion"]["valence"] <= 1
        assert 0 <= plan["emotion"]["arousal"] <= 1
        print("✓ Plan endpoint works with valid structure")
        
        return True
        
    except Exception as e:
        print(f"✗ Smoke test failed: {e}")
        return False
    finally:
        # Stop daemon
        process.terminate()
        process.wait()

def test_scripts():
    """Test that scripts can run without errors"""
    print("\nTesting scripts...")
    
    # Test demo script
    result = subprocess.run(
        [".venv/bin/python", "scripts/demo_cli.py", "--test"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent
    )
    assert result.returncode == 0
    assert "TEST MODE" in result.stdout
    print("✓ Demo script works in test mode")
    
    # Test eval script
    result = subprocess.run(
        [".venv/bin/python", "scripts/eval_suite.py", "--test"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent
    )
    assert result.returncode == 0
    assert "TEST MODE" in result.stdout
    print("✓ Eval script works in test mode")
    
    # Test deployment script syntax
    result = subprocess.run(
        [".venv/bin/python", "-m", "py_compile", "scripts/deploy_systemd.py"],
        capture_output=True,
        cwd=Path(__file__).parent
    )
    assert result.returncode == 0
    print("✓ Deployment script has valid syntax")
    
    return True

def test_openclaw_skill():
    """Test that OpenClaw skill can be imported"""
    print("\nTesting OpenClaw skill...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from openclaw_skill.emotion_core.skill import check_daemon_health, process_user_message
        print("✓ OpenClaw skill imports successfully")
        return True
    except ImportError as e:
        print(f"✗ OpenClaw skill import failed: {e}")
        return False

def main():
    """Run all smoke tests"""
    print("Running smoke tests for emotiond system...")
    print("=" * 50)
    
    tests = [
        test_daemon_startup,
        test_scripts,
        test_openclaw_skill
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        if test_func():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"Smoke test results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All smoke tests passed! System is ready for integration.")
        return 0
    else:
        print("❌ Some smoke tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())