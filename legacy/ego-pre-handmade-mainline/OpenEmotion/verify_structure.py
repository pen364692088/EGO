#!/usr/bin/env python3
"""
Verify project structure and dependencies
"""
import os
import sys

def check_file_exists(path):
    """Check if a file exists and print status"""
    if os.path.exists(path):
        print(f"✓ {path}")
        return True
    else:
        print(f"✗ {path}")
        return False

def check_directory_exists(path):
    """Check if a directory exists and print status"""
    if os.path.exists(path) and os.path.isdir(path):
        print(f"✓ {path}/")
        return True
    else:
        print(f"✗ {path}/")
        return False

def main():
    """Verify project structure"""
    print("Verifying project structure...")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Check required files
    files_to_check = [
        "pyproject.toml",
        "Makefile", 
        "README.md",
        "openclaw_skill/emotion_core/SKILL.md",
        "openclaw_skill/emotion_core/skill.py",
        "openclaw_skill/emotion_core/install.sh",
        "deploy/systemd/user/emotiond.service"
    ]
    
    print("\nFiles:")
    for file_path in files_to_check:
        if not check_file_exists(file_path):
            all_checks_passed = False
    
    # Check required directories
    dirs_to_check = [
        "emotiond",
        "tests",
        "scripts", 
        "data",
        "deploy/systemd/user",
        "openclaw_skill/emotion_core"
    ]
    
    print("\nDirectories:")
    for dir_path in dirs_to_check:
        if not check_directory_exists(dir_path):
            all_checks_passed = False
    
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("✓ All project structure checks passed!")
        sys.exit(0)
    else:
        print("✗ Some checks failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()