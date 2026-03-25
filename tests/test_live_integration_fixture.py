"""
Live Integration Tests with Auto-starting Fixture (D4)

This module provides:
1. A pytest fixture that auto-starts emotiond on a random free port
2. Tests for start/stop, port conflict handling, health timeout messages
3. --no-live CLI option to disable live tests

Usage:
    pytest tests/test_live_integration_fixture.py -v          # Run with live fixture
    pytest tests/test_live_integration_fixture.py -v --no-live # Skip live tests
"""

import pytest
import subprocess
import socket
import time
import os
import signal
import sys
import tempfile
import requests
from pathlib import Path


def get_free_port():
    """Get a random free port from the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_health(url, timeout=30, interval=0.1):
    """Wait for emotiond /health endpoint to respond.
    
    Returns:
        tuple: (success: bool, attempts: int, last_error: str)
    """
    attempts = 0
    last_error = ""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        attempts += 1
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                return True, attempts, ""
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection refused"
        except requests.exceptions.Timeout:
            last_error = "Request timeout"
        except Exception as e:
            last_error = str(e)
        
        time.sleep(interval)
    
    return False, attempts, last_error


class EmotiondProcess:
    """Manages an emotiond process for testing."""
    
    def __init__(self, port=None, timeout=30):
        self.port = port or get_free_port()
        self.timeout = timeout
        self.process = None
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._health_attempts = 0
        self._health_error = ""
        
    def start(self):
        """Start emotiond process and wait for health check."""
        env = os.environ.copy()
        env["EMOTIOND_PORT"] = str(self.port)
        
        # Use the virtual environment's Python
        project_root = Path(__file__).parent.parent
        venv_python = project_root / ".venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = project_root / "venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = sys.executable
        
        cmd = [
            str(venv_python), "-m", "uvicorn",
            "emotiond.api:app",
            "--host", "127.0.0.1",
            "--port", str(self.port)
        ]
        
        self.process = subprocess.Popen(
            cmd,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # Wait for health check
        success, attempts, error = wait_for_health(self.base_url, self.timeout)
        self._health_attempts = attempts
        self._health_error = error
        
        if not success:
            self.stop()
            raise RuntimeError(
                f"emotiond failed to start on port {self.port} within {self.timeout}s. "
                f"Health check attempts: {attempts}. Last error: {error}"
            )
        
        return self
    
    def stop(self):
        """Stop the emotiond process."""
        if self.process is None:
            return
            
        try:
            # Try graceful termination first
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination fails
                self.process.kill()
                self.process.wait(timeout=5)
        except Exception:
            pass
        finally:
            self.process = None
    
    def is_running(self):
        """Check if the process is still running."""
        if self.process is None:
            return False
        return self.process.poll() is None
    
    def __enter__(self):
        return self.start()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


@pytest.fixture(scope="module")
def live_emotiond(request):
    """Fixture that provides a running emotiond instance.
    
    Auto-starts emotiond on a random free port, waits for /health,
    yields the base URL, then shuts down after tests complete.
    
    Use --no-live to skip these tests.
    """
    if request.config.getoption("--no-live"):
        pytest.skip("--no-live specified: skipping live integration tests")
    
    emotiond = EmotiondProcess()
    try:
        emotiond.start()
        yield emotiond
    finally:
        emotiond.stop()


# ============== Tests ==============

class TestEmotiondStartStop:
    """Tests for emotiond start/stop lifecycle."""
    
    def test_emotiond_starts_and_responds_to_health(self, live_emotiond):
        """Test that emotiond starts and responds to health check."""
        response = requests.get(f"{live_emotiond.base_url}/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "emotiond" in data
        assert data["emotiond"]["status"] == "running"
    
    def test_emotiond_health_contains_version(self, live_emotiond):
        """Test that health endpoint returns version info."""
        response = requests.get(f"{live_emotiond.base_url}/health", timeout=5)
        data = response.json()
        assert "version" in data["emotiond"]
        assert data["emotiond"]["version"] == "0.1.0"
    
    def test_emotiond_process_is_running(self, live_emotiond):
        """Test that the emotiond process is actually running."""
        assert live_emotiond.is_running()
        assert live_emotiond.process.poll() is None
    
    def test_emotiond_stops_cleanly(self):
        """Test that emotiond stops cleanly on request."""
        emotiond = EmotiondProcess()
        emotiond.start()
        assert emotiond.is_running()
        
        emotiond.stop()
        assert not emotiond.is_running()
    
    def test_emotiond_multiple_start_stop_cycles(self):
        """Test that emotiond can be started and stopped multiple times."""
        for i in range(3):
            emotiond = EmotiondProcess()
            emotiond.start()
            assert emotiond.is_running(), f"Failed on cycle {i+1}"
            
            # Verify it's responding
            response = requests.get(f"{emotiond.base_url}/health", timeout=5)
            assert response.status_code == 200
            
            emotiond.stop()
            assert not emotiond.is_running()


class TestPortHandling:
    """Tests for port assignment and conflict handling."""
    
    def test_get_free_port_returns_valid_port(self):
        """Test that get_free_port returns a valid, available port."""
        port = get_free_port()
        assert isinstance(port, int)
        assert 1024 <= port <= 65535
        
        # Verify the port is actually available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
    
    def test_get_free_port_returns_different_ports(self):
        """Test that get_free_port returns different ports on successive calls."""
        ports = [get_free_port() for _ in range(10)]
        # Most should be different (allow for rare collisions)
        unique_ports = len(set(ports))
        assert unique_ports >= 8, f"Expected mostly unique ports, got {unique_ports}/10 unique"
    
    def test_emotiond_uses_specified_port(self):
        """Test that emotiond uses the specified port."""
        specific_port = get_free_port()
        emotiond = EmotiondProcess(port=specific_port)
        try:
            emotiond.start()
            assert emotiond.port == specific_port
            
            # Verify it's actually listening on that port
            response = requests.get(f"http://127.0.0.1:{specific_port}/health", timeout=5)
            assert response.status_code == 200
        finally:
            emotiond.stop()
    
    def test_multiple_emotiond_on_different_ports(self):
        """Test that multiple emotiond instances can run on different ports."""
        emotiond1 = EmotiondProcess()
        emotiond2 = EmotiondProcess()
        
        try:
            emotiond1.start()
            emotiond2.start()
            
            assert emotiond1.port != emotiond2.port
            assert emotiond1.is_running()
            assert emotiond2.is_running()
            
            # Both should respond
            r1 = requests.get(f"{emotiond1.base_url}/health", timeout=5)
            r2 = requests.get(f"{emotiond2.base_url}/health", timeout=5)
            assert r1.status_code == 200
            assert r2.status_code == 200
        finally:
            emotiond1.stop()
            emotiond2.stop()
    
    def test_port_conflict_raises_error(self):
        """Test that starting emotiond on an occupied port raises an error."""
        # First, occupy a port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            occupied_port = s.getsockname()[1]
            
            # Try to start emotiond on the occupied port
            emotiond = EmotiondProcess(port=occupied_port, timeout=2)
            
            with pytest.raises(RuntimeError) as exc_info:
                emotiond.start()
            
            error_msg = str(exc_info.value)
            assert "failed to start" in error_msg.lower() or "timeout" in error_msg.lower()
            assert str(occupied_port) in error_msg


class TestHealthTimeoutMessages:
    """Tests for health check timeout behavior and error messages."""
    
    def test_wait_for_health_times_out_on_no_server(self):
        """Test that wait_for_health properly times out when no server is running."""
        # Use a port that's definitely not running (but not occupied)
        # Pick a high port that's unlikely to be used
        unused_port = 54321
        
        success, attempts, error = wait_for_health(
            f"http://127.0.0.1:{unused_port}", 
            timeout=1, 
            interval=0.1
        )
        
        assert success is False
        assert attempts >= 5  # Should have tried multiple times
    
    def test_health_timeout_error_message_includes_attempts(self):
        """Test that timeout error includes the number of attempts made."""
        # Occupy a port so emotiond can't start
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            occupied_port = s.getsockname()[1]
            
            emotiond = EmotiondProcess(port=occupied_port, timeout=1)
            
            with pytest.raises(RuntimeError) as exc_info:
                emotiond.start()
            
            error_msg = str(exc_info.value)
            assert "attempts" in error_msg.lower()
    
    def test_health_timeout_error_message_includes_port(self):
        """Test that timeout error includes the port number."""
        # Occupy a port so emotiond can't start
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            occupied_port = s.getsockname()[1]
            
            emotiond = EmotiondProcess(port=occupied_port, timeout=1)
            
            with pytest.raises(RuntimeError) as exc_info:
                emotiond.start()
            
            error_msg = str(exc_info.value)
            assert str(occupied_port) in error_msg
    
    def test_health_timeout_error_message_includes_timeout(self):
        """Test that timeout error includes the timeout duration."""
        # Occupy a port so emotiond can't start
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            occupied_port = s.getsockname()[1]
            
            emotiond = EmotiondProcess(port=occupied_port, timeout=1)
            
            with pytest.raises(RuntimeError) as exc_info:
                emotiond.start()
            
            error_msg = str(exc_info.value)
            assert "1s" in error_msg or "timeout" in error_msg.lower()
    
    def test_wait_for_health_success_returns_attempts(self, live_emotiond):
        """Test that successful health check returns attempt count."""
        # This test runs against a live emotiond
        success, attempts, error = wait_for_health(
            live_emotiond.base_url,
            timeout=5,
            interval=0.1
        )
        
        assert success is True
        assert attempts >= 1
        assert error == ""


class TestEventEndpointWithLiveServer:
    """Integration tests using the live emotiond fixture."""
    
    def test_event_endpoint_accepts_valid_event(self, live_emotiond):
        """Test that /event endpoint accepts a valid event."""
        headers = {"Content-Type": "application/json"}
        payload = {
            "type": "world_event",
            "actor": "user",
            "target": "assistant",
            "text": "Hello",
            "meta": {"source": "test"}
        }
        
        response = requests.post(
            f"{live_emotiond.base_url}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        # Should not crash (may be denied due to auth, but should not 500)
        assert response.status_code in [200, 201, 202, 403]
    
    def test_health_endpoint_returns_valid_json(self, live_emotiond):
        """Test that /health returns valid JSON structure."""
        response = requests.get(f"{live_emotiond.base_url}/health", timeout=5)
        data = response.json()
        
        assert "ok" in data
        assert "ts" in data
        assert "emotiond" in data
        assert "version" in data["emotiond"]
        assert "status" in data["emotiond"]


class TestNoLiveOption:
    """Tests for --no-live CLI option behavior."""
    
    def test_no_live_option_exists(self, pytestconfig):
        """Test that --no-live option is registered with pytest."""
        # This test verifies the option exists
        assert hasattr(pytestconfig.option, "no_live")
        assert isinstance(pytestconfig.option.no_live, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
