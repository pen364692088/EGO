"""
Self Restorer Tests

测试自我恢复功能。
"""

import pytest
import json
from datetime import datetime, timezone
from pathlib import Path

from egocore.runtime.self_restorer import (
    SelfRestorer,
    RestoreStatus,
    ConflictLevel,
    RestoreError,
    IdentityNotFoundError,
)


@pytest.fixture
def sample_identity():
    """示例身份"""
    return {
        "schema_version": "1.0.0",
        "identity_handle": "ceo",
        "core_name": "CEO Agent",
        "core_role": "personal_assistant",
        "owner_relationship": {
            "owner_id": "user_moonlight",
            "relationship_type": "owned"
        },
        "non_negotiable_commitments": [],
        "forbidden_self_rewrite_zones": [],
        "allowed_change_rules": {"mutable_fields": [], "immutable_fields": []},
        "created_at": "2026-03-16T00:00:00Z",
        "last_modified_at": "2026-03-16T00:00:00Z",
        "modification_audit_trail": [],
    }


@pytest.fixture
def sample_self_model():
    """示例自我模型"""
    return {
        "schema_version": "1.0.0",
        "model_handle": "ceo",
        "capabilities": [],
        "limitations": [],
        "active_goals": [],
        "standing_commitments": [],
        "tool_authority_boundary": {},
        "dependency_map": {},
        "confidence_by_domain": [],
        "known_unknowns": [],
        "created_at": "2026-03-16T00:00:00Z",
        "last_modified_at": "2026-03-16T00:00:00Z",
        "modification_audit_trail": [],
    }


@pytest.fixture
def sample_summary():
    """示例摘要"""
    return {
        "schema_version": "1.0.0",
        "summary_id": "summary_test",
        "identity_handle_ref": "ceo",
        "summary_created_at": "2026-03-16T00:00:00Z",
        "summary_period_start": "2026-03-16T00:00:00Z",
        "summary_period_end": "2026-03-16T00:00:00Z",
        "identity_summary": {
            "core_name": "CEO Agent",
            "core_role": "personal_assistant",
        },
        "current_phase_summary": {},
        "capability_summary": {},
        "constraint_summary": {},
        "active_commitments_summary": {},
        "recent_key_events_summary": [],
        "stable_conclusions": [],
        "open_questions": [],
        "self_model_version_ref": {
            "model_handle": "ceo",
            "snapshot_timestamp": "2026-03-16T00:00:00Z",
        },
        "last_modified_at": "2026-03-16T00:00:00Z",
        "modification_audit_trail": [],
    }


@pytest.fixture
def artifacts_dir(sample_identity, sample_self_model, sample_summary, tmp_path):
    """创建完整的 artifacts 目录"""
    artifacts = tmp_path / "artifacts"

    # Identity
    identity_dir = artifacts / "identity"
    identity_dir.mkdir(parents=True)
    with open(identity_dir / "ceo_invariants_snapshot.json", 'w') as f:
        json.dump(sample_identity, f)

    # Self-model
    model_dir = artifacts / "self_model"
    model_dir.mkdir(parents=True)
    with open(model_dir / "ceo_self_model_snapshot.json", 'w') as f:
        json.dump(sample_self_model, f)

    # Summary
    summary_dir = artifacts / "summary"
    summary_dir.mkdir(parents=True)
    with open(summary_dir / "summary_20260316_ceo.json", 'w') as f:
        json.dump(sample_summary, f)

    return artifacts


@pytest.fixture
def restorer(artifacts_dir):
    """创建测试用恢复器"""
    return SelfRestorer(artifacts_dir=artifacts_dir)


class TestSuccessfulRestore:
    """成功恢复测试"""

    def test_restore_success(self, restorer):
        """测试成功恢复"""
        result = restorer.restore()

        assert result.status == RestoreStatus.SUCCESS.value
        assert "identity" in result.loaded_layers
        assert "self_model" in result.loaded_layers
        assert "summary" in result.loaded_layers

    def test_restore_loads_identity(self, restorer):
        """测试加载身份"""
        result = restorer.restore()

        assert result.identity is not None
        assert result.identity["identity_handle"] == "ceo"

    def test_restore_loads_self_model(self, restorer):
        """测试加载自我模型"""
        result = restorer.restore()

        assert result.self_model is not None
        assert result.self_model["model_handle"] == "ceo"

    def test_restore_loads_summary(self, restorer):
        """测试加载摘要"""
        result = restorer.restore()

        assert result.summary is not None
        assert result.summary["identity_handle_ref"] == "ceo"

    def test_restore_creates_audit(self, restorer):
        """测试创建审计记录"""
        result = restorer.restore()

        assert result.restore_id is not None
        assert result.timestamp is not None
        assert result.session_id is not None


class TestMissingFiles:
    """缺失文件测试"""

    def test_identity_missing_fails(self, tmp_path):
        """测试身份缺失导致失败"""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()

        restorer = SelfRestorer(artifacts_dir=artifacts)
        result = restorer.restore()

        assert result.status == RestoreStatus.FAILED.value
        assert len(result.errors) > 0

    def test_self_model_missing_degraded(self, sample_identity, tmp_path):
        """测试自我模型缺失降级"""
        artifacts = tmp_path / "artifacts"
        identity_dir = artifacts / "identity"
        identity_dir.mkdir(parents=True)
        with open(identity_dir / "ceo_invariants_snapshot.json", 'w') as f:
            json.dump(sample_identity, f)

        restorer = SelfRestorer(artifacts_dir=artifacts)
        result = restorer.restore()

        assert result.status == RestoreStatus.PARTIAL.value
        assert result.degraded_mode is True
        assert "identity" in result.loaded_layers
        assert "self_model" not in result.loaded_layers

    def test_summary_missing_partial(self, sample_identity, sample_self_model, tmp_path):
        """测试摘要缺失部分恢复"""
        artifacts = tmp_path / "artifacts"
        
        identity_dir = artifacts / "identity"
        identity_dir.mkdir(parents=True)
        with open(identity_dir / "ceo_invariants_snapshot.json", 'w') as f:
            json.dump(sample_identity, f)

        model_dir = artifacts / "self_model"
        model_dir.mkdir(parents=True)
        with open(model_dir / "ceo_self_model_snapshot.json", 'w') as f:
            json.dump(sample_self_model, f)

        restorer = SelfRestorer(artifacts_dir=artifacts)
        result = restorer.restore()

        assert "identity" in result.loaded_layers
        assert "self_model" in result.loaded_layers


class TestConsistencyCheck:
    """一致性检查测试"""

    def test_identity_model_mismatch(self, sample_identity, tmp_path):
        """测试身份与模型不匹配"""
        artifacts = tmp_path / "artifacts"
        
        # Identity
        identity_dir = artifacts / "identity"
        identity_dir.mkdir(parents=True)
        with open(identity_dir / "ceo_invariants_snapshot.json", 'w') as f:
            json.dump(sample_identity, f)

        # Self-model with different handle
        model_dir = artifacts / "self_model"
        model_dir.mkdir(parents=True)
        mismatched_model = {
            "schema_version": "1.0.0",
            "model_handle": "different",  # 不匹配
            "capabilities": [],
            "limitations": [],
            "active_goals": [],
            "standing_commitments": [],
            "tool_authority_boundary": {},
            "dependency_map": {},
            "confidence_by_domain": [],
            "known_unknowns": [],
            "created_at": "2026-03-16T00:00:00Z",
            "last_modified_at": "2026-03-16T00:00:00Z",
            "modification_audit_trail": [],
        }
        with open(model_dir / "ceo_self_model_snapshot.json", 'w') as f:
            json.dump(mismatched_model, f)

        restorer = SelfRestorer(artifacts_dir=artifacts)
        result = restorer.restore()

        assert len(result.conflicts) > 0
        assert any(c.get("type") == "identity_model_mismatch" for c in result.conflicts)


class TestConflictHandling:
    """冲突处理测试"""

    def test_error_conflict_fails(self, sample_identity, tmp_path):
        """测试错误级别冲突导致失败"""
        artifacts = tmp_path / "artifacts"
        
        identity_dir = artifacts / "identity"
        identity_dir.mkdir(parents=True)
        with open(identity_dir / "ceo_invariants_snapshot.json", 'w') as f:
            json.dump(sample_identity, f)

        model_dir = artifacts / "self_model"
        model_dir.mkdir(parents=True)
        mismatched_model = {
            "schema_version": "1.0.0",
            "model_handle": "different",
            "capabilities": [],
            "limitations": [],
            "active_goals": [],
            "standing_commitments": [],
            "tool_authority_boundary": {},
            "dependency_map": {},
            "confidence_by_domain": [],
            "known_unknowns": [],
            "created_at": "2026-03-16T00:00:00Z",
            "last_modified_at": "2026-03-16T00:00:00Z",
            "modification_audit_trail": [],
        }
        with open(model_dir / "ceo_self_model_snapshot.json", 'w') as f:
            json.dump(mismatched_model, f)

        restorer = SelfRestorer(artifacts_dir=artifacts)
        result = restorer.restore()

        # error 级别冲突应该导致失败
        assert result.status == RestoreStatus.FAILED.value


class TestAuditTrail:
    """审计轨迹测试"""

    def test_audit_contains_restore_id(self, restorer):
        """测试审计包含 restore_id"""
        result = restorer.restore()

        assert result.restore_id is not None
        assert result.restore_id.startswith("restore_")

    def test_audit_contains_session_id(self, restorer):
        """测试审计包含 session_id"""
        result = restorer.restore(session_id="test_session_123")

        assert result.session_id == "test_session_123"

    def test_audit_contains_duration(self, restorer):
        """测试审计包含耗时"""
        result = restorer.restore()

        assert result.duration_ms >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
