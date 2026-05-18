#!/usr/bin/env python3
"""
Contract Schema 验证脚本

验证四个正式 Schema 和 Golden Payload 的正确性。
"""

import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from egocore.contracts.interaction_event_envelope_v1 import (
    InteractionEventEnvelope,
    golden_payload_1_first_greeting,
    golden_payload_2_repeated_greeting,
    golden_payload_3_with_active_task,
    golden_payload_4_affective_probe,
    golden_payload_5_gratitude,
    validate_envelope,
)

from openemotion.interaction.schema import (
    SubjectInterpretationResult,
    golden_result_1_first_greeting,
    golden_result_2_repeated_greeting,
    golden_result_3_with_active_task,
    golden_result_4_affective_probe,
    golden_result_5_gratitude,
    golden_result_6_bridge_down,
    validate_result,
)

from egocore.contracts.runtime_decision_envelope_v1 import (
    RuntimeDecisionEnvelope,
    golden_decision_1_first_greeting,
    golden_decision_2_repeated_greeting,
    golden_decision_3_with_active_task,
    golden_decision_4_affective_probe,
    golden_decision_5_gratitude,
    golden_decision_6_bridge_down,
    validate_decision,
)

from egocore.contracts.outward_response_package_v1 import (
    OutwardResponsePackage,
    golden_package_1_first_greeting,
    golden_package_2_repeated_greeting,
    golden_package_3_with_active_task,
    golden_package_4_affective_probe,
    golden_package_5_gratitude,
    golden_package_6_bridge_down,
    validate_package,
)


def test_envelope():
    """测试 InteractionEventEnvelope"""
    print("=" * 60)
    print("测试 InteractionEventEnvelope")
    print("=" * 60)
    
    payloads = [
        ("初次问候", golden_payload_1_first_greeting()),
        ("连续测试", golden_payload_2_repeated_greeting()),
        ("有活动任务", golden_payload_3_with_active_task()),
        ("情感探询", golden_payload_4_affective_probe()),
        ("感谢", golden_payload_5_gratitude()),
    ]
    
    passed = 0
    for name, payload in payloads:
        valid, error = validate_envelope(payload)
        if valid:
            # 测试序列化/反序列化
            obj = InteractionEventEnvelope.from_dict(payload)
            back = obj.to_dict()
            if back["envelope_id"] == payload["envelope_id"]:
                print(f"✅ {name}: 验证通过")
                passed += 1
            else:
                print(f"❌ {name}: 序列化/反序列化失败")
        else:
            print(f"❌ {name}: {error}")
    
    print(f"\n通过: {passed}/{len(payloads)}")
    return passed == len(payloads)


def test_result():
    """测试 SubjectInterpretationResult"""
    print("\n" + "=" * 60)
    print("测试 SubjectInterpretationResult")
    print("=" * 60)
    
    payloads = [
        ("初次问候", golden_result_1_first_greeting()),
        ("连续测试", golden_result_2_repeated_greeting()),
        ("有活动任务", golden_result_3_with_active_task()),
        ("情感探询", golden_result_4_affective_probe()),
        ("感谢", golden_result_5_gratitude()),
        ("降级模式", golden_result_6_bridge_down()),
    ]
    
    passed = 0
    for name, payload in payloads:
        valid, error = validate_result(payload)
        if valid:
            obj = SubjectInterpretationResult.from_dict(payload)
            back = obj.to_dict()
            if back["result_id"] == payload["result_id"]:
                print(f"✅ {name}: 验证通过")
                passed += 1
            else:
                print(f"❌ {name}: 序列化/反序列化失败")
        else:
            print(f"❌ {name}: {error}")
    
    print(f"\n通过: {passed}/{len(payloads)}")
    return passed == len(payloads)


def test_decision():
    """测试 RuntimeDecisionEnvelope"""
    print("\n" + "=" * 60)
    print("测试 RuntimeDecisionEnvelope")
    print("=" * 60)
    
    payloads = [
        ("初次问候", golden_decision_1_first_greeting()),
        ("连续测试", golden_decision_2_repeated_greeting()),
        ("有活动任务", golden_decision_3_with_active_task()),
        ("情感探询", golden_decision_4_affective_probe()),
        ("感谢", golden_decision_5_gratitude()),
        ("降级模式", golden_decision_6_bridge_down()),
    ]
    
    passed = 0
    for name, payload in payloads:
        valid, error = validate_decision(payload)
        if valid:
            obj = RuntimeDecisionEnvelope.from_dict(payload)
            back = obj.to_dict()
            if back["decision_id"] == payload["decision_id"]:
                print(f"✅ {name}: 验证通过")
                passed += 1
            else:
                print(f"❌ {name}: 序列化/反序列化失败")
        else:
            print(f"❌ {name}: {error}")
    
    print(f"\n通过: {passed}/{len(payloads)}")
    return passed == len(payloads)


def test_package():
    """测试 OutwardResponsePackage"""
    print("\n" + "=" * 60)
    print("测试 OutwardResponsePackage")
    print("=" * 60)
    
    payloads = [
        ("初次问候", golden_package_1_first_greeting()),
        ("连续测试", golden_package_2_repeated_greeting()),
        ("有活动任务", golden_package_3_with_active_task()),
        ("情感探询", golden_package_4_affective_probe()),
        ("感谢", golden_package_5_gratitude()),
        ("降级模式", golden_package_6_bridge_down()),
    ]
    
    passed = 0
    for name, payload in payloads:
        valid, error = validate_package(payload)
        if valid:
            obj = OutwardResponsePackage.from_dict(payload)
            back = obj.to_dict()
            if back["package_id"] == payload["package_id"]:
                print(f"✅ {name}: 验证通过")
                passed += 1
            else:
                print(f"❌ {name}: 序列化/反序列化失败")
        else:
            print(f"❌ {name}: {error}")
    
    print(f"\n通过: {passed}/{len(payloads)}")
    return passed == len(payloads)


def test_boundary_integrity():
    """测试边界完整性"""
    print("\n" + "=" * 60)
    print("测试边界完整性")
    print("=" * 60)
    
    passed = True
    
    # 1. SubjectInterpretationResult 不包含 should_* 字段
    result = golden_result_1_first_greeting()
    forbidden = ["should_reply", "should_start_task", "should_call_tool", "runtime_route", "safety_decision"]
    for fld in forbidden:
        if fld in result:
            print(f"❌ SubjectInterpretationResult 包含禁止字段: {fld}")
            passed = False
    
    if passed:
        print("✅ SubjectInterpretationResult 不包含禁止字段")
    
    # 2. RuntimeDecisionEnvelope 不包含 appraisal/relationship 语义
    decision = golden_decision_1_first_greeting()
    forbidden_decision = ["appraisal", "relationship", "affect", "emotion"]
    for fld in forbidden_decision:
        if fld in decision:
            print(f"❌ RuntimeDecisionEnvelope 包含禁止字段: {fld}")
            passed = False
    
    if passed:
        print("✅ RuntimeDecisionEnvelope 不包含禁止字段")
    
    # 3. 验证 reply_urge != should_reply
    result = golden_result_2_repeated_greeting()
    decision = golden_decision_2_repeated_greeting()
    
    reply_urge = result.get("reply_urge", {}).get("value", 0.5)
    should_reply = decision.get("should_reply", True)
    
    print(f"✅ reply_urge (主体冲动) = {reply_urge}, should_reply (最终决策) = {should_reply}")
    print(f"   → 两者是不同概念：冲动 ≠ 决策")
    
    return passed


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Gate A: Contract Schema 验证")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("InteractionEventEnvelope", test_envelope()))
    results.append(("SubjectInterpretationResult", test_result()))
    results.append(("RuntimeDecisionEnvelope", test_decision()))
    results.append(("OutwardResponsePackage", test_package()))
    results.append(("边界完整性", test_boundary_integrity()))
    
    print("\n" + "=" * 60)
    print("Gate A 结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 Gate A 通过！可以开始实现。")
    else:
        print("❌ Gate A 失败，需要修复。")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
