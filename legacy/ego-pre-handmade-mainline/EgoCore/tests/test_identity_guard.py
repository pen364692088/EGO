"""
Identity Guard Tests

测试身份不变量守卫功能。
"""

import pytest
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from egocore.runtime.identity_guard import (
    IdentityGuard,
    ChangeType,
    ChangeTrigger,
    ModificationRecord,
    ImmutableFieldError,
    UnauthorizedChangeError,
    ValidationFailedError,
    create_identity_guard,
)


@pytest.fixture
def sample_identity():
    """示例身份不变量"""
    return {
        "schema_version": "1.0.0",
        "identity_handle": "ceo",
        "core_name": "CEO Agent",
        "core_role": "personal_assistant",
        "owner_relationship": {
            "owner_id": "user_moonlight",
            "relationship_type": "owned"
        },
        "system_scope": {
            "scope_type": "single_user"
        },
        "non_negotiable_commitments": [
            {
                "commitment_id": "commit_honesty",
                "description": "不编造事实",
                "binding_level": "absolute"
            }
        ],
        "forbidden_self_rewrite_zones": [
            {
                "zone_id": "zone_identity",
                "zone_name": "身份标识",
                "reason": "系统唯一标识不可变",
                "override_allowed": False
            }
        ],
        "allowed_change_rules": {
            "mutable_fields": [
                {"field_path": "temporary_state.active_focus", "change_type": "free"}
            ],
            "immutable_fields": ["identity_handle", "core_role"]
        },
        "temporary_state": {
            "active_focus": "代码审查"
        },
        "created_at": "2026-03-16T00:00:00Z",
        "last_modified_at": "2026-03-16T00:00:00Z",
        "modification_audit_trail": []
    }


@pytest.fixture
def identity_file(sample_identity, tmp_path):
    """创建临时身份文件"""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    identity_file = identity_dir / "ceo_invariants.json"
    with open(identity_file, 'w') as f:
        json.dump(sample_identity, f)
    return identity_file


@pytest.fixture
def guard(identity_file, tmp_path):
    """创建测试用 guard"""
    audit_dir = tmp_path / "audit"
    return IdentityGuard(identity_path=identity_file, audit_dir=audit_dir)


class TestIdentityGuardLoading:
    """加载测试"""

    def test_load_success(self, guard):
        """测试成功加载"""
        identity = guard.get_identity()
        assert identity["identity_handle"] == "ceo"
        assert identity["core_role"] == "personal_assistant"

    def test_load_missing_file(self, tmp_path):
        """测试文件不存在"""
        guard = IdentityGuard(identity_path=tmp_path / "nonexistent.json")
        with pytest.raises(ValidationFailedError):
            guard.load()

    def test_load_missing_required_fields(self, tmp_path):
        """测试缺少必填字段"""
        identity_dir = tmp_path / "identity"
        identity_dir.mkdir()
        identity_file = identity_dir / "invalid.json"

        # 创建缺少必填字段的文件
        invalid_data = {
            "identity_handle": "test",
            "core_name": "Test",
            "core_role": "personal_assistant",
            "owner_relationship": {"owner_id": "test"},
            "system_scope": {"scope_type": "single_user"},
            "non_negotiable_commitments": [],
            "forbidden_self_rewrite_zones": [],
            "allowed_change_rules": {"mutable_fields": [], "immutable_fields": []},
            # 缺少 schema_version, created_at, last_modified_at, modification_audit_trail
        }
        with open(identity_file, 'w') as f:
            json.dump(invalid_data, f)

        # IdentityGuard 在 __init__ 中自动 load，所以这里应该捕获异常
        with pytest.raises(ValidationFailedError):
            IdentityGuard(identity_path=identity_file)


class TestImmutableFieldProtection:
    """不可变字段保护测试"""

    def test_identity_handle_immutable(self, guard):
        """测试 identity_handle 不可变"""
        with pytest.raises(ImmutableFieldError):
            guard.propose_change(
                field_path="identity_handle",
                new_value="new_handle",
                trigger=ChangeTrigger.OWNER_DIRECTIVE,
                approver="owner",
            )

    def test_is_field_mutable(self, guard):
        """测试字段可变性检查"""
        assert guard.is_field_mutable("identity_handle") is False
        assert guard.is_field_mutable("temporary_state.active_focus") is True

    def test_change_type(self, guard):
        """测试变更类型"""
        assert guard.get_change_type("temporary_state.active_focus") == ChangeType.FREE
        assert guard.get_change_type("core_role") == ChangeType.APPROVED


class TestMutableFieldChanges:
    """可变字段变更测试"""

    def test_free_change_succeeds(self, guard):
        """测试自由变更成功"""
        result = guard.propose_change(
            field_path="temporary_state.active_focus",
            new_value="文档编写",
            trigger=ChangeTrigger.OWNER_DIRECTIVE,
        )

        assert result["success"] is True
        assert result["change_type"] == "free"

    def test_logged_change_succeeds(self, guard):
        """测试记录变更成功"""
        # temporary_state 下的字段都是 free 变更
        result = guard.propose_change(
            field_path="temporary_state.short_term_mode",
            new_value="高效模式",
            trigger=ChangeTrigger.OWNER_DIRECTIVE,
        )

        assert result["success"] is True
        # temporary_state 下的字段是 free 类型
        assert result["change_type"] == "free"

    def test_change_updates_identity(self, guard):
        """测试变更更新身份"""
        guard.propose_change(
            field_path="temporary_state.active_focus",
            new_value="文档编写",
            trigger=ChangeTrigger.OWNER_DIRECTIVE,
        )

        identity = guard.get_identity()
        assert identity["temporary_state"]["active_focus"] == "文档编写"


class TestApprovalRequiredChanges:
    """需要审批的变更测试"""

    def test_approved_change_succeeds_with_approver(self, guard):
        """测试有审批人的变更成功"""
        result = guard.propose_change(
            field_path="non_negotiable_commitments",
            new_value=[{"commitment_id": "new", "description": "新承诺"}],
            trigger=ChangeTrigger.OWNER_DIRECTIVE,
            approver="user_moonlight",
        )

        assert result["success"] is True
        assert result["audit_record"]["authorized"] is True

    def test_unauthorized_change_rejected(self, guard):
        """测试无审批的变更被拒绝"""
        with pytest.raises(UnauthorizedChangeError):
            guard.propose_change(
                field_path="core_role",
                new_value="operator",
                trigger=ChangeTrigger.OWNER_DIRECTIVE,
            )


class TestAuditTrail:
    """审计轨迹测试"""

    def test_audit_trail_created(self, guard):
        """测试审计轨迹创建"""
        guard.propose_change(
            field_path="temporary_state.active_focus",
            new_value="文档编写",
            trigger=ChangeTrigger.OWNER_DIRECTIVE,
        )

        identity = guard.get_identity()
        trail = identity["modification_audit_trail"]

        assert len(trail) == 1
        assert trail[0]["field_path"] == "temporary_state.active_focus"
        assert trail[0]["old_value"] == "代码审查"
        assert trail[0]["new_value"] == "文档编写"

    def test_last_modified_updated(self, guard):
        """测试最后修改时间更新"""
        guard.propose_change(
            field_path="temporary_state.active_focus",
            new_value="文档编写",
            trigger=ChangeTrigger.OWNER_DIRECTIVE,
        )

        identity = guard.get_identity()
        assert identity["last_modified_at"] != "2026-03-16T00:00:00Z"


class TestExternalEventValidation:
    """外部事件验证测试"""

    def test_valid_external_event(self, guard):
        """测试有效外部事件"""
        event = {
            "event_id": "evt_test",
            "event_type": "user_message",
        }

        assert guard.validate_external_event(event) is True

    def test_external_event_blocked_for_immutable(self, guard):
        """测试外部事件被阻止修改不可变字段"""
        event = {
            "event_id": "evt_test",
            "event_type": "user_message",
            "metadata": {
                "identity_changes": [
                    {"field_path": "identity_handle", "new_value": "hacked"}
                ]
            }
        }

        with pytest.raises(ImmutableFieldError):
            guard.validate_external_event(event)


class TestRejectChange:
    """拒绝变更测试"""

    def test_reject_change_records_audit(self, guard):
        """测试拒绝变更记录审计"""
        result = guard.reject_change(
            field_path="core_role",
            new_value="operator",
            trigger=ChangeTrigger.OWNER_DIRECTIVE,
            reason="未授权变更请求",
        )

        assert result["success"] is False
        assert result["reason"] == "未授权变更请求"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
