"""
Test project structure and dependencies
"""
import os
import sys
import pytest

class TestProjectStructure:
    def test_pyproject_exists(self):
        """Test that pyproject.toml exists"""
        assert os.path.exists("pyproject.toml")
    
    def test_makefile_exists(self):
        """Test that Makefile exists"""
        assert os.path.exists("Makefile")
    
    def test_directory_structure(self):
        """Test that required directories exist"""
        required_dirs = [
            "emotiond",
            "tests", 
            "scripts",
            "data",
            "deploy/systemd/user"
        ]
        
        for dir_path in required_dirs:
            assert os.path.exists(dir_path), f"Directory {dir_path} does not exist"
    
    def test_readme_exists(self):
        """Test that README.md exists"""
        assert os.path.exists("README.md")
    
    def test_compatibility_assets_optional(self):
        """Legacy compatibility assets may exist, but are not formal requirements."""
        compat_skill_dir = "openclaw_skill/emotion_core"
        if os.path.exists(compat_skill_dir):
            assert os.path.exists(f"{compat_skill_dir}/SKILL.md")
            assert os.path.exists(f"{compat_skill_dir}/skill.py")
