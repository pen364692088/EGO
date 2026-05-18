"""
Compatibility-only final integration checks for the legacy OpenClaw skill path.

These are not part of the formal OpenEmotion + EgoCore mainline validation.
"""

import os
import sys
import time
import subprocess
import requests
import json
import socket
from pathlib import Path
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openclaw_skill.emotion_core.skill import check_daemon_health, send_event, get_plan, process_user_message, process_assistant_reply


class TestFinalIntegration:
    """Final integration tests that don't require daemon startup."""

    def test_demo_cli_functionality(self):
        """Test that the demo CLI script works correctly."""
        # Run demo script in test mode (no actual daemon startup)
        result = subprocess.run(
            ["venv2/bin/python", "scripts/demo_cli.py", "--test"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        # Should run without errors
        assert result.returncode == 0
        assert "Demo scenarios defined" in result.stdout or "test mode" in result.stdout.lower()

    def test_eval_suite_generation(self):
        """Test that the evaluation suite can generate reports."""
        # Run eval suite in test mode
        result = subprocess.run(
            ["venv2/bin/python", "scripts/eval_suite.py", "--test"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        # Should run without errors
        assert result.returncode == 0
        assert "Evaluation" in result.stdout or "test mode" in result.stdout.lower()

    def test_systemd_deployment_script(self):
        """Test that the systemd deployment script exists and is valid."""
        deployment_script = Path(__file__).parent.parent / "scripts" / "deploy_systemd.py"
        assert deployment_script.exists()
        
        # Check script syntax
        result = subprocess.run(
            ["venv2/bin/python", "-m", "py_compile", str(deployment_script)],
            capture_output=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode == 0, f"Deployment script syntax error: {result.stderr}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
