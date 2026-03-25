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
            "deploy/systemd/user",
            "openclaw_skill/emotion_core"
        ]
        
        for dir_path in required_dirs:
            assert os.path.exists(dir_path), f"Directory {dir_path} does not exist"
    
    def test_readme_exists(self):
        """Test that README.md exists"""
        assert os.path.exists("README.md")
    
    def test_skill_files_exist(self):
        """Test that OpenClaw skill files exist"""
        skill_files = [
            "openclaw_skill/emotion_core/SKILL.md",
            "openclaw_skill/emotion_core/skill.py",
            "openclaw_skill/emotion_core/install.sh"
        ]
        
        for file_path in skill_files:
            assert os.path.exists(file_path), f"Skill file {file_path} does not exist"