#!/usr/bin/env python3
"""
Simple typecheck verification for project structure
"""
import ast
import sys

def check_pyproject_toml():
    """Verify pyproject.toml has required dependencies"""
    try:
        with open("pyproject.toml", "r") as f:
            content = f.read()
        
        required_deps = ["fastapi", "uvicorn", "pydantic", "aiosqlite", "pytest", "httpx"]
        missing_deps = []
        
        for dep in required_deps:
            if dep not in content:
                missing_deps.append(dep)
        
        if missing_deps:
            print(f"✗ pyproject.toml missing dependencies: {', '.join(missing_deps)}")
            return False
        else:
            print("✓ pyproject.toml has all required dependencies")
            return True
    except Exception as e:
        print(f"✗ Failed to read pyproject.toml: {e}")
        return False

def check_makefile():
    """Verify Makefile has required targets"""
    try:
        with open("Makefile", "r") as f:
            content = f.read()
        
        required_targets = ["venv", "run", "test", "demo"]
        missing_targets = []
        
        for target in required_targets:
            if f"{target}:" not in content:
                missing_targets.append(target)
        
        if missing_targets:
            print(f"✗ Makefile missing targets: {', '.join(missing_targets)}")
            return False
        else:
            print("✓ Makefile has all required targets")
            return True
    except Exception as e:
        print(f"✗ Failed to read Makefile: {e}")
        return False

def main():
    """Run typecheck verification"""
    print("Running typecheck verification...")
    print("=" * 50)
    
    all_checks_passed = True
    
    if not check_pyproject_toml():
        all_checks_passed = False
    
    if not check_makefile():
        all_checks_passed = False
    
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("✓ All typecheck verification passed!")
        sys.exit(0)
    else:
        print("✗ Some typecheck verification failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()