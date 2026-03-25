#!/usr/bin/env python3
"""
Simple structure verification without pytest
"""
import os
import sys

def test_pyproject_exists():
    """Test that pyproject.toml exists"""
    assert os.path.exists("pyproject.toml")
    print("✓ pyproject.toml exists")

def test_makefile_exists():
    """Test that Makefile exists"""
    assert os.path.exists("Makefile")
    print("✓ Makefile exists")

def test_directory_structure():
    """Test that required directories exist"""
    required_dirs = [
        "emotiond",
        "tests", 
        "scripts",
        "data",
        "deploy/systemd/user",
        "openclaw_skill/emotion_core"
    ]
    
    for dir_path in required_dirs:
        assert os.path.exists(dir_path), f"Directory {dir_path} does not exist"
        print(f"✓ Directory {dir_path} exists")

def test_readme_exists():
    """Test that README.md exists"""
    assert os.path.exists("README.md")
    print("✓ README.md exists")

def test_skill_files_exist():
    """Test that OpenClaw skill files exist"""
    skill_files = [
        "openclaw_skill/emotion_core/SKILL.md",
        "openclaw_skill/emotion_core/skill.py",
        "openclaw_skill/emotion_core/install.sh"
    ]
    
    for file_path in skill_files:
        assert os.path.exists(file_path), f"Skill file {file_path} does not exist"
        print(f"✓ Skill file {file_path} exists")

def test_emotiond_files_exist():
    """Test that emotiond package files exist"""
    emotiond_files = [
        "emotiond/__init__.py",
        "emotiond/api.py",
        "emotiond/core.py",
        "emotiond/db.py",
        "emotiond/models.py",
        "emotiond/config.py"
    ]
    
    for file_path in emotiond_files:
        assert os.path.exists(file_path), f"Emotiond file {file_path} does not exist"
        print(f"✓ Emotiond file {file_path} exists")

def test_scripts_files_exist():
    """Test that scripts files exist"""
    scripts_files = [
        "scripts/demo_cli.py"
    ]
    
    for file_path in scripts_files:
        assert os.path.exists(file_path), f"Script file {file_path} does not exist"
        print(f"✓ Script file {file_path} exists")

def test_tests_files_exist():
    """Test that tests files exist"""
    tests_files = [
        "tests/test_project_structure.py",
        "tests/test_implementation.py"
    ]
    
    for file_path in tests_files:
        assert os.path.exists(file_path), f"Test file {file_path} does not exist"
        print(f"✓ Test file {file_path} exists")

def main():
    """Run all tests"""
    print("Running project structure tests...")
    print("=" * 50)
    
    tests = [
        test_pyproject_exists,
        test_makefile_exists,
        test_directory_structure,
        test_readme_exists,
        test_skill_files_exist,
        test_emotiond_files_exist,
        test_scripts_files_exist,
        test_tests_files_exist
    ]
    
    all_passed = True
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            all_passed = False
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error: {e}")
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("✓ All project structure tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()