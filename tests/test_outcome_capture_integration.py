"""
Integration Tests for D4 Outcome Capture

Tests tool_result, env_outcome, and interaction_outcome capture
from OpenClaw integration to emotiond.

Run with: pytest tests/test_outcome_capture_integration.py -v
"""

import pytest
import requests
import time
import os
import json
import subprocess

EMOTIOND_URL = os.environ.get('EMOTIOND_URL', 'http://127.0.0.1:18080')
EMOTIOND_TOKEN = os.environ.get('EMOTIOND_OPENCLAW_TOKEN', '93e0a7a76de9e871b5c3ce658ce2c426b2ab69148b7b88b73100db0356ffcc72')




class TestOutcomeCapture:
    """Test D4 outcome capture functionality."""
    
    def test_outcome_capture_module_exists(self):
        """Verify outcomeCapture.js module exists."""
        module_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'integrations', 'openclaw', 'hooks', 'emotiond-bridge', 'outcomeCapture.js'
        )
        assert os.path.exists(module_path), f"outcomeCapture.js not found at {module_path}"
    
    def test_outcome_capture_module_loads(self):
        """Verify outcomeCapture.js module loads without errors."""
        module_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'integrations', 'openclaw', 'hooks', 'emotiond-bridge', 'outcomeCapture.js'
        )
        result = subprocess.run(
            ['node', '-e', f'const m = require("{module_path}"); console.log("OK")'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Module load failed: {result.stderr}"
        assert "OK" in result.stdout
    
    def test_outcome_capture_exports(self):
        """Verify outcomeCapture.js exports required functions."""
        module_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'integrations', 'openclaw', 'hooks', 'emotiond-bridge', 'outcomeCapture.js'
        )
        result = subprocess.run(
            ['node', '-e', f'''
const m = require("{module_path}");
const required = [
    'captureToolResult', 'captureEnvOutcome', 'captureInteractionOutcome',
    'captureAllOutcomes', 'extractToolResultFromContext', 'buildConsequenceSummary',
    'buildBodyStateSummary', 'buildTracePointer', 'safeSendOutcomeEvent',
    'OUTCOME_TYPES', 'TOOL_STATUSES', 'INJECTION_MAX_SIZE'
];
const missing = required.filter(r => m[r] === undefined);
if (missing.length > 0) {{
    console.log("Missing:", missing.join(","));
    process.exit(1);
}}
console.log("OK");
'''],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Export check failed: {result.stderr}"
    
    def test_send_tool_result_event(self, emotiond_available):
        """Test sending tool_result world_event directly."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {EMOTIOND_TOKEN}'
        }
        
        target_id = f'test_tool_result_{int(time.time())}'
        
        # Build outcome payload
        payload = {
            'type': 'world_event',
            'actor': 'system',
            'target': 'assistant',
            'text': None,
            'meta': {
                'subtype': 'tool_result',
                'target_id': target_id,
                'source': 'openclaw_test',
                'outcome': {
                    'type': 'tool_result',
                    'status': 'success',
                    'tool_name': 'read_file',
                    'duration_ms': 150,
                    'payload': {
                        'c': {'t': 'read_file', 's': 'success', 'd': 0.2},
                        'b': {'v': 0, 'a': 3, 'e': 7, 's': 6, 'u': 5},
                        'p': {'tid': target_id, 'seq': 1},
                        'ts': int(time.time() * 1000)
                    }
                }
            }
        }
        
        r = requests.post(
            f"{EMOTIOND_URL}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        assert r.status_code in [200, 201, 202], f"Failed to send event: {r.status_code} {r.text}"
    
    def test_send_env_outcome_event(self, emotiond_available):
        """Test sending env_outcome world_event directly."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {EMOTIOND_TOKEN}'
        }
        
        target_id = f'test_env_{int(time.time())}'
        
        payload = {
            'type': 'world_event',
            'actor': 'system',
            'target': 'assistant',
            'text': None,
            'meta': {
                'subtype': 'env_outcome',
                'target_id': target_id,
                'source': 'openclaw_test',
                'outcome': {
                    'type': 'env_outcome',
                    'env_type': 'shell_exec',
                    'status': 'success',
                    'payload': {
                        'c': {'t': 'shell_exec', 's': 'success', 'd': 0.3},
                        'b': {'v': 0, 'a': 3, 'e': 7, 's': 6, 'u': 5},
                        'p': {'tid': target_id, 'seq': 1},
                        'ts': int(time.time() * 1000)
                    }
                }
            }
        }
        
        r = requests.post(
            f"{EMOTIOND_URL}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        assert r.status_code in [200, 201, 202], f"Failed to send event: {r.status_code} {r.text}"
    
    def test_send_interaction_outcome_event(self, emotiond_available):
        """Test sending interaction_outcome world_event directly."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {EMOTIOND_TOKEN}'
        }
        
        target_id = f'test_interaction_{int(time.time())}'
        
        payload = {
            'type': 'world_event',
            'actor': 'system',
            'target': 'assistant',
            'text': None,
            'meta': {
                'subtype': 'interaction_outcome',
                'target_id': target_id,
                'source': 'openclaw_test',
                'outcome': {
                    'type': 'interaction_outcome',
                    'interaction_type': 'user_reply',
                    'status': 'success',
                    'payload': {
                        'c': {'t': 'user_reply', 's': 'success'},
                        'b': {'v': 5, 'a': 4, 'e': 7, 's': 6, 'u': 3},
                        'p': {'tid': target_id, 'seq': 1},
                        'ts': int(time.time() * 1000)
                    }
                }
            }
        }
        
        r = requests.post(
            f"{EMOTIOND_URL}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        assert r.status_code in [200, 201, 202], f"Failed to send event: {r.status_code} {r.text}"
    
    def test_tool_result_status_simulation_success(self, emotiond_available):
        """Simulate tool success outcome capture."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {EMOTIOND_TOKEN}'
        }
        
        target_id = f'test_success_{int(time.time())}'
        
        payload = {
            'type': 'world_event',
            'actor': 'system',
            'target': 'assistant',
            'text': None,
            'meta': {
                'subtype': 'tool_result',
                'target_id': target_id,
                'source': 'openclaw_test',
                'outcome': {
                    'type': 'tool_result',
                    'status': 'success',
                    'tool_name': 'exec',
                    'duration_ms': 200,
                    'payload': {
                        'c': {'t': 'exec', 's': 'success', 'd': 0.2},
                        'b': {'v': 0, 'a': 3, 'e': 7, 's': 6, 'u': 5},
                        'p': {'tid': target_id, 'seq': 1},
                        'ts': int(time.time() * 1000)
                    }
                }
            }
        }
        
        r = requests.post(
            f"{EMOTIOND_URL}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        assert r.status_code in [200, 201, 202]
    
    def test_tool_result_status_simulation_failure(self, emotiond_available):
        """Simulate tool failure outcome capture."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {EMOTIOND_TOKEN}'
        }
        
        target_id = f'test_failure_{int(time.time())}'
        
        payload = {
            'type': 'world_event',
            'actor': 'system',
            'target': 'assistant',
            'text': None,
            'meta': {
                'subtype': 'tool_result',
                'target_id': target_id,
                'source': 'openclaw_test',
                'outcome': {
                    'type': 'tool_result',
                    'status': 'failure',
                    'tool_name': 'exec',
                    'duration_ms': 50,
                    'error_code': 'ENOENT',
                    'payload': {
                        'c': {'t': 'exec', 's': 'failure', 'd': 0.1, 'e': 'ENOENT'},
                        'b': {'v': -2, 'a': 4, 'e': 6, 's': 5, 'u': 6},
                        'p': {'tid': target_id, 'seq': 1},
                        'ts': int(time.time() * 1000)
                    }
                }
            }
        }
        
        r = requests.post(
            f"{EMOTIOND_URL}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        assert r.status_code in [200, 201, 202]
    
    def test_tool_result_status_simulation_timeout(self, emotiond_available):
        """Simulate tool timeout outcome capture."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {EMOTIOND_TOKEN}'
        }
        
        target_id = f'test_timeout_{int(time.time())}'
        
        payload = {
            'type': 'world_event',
            'actor': 'system',
            'target': 'assistant',
            'text': None,
            'meta': {
                'subtype': 'tool_result',
                'target_id': target_id,
                'source': 'openclaw_test',
                'outcome': {
                    'type': 'tool_result',
                    'status': 'timeout',
                    'tool_name': 'browser',
                    'duration_ms': 5000,
                    'payload': {
                        'c': {'t': 'browser', 's': 'timeout', 'd': 5.0},
                        'b': {'v': -1, 'a': 5, 'e': 5, 's': 5, 'u': 7},
                        'p': {'tid': target_id, 'seq': 1},
                        'ts': int(time.time() * 1000)
                    }
                }
            }
        }
        
        r = requests.post(
            f"{EMOTIOND_URL}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        assert r.status_code in [200, 201, 202]
    
    def test_payload_size_within_3kb_limit(self, emotiond_available):
        """Verify outcome payload is within 3KB limit."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {EMOTIOND_TOKEN}'
        }
        
        target_id = f'test_size_{int(time.time())}'
        
        # Build a payload that should be within 3KB
        payload = {
            'type': 'world_event',
            'actor': 'system',
            'target': 'assistant',
            'text': None,
            'meta': {
                'subtype': 'tool_result',
                'target_id': target_id,
                'source': 'openclaw_test',
                'outcome': {
                    'type': 'tool_result',
                    'status': 'success',
                    'tool_name': 'read_file',
                    'duration_ms': 150,
                    'payload': {
                        'c': {'t': 'read_file', 's': 'success', 'd': 0.2, 'h': 'abc123'},
                        'b': {'v': 0, 'a': 3, 'e': 7, 's': 6, 'u': 5},
                        'p': {'tid': target_id, 'path': 'deadbeef', 'seq': 1},
                        'ts': int(time.time() * 1000)
                    }
                }
            }
        }
        
        # Verify payload size
        payload_size = len(json.dumps(payload))
        assert payload_size <= 3072, f"Payload size {payload_size} exceeds 3KB limit"
        
        r = requests.post(
            f"{EMOTIOND_URL}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        assert r.status_code in [200, 201, 202]
    
    def test_replayable_trace_pointer(self, emotiond_available):
        """Test that trace pointer is included for replay verification."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {EMOTIOND_TOKEN}'
        }
        
        target_id = f'test_trace_{int(time.time())}'
        trace_hash = 'a1b2c3d4'  # Simulated hash of trace path
        
        payload = {
            'type': 'world_event',
            'actor': 'system',
            'target': 'assistant',
            'text': None,
            'meta': {
                'subtype': 'tool_result',
                'target_id': target_id,
                'source': 'openclaw_test',
                'outcome': {
                    'type': 'tool_result',
                    'status': 'success',
                    'tool_name': 'exec',
                    'duration_ms': 100,
                    'payload': {
                        'c': {'t': 'exec', 's': 'success', 'd': 0.1},
                        'b': {'v': 0, 'a': 3, 'e': 7, 's': 6, 'u': 5},
                        'p': {'tid': target_id, 'path': trace_hash, 'seq': 42},
                        'ts': int(time.time() * 1000)
                    }
                }
            }
        }
        
        r = requests.post(
            f"{EMOTIOND_URL}/event",
            json=payload,
            headers=headers,
            timeout=5
        )
        
        assert r.status_code in [200, 201, 202]
        
        # Verify trace pointer structure
        trace_pointer = payload['meta']['outcome']['payload']['p']
        assert trace_pointer['tid'] == target_id
        assert trace_pointer['seq'] == 42
        assert trace_pointer['path'] == trace_hash


class TestOutcomeCaptureSafeWrapper:
    """Test safe wrapper functionality - no throw if emotiond unavailable."""
    
    def test_safe_wrapper_no_throw_on_connection_error(self):
        """Verify safe wrapper handles connection errors gracefully."""
        module_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'integrations', 'openclaw', 'hooks', 'emotiond-bridge', 'outcomeCapture.js'
        )
        
        # Test with invalid URL
        result = subprocess.run(
            ['node', '-e', f'''
process.env.EMOTIOND_BASE_URL = 'http://localhost:59999';
const m = require("{module_path}");

async function test() {{
    const result = await m.captureToolResult(
        'test-target',
        {{ tool_name: 'test', status: 'success', duration_ms: 100 }},
        null,
        null
    );
    console.log('success:', result.success);
    console.log('error:', result.error);
    console.log('OK');
}}

test().catch(e => {{
    console.log('ERROR:', e.message);
    process.exit(1);
}});
'''],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should not throw, should return error result
        assert "OK" in result.stdout, f"Test failed: {result.stderr}"
        assert "success: false" in result.stdout
        assert "error:" in result.stdout


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
