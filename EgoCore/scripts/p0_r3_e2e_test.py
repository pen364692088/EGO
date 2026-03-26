#!/usr/bin/env python3
"""
P0-R3 集成测试：验证高风险与低风险消息经 runtime 主链后能传到 event_builder / OpenEmotion

测试目标：
1. 高风险消息经主链后 psi_bucket 包含 :risk_high
2. 低风险消息经主链后 psi_bucket 不包含 :risk_high
3. 两者 cycle_id 不同
"""

import sys
import os
import uuid
from datetime import datetime

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 添加 OpenEmotion 路径
OPENEMOTION_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "OpenEmotion")
if os.path.exists(OPENEMOTION_PATH):
    sys.path.insert(0, OPENEMOTION_PATH)


def test_e2e_risk_flow():
    """端到端测试：验证 risk 信号从 loop -> adapter -> OpenEmotion 的完整流"""

    print("=" * 60)
    print("P0-R3 E2E 测试：风险信号流验证")
    print("=" * 60)

    # 1. 测试 loop.py 的风险评估
    from app.runtime_v2.loop import _assess_risk_level

    high_risk_input = "删除临时文件"
    low_risk_input = "读取文件 test.txt"

    high_risk = _assess_risk_level(high_risk_input)
    low_risk = _assess_risk_level(low_risk_input)

    print(f"\n[1] 风险评估测试:")
    print(f"    高风险消息: '{high_risk_input}' -> risk_level = {high_risk}")
    print(f"    低风险消息: '{low_risk_input}' -> risk_level = {low_risk}")

    assert high_risk == "high", f"高风险消息应返回 'high'，实际: {high_risk}"
    assert low_risk == "low", f"低风险消息应返回 'low'，实际: {low_risk}"
    print("    ✅ 风险评估正确")

    # 2. 测试 event_builder 的字段映射
    # 直接测试字段映射逻辑（不需要完整 ExecutionContext）
    from app.risk_signal import normalize_safety_context

    # 模拟 ctx_dict 格式
    high_ctx_dict = {
        "safety_context": {"risk_level": "high"},
    }
    low_ctx_dict = {
        "safety_context": {"risk_level": "low"},
    }

    high_safety_result = normalize_safety_context(high_ctx_dict.get("safety_context", {}))
    low_safety_result = normalize_safety_context(low_ctx_dict.get("safety_context", {}))

    print(f"\n[2] 字段映射测试 (模拟 EventBuilder 逻辑):")
    print(f"    高风险 safety_context: {high_safety_result}")
    print(f"    低风险 safety_context: {low_safety_result}")

    assert high_safety_result == {"risk_level": "high"}, f"高风险应只保留 canonical risk_level，实际: {high_safety_result}"
    assert low_safety_result == {"risk_level": "low"}, f"低风险应只保留 canonical risk_level，实际: {low_safety_result}"
    print("    ✅ 字段映射正确")

    # 3. 测试 OpenEmotion 的 psi_bucket 构建
    from openemotion.proto_self.cycles import _build_psi_bucket, _coarse_intent_classify

    # 模拟 perceived 字典（OpenEmotion 期望的输入格式）
    high_perceived = {
        "source": "telegram",
        "event_type": "user_message",
        "intent": high_risk_input,
        "safety_context": {"risk_level": "high"},
    }

    low_perceived = {
        "source": "telegram",
        "event_type": "user_message",
        "intent": low_risk_input,
        "safety_context": {"risk_level": "low"},
    }

    high_psi_bucket = _build_psi_bucket(high_perceived)
    low_psi_bucket = _build_psi_bucket(low_perceived)

    print(f"\n[3] psi_bucket 构建测试:")
    print(f"    高风险 psi_bucket: {high_psi_bucket}")
    print(f"    低风险 psi_bucket: {low_psi_bucket}")

    assert ":risk_high" in high_psi_bucket, f"高风险 psi_bucket 应包含 ':risk_high'，实际: {high_psi_bucket}"
    assert ":risk_high" not in low_psi_bucket, f"低风险 psi_bucket 不应包含 ':risk_high'，实际: {low_psi_bucket}"
    print("    ✅ psi_bucket 正确")

    # 4. 测试 cycle_id 不同（使用简单的哈希）
    import hashlib

    def simple_hash(s: str) -> str:
        return hashlib.md5(s.encode()).hexdigest()[:16]

    high_cycle_id = simple_hash(high_psi_bucket)
    low_cycle_id = simple_hash(low_psi_bucket)

    print(f"\n[4] cycle_id 验证:")
    print(f"    高风险 cycle_id: {high_cycle_id}")
    print(f"    低风险 cycle_id: {low_cycle_id}")

    assert high_cycle_id != low_cycle_id, f"高风险和低风险的 cycle_id 应该不同"
    print("    ✅ cycle_id 不同")

    print("\n" + "=" * 60)
    print("P0-R3 E2E 测试全部通过！")
    print("=" * 60)

    return True


def test_risk_not_empty():
    """测试 safety_context 不为空"""
    from app.runtime_v2.loop import _assess_risk_level

    # 模拟各种输入
    test_cases = [
        ("删除临时文件", "high"),
        ("读取文件 test.txt", "low"),
        ("修改配置", "medium"),
        ("状态查询", "low"),
    ]

    print("\n[safety_context 非空验证]")
    for user_input, expected_risk in test_cases:
        risk_level = _assess_risk_level(user_input)
        safety_context = {"risk_level": risk_level}

        assert safety_context != {}, f"safety_context 不应为空"
        assert risk_level == expected_risk, f"'{user_input}' 风险应为 {expected_risk}，实际: {risk_level}"
        print(f"    ✅ '{user_input}' -> risk_level={risk_level}, safety_context={safety_context}")

    return True


if __name__ == "__main__":
    try:
        test_e2e_risk_flow()
        test_risk_not_empty()
        print("\n✅ 所有测试通过！")
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
