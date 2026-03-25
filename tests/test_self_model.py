"""Tests for US-701 Self-Model v0."""

import pytest
from core.self_model import (
    Identity,
    CapabilityBoundary,
    OwnershipBoundary,
    SelfModel,
    BoundaryType,
    render_self_report,
    validate_self_report,
)


class TestIdentity:
    def test_default_identity(self):
        identity = Identity()
        assert identity.name == "OpenEmotion Agent"
        assert len(identity.principles) > 0
        assert len(identity.long_term_goals) > 0
    
    def test_serialization(self):
        identity = Identity(
            name="Test Agent",
            principles=["principle1", "principle2"],
            preferences={"pref1": 0.5},
        )
        data = identity.to_dict()
        restored = Identity.from_dict(data)
        assert restored.name == "Test Agent"
        assert len(restored.principles) == 2


class TestCapabilityBoundary:
    def test_can_do_allowed(self):
        cap = CapabilityBoundary()
        result = cap.check_capability("analyze_emotions")
        assert result["allowed"] is True
    
    def test_cannot_do_blocked(self):
        cap = CapabilityBoundary()
        result = cap.check_capability("modify_user_data")
        assert result["allowed"] is False
        assert result["reason"] == "capability_limited"
    
    def test_needs_tools(self):
        cap = CapabilityBoundary()
        result = cap.check_capability("web_search")
        assert result["allowed"] is True
        assert result["reason"] == "requires_tools"
    
    def test_unknown_capability(self):
        cap = CapabilityBoundary()
        result = cap.check_capability("unknown_action")
        assert result["allowed"] is False


class TestOwnershipBoundary:
    def test_classify_self(self):
        owner = OwnershipBoundary()
        assert owner.classify("my_thoughts") == BoundaryType.SELF
        assert owner.classify("my_emotions") == BoundaryType.SELF
    
    def test_classify_other(self):
        owner = OwnershipBoundary()
        assert owner.classify("user_emotions") == BoundaryType.OTHER
        assert owner.classify("user_preferences") == BoundaryType.OTHER
    
    def test_classify_environment(self):
        owner = OwnershipBoundary()
        assert owner.classify("external_events") == BoundaryType.ENVIRONMENT


class TestSelfModel:
    def test_default_self_model(self):
        model = SelfModel()
        assert model.identity is not None
        assert model.capability is not None
        assert model.ownership is not None
    
    def test_update_summary(self):
        model = SelfModel()
        model.update_summary("Updated summary", ["evidence1", "evidence2"])
        assert model.current_summary == "Updated summary"
        assert len(model.evidence_refs) == 2
    
    def test_check_action_allowed(self):
        model = SelfModel()
        result = model.check_action("analyze_emotions")
        assert result["allowed"] is True
        assert result["identity_aligned"] is True
    
    def test_check_action_blocked(self):
        model = SelfModel()
        result = model.check_action("deceive_user")
        # "deceive" should fail identity alignment
        assert result["identity_aligned"] is False
    
    def test_compute_hash(self):
        model = SelfModel()
        hash1 = model.compute_hash()
        hash2 = model.compute_hash()
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex
    
    def test_serialization(self):
        model = SelfModel()
        model.update_summary("Test", ["ev1"])
        data = model.to_dict()
        restored = SelfModel.from_dict(data)
        assert restored.current_summary == "Test"
        assert len(restored.evidence_refs) == 1


class TestSelfReport:
    def test_render_self_report(self):
        model = SelfModel()
        model.update_summary("Test summary", ["ev1", "ev2"])
        report = render_self_report(model)
        
        assert "summary" in report
        assert report["summary"] == "Test summary"
        assert len(report["evidence_refs"]) == 2
        assert "model_hash" in report
    
    def test_self_report_with_additional_evidence(self):
        model = SelfModel()
        evidence = {"data": "test", "provenance": {"source": "system"}}
        report = render_self_report(model, evidence)
        
        assert "additional_evidence" in report
    
    def test_self_report_rejects_evidence_without_provenance(self):
        model = SelfModel()
        evidence = {"data": "test"}  # No provenance
        report = render_self_report(model, evidence)
        
        assert "additional_evidence" not in report
        assert "evidence_warning" in report


class TestSelfReportValidation:
    def test_valid_report(self):
        model = SelfModel()
        model.update_summary("Test", ["ev1"])
        report = render_self_report(model)
        result = validate_self_report(report, model)
        
        assert result["valid"] is True
        assert result["alignment_score"] == 1.0
    
    def test_hash_mismatch(self):
        model = SelfModel()
        report = {
            "model_hash": "wronghash",
            "evidence_refs": [],
        }
        result = validate_self_report(report, model)
        
        assert result["valid"] is False
        assert "model_hash_mismatch" in result["issues"]
    
    def test_unverified_evidence_refs(self):
        model = SelfModel()
        model.update_summary("Test", ["actual_ev"])
        report = {
            "model_hash": model.compute_hash(),
            "evidence_refs": ["fake_ev"],
        }
        result = validate_self_report(report, model)
        
        assert result["valid"] is False
        assert "unverified_evidence_refs" in result["issues"]
