"""
Tests for MVP-2.1.1: Server-side source resolution + meta sanitization + time_passed clamp.

Tests:
1. Spoof attempt: user sends meta.source="system" with betrayal → DENY
2. Valid system token: betrayal → ALLOW
3. Valid openclaw token: repair_success → ALLOW
4. Unknown meta key from user → DENY with audit reason
5. time_passed user seconds=100000 → ALLOW, clamped to 300, clamped_from recorded
6. time_passed user seconds=0 → DENY
7. Server-decided meta.source saved even if client sent different
8. eval_suite uses system/openclaw token and passes
"""
import pytest
import os
import sys
import tempfile
import asyncio
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.security import (
    resolve_server_source,
    sanitize_meta_for_user,
    validate_event_for_source,
    USER_ALLOWED_SUBTYPES,
    USER_ALLOWED_META_KEYS,
    TIME_PASSED_MIN_SECONDS,
    TIME_PASSED_MAX_SECONDS
)


class TestSourceResolution:
    """Test 1, 7: Server-side source resolution"""
    
    def test_no_token_returns_user(self):
        """No token → user source"""
        assert resolve_server_source(None, None) == "user"
    
    def test_empty_token_returns_user(self):
        """Empty token → user source"""
        assert resolve_server_source("", "") == "user"
    
    def test_system_token_bearer_header(self, monkeypatch):
        """Valid system token in Bearer header → system source"""
        monkeypatch.setenv("EMOTIOND_SYSTEM_TOKEN", "secret-system-token")
        result = resolve_server_source("Bearer secret-system-token", None)
        assert result == "system"
    
    def test_system_token_x_header(self, monkeypatch):
        """Valid system token in X-Emotiond-Token header → system source"""
        monkeypatch.setenv("EMOTIOND_SYSTEM_TOKEN", "secret-system-token")
        result = resolve_server_source(None, "secret-system-token")
        assert result == "system"
    
    def test_openclaw_token_bearer_header(self, monkeypatch):
        """Valid openclaw token in Bearer header → openclaw source"""
        monkeypatch.setenv("EMOTIOND_OPENCLAW_TOKEN", "secret-openclaw-token")
        result = resolve_server_source("Bearer secret-openclaw-token", None)
        assert result == "openclaw"
    
    def test_openclaw_token_x_header(self, monkeypatch):
        """Valid openclaw token in X-Emotiond-Token header → openclaw source"""
        monkeypatch.setenv("EMOTIOND_OPENCLAW_TOKEN", "secret-openclaw-token")
        result = resolve_server_source(None, "secret-openclaw-token")
        assert result == "openclaw"
    
    def test_invalid_token_returns_user(self, monkeypatch):
        """Invalid token → user source"""
        monkeypatch.setenv("EMOTIOND_SYSTEM_TOKEN", "secret-system-token")
        monkeypatch.setenv("EMOTIOND_OPENCLAW_TOKEN", "secret-openclaw-token")
        result = resolve_server_source("Bearer wrong-token", None)
        assert result == "user"
    
    def test_bearer_header_case_insensitive(self, monkeypatch):
        """Bearer header is case-insensitive"""
        monkeypatch.setenv("EMOTIOND_SYSTEM_TOKEN", "secret-token")
        result = resolve_server_source("bearer secret-token", None)
        assert result == "system"


class TestMetaSanitization:
    """Test 1, 4, 5, 6: Meta sanitization for user source"""
    
    def test_spoof_attempt_betrayal_denied(self):
        """Test 1: User sends meta.source="system" with betrayal → DENY"""
        meta = {"subtype": "betrayal", "source": "system"}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        assert deny_reason is not None
        assert "betrayal" in deny_reason.lower()
        assert "betrayal" in deny_reason.lower()
        assert audit_info is not None
        assert "denied_subtype" in audit_info
    
    def test_spoof_attempt_repair_success_denied(self):
        """Repair_success from user → DENY"""
        meta = {"subtype": "repair_success", "source": "system"}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        assert deny_reason is not None
        assert "repair_success" in deny_reason.lower()
        assert "repair_success" in deny_reason.lower()
    
    def test_unknown_meta_key_denied(self):
        """Test 4: Unknown meta key from user → DENY"""
        meta = {"subtype": "care", "unauthorized_key": "value"}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        assert deny_reason is not None
        assert "unknown meta keys" in deny_reason.lower()
        assert "unknown meta keys" in deny_reason.lower()
        assert audit_info is not None
        assert "denied_keys" in audit_info
        assert "unauthorized_key" in audit_info["denied_keys"]
    
    def test_time_passed_clamped(self):
        """Test 5: time_passed user seconds=100000 → clamped to 300, clamped_from recorded"""
        meta = {"subtype": "time_passed", "seconds": 100000}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        assert deny_reason is None
        assert sanitized["seconds"] == TIME_PASSED_MAX_SECONDS  # 300
        assert sanitized["clamped_from"] == 100000
        assert audit_info is not None
        assert audit_info["original_seconds"] == 100000
        assert audit_info["clamped_to"] == 300
    
    def test_time_passed_below_minimum_denied(self):
        """Test 6: time_passed user seconds=0 → DENY"""
        meta = {"subtype": "time_passed", "seconds": 0}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        assert deny_reason is not None
        assert "must be >=" in deny_reason.lower()
        assert "must be >=" in deny_reason.lower()
    
    def test_time_passed_negative_denied(self):
        """time_passed with negative seconds → DENY"""
        meta = {"subtype": "time_passed", "seconds": -10}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        assert deny_reason is not None
        assert "must be >=" in deny_reason.lower()
    
    def test_time_passed_valid_allowed(self):
        """Valid time_passed → ALLOW"""
        meta = {"subtype": "time_passed", "seconds": 60}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        assert deny_reason is None
        assert sanitized["seconds"] == 60
        assert "clamped_from" not in sanitized
    
    def test_allowed_subtypes_pass(self):
        """All user-allowed subtypes pass"""
        for subtype in USER_ALLOWED_SUBTYPES:
            meta = {"subtype": subtype}
            if subtype == "time_passed":
                meta["seconds"] = 60
            sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
            
            assert deny_reason is None, f"Subtype {subtype} should be allowed"
    
    def test_non_world_event_passes_through(self):
        """Non-world_event types pass through"""
        meta = {"source": "user", "custom_key": "value"}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "user_message")
        
        assert deny_reason is None
        assert sanitized == meta


class TestValidateEventForSource:
    """Test source-aware validation"""
    
    def test_system_source_allows_betrayal(self):
        """Test 2: Valid system token → betrayal ALLOW"""
        meta = {"subtype": "betrayal"}
        allowed, deny_reason, sanitized = validate_event_for_source(
            "world_event", meta, "system"
        )
        
        assert allowed is True
        assert deny_reason is None
        assert sanitized == meta
    
    def test_openclaw_source_allows_repair_success(self):
        """Test 3: Valid openclaw token → repair_success ALLOW"""
        meta = {"subtype": "repair_success"}
        allowed, deny_reason, sanitized = validate_event_for_source(
            "world_event", meta, "openclaw"
        )
        
        assert allowed is True
        assert deny_reason is None
        assert sanitized == meta
    
    def test_user_source_denies_betrayal(self):
        """User source → betrayal DENY"""
        meta = {"subtype": "betrayal"}
        allowed, deny_reason, sanitized = validate_event_for_source(
            "world_event", meta, "user"
        )
        
        assert allowed is False
        assert deny_reason is not None  # betrayal is restricted for user source
    
    def test_system_source_allows_unknown_keys(self):
        """System source allows unknown meta keys"""
        meta = {"subtype": "betrayal", "custom_key": "value", "another_key": 123}
        allowed, deny_reason, sanitized = validate_event_for_source(
            "world_event", meta, "system"
        )
        
        assert allowed is True
        assert deny_reason is None
        assert sanitized == meta


class TestClientSourcePreservation:
    """Test 7: Server-decided meta.source saved even if client sent different"""
    
    def test_source_key_ignored_in_sanitizer(self):
        """source key is excluded from sanitizer check (API layer handles it)"""
        meta = {"subtype": "care", "source": "spoofed-system"}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        # The source key is excluded from unknown_keys check since API layer overwrites it
        # The sanitizer just passes it through; API layer will overwrite with server_source
        assert deny_reason is None
        assert sanitized["subtype"] == "care"
        # Note: source will be overwritten by api.py with server-decided value
    
    def test_client_source_key_allowed(self):
        """client_source key is allowed in user meta"""
        meta = {"subtype": "care", "client_source": "user-reported"}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        assert deny_reason is None
        assert sanitized["client_source"] == "user-reported"


class TestIntegrationWithAPI:
    """Integration tests with FastAPI app"""
    
    @pytest.fixture
    def test_env(self, monkeypatch, tmp_path):
        """Set up test environment"""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("EMOTIOND_DB_PATH", str(db_path))
        monkeypatch.setenv("EMOTIOND_SYSTEM_TOKEN", "test-system-token")
        monkeypatch.setenv("EMOTIOND_OPENCLAW_TOKEN", "test-openclaw-token")
        return {
            "db_path": str(db_path),
            "system_token": "test-system-token",
            "openclaw_token": "test-openclaw-token"
        }
    
    def test_full_integration(self, test_env):
        """Full integration test with FastAPI app"""
        # This would require starting the daemon, which is done in eval_suite
        # Here we just verify the security module works correctly
        pass


class TestAllowedSubtypesAndKeys:
    """Verify allowed subtypes and keys"""
    
    def test_user_allowed_subtypes_complete(self):
        """Verify all user-allowed subtypes are defined"""
        expected = {"care", "rejection", "ignored", "apology", "time_passed"}
        assert USER_ALLOWED_SUBTYPES == expected
    
    def test_user_allowed_meta_keys_complete(self):
        """Verify all user-allowed meta keys are defined (source is server-controlled)"""
        expected = {"subtype", "seconds", "client_source", "request_id", "test", "severity"}
        assert USER_ALLOWED_META_KEYS == expected
    
    def test_time_passed_bounds(self):
        """Verify time_passed bounds"""
        assert TIME_PASSED_MIN_SECONDS == 1
        assert TIME_PASSED_MAX_SECONDS == 300


class TestEdgeCases:
    """Edge case tests"""
    
    def test_none_meta(self):
        """None meta should be handled"""
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(None, "world_event")
        assert deny_reason is None
        assert sanitized == {}
    
    def test_empty_meta(self):
        """Empty meta should be handled"""
        sanitized, deny_reason, audit_info = sanitize_meta_for_user({}, "world_event")
        assert deny_reason is None
        assert sanitized == {}
    
    def test_meta_without_subtype(self):
        """Meta without subtype should pass (backward compatibility for generic world_events)"""
        meta = {"custom_key": "value"}
        sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, "world_event")
        
        # Should pass - no subtype means backward compatibility mode
        assert deny_reason is None  # No subtype = backward compatibility
    
    def test_time_passed_at_boundary(self):
        """time_passed at exact boundaries"""
        # At minimum
        meta = {"subtype": "time_passed", "seconds": 1}
        sanitized, deny_reason, _ = sanitize_meta_for_user(meta, "world_event")
        assert deny_reason is None
        assert sanitized["seconds"] == 1
        
        # At maximum
        meta = {"subtype": "time_passed", "seconds": 300}
        sanitized, deny_reason, _ = sanitize_meta_for_user(meta, "world_event")
        assert deny_reason is None
        assert sanitized["seconds"] == 300
        assert "clamped_from" not in sanitized


class TestAPITokenRequired:
    """Test 8: eval_suite uses system/openclaw token and passes"""
    
    def test_eval_suite_token_missing(self, monkeypatch):
        """Verify eval_suite requires token - exits with error"""
        # Import and check - should exit
        import subprocess
        
        code = """
import os
import sys
os.environ.pop("EMOTIOND_SYSTEM_TOKEN", None)
sys.path.insert(0, ".")
from scripts.eval_suite import get_system_token
get_system_token()  # This should exit
print("FAIL: Should have exited")
"""
        result = subprocess.run(
            [".venv/bin/python", "-c", code],
            capture_output=True,
            text=True,
            cwd="/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion"
        )
        
        # Should have non-zero exit code
        assert result.returncode != 0, f"Expected non-zero exit, got: {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "ERROR" in result.stdout or "ERROR" in result.stderr, f"Expected error in stderr: {result.stderr}"
    
    def test_eval_suite_token_present(self, monkeypatch):
        """Verify eval_suite works with token present"""
        import subprocess
        import sys
        
        code = '''
import os
import sys
os.environ["EMOTIOND_SYSTEM_TOKEN"] = "test-token"
sys.path.insert(0, "/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion")
from scripts.eval_suite import get_system_token; get_system_token()
print("Token:", get_system_token())
'''
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "test-token" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
