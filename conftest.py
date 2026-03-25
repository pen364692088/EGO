"""
pytest configuration for OpenEmotion tests with mock emotiond service.
"""

import pytest
import subprocess
import time
import sys
import os
import socket

# Add the fixtures directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tests', 'fixtures'))

# Mock server uses port 18081 to avoid conflicts with real daemon on 18080
MOCK_PORT = 18081


def is_port_in_use(port, host='127.0.0.1'):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def kill_process_on_port(port):
    """Kill any process using the specified port."""
    import subprocess
    try:
        result = subprocess.run(
            ['lsof', '-t', '-i', f':{port}'],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    subprocess.run(['kill', '-9', pid], capture_output=True)
                except Exception:
                    pass
    except Exception:
        pass


@pytest.fixture(scope='session')
def mock_emotiond():
    """Start mock emotiond service for integration tests."""
    # Import the mock server
    import mock_emotiond
    
    # Kill any existing process on the mock port
    kill_process_on_port(MOCK_PORT)
    time.sleep(0.5)
    
    # Start the server on dedicated mock port
    httpd, server_thread = mock_emotiond.start_mock_server(port=MOCK_PORT)
    
    # Give it time to start
    time.sleep(1)
    
    # Set environment variables for tests (mock server URL)
    os.environ['EMOTIOND_URL'] = f'http://127.0.0.1:{MOCK_PORT}'
    os.environ['EMOTIOND_OPENCLAW_TOKEN'] = '93e0a7a76de9e871b5c3ce658ce2c426b2ab69148b7b88b73100db0356ffcc72'
    
    yield {
        'url': f'http://127.0.0.1:{MOCK_PORT}',
        'token': '93e0a7a76de9e871b5c3ce658ce2c426b2ab69148b7b88b73100db0356ffcc72'
    }
    
    # Cleanup
    try:
        httpd.shutdown()
        server_thread.join(timeout=5)
    except Exception:
        pass
    finally:
        # Ensure port is freed
        kill_process_on_port(MOCK_PORT)


@pytest.fixture(scope='session')
def emotiond_available(mock_emotiond):
    """Override the original emotiond_available fixture to always return True."""
    return True
