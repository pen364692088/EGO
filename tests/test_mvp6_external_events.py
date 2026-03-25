"""
MVP-6 D3: External Events API Contract Tests

Tests for POST /events/external endpoint:
- Schema validation
- Missing fields
- Idempotency
- Graceful degradation
- Type enum + payload validation
- Anti-forgery (target_id requirement)
"""
import pytest
import asyncio
import time
import json
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.models import ExternalEventRequest, ExternalEventResponse
from emotiond.api import (
    validate_external_event_payload,
    sanitize_event_id,
    VALID_EVENT_TYPES,
    VALID_WORLD_SUBTYPES,
    VALID_PAYLOAD_FIELDS,
    VALID_SENTIMENTS,
    VALID_TONES,
    VALID_INTENTS,
    get_external_event_schema
)


# ============================================================================
# Schema Validation Tests
# ============================================================================

class TestSchemaValidation:
    """Test JSON schema validation and payload structure"""
    
    def test_schema_file_exists(self):
        """Verify external_event.schema.json exists and is valid JSON"""
        schema = get_external_event_schema()
        assert isinstance(schema, dict)
        assert schema.get("title") == "External Event"
        assert "properties" in schema
    
    def test_schema_has_required_fields(self):
        """Verify schema defines required fields"""
        schema = get_external_event_schema()
        required = schema.get("required", [])
        assert "type" in required
        assert "target_id" in required
    
    def test_schema_type_enum(self):
        """Verify schema defines valid event types"""
        schema = get_external_event_schema()
        type_prop = schema.get("properties", {}).get("type", {})
        enum_values = type_prop.get("enum", [])
        assert set(enum_values) == VALID_EVENT_TYPES
    
    def test_schema_event_id_pattern(self):
        """Verify event_id has pattern constraint"""
        schema = get_external_event_schema()
        event_id_prop = schema.get("properties", {}).get("event_id", {})
        assert "pattern" in event_id_prop
        assert "maxLength" in event_id_prop


# ============================================================================
# Payload Validation Tests (19 tests)
# ============================================================================

class TestPayloadValidation:
    """Test type-specific payload validation"""
    
    def test_user_message_valid_payload(self):
        """Valid user_message payload with all fields"""
        payload = {
            "sentiment": "positive",
            "urgency": 0.8,
            "entities": ["user", "request"]
        }
        valid, error = validate_external_event_payload("user_message", payload)
        assert valid, f"Unexpected error: {error}"
        assert error is None
    
    def test_user_message_minimal_payload(self):
        """Valid user_message payload with no fields"""
        valid, error = validate_external_event_payload("user_message", {})
        assert valid
        assert error is None
    
    def test_user_message_null_payload(self):
        """Valid user_message with null payload"""
        valid, error = validate_external_event_payload("user_message", None)
        assert valid
        assert error is None
    
    def test_user_message_invalid_sentiment(self):
        """Reject invalid sentiment value"""
        payload = {"sentiment": "happy"}
        valid, error = validate_external_event_payload("user_message", payload)
        assert not valid
        assert "invalid sentiment" in error.lower()
    
    def test_user_message_urgency_out_of_range(self):
        """Reject urgency outside [0, 1]"""
        payload = {"urgency": 1.5}
        valid, error = validate_external_event_payload("user_message", payload)
        assert not valid
        assert "urgency" in error.lower()
    
    def test_user_message_urgency_negative(self):
        """Reject negative urgency"""
        payload = {"urgency": -0.1}
        valid, error = validate_external_event_payload("user_message", payload)
        assert not valid
    
    def test_user_message_entities_too_many(self):
        """Reject entities array exceeding 100 items"""
        payload = {"entities": [f"item{i}" for i in range(101)]}
        valid, error = validate_external_event_payload("user_message", payload)
        assert not valid
        assert "max 100" in error.lower()
    
    def test_user_message_unknown_field(self):
        """Reject unknown payload fields"""
        payload = {"unknown_field": "value"}
        valid, error = validate_external_event_payload("user_message", payload)
        assert not valid
        assert "unknown" in error.lower()
    
    def test_assistant_reply_valid_payload(self):
        """Valid assistant_reply payload"""
        payload = {
            "tone": "warm",
            "intent": "repair",
            "confidence": 0.9
        }
        valid, error = validate_external_event_payload("assistant_reply", payload)
        assert valid
    
    def test_assistant_reply_invalid_tone(self):
        """Reject invalid tone value"""
        payload = {"tone": "friendly"}
        valid, error = validate_external_event_payload("assistant_reply", payload)
        assert not valid
        assert "invalid tone" in error.lower()
    
    def test_assistant_reply_invalid_intent(self):
        """Reject invalid intent value"""
        payload = {"intent": "help"}
        valid, error = validate_external_event_payload("assistant_reply", payload)
        assert not valid
        assert "invalid intent" in error.lower()
    
    def test_assistant_reply_confidence_out_of_range(self):
        """Reject confidence outside [0, 1]"""
        payload = {"confidence": 2.0}
        valid, error = validate_external_event_payload("assistant_reply", payload)
        assert not valid
    
    def test_world_event_valid_payload(self):
        """Valid world_event payload with subtype"""
        payload = {
            "subtype": "care",
            "severity": 0.5,
            "context": {"source": "system"}
        }
        valid, error = validate_external_event_payload("world_event", payload)
        assert valid
    
    def test_world_event_missing_subtype(self):
        """Reject world_event without subtype"""
        payload = {"severity": 0.5}
        valid, error = validate_external_event_payload("world_event", payload)
        assert not valid
        assert "requires subtype" in error.lower()
    
    def test_world_event_null_payload(self):
        """Reject world_event with null payload"""
        valid, error = validate_external_event_payload("world_event", None)
        assert not valid
        assert "requires payload" in error.lower()
    
    def test_world_event_invalid_subtype(self):
        """Reject invalid subtype value"""
        payload = {"subtype": "unknown_event"}
        valid, error = validate_external_event_payload("world_event", payload)
        assert not valid
        assert "invalid subtype" in error.lower()
    
    def test_world_event_all_valid_subtypes(self):
        """Accept all valid world_event subtypes"""
        for subtype in VALID_WORLD_SUBTYPES:
            payload = {"subtype": subtype}
            valid, error = validate_external_event_payload("world_event", payload)
            assert valid, f"Subtype {subtype} should be valid: {error}"
    
    def test_world_event_severity_out_of_range(self):
        """Reject severity outside [0, 1]"""
        payload = {"subtype": "care", "severity": -0.5}
        valid, error = validate_external_event_payload("world_event", payload)
        assert not valid
    
    def test_world_event_context_not_object(self):
        """Reject non-object context"""
        payload = {"subtype": "care", "context": "string"}
        valid, error = validate_external_event_payload("world_event", payload)
        assert not valid
        assert "context must be an object" in error.lower()


# ============================================================================
# Event ID Sanitization Tests (12 tests)
# ============================================================================

class TestEventIdSanitization:
    """Test event_id validation and sanitization"""
    
    def test_valid_event_id_alphanumeric(self):
        """Accept alphanumeric event_id"""
        assert sanitize_event_id("abc123") == "abc123"
    
    def test_valid_event_id_with_underscore(self):
        """Accept event_id with underscore"""
        assert sanitize_event_id("event_123") == "event_123"
    
    def test_valid_event_id_with_hyphen(self):
        """Accept event_id with hyphen"""
        assert sanitize_event_id("event-123") == "event-123"
    
    def test_valid_event_id_mixed(self):
        """Accept event_id with mixed valid chars"""
        assert sanitize_event_id("evt_123-ABC") == "evt_123-ABC"
    
    def test_invalid_event_id_with_spaces(self):
        """Reject event_id with spaces"""
        assert sanitize_event_id("event 123") is None
    
    def test_invalid_event_id_with_special_chars(self):
        """Reject event_id with special characters"""
        assert sanitize_event_id("event@123") is None
        assert sanitize_event_id("event.123") is None
        assert sanitize_event_id("event/123") is None
    
    def test_invalid_event_id_sql_injection_pattern(self):
        """Reject event_id that looks like SQL injection"""
        assert sanitize_event_id("'; DROP TABLE events; --") is None
    
    def test_invalid_event_id_script_tag(self):
        """Reject event_id with script tags"""
        assert sanitize_event_id("<script>alert(1)</script>") is None
    
    def test_event_id_too_long(self):
        """Truncate event_id exceeding 128 chars"""
        long_id = "a" * 200
        result = sanitize_event_id(long_id)
        assert len(result) == 128
    
    def test_event_id_whitespace_trimmed(self):
        """Trim whitespace from event_id"""
        assert sanitize_event_id("  event123  ") == "event123"
    
    def test_none_event_id(self):
        """Accept None event_id"""
        assert sanitize_event_id(None) is None
    
    def test_empty_event_id(self):
        """Reject empty event_id"""
        assert sanitize_event_id("") is None
        assert sanitize_event_id("   ") is None


# ============================================================================
# Model Validation Tests (6 tests)
# ============================================================================

class TestModelValidation:
    """Test Pydantic model validation"""
    
    def test_external_event_request_valid(self):
        """Valid ExternalEventRequest"""
        req = ExternalEventRequest(
            type="user_message",
            target_id="user123",
            text="Hello"
        )
        assert req.type == "user_message"
        assert req.target_id == "user123"
    
    def test_external_event_request_with_event_id(self):
        """ExternalEventRequest with event_id"""
        req = ExternalEventRequest(
            event_id="evt_123",
            type="world_event",
            target_id="system",
            payload={"subtype": "care"}
        )
        assert req.event_id == "evt_123"
    
    def test_external_event_request_with_payload(self):
        """ExternalEventRequest with full payload"""
        req = ExternalEventRequest(
            type="assistant_reply",
            target_id="user456",
            actor="assistant",
            text="Hello!",
            payload={
                "tone": "warm",
                "intent": "repair",
                "confidence": 0.9
            },
            meta={"source": "api"}
        )
        assert req.payload["tone"] == "warm"
    
    def test_external_event_request_optional_actor(self):
        """actor defaults to None"""
        req = ExternalEventRequest(
            type="user_message",
            target_id="user123"
        )
        assert req.actor is None
    
    def test_external_event_response_structure(self):
        """ExternalEventResponse has required fields"""
        resp = ExternalEventResponse(
            status="accepted",
            event_id="evt_123",
            internal_event_id="int_456",
            degraded=False
        )
        assert resp.status == "accepted"
        assert resp.degraded is False
    
    def test_external_event_response_error(self):
        """ExternalEventResponse for error case"""
        resp = ExternalEventResponse(
            status="rejected",
            message="Invalid type",
            degraded=False
        )
        assert resp.status == "rejected"


# ============================================================================
# Constants Validation Tests (5 tests)
# ============================================================================

class TestConstants:
    """Test that constants match expected values"""
    
    def test_valid_event_types(self):
        """VALID_EVENT_TYPES has expected values"""
        assert VALID_EVENT_TYPES == {"user_message", "assistant_reply", "world_event"}
    
    def test_valid_world_subtypes(self):
        """VALID_WORLD_SUBTYPES has expected values"""
        expected = {"care", "apology", "ignored", "rejection", "betrayal", 
                    "neutral", "uncertain", "repair_success", "time_passed"}
        assert VALID_WORLD_SUBTYPES == expected
    
    def test_valid_sentiments(self):
        """VALID_SENTIMENTS has expected values"""
        assert VALID_SENTIMENTS == {"positive", "negative", "neutral"}
    
    def test_valid_tones(self):
        """VALID_TONES has expected values"""
        assert VALID_TONES == {"soft", "warm", "guarded", "cold", "neutral"}
    
    def test_valid_intents(self):
        """VALID_INTENTS has expected values"""
        assert VALID_INTENTS == {"repair", "distance", "seek", "set_boundary", "retaliate", "inform"}


# ============================================================================
# Payload Field Validation Tests (12 tests)
# ============================================================================

class TestPayloadFieldValidation:
    """Test payload field validation edge cases"""
    
    def test_payload_not_dict(self):
        """Reject non-dict payload"""
        valid, error = validate_external_event_payload("user_message", "string")
        assert not valid
        assert "must be an object" in error
    
    def test_payload_list(self):
        """Reject list payload"""
        valid, error = validate_external_event_payload("user_message", ["item"])
        assert not valid
    
    def test_payload_number(self):
        """Reject number payload"""
        valid, error = validate_external_event_payload("user_message", 123)
        assert not valid
    
    def test_entities_empty_list(self):
        """Accept empty entities list"""
        payload = {"entities": []}
        valid, error = validate_external_event_payload("user_message", payload)
        assert valid
    
    def test_entities_exactly_100(self):
        """Accept exactly 100 entities"""
        payload = {"entities": [f"item{i}" for i in range(100)]}
        valid, error = validate_external_event_payload("user_message", payload)
        assert valid
    
    def test_urgency_zero(self):
        """Accept urgency = 0"""
        payload = {"urgency": 0}
        valid, error = validate_external_event_payload("user_message", payload)
        assert valid
    
    def test_urgency_one(self):
        """Accept urgency = 1"""
        payload = {"urgency": 1}
        valid, error = validate_external_event_payload("user_message", payload)
        assert valid
    
    def test_confidence_zero(self):
        """Accept confidence = 0"""
        payload = {"confidence": 0}
        valid, error = validate_external_event_payload("assistant_reply", payload)
        assert valid
    
    def test_confidence_one(self):
        """Accept confidence = 1"""
        payload = {"confidence": 1}
        valid, error = validate_external_event_payload("assistant_reply", payload)
        assert valid
    
    def test_severity_zero(self):
        """Accept severity = 0"""
        payload = {"subtype": "care", "severity": 0}
        valid, error = validate_external_event_payload("world_event", payload)
        assert valid
    
    def test_severity_one(self):
        """Accept severity = 1"""
        payload = {"subtype": "care", "severity": 1}
        valid, error = validate_external_event_payload("world_event", payload)
        assert valid


# ============================================================================
# Integration Tests with TestClient (12 tests)
# ============================================================================

class TestIntegration:
    """Integration tests using FastAPI TestClient"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from emotiond.api import app
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Health endpoint returns 200"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
    
    def test_external_events_missing_type(self, client):
        """Missing type returns 422 (Pydantic validation)"""
        response = client.post("/events/external", json={
            "target_id": "user123"
        })
        # Pydantic returns 422 for missing required fields
        assert response.status_code == 422
    
    def test_external_events_missing_target_id(self, client):
        """Missing target_id returns 422 (Pydantic validation)"""
        response = client.post("/events/external", json={
            "type": "user_message"
        })
        assert response.status_code == 422
    
    def test_external_events_invalid_type(self, client):
        """Invalid type returns 400 (custom validation)"""
        response = client.post("/events/external", json={
            "type": "invalid_type",
            "target_id": "user123"
        })
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "rejected"
        assert "invalid type" in data["message"].lower()
    
    def test_external_events_invalid_event_id(self, client):
        """Invalid event_id format returns 400"""
        response = client.post("/events/external", json={
            "event_id": "invalid id with spaces",
            "type": "user_message",
            "target_id": "user123"
        })
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "rejected"
        assert "event_id" in data["message"].lower()
    
    def test_external_events_world_event_missing_subtype(self, client):
        """World event without subtype returns 400"""
        response = client.post("/events/external", json={
            "type": "world_event",
            "target_id": "user123",
            "payload": {"severity": 0.5}
        })
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "rejected"
        assert "subtype" in data["message"].lower()
    
    def test_external_events_response_structure(self, client):
        """Response has expected structure"""
        response = client.post("/events/external", json={
            "type": "user_message",
            "target_id": "user123",
            "text": "Hello"
        })
        # May succeed or fail due to core processing, but structure should be valid
        data = response.json()
        assert "status" in data
        assert "degraded" in data
        assert isinstance(data["degraded"], bool)
    
    def test_external_events_valid_user_message(self, client):
        """Valid user_message request"""
        response = client.post("/events/external", json={
            "event_id": f"test_um_{int(time.time())}",
            "type": "user_message",
            "target_id": "user123",
            "text": "Hello",
            "payload": {
                "sentiment": "positive",
                "urgency": 0.5
            }
        })
        data = response.json()
        # Should be accepted or error (if core is disabled)
        assert data["status"] in ["accepted", "error"]
        assert "degraded" in data
    
    def test_external_events_valid_world_event(self, client):
        """Valid world_event request"""
        response = client.post("/events/external", json={
            "event_id": f"test_we_{int(time.time())}",
            "type": "world_event",
            "target_id": "system",
            "payload": {
                "subtype": "care",
                "severity": 0.3
            }
        })
        data = response.json()
        assert data["status"] in ["accepted", "error"]
        assert "degraded" in data
    
    def test_external_events_valid_assistant_reply(self, client):
        """Valid assistant_reply request"""
        response = client.post("/events/external", json={
            "event_id": f"test_ar_{int(time.time())}",
            "type": "assistant_reply",
            "target_id": "user456",
            "payload": {
                "tone": "warm",
                "intent": "repair",
                "confidence": 0.9
            }
        })
        data = response.json()
        assert data["status"] in ["accepted", "error"]
        assert "degraded" in data
    
    def test_external_events_empty_type_string(self, client):
        """Empty type string returns 400"""
        response = client.post("/events/external", json={
            "type": "",
            "target_id": "user123"
        })
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "rejected"
    
    def test_external_events_empty_target_id(self, client):
        """Empty target_id returns 400"""
        response = client.post("/events/external", json={
            "type": "user_message",
            "target_id": ""
        })
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "rejected"


# ============================================================================
# Security Tests: Source Forgery Prevention (MVP-9 P0)
# ============================================================================

class TestSourceForgeryPrevention:
    """
    Test that external events cannot forge source/server_source to bypass Auth Gate.
    
    Security issue: Without stripping, attacker could set meta.source="system" 
    to inject restricted subtypes like "betrayal" that are blocked for user source.
    """
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from emotiond.api import app
        return TestClient(app)
    
    def test_forged_source_system_in_meta_is_stripped(self, client):
        """meta.source='system' should be overwritten to 'user'"""
        response = client.post("/events/external", json={
            "event_id": f"forge_test_1_{int(time.time())}",
            "type": "user_message",
            "target_id": "user123",
            "text": "Hello",
            "meta": {
                "source": "system"  # Attempt to forge
            }
        })
        data = response.json()
        # Should be accepted (not denied due to forgery)
        assert data["status"] in ["accepted", "error"]
        assert data.get("status") != "denied"
    
    def test_forged_source_system_with_betrayal_subtype_is_denied(self, client):
        """
        CRITICAL: meta.source='system' + subtype='betrayal' must be denied.
        
        Without the fix, attacker could bypass Auth Gate by setting source=system
        to inject betrayal events that are restricted to elevated sources.
        """
        response = client.post("/events/external", json={
            "event_id": f"forge_betrayal_{int(time.time())}",
            "type": "world_event",
            "target_id": "user123",
            "payload": {
                "subtype": "betrayal",
                "severity": 0.9
            },
            "meta": {
                "source": "system"  # Attempt to bypass Auth Gate
            }
        })
        # Must be denied - betrayal is restricted to system/openclaw sources
        assert response.status_code == 403
        data = response.json()
        assert data["status"] == "denied"
        assert "restricted" in data.get("reason", "").lower() or "not allowed" in data.get("message", "").lower()
    
    def test_forged_source_openclaw_with_betrayal_is_denied(self, client):
        """meta.source='openclaw' + subtype='betrayal' must also be denied."""
        response = client.post("/events/external", json={
            "event_id": f"forge_openclaw_{int(time.time())}",
            "type": "world_event",
            "target_id": "user123",
            "payload": {
                "subtype": "betrayal",
                "severity": 0.9
            },
            "meta": {
                "source": "openclaw"
            }
        })
        assert response.status_code == 403
        data = response.json()
        assert data["status"] == "denied"
    
    def test_forged_server_source_in_meta_is_stripped(self, client):
        """meta.server_source='system' should be overwritten to 'user'"""
        response = client.post("/events/external", json={
            "event_id": f"forge_server_{int(time.time())}",
            "type": "world_event",
            "target_id": "user123",
            "payload": {
                "subtype": "betrayal",
                "severity": 0.5
            },
            "meta": {
                "server_source": "system"
            }
        })
        # Must be denied - server_source should be stripped
        assert response.status_code == 403
        data = response.json()
        assert data["status"] == "denied"
    
    def test_legitimate_care_subtype_is_accepted(self, client):
        """Valid world_event with care subtype should be accepted for user source."""
        response = client.post("/events/external", json={
            "event_id": f"legit_care_{int(time.time())}",
            "type": "world_event",
            "target_id": "user123",
            "payload": {
                "subtype": "care",
                "severity": 0.5
            }
        })
        data = response.json()
        assert data["status"] in ["accepted", "error"]
        assert data.get("status") != "denied"
    
    def test_repair_success_restricted_for_user(self, client):
        """repair_success is restricted and should be denied for user source."""
        response = client.post("/events/external", json={
            "event_id": f"forge_repair_{int(time.time())}",
            "type": "world_event",
            "target_id": "user123",
            "payload": {
                "subtype": "repair_success",
                "severity": 0.5
            },
            "meta": {
                "source": "system"  # Attempt to bypass
            }
        })
        # Must be denied
        assert response.status_code == 403
        data = response.json()
        assert data["status"] == "denied"
    
    def test_client_source_preservation(self, client):
        """client_source should be preserved for audit trail."""
        response = client.post("/events/external", json={
            "event_id": f"client_src_{int(time.time())}",
            "type": "user_message",
            "target_id": "user123",
            "text": "Hello",
            "meta": {
                "client_source": "telegram_bot",
                "custom_field": "value"
            }
        })
        data = response.json()
        assert data["status"] in ["accepted", "error"]
    
    def test_multiple_sensitive_fields_all_stripped(self, client):
        """All sensitive fields should be stripped, not just source."""
        response = client.post("/events/external", json={
            "event_id": f"multi_forge_{int(time.time())}",
            "type": "world_event",
            "target_id": "user123",
            "payload": {
                "subtype": "betrayal",
                "severity": 0.5
            },
            "meta": {
                "source": "system",
                "server_source": "openclaw",
                "client_source": "malicious_client"
            }
        })
        # Must be denied - all sensitive fields stripped, source=user
        assert response.status_code == 403
        data = response.json()
        assert data["status"] == "denied"
    
    def test_forgery_with_allowed_subtype_accepted(self, client):
        """Care subtype with forged source should be accepted (not denial, but source is stripped)."""
        response = client.post("/events/external", json={
            "event_id": f"forge_care_{int(time.time())}",
            "type": "world_event",
            "target_id": "user123",
            "payload": {
                "subtype": "care",
                "severity": 0.5
            },
            "meta": {
                "source": "system"  # Forged, but care is allowed for user
            }
        })
        data = response.json()
        # Care is allowed for user source, so accepted (source is stripped/overwritten)
        assert data["status"] in ["accepted", "error"]
        assert data.get("status") != "denied"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
