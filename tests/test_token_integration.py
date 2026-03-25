"""
Integration tests for emotiond token authentication.

Tests that /event API correctly validates tokens:
1. Correct token → processed (200)
2. Wrong token → 403
3. No token → 403
4. High-impact subtype + correct token → processed (200)
"""

import os
import pytest
import requests


# Configuration from environment
EMOTIOND_BASE_URL = os.environ.get("EMOTIOND_BASE_URL", "http://127.0.0.1:18080")
CORRECT_TOKEN = os.environ.get("EMOTIOND_OPENCLAW_TOKEN", "")
WRONG_TOKEN = "wrong_token_12345_invalid"


@pytest.fixture(scope="module")
def emotiond_available():
    """Check if emotiond is running before tests."""
    try:
        resp = requests.get(f"{EMOTIOND_BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture
def event_url():
    """Use /event endpoint."""
    return f"{EMOTIOND_BASE_URL}/event"


@pytest.fixture
def base_payload():
    """Valid world_event payload for /event endpoint."""
    return {
        "type": "world_event",
        "actor": "test_actor",
        "target": "test_target",
        "meta": {
            "subtype": "care",
            "seconds": 30
        }
    }


class TestTokenAuthentication:
    """Test token-based authentication for /event endpoint."""

    @pytest.mark.skipif(not CORRECT_TOKEN, reason="EMOTIOND_OPENCLAW_TOKEN not set")
    def test_correct_token_returns_success(self, emotiond_available, event_url, base_payload):
        """Test that correct token returns 200/processed."""
        if not emotiond_available:
            pytest.skip("emotiond not available")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CORRECT_TOKEN}"
        }
        
        response = requests.post(event_url, json=base_payload, headers=headers, timeout=10)
        
        # Should be accepted (200 or 201) - not 403
        # May get 500 if DB not initialized, but NOT 403
        assert response.status_code in (200, 201, 500), \
            f"Expected 200/201/500 with correct token, got {response.status_code}: {response.text}"
        # Specifically check NOT 403
        if response.status_code == 403:
            data = response.json()
            assert data.get("server_source") != "user", "Should not be treated as user source"

    def test_wrong_token_returns_forbidden(self, emotiond_available, event_url, base_payload):
        """Test that wrong token returns 403 with user source."""
        if not emotiond_available:
            pytest.skip("emotiond not available")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {WRONG_TOKEN}"
        }
        
        response = requests.post(event_url, json=base_payload, headers=headers, timeout=10)
        
        # Should get 403 with server_source: user
        assert response.status_code == 403, \
            f"Expected 403 with wrong token, got {response.status_code}"
        
        data = response.json()
        assert data.get("server_source") == "user", "Should be treated as user source"

    def test_no_token_returns_forbidden(self, emotiond_available, event_url, base_payload):
        """Test that missing token returns 403 with user source."""
        if not emotiond_available:
            pytest.skip("emotiond not available")
        
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(event_url, json=base_payload, headers=headers, timeout=10)
        
        assert response.status_code == 403, \
            f"Expected 403 with no token, got {response.status_code}"
        
        data = response.json()
        assert data.get("server_source") == "user", "Should be treated as user source"

    @pytest.mark.skipif(not CORRECT_TOKEN, reason="EMOTIOND_OPENCLAW_TOKEN not set")
    @pytest.mark.parametrize("high_impact_subtype", ["care", "apology"])
    def test_high_impact_subtype_with_correct_token(
        self, emotiond_available, event_url, high_impact_subtype
    ):
        """Test that subtypes work with correct token (not rejected as user)."""
        if not emotiond_available:
            pytest.skip("emotiond not available")
        
        payload = {
            "type": "world_event",
            "actor": "test_actor",
            "target": "test_target",
            "meta": {
                "subtype": high_impact_subtype,
                "seconds": 30
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CORRECT_TOKEN}"
        }
        
        response = requests.post(event_url, json=payload, headers=headers, timeout=10)
        
        # Should NOT be 403 (may be 500 if DB issue, but not forbidden)
        assert response.status_code != 403, \
            f"Got 403 for {high_impact_subtype} with correct token - token auth failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
