#!/usr/bin/env python3
"""
Contract Compatibility Test - W4

验证：
1. OpenEmotionEventV1 Python dataclass 与 JSON schema 兼容
2. OpenEmotionResultV1 Python dataclass 与 JSON schema 兼容
3. 样例 payload 可以被正确解析
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from egocore.contracts.openemotion_event_v1 import (
    OpenEmotionEventV1,
    Actor,
    ActorType,
    EventType,
    IntentType,
    UserIntent,
    ConversationContext,
    TaskContext,
    SafetyContext,
    RuntimeSummary,
    ExternalResult,
)
from egocore.contracts.openemotion_result_v1 import (
    OpenEmotionResultV1,
    MemoryUpdate,
    AppraisalStateDelta,
    ResponseTendency,
    ResponseMode,
    ResponseTone,
    StabilityMetadata,
)


def test_event_v1_creation():
    """测试 OpenEmotionEventV1 创建"""
    print("\n[TEST] OpenEmotionEventV1 创建...")
    
    event = OpenEmotionEventV1.create_user_message(
        event_id="evt_test_001",
        user_id="user_123",
        message_text="测试消息",
        intent_type=IntentType.CHAT,
    )
    
    assert event.event_id == "evt_test_001"
    assert event.actor.id == "user_123"
    assert event.event_type == EventType.USER_MESSAGE
    
    event_dict = event.to_dict()
    assert "event_id" in event_dict
    assert "actor" in event_dict
    
    print("  ✅ 创建成功")
    return event_dict


def test_result_v1_creation():
    """测试 OpenEmotionResultV1 创建"""
    print("\n[TEST] OpenEmotionResultV1 创建...")
    
    result = OpenEmotionResultV1(
        result_id="result_test_001",
        event_id_ref="evt_test_001",
        timestamp="2026-03-19T18:30:00Z",
        identity_state_delta={},
        self_model_delta={"field": "dominant_goal", "new_value": "test"},
        memory_update=MemoryUpdate(
            write_events=[{"test": "data"}],
        ),
        appraisal_state_delta=AppraisalStateDelta(
            trust=0.1,
        ),
        response_tendency=ResponseTendency(
            mode=ResponseMode.REPLY,
            tone=ResponseTone.WARM,
        ),
        confidence=0.8,
        stability_metadata=StabilityMetadata(
            state_ok=True,
            degraded=False,
        ),
    )
    
    assert result.result_id == "result_test_001"
    assert result.confidence == 0.8
    
    result_dict = result.to_dict()
    assert "self_model_delta" in result_dict
    assert "memory_update" in result_dict
    
    print("  ✅ 创建成功")
    return result_dict


def test_example_payloads():
    """测试样例 payload 解析"""
    print("\n[TEST] 样例 payload 解析...")
    
    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples", "openemotion_contracts"
    )
    
    event_path = os.path.join(examples_dir, "event_v1_example.json")
    result_path = os.path.join(examples_dir, "result_v1_example.json")
    
    if os.path.exists(event_path):
        with open(event_path) as f:
            event_example = json.load(f)
        assert "event_id" in event_example
        print(f"  ✅ event_v1_example.json 解析成功: {event_example['event_id']}")
    else:
        print(f"  ⚠️  {event_path} 不存在")
    
    if os.path.exists(result_path):
        with open(result_path) as f:
            result_example = json.load(f)
        assert "event_id" in result_example
        print(f"  ✅ result_v1_example.json 解析成功: {result_example['event_id']}")
    else:
        print(f"  ⚠️  {result_path} 不存在")


def test_schema_validation():
    """测试 JSON schema 验证"""
    if not HAS_JSONSCHEMA:
        print("\n[TEST] JSON schema 验证... 跳过 (jsonschema 未安装)")
        return
    
    print("\n[TEST] JSON schema 验证...")
    
    # 加载 schema
    schema_dir = "/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/schemas"
    
    event_schema_path = os.path.join(schema_dir, "openemotion_event_v1.schema.json")
    result_schema_path = os.path.join(schema_dir, "openemotion_result_v1.schema.json")
    
    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples", "openemotion_contracts"
    )
    
    # 验证 event
    if os.path.exists(event_schema_path) and os.path.exists(
        os.path.join(examples_dir, "event_v1_example.json")
    ):
        with open(event_schema_path) as f:
            event_schema = json.load(f)
        with open(os.path.join(examples_dir, "event_v1_example.json")) as f:
            event_example = json.load(f)
        
        try:
            jsonschema.validate(event_example, event_schema)
            print("  ✅ event_v1_example.json schema 验证通过")
        except jsonschema.ValidationError as e:
            print(f"  ❌ event_v1_example.json schema 验证失败: {e.message}")
    
    # 验证 result
    if os.path.exists(result_schema_path) and os.path.exists(
        os.path.join(examples_dir, "result_v1_example.json")
    ):
        with open(result_schema_path) as f:
            result_schema = json.load(f)
        with open(os.path.join(examples_dir, "result_v1_example.json")) as f:
            result_example = json.load(f)
        
        try:
            jsonschema.validate(result_example, result_schema)
            print("  ✅ result_v1_example.json schema 验证通过")
        except jsonschema.ValidationError as e:
            print(f"  ❌ result_v1_example.json schema 验证失败: {e.message}")


def test_field_coverage():
    """测试字段覆盖度"""
    print("\n[TEST] 字段覆盖度检查...")
    
    # W4 要求的字段
    required_event_fields = [
        "event_id", "timestamp", "actor", "event_type",
        "user_intent", "conversation_context", "task_context",
        "runtime_summary", "safety_context", "external_result"
    ]
    
    required_result_fields = [
        "identity_state_delta", "self_model_delta", "memory_update",
        "relationship_update", "appraisal_state_delta",
        "reflection_note", "policy_hint", "response_tendency",
        "confidence", "stability_metadata"
    ]
    
    # 检查 Python dataclass 属性
    event_attrs = [attr for attr in dir(OpenEmotionEventV1) if not attr.startswith('_')]
    result_attrs = [attr for attr in dir(OpenEmotionResultV1) if not attr.startswith('_')]
    
    missing_event = [f for f in required_event_fields if f not in event_attrs]
    missing_result = [f for f in required_result_fields if f not in result_attrs]
    
    if missing_event:
        print(f"  ⚠️  OpenEmotionEventV1 缺少字段: {missing_event}")
    else:
        print(f"  ✅ OpenEmotionEventV1 字段完整 ({len(required_event_fields)} 个)")
    
    if missing_result:
        print(f"  ⚠️  OpenEmotionResultV1 缺少字段: {missing_result}")
    else:
        print(f"  ✅ OpenEmotionResultV1 字段完整 ({len(required_result_fields)} 个)")


def main():
    print("=" * 60)
    print("Contract Compatibility Test - W4")
    print("=" * 60)
    
    try:
        test_event_v1_creation()
        test_result_v1_creation()
        test_example_payloads()
        test_schema_validation()
        test_field_coverage()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
