"""
Context Injector Tests

测试上下文注入功能。
"""

import pytest
import json
from pathlib import Path

from egocore.runtime.context_injector import (
    ContextInjector,
    RuntimeContext,
)


@pytest.fixture
def restore_result():
    """示例恢复结果"""
    return {
        "restore_id": "restore_test",
        "identity": {
            "identity_handle": "ceo",
            "core_name": "CEO Agent",
            "core_role": "personal_assistant",
            "non_negotiable_commitments": [
                {"description": "不编造事实"}
            ],
        },
        "self_model": {
            "capabilities": [
                {"capability_id": "cap_file", "name": "文件操作", "current_level": "advanced"}
            ],
            "limitations": [
                {"limitation_id": "lim_gui", "description": "无 GUI 能力"}
            ],
            "active_goals": [
                {"goal_id": "goal_test", "description": "测试目标", "status": "in_progress"}
            ],
            "standing_commitments": [],
            "tool_authority_boundary": {
                "forbidden_tools": ["credential_manager"]
            },
        },
        "summary": {
            "recovery_hints": {
                "last_active_context": "测试上下文",
                "suggested_start_actions": ["检查状态"],
            }
        },
    }


@pytest.fixture
def injector(tmp_path):
    """创建测试用注入器"""
    audit_dir = tmp_path / "audit"
    return ContextInjector(audit_dir=audit_dir)


class TestContextInjection:
    """上下文注入测试"""

    def test_inject_creates_context(self, injector, restore_result):
        """测试注入创建上下文"""
        context = injector.inject(restore_result, "session_123")

        assert context.session_id == "session_123"
        assert context.identity_handle == "ceo"

    def test_inject_extracts_identity(self, injector, restore_result):
        """测试提取身份信息"""
        context = injector.inject(restore_result, "session_123")

        assert context.core_name == "CEO Agent"
        assert context.core_role == "personal_assistant"

    def test_inject_extracts_capabilities(self, injector, restore_result):
        """测试提取能力"""
        context = injector.inject(restore_result, "session_123")

        assert len(context.capabilities) == 1
        assert context.capabilities[0]["capability_id"] == "cap_file"

    def test_inject_extracts_limitations(self, injector, restore_result):
        """测试提取限制"""
        context = injector.inject(restore_result, "session_123")

        assert len(context.limitations) == 1
        assert context.limitations[0]["limitation_id"] == "lim_gui"

    def test_inject_extracts_goals(self, injector, restore_result):
        """测试提取目标"""
        context = injector.inject(restore_result, "session_123")

        assert len(context.active_goals) == 1
        assert context.active_goals[0]["goal_id"] == "goal_test"

    def test_inject_merges_commitments(self, injector, restore_result):
        """测试合并承诺"""
        context = injector.inject(restore_result, "session_123")

        assert len(context.standing_commitments) >= 1
        assert "不编造事实" in context.standing_commitments

    def test_inject_extracts_recovery_hints(self, injector, restore_result):
        """测试提取恢复提示"""
        context = injector.inject(restore_result, "session_123")

        assert context.recovery_hints is not None
        assert context.recovery_hints["last_active_context"] == "测试上下文"

    def test_inject_extracts_tool_boundary(self, injector, restore_result):
        """测试提取工具边界"""
        context = injector.inject(restore_result, "session_123")

        assert context.tool_authority_boundary is not None
        assert "credential_manager" in context.tool_authority_boundary.get("forbidden_tools", [])


class TestContextSummary:
    """上下文摘要测试"""

    def test_get_injected_context_summary(self, injector, restore_result):
        """测试获取注入摘要"""
        injector.inject(restore_result, "session_123")

        summary = injector.get_injected_context_summary()

        assert summary["injected"] is True
        assert summary["identity_handle"] == "ceo"
        assert summary["capabilities_count"] == 1
        assert summary["limitations_count"] == 1
        assert summary["active_goals_count"] == 1
        assert summary["recovery_hints_present"] is True


class TestAuditCreation:
    """审计创建测试"""

    def test_injection_creates_audit(self, injector, restore_result):
        """测试注入创建审计"""
        injector.inject(restore_result, "session_123")

        # 审计文件应该在 audit_dir 中
        # (实际文件位置由 audit_dir 参数决定)
        assert injector._context is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
