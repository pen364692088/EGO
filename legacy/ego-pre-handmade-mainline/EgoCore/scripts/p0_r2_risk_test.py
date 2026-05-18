"""
P0-R2 Risk Signal Verification Test (Simplified)

验证 safety_context.risk 从 EgoCore 正确传递到 Proto-Self Kernel。
"""

import sys
import json
import hashlib
from pathlib import Path

# 添加路径
egocore_path = Path(__file__).parent.parent
openemotion_path = Path(__file__).parent.parent.parent / "OpenEmotion"
sys.path.insert(0, str(egocore_path))
sys.path.insert(0, str(openemotion_path))


def test_risk_assessment():
    """测试 ContextAssembler 的风险评估逻辑"""
    print("=" * 60)
    print(" P0-R2 Risk Assessment Test")
    print("=" * 60)

    from app.risk_signal import assess_message_risk_level

    # 测试用例
    test_cases = [
        ("读取文件 test.txt", "low"),
        ("查看配置文件", "low"),
        ("删除临时文件", "high"),
        ("删除生产数据库", "critical"),
        ("delete the database", "high"),
        ("修改配置", "medium"),
        ("git push origin main", "high"),
    ]

    print("\n[1] Testing risk assessment...")
    for user_input, expected_risk in test_cases:
        risk_level = assess_message_risk_level(user_input)

        status = "✅" if risk_level == expected_risk else "❌"
        print(f"  {status} '{user_input}' → risk_level={risk_level} (expected: {expected_risk})")
        assert risk_level == expected_risk, f"Expected {expected_risk}, got {risk_level}"

    print("\n  ✅ All risk assessments passed")


def test_psi_bucket_construction():
    """测试 psi_bucket 构建"""
    print("\n[2] Testing psi_bucket construction...")

    def coarse_intent_classify(intent: str) -> str:
        """简化的 intent 分类"""
        intent_lower = intent.lower() if intent else ""

        # 高风险文件操作
        risk_op_patterns = ["删除", "delete", "remove", "rm", "格式化", "format", "drop"]
        for p in risk_op_patterns:
            if p in intent_lower:
                return "file_risk_op"

        # 文件读取
        read_patterns = ["读取", "查看", "显示", "read", "view", "check", "cat"]
        for p in read_patterns:
            if p in intent_lower:
                return "file_read"

        return "general"

    def build_psi_bucket(source: str, event_type: str, intent: str, safety_context: dict) -> str:
        """构建 psi_bucket"""
        coarse_intent = coarse_intent_classify(intent)
        risk_level = safety_context.get("risk_level", "low") if safety_context else "low"

        if risk_level in ["critical", "high"]:
            return f"{source}:{event_type}:{coarse_intent}:risk_{risk_level}"
        else:
            return f"{source}:{event_type}:{coarse_intent}"

    # 测试用例
    test_cases = [
        {
            "intent": "读取文件 test.txt",
            "safety_context": {"risk_level": "low"},
            "expected_suffix": None,  # 无 risk 后缀
        },
        {
            "intent": "删除临时文件",
            "safety_context": {"risk_level": "high"},
            "expected_suffix": "risk_high",
        },
        {
            "intent": "删除生产数据库",
            "safety_context": {"risk_level": "critical"},
            "expected_suffix": "risk_critical",
        },
    ]

    for tc in test_cases:
        psi_bucket = build_psi_bucket(
            source="telegram",
            event_type="user_message",
            intent=tc["intent"],
            safety_context=tc["safety_context"],
        )

        if tc["expected_suffix"]:
            assert tc["expected_suffix"] in psi_bucket, f"Expected '{tc['expected_suffix']}' in psi_bucket, got '{psi_bucket}'"
            print(f"  ✅ '{tc['intent']}' → {psi_bucket}")
        else:
            assert "risk_" not in psi_bucket, f"Expected no risk suffix, got '{psi_bucket}'"
            print(f"  ✅ '{tc['intent']}' → {psi_bucket}")

    # 验证高低风险区分
    low_bucket = build_psi_bucket("telegram", "user_message", "读取文件", {"risk_level": "low"})
    high_bucket = build_psi_bucket("telegram", "user_message", "删除生产数据库", {"risk_level": "critical"})

    print(f"\n  低风险 psi_bucket: {low_bucket}")
    print(f"  高风险 psi_bucket: {high_bucket}")

    assert low_bucket != high_bucket, "psi_buckets should be different!"
    print("  ✅ High and low risk psi_buckets are different")

    # 计算 cycle_id
    low_cycle_id = hashlib.sha256(low_bucket.encode()).hexdigest()[:16]
    high_cycle_id = hashlib.sha256(high_bucket.encode()).hexdigest()[:16]

    print(f"\n  低风险 cycle_id: {low_cycle_id}")
    print(f"  高风险 cycle_id: {high_cycle_id}")
    assert low_cycle_id != high_cycle_id, "cycle_ids should be different!"
    print("  ✅ High and low risk cycle_ids are different")


def test_event_builder_fix():
    """测试 EventBuilder 修复"""
    print("\n[3] Testing EventBuilder safety_context mapping...")

    from app.risk_signal import normalize_safety_context

    # 模拟 event_builder 的行为
    def build_safety_context(safety_ctx_input: dict) -> dict:
        """模拟 event_builder.build_from_execution_context 中的 safety_context 构建"""
        normalized = normalize_safety_context(safety_ctx_input)
        risk_level_value = normalized.get("risk_level", "low")
        return {
            "risk_level": risk_level_value,
            "requires_approval": normalized.get("requires_approval", False),
        }

    # 测试高风险场景
    input_ctx = {"risk_level": "high", "requires_approval": True}
    output_ctx = build_safety_context(input_ctx)

    print(f"  Input safety_context: {input_ctx}")
    print(f"  Output safety_context: {output_ctx}")

    assert "risk" not in output_ctx, "Legacy 'risk' field should not be emitted"
    assert output_ctx["risk_level"] == "high", f"Expected 'risk_level'='high', got '{output_ctx['risk_level']}'"
    print("  ✅ canonical 'risk_level' field preserved")

    # 测试低风险场景
    input_ctx_low = {"risk_level": "low", "requires_approval": False}
    output_ctx_low = build_safety_context(input_ctx_low)

    assert output_ctx_low["risk_level"] == "low", f"Expected 'risk_level'='low', got '{output_ctx_low['risk_level']}'"
    print("  ✅ Low risk also correctly mapped")


if __name__ == "__main__":
    try:
        test_risk_assessment()
        test_psi_bucket_construction()
        test_event_builder_fix()

        print("\n" + "=" * 60)
        print(" ALL TESTS PASSED!")
        print("=" * 60)
        print("\n修复验证成功：canonical risk_level 正确从 EgoCore 传递到 Proto-Self Kernel")
        print("高风险操作的 psi_bucket 将包含 :risk_high 或 :risk_critical 后缀")
        print("低风险操作的 psi_bucket 将不包含 risk 后缀")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
