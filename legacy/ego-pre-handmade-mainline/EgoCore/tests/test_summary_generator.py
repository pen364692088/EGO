"""
Summary Generator Tests

测试长期自我摘要生成功能。
"""

import pytest
import json
from datetime import datetime, timezone
from pathlib import Path

from egocore.runtime.summary_generator import (
    SummaryGenerator,
    SummaryAction,
    ValidationFailedError,
    AlignmentError,
)


@pytest.fixture
def sample_identity():
    """示例身份不变量"""
    return {
        "identity_handle": "ceo",
        "core_name": "CEO Agent",
        "core_role": "personal_assistant",
        "owner_relationship": {
            "owner_id": "user_moonlight",
            "relationship_type": "owned"
        },
        "non_negotiable_commitments": [
            {
                "commitment_id": "commit_honesty",
                "description": "不编造事实",
                "binding_level": "absolute"
            }
        ],
    }


@pytest.fixture
def sample_self_model():
    """示例自我模型"""
    return {
        "model_handle": "ceo",
        "capabilities": [
            {
                "capability_id": "cap_file",
                "name": "文件操作",
                "category": "file_operations",
                "current_level": "advanced",
            },
            {
                "capability_id": "cap_code",
                "name": "代码执行",
                "category": "code_execution",
                "current_level": "intermediate",
            }
        ],
        "limitations": [
            {
                "limitation_id": "lim_gui",
                "description": "无 GUI 能力",
                "impact_level": "medium"
            }
        ],
        "active_goals": [
            {
                "goal_id": "goal_test",
                "description": "测试目标",
                "status": "in_progress",
                "priority": "high",
                "progress": 0.5
            }
        ],
        "last_modified_at": "2026-03-16T00:00:00Z",
    }


@pytest.fixture
def generator(tmp_path):
    """创建测试用生成器"""
    output_dir = tmp_path / "summary"
    audit_dir = tmp_path / "audit"
    return SummaryGenerator(output_dir=output_dir, audit_dir=audit_dir)


class TestSummaryGeneration:
    """摘要生成测试"""

    def test_generate_basic(self, generator, sample_identity, sample_self_model):
        """测试基本生成"""
        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        assert summary["schema_version"] == "1.0.0"
        assert summary["identity_handle_ref"] == "ceo"
        assert summary["identity_summary"]["core_name"] == "CEO Agent"
        assert summary["identity_summary"]["core_role"] == "personal_assistant"

    def test_generate_with_events(self, generator, sample_identity, sample_self_model):
        """测试带事件生成"""
        events = [
            {
                "event_type": "milestone",
                "summary": "P1-A 完成",
                "significance": "high",
            }
        ]

        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
            recent_events=events,
        )

        assert len(summary["recent_key_events_summary"]) == 1

    def test_generate_with_conclusions(self, generator, sample_identity, sample_self_model):
        """测试带结论生成"""
        conclusions = [
            {
                "conclusion_id": "conc_test",
                "statement": "测试结论",
                "confidence": 0.9,
                "basis": "测试",
            }
        ]

        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
            stable_conclusions=conclusions,
        )

        assert len(summary["stable_conclusions"]) == 1

    def test_summary_has_audit_trail(self, generator, sample_identity, sample_self_model):
        """测试审计轨迹"""
        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        assert len(summary["modification_audit_trail"]) >= 1
        assert summary["modification_audit_trail"][0]["action"] == "created"


class TestSummaryRefresh:
    """摘要刷新测试"""

    def test_refresh_basic(self, generator, sample_identity, sample_self_model):
        """测试基本刷新"""
        # 先生成
        original = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        # 再刷新
        refreshed = generator.refresh(
            existing_summary=original,
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        assert refreshed["summary_id"] == original["summary_id"]
        assert len(refreshed["modification_audit_trail"]) >= 2

    def test_refresh_merges_events(self, generator, sample_identity, sample_self_model):
        """测试事件合并"""
        # 先生成
        original = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
            recent_events=[
                {"event_type": "test1", "summary": "事件1", "significance": "medium"}
            ],
        )

        # 再刷新
        refreshed = generator.refresh(
            existing_summary=original,
            identity_invariants=sample_identity,
            self_model=sample_self_model,
            recent_events=[
                {"event_type": "test2", "summary": "事件2", "significance": "high"}
            ],
        )

        # 应该有两个事件
        assert len(refreshed["recent_key_events_summary"]) >= 1


class TestAlignmentVerification:
    """对齐验证测试"""

    def test_verify_alignment_success(self, generator, sample_identity, sample_self_model):
        """测试对齐成功"""
        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        result = generator.verify_alignment(
            summary=summary,
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        assert result["aligned"] is True
        assert len(result["issues"]) == 0

    def test_verify_alignment_mismatch(self, generator, sample_identity, sample_self_model):
        """测试对齐不匹配"""
        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        # 修改 identity 造成不匹配
        modified_identity = sample_identity.copy()
        modified_identity["identity_handle"] = "different"

        result = generator.verify_alignment(
            summary=summary,
            identity_invariants=modified_identity,
            self_model=sample_self_model,
        )

        assert result["aligned"] is False
        assert len(result["issues"]) >= 1


class TestCapabilitySummary:
    """能力摘要测试"""

    def test_capability_summary_extraction(self, generator, sample_identity, sample_self_model):
        """测试能力摘要提取"""
        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        cap_summary = summary["capability_summary"]

        assert "strong_domains" in cap_summary
        assert "developing_domains" in cap_summary
        assert "known_limitations" in cap_summary

        # file_operations 是 advanced，应该在 strong_domains
        assert "file_operations" in cap_summary["strong_domains"]

        # code_execution 是 intermediate，应该在 developing_domains
        assert "code_execution" in cap_summary["developing_domains"]


class TestEventCompression:
    """事件压缩测试"""

    def test_compress_events_max_20(self, generator, sample_identity, sample_self_model):
        """测试事件压缩最多 20 条"""
        # 生成 30 个事件
        events = [
            {
                "event_type": f"event_{i}",
                "summary": f"事件 {i}",
                "significance": "low",
            }
            for i in range(30)
        ]

        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
            recent_events=events,
        )

        assert len(summary["recent_key_events_summary"]) <= 20


class TestRecoveryHints:
    """恢复提示测试"""

    def test_recovery_hints_generated(self, generator, sample_identity, sample_self_model):
        """测试恢复提示生成"""
        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        hints = summary["recovery_hints"]

        assert "last_active_context" in hints
        assert "suggested_start_actions" in hints
        assert "pending_tasks" in hints


class TestForbiddenFields:
    """禁止字段测试"""

    def test_no_memory_fields(self, generator, sample_identity, sample_self_model):
        """测试无 memory 字段"""
        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        # 不应包含 memory 相关字段
        assert "event_memory" not in summary
        assert "narrative_memory" not in summary
        assert "policy_memory" not in summary

    def test_no_appraisal_fields(self, generator, sample_identity, sample_self_model):
        """测试无 appraisal 字段"""
        summary = generator.generate(
            identity_invariants=sample_identity,
            self_model=sample_self_model,
        )

        assert "appraisal_state" not in summary
        assert "emotion_state" not in summary
        assert "reflection_note" not in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
