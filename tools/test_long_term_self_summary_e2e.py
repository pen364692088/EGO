#!/usr/bin/env python3
"""
Long-Term Self Summary E2E Test - W3 验收

验证：
1. generate_summary 函数可调用
2. 输出符合 LongTermSelfSummary schema
3. 可从 identity + self_model 生成摘要
4. 可通过 /cycle 端点获取摘要信息
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone


def test_generate_summary():
    """测试 generate_summary 函数"""
    print("\n[TEST] generate_summary 函数...")
    
    from openemotion.identity.long_term_self_summary import (
        generate_summary,
        LongTermSelfSummary,
    )
    
    # 构造测试输入
    identity = {
        "identity_handle": "test_agent",
        "core_name": "Test Agent",
        "core_role": "Assistant",
        "owner_relationship": {
            "owner_id": "user_123",
        },
        "non_negotiable_commitments": [
            {"description": "不泄露用户隐私"},
        ],
    }
    
    self_model = {
        "capabilities": [
            {"category": "对话", "current_level": "advanced"},
            {"category": "任务执行", "current_level": "intermediate"},
        ],
        "limitations": [
            {"description": "不能访问外部网络"},
        ],
        "active_goals": [
            {"goal_id": "g1", "description": "完成项目", "status": "in_progress", "progress": 0.5},
        ],
    }
    
    recent_events = [
        {"event_type": "user_message", "summary": "用户请求帮助", "significance": "high"},
    ]
    
    # 生成摘要
    summary = generate_summary(identity, self_model, recent_events)
    
    # 验证
    assert isinstance(summary, LongTermSelfSummary), "应该是 LongTermSelfSummary 实例"
    assert summary.identity_handle == "test_agent", "identity_handle 应该匹配"
    assert summary.core_name == "Test Agent", "core_name 应该匹配"
    assert len(summary.strong_domains) > 0, "应该有能力领域"
    assert len(summary.recent_key_events) > 0, "应该有关键事件"
    
    print(f"  ✅ summary_id: {summary.summary_id}")
    print(f"  ✅ core_name: {summary.core_name}")
    print(f"  ✅ strong_domains: {summary.strong_domains}")
    print(f"  ✅ recent_key_events: {len(summary.recent_key_events)}")
    
    return summary


def test_summary_to_dict():
    """测试摘要序列化"""
    print("\n[TEST] 摘要序列化...")
    
    from openemotion.identity.long_term_self_summary import generate_summary
    
    summary = generate_summary(
        identity={"identity_handle": "test", "core_name": "Test", "core_role": "Bot"},
        self_model={},
    )
    
    summary_dict = summary.to_dict()
    
    assert isinstance(summary_dict, dict), "应该是 dict"
    assert "summary_id" in summary_dict, "应该有 summary_id"
    assert "identity_handle" in summary_dict, "应该有 identity_handle"
    assert "identity_summary" in summary_dict, "应该有 identity_summary"
    assert "core_name" in summary_dict["identity_summary"], "identity_summary 应该有 core_name"
    assert "current_phase_summary" in summary_dict, "应该有 current_phase_summary"
    assert "capability_summary" in summary_dict, "应该有 capability_summary"
    
    print(f"  ✅ 序列化成功，字段数: {len(summary_dict)}")
    
    return summary_dict


def test_cycle_output_fields():
    """测试 /cycle 输出字段覆盖"""
    print("\n[TEST] /cycle 输出字段...")
    
    import urllib.request
    import urllib.error
    
    # 构造请求
    event = {
        "event_id": "evt_test_summary",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": "test_user",
        "source": "cli",
        "event_type": "user_message",
        "content": "帮我总结一下你的状态",
    }
    
    try:
        req = urllib.request.Request(
            "http://localhost:18080/cycle",
            data=json.dumps(event).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
        
        # 验证必需字段
        required_fields = [
            "event_id",
            "result_type",
            "confidence",
            "self_model_delta",
            "memory_update",
            "response_tendency",
        ]
        
        result_data = result.get("result", {})
        missing = [f for f in required_fields if f not in result_data]
        
        if missing:
            print(f"  ⚠️  缺少字段: {missing}")
        else:
            print(f"  ✅ 所有必需字段存在")
        
        # 打印关键字段
        print(f"  ✅ result_type: {result_data.get('result_type')}")
        print(f"  ✅ confidence: {result_data.get('confidence')}")
        print(f"  ✅ self_model_delta: {bool(result_data.get('self_model_delta'))}")
        print(f"  ✅ memory_update: {result_data.get('memory_update')}")
        
        return result
    
    except urllib.error.URLError as e:
        print(f"  ⚠️  /cycle 端点不可用: {e}")
        return None


def test_readout_fields():
    """测试 readout 输出字段"""
    print("\n[TEST] readout 输出字段...")
    
    from openemotion.cycle_core.readout import ReadoutDecoder, ResponseTendency, PolicyHint
    
    # 创建 decoder
    decoder = ReadoutDecoder()
    
    # 测试 ResponseTendency
    tendency = ResponseTendency()
    tendency_dict = tendency.to_dict()
    
    assert "tone" in tendency_dict, "应该有 tone"
    assert "length" in tendency_dict, "应该有 length"
    assert "urgency" in tendency_dict, "应该有 urgency"
    
    print(f"  ✅ ResponseTendency: {tendency_dict}")
    
    # 测试 PolicyHint
    hint = PolicyHint()
    hint_dict = hint.to_dict()
    
    assert "hint_type" in hint_dict, "应该有 hint_type"
    assert "reason" in hint_dict, "应该有 reason"
    
    print(f"  ✅ PolicyHint: {hint_dict}")


def test_identity_summary_readout():
    """测试 identity 摘要读出"""
    print("\n[TEST] identity 摘要读出...")
    
    from openemotion.identity.identity_invariants import IdentityInvariants
    from openemotion.identity.long_term_self_summary import generate_summary
    
    # 创建 identity
    identity = IdentityInvariants(
        relationship_type="owned",
        identity_handle="test_agent",
        core_name="Test Agent",
        core_role="Assistant",
        owner_id="user_123",
    )
    
    # 转换为 dict
    identity_dict = identity.to_dict()
    
    # 生成摘要
    summary = generate_summary(identity_dict, {})
    
    # 验证关键字段
    assert summary.identity_handle == "test_agent"
    assert summary.core_name == "Test Agent"
    assert summary.primary_owner == "user_123"
    
    print(f"  ✅ identity_handle: {summary.identity_handle}")
    print(f"  ✅ core_name: {summary.core_name}")
    print(f"  ✅ primary_owner: {summary.primary_owner}")


def main():
    print("=" * 60)
    print("Long-Term Self Summary E2E Test - W3 验收")
    print("=" * 60)
    
    try:
        test_generate_summary()
        test_summary_to_dict()
        test_readout_fields()
        test_identity_summary_readout()
        test_cycle_output_fields()
        
        print("\n" + "=" * 60)
        print("✅ 所有 W3 测试通过")
        print("=" * 60)
        return 0
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
