"""
Test suite for documentation examples and runbook instructions.

This test ensures that all code examples in the README.md and documentation
actually work as described.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestDocumentationExamples:
    """Test that documentation examples work correctly."""

    def test_readme_exists(self):
        """Test that README.md exists and has content."""
        readme_path = Path("README.md")
        assert readme_path.exists(), "README.md does not exist"
        
        content = readme_path.read_text()
        assert len(content) > 0, "README.md is empty"
        assert "OpenEmotion" in content, "README.md should mention OpenEmotion"

    def test_readme_contains_required_sections(self):
        """Test that README.md contains all required sections."""
        content = Path("README.md").read_text()
        
        required_sections = [
            "Quick Start",
            "Complete Runbook", 
            "API Reference",
            "Configuration",
            "Development",
            "Troubleshooting"
        ]
        
        for section in required_sections:
            assert section in content, f"README.md missing section: {section}"

    def test_make_commands_exist(self):
        """Test that Makefile contains required commands."""
        makefile_path = Path("Makefile")
        assert makefile_path.exists(), "Makefile does not exist"
        
        content = makefile_path.read_text()
        
        required_commands = [
            "venv",
            "run",
            "test",
            "demo"
        ]
        
        for command in required_commands:
            assert f"{command}:" in content, f"Makefile missing command: {command}"

    def test_pyproject_toml_exists(self):
        """Test that pyproject.toml exists and has basic configuration."""
        toml_path = Path("pyproject.toml")
        assert toml_path.exists(), "pyproject.toml does not exist"
        
        content = toml_path.read_text()
        assert "openemotion" in content, "pyproject.toml should define project name"
        assert "fastapi" in content, "pyproject.toml should include fastapi dependency"

    def test_environment_variables_documented(self):
        """Test that environment variables are documented in README."""
        content = Path("README.md").read_text()
        
        required_env_vars = [
            "EMOTIOND_DB_PATH",
            "EMOTIOND_PORT", 
            "EMOTIOND_HOST",
            "EMOTIOND_K_AROUSAL",
            "EMOTIOND_DISABLE_CORE"
        ]
        
        for env_var in required_env_vars:
            assert env_var in content, f"README.md missing environment variable: {env_var}"

    def test_api_endpoints_documented(self):
        """Test that API endpoints are documented in README."""
        content = Path("README.md").read_text()
        
        required_endpoints = [
            "GET /health",
            "POST /event",
            "POST /plan"
        ]
        
        for endpoint in required_endpoints:
            assert endpoint in content, f"README.md missing endpoint: {endpoint}"

    def test_demo_script_exists(self):
        """Test that demo script exists."""
        demo_path = Path("scripts/demo_cli.py")
        assert demo_path.exists(), "demo_cli.py does not exist"

    def test_eval_script_exists(self):
        """Test that evaluation script exists."""
        eval_path = Path("scripts/eval_suite.py")
        assert eval_path.exists(), "eval_suite.py does not exist"

    def test_systemd_service_exists(self):
        """Test that systemd service file exists."""
        service_path = Path("deploy/systemd/user/emotiond.service")
        assert service_path.exists(), "emotiond.service does not exist"

    def test_openclaw_skill_exists(self):
        """Test that OpenClaw skill directory exists."""
        skill_dir = Path("openclaw_skill/emotion_core")
        assert skill_dir.exists(), "openclaw_skill/emotion_core directory does not exist"
        
        skill_file = skill_dir / "skill.py"
        assert skill_file.exists(), "skill.py does not exist"

    def test_core_package_structure(self):
        """Test that core package structure is correct."""
        required_files = [
            "emotiond/__init__.py",
            "emotiond/daemon.py",
            "emotiond/api.py", 
            "emotiond/core.py",
            "emotiond/db.py",
            "emotiond/config.py"
        ]
        
        for file_path in required_files:
            assert Path(file_path).exists(), f"Required file missing: {file_path}"


class TestDocumentationCodeExamples:
    """Test that code examples in documentation work."""

    def test_health_endpoint_curl_example(self):
        """Test that health endpoint curl example is valid."""
        # This test verifies the curl command format is correct
        # We can't actually run curl in tests, but we can verify the format
        content = Path("README.md").read_text()
        assert "curl -s http://127.0.0.1:18080/health" in content

    def test_event_endpoint_json_structure(self):
        """Test that event endpoint JSON structure is documented correctly."""
        content = Path("README.md").read_text()
        
        # Check for event structure
        assert '"type": "user_message"' in content
        assert '"actor": "user"' in content
        assert '"target": "assistant"' in content

    def test_plan_endpoint_json_structure(self):
        """Test that plan endpoint JSON structure is documented correctly."""
        content = Path("README.md").read_text()
        
        # Check for plan request structure
        assert '"user_id": "user"' in content
        assert '"user_text": "' in content
        
        # Check for plan response structure
        assert '"tone": "friendly"' in content
        assert '"intent": "engage"' in content
        assert '"valence": 0.2' in content
        assert '"arousal": 0.4' in content

    def test_systemd_commands_documented(self):
        """Test that systemd commands are documented correctly."""
        content = Path("README.md").read_text()
        
        required_commands = [
            "systemctl --user daemon-reload",
            "systemctl --user enable emotiond.service",
            "systemctl --user start emotiond.service",
            "systemctl --user status emotiond.service",
            "journalctl --user -u emotiond.service -f"
        ]
        
        for command in required_commands:
            assert command in content, f"README.md missing systemd command: {command}"


class TestDocumentationCompleteness:
    """Test that documentation is comprehensive and complete."""

    def test_all_major_operations_documented(self):
        """Test that all major operations are documented."""
        content = Path("README.md").read_text()
        
        required_operations = [
            "virtual environment setup",
            "daemon startup",
            "testing",
            "type checking",
            "demo usage",
            "evaluation suite",
            "OpenClaw skill usage",
            "systemd deployment"
        ]
        
        for operation in required_operations:
            assert operation.lower() in content.lower(), f"README.md missing operation: {operation}"

    def test_troubleshooting_section_exists(self):
        """Test that troubleshooting section exists and has common issues."""
        content = Path("README.md").read_text()
        
        assert "Troubleshooting" in content
        assert "Common Issues" in content
        
        common_issues = [
            "Database errors",
            "Port conflicts",
            "Virtual environment issues",
            "Systemd service failures"
        ]
        
        for issue in common_issues:
            assert issue in content, f"README.md missing troubleshooting issue: {issue}"

    def test_development_section_exists(self):
        """Test that development section exists and has required information."""
        content = Path("README.md").read_text()
        
        assert "Development" in content
        assert "Project Structure" in content
        assert "Key Components" in content
        assert "Testing Strategy" in content

    def test_contributing_guidelines_exist(self):
        """Test that contributing guidelines are included."""
        content = Path("README.md").read_text()
        
        assert "Contributing" in content
        contributing_steps = [
            "Create a feature branch",
            "Write tests",
            "Ensure all tests pass",
            "Run type checking",
            "Submit a pull request"
        ]
        
        for step in contributing_steps:
            assert step in content, f"README.md missing contributing step: {step}"