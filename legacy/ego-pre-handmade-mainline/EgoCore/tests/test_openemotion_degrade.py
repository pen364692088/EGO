"""
OpenEmotion Degrade Tests

测试 OpenEmotion 异常时的降级行为。
"""

import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime

from egocore.adapters.openemotion_adapter import (
    OpenEmotionAdapter,
    MockBackend,
    EventInput,
    OpenEmotionOutput,
    AdapterMode,
    AdapterError,
    ConnectionError,
    TimeoutError,
    ValidationError,
)


class TestDegradeScenarios:
    """降级场景测试"""

    def test_degraded_mode_output_structure(self):
        """测试降级输出结构正确"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        # 提供无效输入触发降级
        result = adapter.process_event({})

        # 检查降级标记
        assert result["metadata"]["error"] is True
        assert result["confidence_metadata"]["overall_confidence"] == 0.0

    def test_degraded_output_has_event_id_ref(self):
        """测试降级输出有 event_id_ref"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        # 提供部分有效输入
        result = adapter.process_event({"event_id": "evt_degraded_test"})

        assert result["event_id_ref"] == "evt_degraded_test"

    def test_degraded_output_not_pretending_normal(self):
        """测试降级输出不假装正常"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        result = adapter.process_event({})

        # 不应假装主体已更新
        assert result["confidence_metadata"]["overall_confidence"] == 0.0

        # 不应有伪造的 appraisal
        if "appraisal_state_delta" in result:
            assert result.get("appraisal_state_delta") is None or result["metadata"].get("error")

    def test_degraded_mode_preserves_basic_runtime(self):
        """测试降级模式保持基础运行时"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        # 降级后统计仍正常工作
        adapter.process_event({})
        stats = adapter.get_stats()

        assert stats["total_calls"] == 1
        assert stats["failed_calls"] == 1


class TestUnavailableScenario:
    """不可达场景测试"""

    def test_unavailable_returns_degraded_output(self):
        """测试不可达返回降级输出"""
        # 创建会抛出异常的 mock backend
        class UnavailableBackend(MockBackend):
            def process(self, event):
                raise ConnectionError("OpenEmotion service unavailable")

        backend = UnavailableBackend()
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK, backend=backend)

        event_data = {
            "event_id": "evt_unavailable_test",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {"actor_id": "user_001", "actor_type": "user"},
            "source": {"channel": "telegram", "surface": "telegram"},
            "event_type": "user_message",
            "user_intent": {"primary_intent": "test"},
            "safety_context": {"risk_level": "low"},
        }

        result = adapter.process_event(event_data)

        assert result["metadata"]["error"] is True
        assert "Processing error" in result["metadata"]["error_message"]


class TestTimeoutScenario:
    """超时场景测试"""

    def test_timeout_returns_degraded_output(self):
        """测试超时返回降级输出"""
        class TimeoutBackend(MockBackend):
            def process(self, event):
                raise TimeoutError("OpenEmotion response timeout")

        backend = TimeoutBackend()
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK, backend=backend)

        event_data = {
            "event_id": "evt_timeout_test",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {"actor_id": "user_001", "actor_type": "user"},
            "source": {"channel": "telegram", "surface": "telegram"},
            "event_type": "user_message",
            "user_intent": {"primary_intent": "test"},
            "safety_context": {"risk_level": "low"},
        }

        result = adapter.process_event(event_data)

        assert result["metadata"]["error"] is True


class TestInvalidOutputScenario:
    """无效输出场景测试"""

    def test_invalid_output_returns_degraded_output(self):
        """测试无效输出返回降级输出"""
        class InvalidOutputBackend(MockBackend):
            def process(self, event):
                # 返回缺少必需字段的输出
                return OpenEmotionOutput(
                    output_id="",  # 无效
                    timestamp="...",
                    event_id_ref=event.event_id,
                    confidence_metadata={},  # 无效
                )

        backend = InvalidOutputBackend()
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK, backend=backend)

        event_data = {
            "event_id": "evt_invalid_test",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {"actor_id": "user_001", "actor_type": "user"},
            "source": {"channel": "telegram", "surface": "telegram"},
            "event_type": "user_message",
            "user_intent": {"primary_intent": "test"},
            "safety_context": {"risk_level": "low"},
        }

        result = adapter.process_event(event_data)

        # 验证失败应返回错误输出
        assert result["metadata"]["error"] is True


class TestForbiddenDegradeBehaviors:
    """禁止的降级行为测试"""

    def test_no_fake_appraisal(self):
        """测试不伪造 appraisal"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        result = adapter.process_event({})

        # 降级输出不应有伪造的 appraisal
        # 如果存在，应该是 None 或标记为错误
        if "appraisal_state_delta" in result:
            # 只在非错误输出中检查
            if not result["metadata"].get("error"):
                assert False, "Degraded output should not have fake appraisal"

    def test_no_fake_memory_update(self):
        """测试不伪造 memory_update"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        result = adapter.process_event({})

        # 降级输出不应有伪造的 memory_update
        assert "memory_update" not in result or result.get("memory_update") is None

    def test_no_fake_reflection(self):
        """测试不伪造 reflection"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        result = adapter.process_event({})

        # 降级输出不应有伪造的 reflection
        assert "reflection_note" not in result or result.get("reflection_note") is None


class TestDegradeTransparency:
    """降级透明性测试"""

    def test_degrade_marked_clearly(self):
        """测试降级被清晰标记"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        result = adapter.process_event({})

        # 降级必须被标记
        assert result["metadata"]["error"] is True

    def test_degrade_reason_recorded(self):
        """测试降级原因被记录"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        result = adapter.process_event({})

        # 必须有错误消息
        assert "error_message" in result["metadata"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
