"""
OpenEmotion Adapter Tests
"""

import pytest
import json
from datetime import datetime

from egocore.adapters.openemotion_adapter import (
    OpenEmotionAdapter,
    MockBackend,
    EventInput,
    OpenEmotionOutput,
    AdapterMode,
    ValidationError,
    create_adapter,
)


class TestEventInput:
    """EventInput 测试"""

    def test_from_dict_minimal(self):
        """测试最小必填字段"""
        data = {
            "event_id": "evt_test_001",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {"actor_id": "user_001", "actor_type": "user"},
            "source": {"channel": "telegram", "surface": "telegram"},
            "event_type": "user_message",
            "user_intent": {"primary_intent": "test"},
            "safety_context": {"risk_level": "low"},
        }

        event = EventInput.from_dict(data)

        assert event.event_id == "evt_test_001"
        assert event.event_type == "user_message"
        assert event.task_context is None

    def test_from_dict_full(self):
        """测试完整字段"""
        data = {
            "event_id": "evt_test_002",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {"actor_id": "user_001", "actor_type": "user"},
            "source": {"channel": "telegram", "surface": "telegram"},
            "event_type": "user_message",
            "user_intent": {"primary_intent": "test"},
            "safety_context": {"risk_level": "low"},
            "task_context": {"task_id": "task_001"},
            "conversation_context": {"turn_number": 1},
            "runtime_summary": {"model_in_use": "test-model"},
            "external_result": {"success": True},
            "metadata": {"custom": "value"},
        }

        event = EventInput.from_dict(data)

        assert event.task_context["task_id"] == "task_001"
        assert event.metadata["custom"] == "value"

    def test_to_dict(self):
        """测试转换为字典"""
        event = EventInput(
            event_id="evt_test_003",
            timestamp="2026-03-16T00:00:00Z",
            actor={"actor_id": "user_001", "actor_type": "user"},
            source={"channel": "telegram", "surface": "telegram"},
            event_type="user_message",
            user_intent={"primary_intent": "test"},
            safety_context={"risk_level": "low"},
        )

        result = event.to_dict()

        assert result["event_id"] == "evt_test_003"
        assert "task_context" not in result  # 可选字段未设置时不应出现


class TestMockBackend:
    """MockBackend 测试"""

    def test_default_response(self):
        """测试默认响应生成"""
        backend = MockBackend()

        event = EventInput(
            event_id="evt_test_001",
            timestamp="2026-03-16T00:00:00Z",
            actor={"actor_id": "user_001", "actor_type": "user"},
            source={"channel": "telegram", "surface": "telegram"},
            event_type="user_message",
            user_intent={"primary_intent": "test"},
            safety_context={"risk_level": "low"},
        )

        output = backend.process(event)

        assert output.event_id_ref == "evt_test_001"
        assert output.confidence_metadata["overall_confidence"] == 0.9
        assert output.appraisal_state_delta is not None

    def test_custom_response_generator(self):
        """测试自定义响应生成器"""
        def custom_generator(event: EventInput) -> OpenEmotionOutput:
            return OpenEmotionOutput(
                output_id="out_custom_001",
                timestamp="2026-03-16T00:00:00Z",
                event_id_ref=event.event_id,
                confidence_metadata={"overall_confidence": 0.99},
            )

        backend = MockBackend(response_generator=custom_generator)

        event = EventInput(
            event_id="evt_test_002",
            timestamp="2026-03-16T00:00:00Z",
            actor={"actor_id": "user_001", "actor_type": "user"},
            source={"channel": "telegram", "surface": "telegram"},
            event_type="user_message",
            user_intent={"primary_intent": "test"},
            safety_context={"risk_level": "low"},
        )

        output = backend.process(event)

        assert output.output_id == "out_custom_001"
        assert output.confidence_metadata["overall_confidence"] == 0.99

    def test_call_history(self):
        """测试调用历史记录"""
        backend = MockBackend()

        event = EventInput(
            event_id="evt_history_001",
            timestamp="2026-03-16T00:00:00Z",
            actor={"actor_id": "user_001", "actor_type": "user"},
            source={"channel": "telegram", "surface": "telegram"},
            event_type="user_message",
            user_intent={"primary_intent": "test"},
            safety_context={"risk_level": "low"},
        )

        backend.process(event)
        backend.process(event)

        assert len(backend.call_history) == 2
        assert backend.call_history[0]["event_id"] == "evt_history_001"


class TestOpenEmotionAdapter:
    """OpenEmotionAdapter 测试"""

    def test_mock_mode_initialization(self):
        """测试 mock 模式初始化"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        assert adapter.mode == AdapterMode.MOCK
        assert isinstance(adapter.backend, MockBackend)

    def test_process_event_success(self):
        """测试成功处理事件"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        event_input = {
            "event_id": "evt_adapter_001",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {"actor_id": "user_001", "actor_type": "user"},
            "source": {"channel": "telegram", "surface": "telegram"},
            "event_type": "user_message",
            "user_intent": {"primary_intent": "test"},
            "safety_context": {"risk_level": "low"},
        }

        result = adapter.process_event(event_input)

        assert "output_id" in result
        assert result["event_id_ref"] == "evt_adapter_001"
        assert adapter.stats["successful_calls"] == 1

    def test_process_event_validation_error(self):
        """测试输入验证错误"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        # 缺少必填字段
        event_input = {
            "event_id": "evt_adapter_002",
            # 缺少 timestamp 和其他必填字段
        }

        result = adapter.process_event(event_input)

        assert result["metadata"]["error"] is True
        assert "Validation error" in result["metadata"]["error_message"]
        assert adapter.stats["failed_calls"] == 1

    def test_stats_tracking(self):
        """测试统计追踪"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        event_input = {
            "event_id": "evt_stats_001",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {"actor_id": "user_001", "actor_type": "user"},
            "source": {"channel": "telegram", "surface": "telegram"},
            "event_type": "user_message",
            "user_intent": {"primary_intent": "test"},
            "safety_context": {"risk_level": "low"},
        }

        adapter.process_event(event_input)
        adapter.process_event(event_input)

        stats = adapter.get_stats()
        assert stats["total_calls"] == 2
        assert stats["successful_calls"] == 2

    def test_reset_stats(self):
        """测试重置统计"""
        adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)

        event_input = {
            "event_id": "evt_reset_001",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {"actor_id": "user_001", "actor_type": "user"},
            "source": {"channel": "telegram", "surface": "telegram"},
            "event_type": "user_message",
            "user_intent": {"primary_intent": "test"},
            "safety_context": {"risk_level": "low"},
        }

        adapter.process_event(event_input)
        adapter.reset_stats()

        stats = adapter.get_stats()
        assert stats["total_calls"] == 0


class TestCreateAdapter:
    """create_adapter 工厂函数测试"""

    def test_create_mock_adapter(self):
        """测试创建 mock 适配器"""
        adapter = create_adapter(mode="mock")

        assert adapter.mode == AdapterMode.MOCK
        assert isinstance(adapter.backend, MockBackend)

    def test_create_real_adapter_requires_endpoint(self):
        """测试 real 模式需要 endpoint"""
        with pytest.raises(ValueError):
            create_adapter(mode="real")


class TestEventInputValidation:
    """EventInput 验证测试"""

    def test_valid_event_types(self):
        """测试有效事件类型"""
        valid_types = [
            "user_message", "user_command", "task_started",
            "task_completed", "task_failed", "tool_invoked",
            "tool_result", "state_change", "external_event",
            "system_notification"
        ]

        for event_type in valid_types:
            data = {
                "event_id": f"evt_type_{event_type}",
                "timestamp": "2026-03-16T00:00:00Z",
                "actor": {"actor_id": "user_001", "actor_type": "user"},
                "source": {"channel": "telegram", "surface": "telegram"},
                "event_type": event_type,
                "user_intent": {"primary_intent": "test"},
                "safety_context": {"risk_level": "low"},
            }

            event = EventInput.from_dict(data)
            assert event.event_type == event_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
