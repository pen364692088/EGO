"""
Self-Model Manager Tests

测试 self-model 管理功能。
"""

import pytest
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock

from egocore.runtime.self_model_manager import (
    SelfModelManager,
    ChangeType,
    ValidationFailedError,
    IdentityAlignmentError,
    UnauthorizedUpdateError,
)


@pytest.fixture
def sample_self_model():
    """示例 self-model"""
    return {
        "schema_version": "1.0.0",
        "model_handle": "ceo",
        "capabilities": [
            {
                "capability_id": "cap_file_read",
                "name": "文件读取",
                "category": "file_operations",
                "current_level": "advanced",
            }
        ],
        "limitations": [
            {
                "limitation_id": "lim_no_gui",
                "description": "无法直接操作 GUI",
                "impact_level": "medium",
            }
        ],
        "active_goals": [
            {
                "goal_id": "goal_test",
                "description": "测试目标",
                "status": "in_progress",
                "priority": "high",
            }
        ],
        "standing_commitments": [],
        "tool_authority_boundary": {
            "current_allowed_tools": ["read", "write"],
            "forbidden_tools": ["credential_manager"],
        },
        "dependency_map": {
            "external_services": [],
            "internal_modules": [],
        },
        "confidence_by_domain": [
            {"domain": "code", "confidence": 0.85}
        ],
        "known_unknowns": [],
        "current_mode": {
            "mode_name": "normal",
        },
        "created_at": "2026-03-16T00:00:00Z",
        "last_modified_at": "2026-03-16T00:00:00Z",
        "modification_audit_trail": [],
    }


@pytest.fixture
def self_model_file(sample_self_model, tmp_path):
    """创建临时 self-model 文件"""
    model_dir = tmp_path / "self_model"
    model_dir.mkdir()
    model_file = model_dir / "ceo_self_model.json"
    with open(model_file, 'w') as f:
        json.dump(sample_self_model, f)
    return model_file


@pytest.fixture
def manager(self_model_file, tmp_path):
    """创建测试用 manager"""
    audit_dir = tmp_path / "audit"
    return SelfModelManager(
        self_model_path=self_model_file,
        audit_dir=audit_dir,
    )


class TestSelfModelLoading:
    """加载测试"""

    def test_load_success(self, manager):
        """测试成功加载"""
        model = manager.get_model()
        assert model["model_handle"] == "ceo"
        assert len(model["capabilities"]) == 1

    def test_load_missing_file(self, tmp_path):
        """测试文件不存在"""
        manager = SelfModelManager(
            self_model_path=tmp_path / "nonexistent.json"
        )
        with pytest.raises(ValidationFailedError):
            manager.load()

    def test_load_missing_required_fields(self, tmp_path):
        """测试缺少必填字段"""
        model_dir = tmp_path / "self_model"
        model_dir.mkdir()
        model_file = model_dir / "invalid.json"

        # 缺少大部分必填字段
        invalid_data = {
            "schema_version": "1.0.0",
            "model_handle": "test",
            # 缺少其他必填字段
        }
        with open(model_file, 'w') as f:
            json.dump(invalid_data, f)

        # SelfModelManager 在 __init__ 中自动 load，应该捕获异常
        with pytest.raises(ValidationFailedError):
            SelfModelManager(self_model_path=model_file)


class TestCapabilityManagement:
    """能力管理测试"""

    def test_add_capability(self, manager):
        """测试添加能力"""
        result = manager.add_capability({
            "capability_id": "cap_web",
            "name": "网页访问",
            "category": "web_access",
            "current_level": "intermediate",
        })

        assert result["success"] is True
        model = manager.get_model()
        assert len(model["capabilities"]) == 2

    def test_update_capability_level(self, manager):
        """测试更新能力等级"""
        result = manager.update_capability_level("cap_file_read", "expert")

        assert result["success"] is True
        model = manager.get_model()
        assert model["capabilities"][0]["current_level"] == "expert"

    def test_update_nonexistent_capability(self, manager):
        """测试更新不存在的能力"""
        with pytest.raises(ValidationFailedError):
            manager.update_capability_level("nonexistent", "expert")


class TestLimitationManagement:
    """限制管理测试"""

    def test_add_limitation(self, manager):
        """测试添加限制"""
        result = manager.add_limitation({
            "limitation_id": "lim_time",
            "description": "时间限制",
            "impact_level": "low",
        })

        assert result["success"] is True
        model = manager.get_model()
        assert len(model["limitations"]) == 2


class TestGoalManagement:
    """目标管理测试"""

    def test_add_goal(self, manager):
        """测试添加目标"""
        result = manager.add_goal({
            "goal_id": "goal_new",
            "description": "新目标",
            "status": "proposed",
            "priority": "medium",
        })

        assert result["success"] is True
        model = manager.get_model()
        assert len(model["active_goals"]) == 2

    def test_update_goal_status(self, manager):
        """测试更新目标状态"""
        result = manager.update_goal_status("goal_test", "completed")

        assert result["success"] is True
        model = manager.get_model()
        assert model["active_goals"][0]["status"] == "completed"

    def test_update_nonexistent_goal(self, manager):
        """测试更新不存在的目标"""
        with pytest.raises(ValidationFailedError):
            manager.update_goal_status("nonexistent", "completed")


class TestFieldUpdate:
    """字段更新测试"""

    def test_update_free_field(self, manager):
        """测试自由更新字段"""
        result = manager.update_field(
            "current_mode.mode_name",
            "high_performance",
        )

        assert result["success"] is True
        model = manager.get_model()
        assert model["current_mode"]["mode_name"] == "high_performance"

    def test_update_logged_field(self, manager):
        """测试记录更新字段"""
        result = manager.update_field(
            "confidence_by_domain",
            [{"domain": "code", "confidence": 0.9}],
        )

        assert result["success"] is True

    def test_update_identity_aligned_field_without_guard(self, manager):
        """测试对齐字段需要特殊处理"""
        # 对齐字段应该抛出 UnauthorizedUpdateError
        with pytest.raises(UnauthorizedUpdateError):
            manager.update_field(
                "tool_authority_boundary.forbidden_tools",
                ["new_forbidden_tool"],
            )


class TestAuditTrail:
    """审计轨迹测试"""

    def test_audit_trail_created_on_capability_update(self, manager):
        """测试能力更新创建审计轨迹"""
        manager.update_capability_level("cap_file_read", "expert")

        model = manager.get_model()
        trail = model["modification_audit_trail"]

        assert len(trail) >= 1

    def test_audit_trail_created_on_goal_status_update(self, manager):
        """测试目标状态更新创建审计轨迹"""
        manager.update_goal_status("goal_test", "completed")

        model = manager.get_model()
        trail = model["modification_audit_trail"]

        assert len(trail) >= 1


class TestIdentityAlignment:
    """Identity 对齐测试"""

    def test_check_alignment_no_guard(self, manager):
        """测试无 identity guard"""
        result = manager.check_identity_alignment()

        assert "warnings" in result

    def test_check_alignment_with_guard(self, self_model_file, tmp_path):
        """测试有 identity guard"""
        # 创建 mock identity guard
        mock_guard = MagicMock()
        mock_guard.get_identity.return_value = {
            "identity_handle": "ceo",
            "non_negotiable_commitments": [],
            "tool_authority_boundary": {
                "forbidden_tools": ["credential_manager"],
            },
        }

        audit_dir = tmp_path / "audit"
        manager = SelfModelManager(
            self_model_path=self_model_file,
            identity_guard=mock_guard,
            audit_dir=audit_dir,
        )

        result = manager.check_identity_alignment()

        assert result["aligned"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
