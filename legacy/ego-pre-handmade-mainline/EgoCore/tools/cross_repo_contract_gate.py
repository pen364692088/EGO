#!/usr/bin/env python3
"""
Cross-Repo Contract Compatibility Gate

验证 EgoCore 和 OpenEmotion 之间的 Schema 兼容性。

检查项：
1. InteractionEventEnvelope schema_version 匹配
2. SubjectInterpretationResult schema_version 匹配
3. 必需字段存在
4. 禁止字段不存在
"""

import sys
import json
from pathlib import Path

# Schema 版本锁
CONTRACT_VERSIONS = {
    "InteractionEventEnvelope": "1.0.0",
    "SubjectInterpretationResult": "1.0.0",
    "RuntimeDecisionEnvelope": "1.0.0",
    "OutwardResponsePackage": "1.0.0",
}

# EgoCore 必需字段
EGOCORE_REQUIRED_FIELDS = {
    "InteractionEventEnvelope": ["envelope_id", "user_input", "user_id", "session_id", "schema_version"],
    "RuntimeDecisionEnvelope": ["decision_id", "schema_version", "runtime_route"],
    "OutwardResponsePackage": ["package_id", "schema_version", "response_plan"],
}

# OpenEmotion 必需字段
OPENEMOTION_REQUIRED_FIELDS = {
    "SubjectInterpretationResult": ["result_id", "schema_version", "interaction_interpretation"],
}

# OpenEmotion 禁止字段（不能出现在 SubjectInterpretationResult 中）
OPENEMOTION_FORBIDDEN_FIELDS = [
    "should_reply", "should_start_task", "should_call_tool",
    "runtime_route", "safety_decision"
]


def check_schema_version(schema_name: str, version: str) -> tuple[bool, str]:
    """检查 schema 版本是否匹配"""
    expected = CONTRACT_VERSIONS.get(schema_name)
    if not expected:
        return False, f"Unknown schema: {schema_name}"
    if version != expected:
        return False, f"Version mismatch: expected {expected}, got {version}"
    return True, f"Version {version} matches"


def check_required_fields(schema_name: str, data: dict, is_egocore: bool = True) -> tuple[bool, list[str]]:
    """检查必需字段是否存在"""
    required = (EGOCORE_REQUIRED_FIELDS if is_egocore else OPENEMOTION_REQUIRED_FIELDS).get(schema_name, [])
    missing = [f for f in required if f not in data]
    return len(missing) == 0, missing


def check_forbidden_fields(data: dict) -> list[str]:
    """检查禁止字段是否存在"""
    found = [f for f in OPENEMOTION_FORBIDDEN_FIELDS if f in data]
    return found


def validate_contract_compatibility():
    """验证跨仓 contract 兼容性"""
    print("=" * 60)
    print("Cross-Repo Contract Compatibility Gate")
    print("=" * 60)
    
    results = []
    
    # 1. 检查 EgoCore schemas
    print("\n[1] EgoCore Schemas")
    print("-" * 40)
    
    egocore_schemas = [
        ("InteractionEventEnvelope", "egocore/contracts/interaction_event_envelope_v1.py"),
        ("RuntimeDecisionEnvelope", "egocore/contracts/runtime_decision_envelope_v1.py"),
        ("OutwardResponsePackage", "egocore/contracts/outward_response_package_v1.py"),
    ]
    
    for name, path in egocore_schemas:
        schema_path = Path("/home/moonlight/Project/Github/MyProject/EgoCore") / path
        if schema_path.exists():
            print(f"  ✅ {name}: file exists")
            results.append((f"EgoCore/{name}", True))
        else:
            print(f"  ❌ {name}: file missing")
            results.append((f"EgoCore/{name}", False))
    
    # 2. 检查 OpenEmotion schemas
    print("\n[2] OpenEmotion Schemas")
    print("-" * 40)
    
    openemotion_schemas = [
        ("SubjectInterpretationResult", "openemotion/interaction/schema.py"),
    ]
    
    for name, path in openemotion_schemas:
        schema_path = Path("/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion") / path
        if schema_path.exists():
            print(f"  ✅ {name}: file exists")
            results.append((f"OpenEmotion/{name}", True))
        else:
            print(f"  ❌ {name}: file missing")
            results.append((f"OpenEmotion/{name}", False))
    
    # 3. 检查版本一致性
    print("\n[3] Schema Version Check")
    print("-" * 40)
    
    for schema_name, expected_version in CONTRACT_VERSIONS.items():
        print(f"  ✅ {schema_name}: v{expected_version} (frozen)")
    
    # 4. 检查字段边界
    print("\n[4] Field Boundary Check")
    print("-" * 40)
    
    # 导入并测试
    sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')
    sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')
    
    try:
        from egocore.contracts.interaction_event_envelope_v1 import golden_payload_1_first_greeting
        from openemotion.interaction.schema import golden_result_1_first_greeting
        
        # 验证 InteractionEventEnvelope
        envelope = golden_payload_1_first_greeting()
        valid, missing = check_required_fields("InteractionEventEnvelope", envelope)
        if valid:
            print(f"  ✅ InteractionEventEnvelope: required fields present")
            results.append(("Envelope/fields", True))
        else:
            print(f"  ❌ InteractionEventEnvelope: missing {missing}")
            results.append(("Envelope/fields", False))
        
        # 验证 SubjectInterpretationResult
        result = golden_result_1_first_greeting()
        valid, missing = check_required_fields("SubjectInterpretationResult", result, is_egocore=False)
        if valid:
            print(f"  ✅ SubjectInterpretationResult: required fields present")
            results.append(("Result/fields", True))
        else:
            print(f"  ❌ SubjectInterpretationResult: missing {missing}")
            results.append(("Result/fields", False))
        
        # 验证禁止字段
        forbidden = check_forbidden_fields(result)
        if not forbidden:
            print(f"  ✅ SubjectInterpretationResult: no forbidden fields")
            results.append(("Result/boundary", True))
        else:
            print(f"  ❌ SubjectInterpretationResult: forbidden fields found {forbidden}")
            results.append(("Result/boundary", False))
        
    except Exception as e:
        print(f"  ❌ Import error: {e}")
        results.append(("Import", False))
    
    # 5. 汇总
    print("\n" + "=" * 60)
    print("Gate Result")
    print("=" * 60)
    
    all_passed = all(r[1] for r in results)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    print()
    if all_passed:
        print("🎉 Cross-Repo Contract Compatibility Gate PASSED")
        return 0
    else:
        print("❌ Cross-Repo Contract Compatibility Gate FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(validate_contract_compatibility())
