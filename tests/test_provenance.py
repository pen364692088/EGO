"""Tests for US-643 Provenance + Signature Attribution."""

import pytest
from core.provenance import (
    Provenance,
    Source,
    sign_payload,
    verify_signature,
    sign_artifact,
    verify_artifact,
    is_internal_source,
    validate_provenance_for_write,
)


class TestProvenanceBasics:
    def test_provenance_creation(self):
        prov = Provenance(source=Source.SYSTEM)
        assert prov.source == Source.SYSTEM
        assert prov.timestamp is not None
        assert prov.trace_id is not None
        assert prov.signature is None
        assert prov.parent_id is None
    
    def test_provenance_serialization(self):
        prov = Provenance(source=Source.INFERENCE, parent_id="parent-123")
        data = prov.to_dict()
        assert data["source"] == "inference"
        assert data["parent_id"] == "parent-123"
        
        restored = Provenance.from_dict(data)
        assert restored.source == Source.INFERENCE
        assert restored.parent_id == "parent-123"


class TestSigning:
    def test_sign_and_verify_payload(self):
        payload = {"event": "test", "data": [1, 2, 3]}
        sig = sign_payload(payload, b"test-secret")
        assert len(sig) == 64  # SHA-256 hex
        assert verify_signature(payload, sig, b"test-secret")
    
    def test_verify_wrong_secret(self):
        payload = {"event": "test"}
        sig = sign_payload(payload, b"correct-secret")
        assert not verify_signature(payload, sig, b"wrong-secret")
    
    def test_verify_tampered_payload(self):
        payload = {"event": "test"}
        sig = sign_payload(payload, b"secret")
        tampered = {"event": "modified"}
        assert not verify_signature(tampered, sig, b"secret")


class TestArtifactSigning:
    def test_sign_artifact(self):
        artifact = {"type": "episode", "content": "test"}
        signed = sign_artifact(artifact.copy(), Source.SYSTEM)
        
        assert "provenance" in signed
        prov = signed["provenance"]
        assert prov["source"] == "system"
        assert prov["signature"] is not None
    
    def test_verify_signed_artifact(self):
        artifact = {"type": "episode", "content": "test"}
        signed = sign_artifact(artifact.copy(), Source.INFERENCE)
        
        assert verify_artifact(signed)
    
    def test_tampered_artifact_fails_verification(self):
        artifact = {"type": "episode", "content": "test"}
        signed = sign_artifact(artifact.copy(), Source.SYSTEM)
        
        # Tamper with content
        signed["content"] = "modified"
        assert not verify_artifact(signed)


class TestSourceValidation:
    def test_internal_sources(self):
        assert is_internal_source(Source.SYSTEM)
        assert is_internal_source(Source.INFERENCE)
        assert is_internal_source(Source.ROLLOUT)
        assert is_internal_source(Source.REFLECTION)
        assert is_internal_source(Source.MEMORY)
        assert not is_internal_source(Source.USER)
    
    def test_validate_missing_provenance(self):
        artifact = {"type": "episode"}
        valid, reason = validate_provenance_for_write(artifact)
        assert not valid
        assert reason == "missing_provenance"
    
    def test_validate_internal_without_signature(self):
        artifact = {
            "type": "episode",
            "provenance": {
                "source": "system",
                "signature": None,
            }
        }
        valid, reason = validate_provenance_for_write(artifact)
        assert not valid
        assert reason == "missing_signature_for_internal_source"
    
    def test_validate_valid_internal(self):
        artifact = sign_artifact({"type": "episode"}, Source.INFERENCE)
        valid, reason = validate_provenance_for_write(artifact)
        assert valid
        assert reason == "ok"
    
    def test_validate_user_source_allowed_without_sig(self):
        artifact = {
            "type": "episode",
            "provenance": {
                "source": "user",
                "signature": None,
            }
        }
        valid, reason = validate_provenance_for_write(artifact)
        # User sources are allowed without signature
        assert valid
