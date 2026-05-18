"""
Tests for demo CLI script functionality
"""
import pytest
import asyncio
import httpx
import subprocess
import sys
import time
from pathlib import Path


class TestDemoCLI:
    """Test suite for demo CLI script"""
    
    @pytest.fixture
    async def client(self):
        """Async HTTP client for testing"""
        async with httpx.AsyncClient(base_url="http://127.0.0.1:18080", timeout=30.0) as client:
            yield client
    
    def test_demo_script_exists(self):
        """Test that demo script exists and is executable"""
        demo_path = Path("scripts/demo_cli.py")
        assert demo_path.exists(), "demo_cli.py script should exist"
        
        # Check shebang line
        with open(demo_path, 'r') as f:
            first_line = f.readline().strip()
            assert first_line == "#!/usr/bin/env python3", "Script should have proper shebang"
    
    def test_demo_script_imports(self):
        """Test that demo script has all required imports"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
            
        # Check for required imports
        required_imports = [
            "import asyncio",
            "import httpx",
            "import time",
            "from typing import"
        ]
        
        for imp in required_imports:
            assert imp in content, f"Script should import {imp}"
    
    def test_demo_script_structure(self):
        """Test that demo script has proper structure"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        # Check for required functions and structure
        assert "async def demo_scenario(test_mode=False):" in content, "Script should have demo_scenario function"
        assert "if __name__ == \"__main__\":" in content, "Script should have main guard"
        assert "asyncio.run(demo_scenario(test_mode=test_mode))" in content, "Script should run demo_scenario"
    
    def test_demo_scenarios_defined(self):
        """Test that all required scenarios are defined in demo"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        # Check for all required scenario labels
        required_scenarios = [
            "SCENARIO 1: ACCEPTANCE",
            "SCENARIO 2: REJECTION", 
            "SCENARIO 3: BETRAYAL",
            "SCENARIO 4: SEPARATION GAP",
            "SCENARIO 5: REPAIR"
        ]
        
        for scenario in required_scenarios:
            assert scenario in content, f"Demo should include {scenario}"
    
    def test_demo_health_check(self):
        """Test that demo includes health check"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        assert "await client.get(\"/health\")" in content, "Demo should include health check"
        assert "Health check:" in content, "Demo should print health check status"
    
    def test_demo_acceptance_scenario(self):
        """Test that acceptance scenario builds bond"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        assert "Building strong bond with target A" in content, "Acceptance scenario should build bond"
        assert "I really appreciate you" in content, "Acceptance should use appreciative language"
    
    def test_demo_rejection_scenario(self):
        """Test that rejection scenario induces sadness"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        assert "Target A suddenly rejects" in content, "Rejection scenario should show sudden rejection"
        assert "Leave me alone" in content, "Rejection should use distancing language"
    
    def test_demo_betrayal_scenario(self):
        """Test that betrayal scenario shows object-specific grudge"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        assert "Target B betrays" in content, "Betrayal scenario should involve target B"
        assert "object-specific grudge" in content, "Betrayal should demonstrate object-specific dynamics"
        assert "I've been lying to you" in content, "Betrayal should involve deception"
    
    def test_demo_separation_scenario(self):
        """Test that separation scenario shows attachment pain"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        assert "SEPARATION GAP" in content, "Separation scenario should be labeled"
        assert "attachment separation pain" in content, "Separation should mention attachment pain"
        assert "await asyncio.sleep(10)" in content, "Separation should include time delay"
    
    def test_demo_repair_scenario(self):
        """Test that repair scenario attempts relationship repair"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        assert "Target A attempts to repair" in content, "Repair scenario should involve repair attempts"
        assert "I'm really sorry" in content, "Repair should include apologies"
        assert "repair our relationship" in content, "Repair should explicitly mention relationship repair"
    
    def test_demo_summary_section(self):
        """Test that demo includes comprehensive summary"""
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        assert "DEMO SUMMARY:" in content, "Demo should include summary section"
        
        # Check for all scenario summaries
        summary_items = [
            "Acceptance: Built bond",
            "Rejection: Induced sadness",
            "Betrayal: Demonstrated object-specific grudge",
            "Separation: Showed attachment separation pain",
            "Repair: Attempted relationship repair"
        ]
        
        for item in summary_items:
            assert item in content, f"Demo summary should include: {item}"
    
    def test_demo_script_runnable(self):
        """Test that demo script can be executed without syntax errors"""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "scripts/demo_cli.py"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Demo script has syntax errors: {result.stderr}"


class TestDemoIntegration:
    """Integration tests for demo functionality"""
    
    @pytest.mark.asyncio
    async def test_demo_requires_running_daemon(self):
        """Test that demo requires a running daemon"""
        # This test verifies that the demo script properly handles
        # the case where the daemon is not running
        demo_path = Path("scripts/demo_cli.py")
        
        with open(demo_path, 'r') as f:
            content = f.read()
        
        # Check for proper error handling
        assert "Health check failed" in content, "Demo should handle health check failures"
        assert "except Exception as e" in content, "Demo should catch exceptions during health check"