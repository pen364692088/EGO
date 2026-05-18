#!/usr/bin/env python3
"""
EgoCore 直连 emotiond 验证脚本

Phase 2 验证目标：
1. EgoCore 可以不经过 OpenClaw，直接完成 ingress → emotiond → decision → outbound
2. 结构化 request/response 可保存、可回放、可定位

运行方式：
    cd /home/moonlight/Project/Github/MyProject/EgoCore
    python tools/test_egocore_emotiond_direct.py
"""

import asyncio
import json
import sys
import time
import subprocess
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# EgoCore 路径
EGOCORE_ROOT = Path("/home/moonlight/Project/Github/MyProject/EgoCore")
OPENEMOTION_ROOT = Path("/home/moonlight/openclaw-work/OpenEmotion-audit")

# 添加到 sys.path
sys.path.insert(0, str(EGOCORE_ROOT))
sys.path.insert(0, str(OPENEMOTION_ROOT))

# Artifact 目录
ARTIFACT_DIR = EGOCORE_ROOT / "artifacts" / "egocore_emotiond_direct" / datetime.now().strftime("%Y%m%d_%H%M%S")


def save_artifact(name: str, data: Dict[str, Any]) -> Path:
    """保存 artifact"""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def create_event_input(event_type: str = "user_message", text: str = "") -> Dict[str, Any]:
    """创建事件输入"""
    return {
        "event_id": f"evt_{int(time.time() * 1000)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": {
            "actor_id": "test_user",
            "actor_type": "human"
        },
        "source": {
            "channel": "telegram",
            "source_id": "test_chat_001"
        },
        "event_type": event_type,
        "user_intent": {
            "intent_type": "chat",
            "confidence": 0.9
        },
        "safety_context": {
            "risk_level": "low",
            "permissions": ["read", "write"]
        },
        "conversation_context": {
            "conversation_id": "test_conv_001",
            "turn_number": 1
        },
        "metadata": {
            "user_message": text
        },
        "trace_id": f"trace_{int(time.time() * 1000)}",
        "case_id": "direct_test_001"
    }


def test_module_import():
    """测试模块导入"""
    print("\n=== Test 1: Module Import ===")
    
    try:
        from egocore.adapters.openemotion_adapter import OpenEmotionAdapter, AdapterMode
        print("✅ OpenEmotionAdapter import OK")
    except Exception as e:
        print(f"❌ OpenEmotionAdapter import failed: {e}")
        return False
    
    try:
        from emotiond.api import app
        print("✅ emotiond.api import OK")
    except Exception as e:
        print(f"❌ emotiond.api import failed: {e}")
        return False
    
    try:
        from emotiond.core import process_event, load_initial_state
        print("✅ emotiond.core import OK")
    except Exception as e:
        print(f"❌ emotiond.core import failed: {e}")
        return False
    
    return True


def test_mock_mode():
    """测试 Mock 模式"""
    print("\n=== Test 2: Mock Mode ===")
    
    from egocore.adapters.openemotion_adapter import OpenEmotionAdapter, AdapterMode
    
    adapter = OpenEmotionAdapter(mode=AdapterMode.MOCK)
    
    event_input = create_event_input("user_message", "Hello, this is a test message")
    
    # 保存请求 artifact
    save_artifact("mock_request", event_input)
    
    # 处理事件
    output = adapter.process_event(event_input)
    
    # 保存响应 artifact
    save_artifact("mock_response", output)
    
    # 验证输出
    assert output.get("output_id"), "output_id is required"
    assert output.get("event_id_ref"), "event_id_ref is required"
    assert "valence" in output, "valence is required"
    assert "arousal" in output, "arousal is required"
    
    print(f"✅ Mock mode works")
    print(f"   output_id: {output.get('output_id')}")
    print(f"   valence: {output.get('valence')}")
    print(f"   arousal: {output.get('arousal')}")
    
    return True


def test_direct_module_call():
    """测试直接模块调用（不经过 HTTP）"""
    print("\n=== Test 3: Direct Module Call ===")
    
    from emotiond.models import Event
    from emotiond.core import process_event, load_initial_state
    
    # 初始化状态
    asyncio.run(load_initial_state())
    
    # 创建 OpenEmotion Event
    event = Event(
        type="user_message",
        actor="test_user",
        target="assistant",
        text="Hello from EgoCore direct call",
        meta={
            "source": "egocore_direct",
            "trace_id": f"trace_{int(time.time() * 1000)}"
        }
    )
    
    # 保存请求
    request_data = {
        "type": event.type,
        "actor": event.actor,
        "target": event.target,
        "text": event.text,
        "meta": event.meta
    }
    save_artifact("direct_module_request", request_data)
    
    # 处理事件
    result = asyncio.run(process_event(event))
    
    # 保存响应
    save_artifact("direct_module_response", result)
    
    # 验证
    assert result.get("status") in ["processed", "accepted"], f"Unexpected status: {result.get('status')}"
    
    print(f"✅ Direct module call works")
    print(f"   status: {result.get('status')}")
    print(f"   valence: {result.get('valence')}")
    print(f"   arousal: {result.get('arousal')}")
    
    return True


def test_adapter_with_real_backend():
    """测试 Adapter 使用 RealHTTPBackend（需要 emotiond 服务运行）"""
    print("\n=== Test 4: Real HTTP Backend (requires emotiond running) ===")
    
    from egocore.adapters.openemotion_adapter import OpenEmotionAdapter, AdapterMode
    
    # 创建 REAL_HTTP 模式的 adapter
    adapter = OpenEmotionAdapter(
        mode=AdapterMode.REAL_HTTP,
        base_url="http://localhost:8000",
        artifact_dir=ARTIFACT_DIR
    )
    
    # 健康检查
    async def check_health():
        return await adapter.health_check()
    
    is_healthy = asyncio.run(check_health())
    
    if not is_healthy:
        print("⚠️ emotiond service not running on localhost:8000")
        print("   Skipping REAL_HTTP test (emotiond needs to be started separately)")
        print("   To start: cd OpenEmotion && python -m emotiond.main")
        return None  # Not a failure, just skipped
    
    print("✅ emotiond health check passed")
    
    # 处理事件
    event_input = create_event_input("user_message", "Hello via REAL HTTP")
    save_artifact("real_http_request", event_input)
    
    output = adapter.process_event(event_input)
    save_artifact("real_http_response", output)
    
    # 验证
    assert output.get("output_id"), "output_id is required"
    assert output.get("event_id_ref"), "event_id_ref is required"
    
    print(f"✅ Real HTTP mode works")
    print(f"   output_id: {output.get('output_id')}")
    print(f"   valence: {output.get('valence')}")
    print(f"   arousal: {output.get('arousal')}")
    print(f"   transport_metadata: {output.get('transport_metadata')}")
    
    return True


def test_e2e_flow():
    """测试完整 E2E 流程"""
    print("\n=== Test 5: E2E Flow (3 scenarios) ===")
    
    from emotiond.models import Event
    from emotiond.core import process_event, load_initial_state
    
    # 初始化状态
    asyncio.run(load_initial_state())
    
    results = []
    
    # Scenario 1: 普通聊天
    print("\n  Scenario 1: Normal Chat")
    event1 = Event(
        type="user_message",
        actor="test_user",
        target="assistant",
        text="你好，今天天气不错",
        meta={"source": "egocore_direct", "case_id": "scenario_1"}
    )
    result1 = asyncio.run(process_event(event1))
    save_artifact("scenario_1_response", result1)
    print(f"    status: {result1.get('status')}, valence: {result1.get('valence')}")
    results.append(("scenario_1", result1.get("status") in ["processed", "accepted"]))
    
    # Scenario 2: 跨轮记忆
    print("\n  Scenario 2: Cross-turn Memory")
    event2 = Event(
        type="user_message",
        actor="test_user",
        target="assistant",
        text="我刚才说天气不错，你记得吗？",
        meta={"source": "egocore_direct", "case_id": "scenario_2"}
    )
    result2 = asyncio.run(process_event(event2))
    save_artifact("scenario_2_response", result2)
    print(f"    status: {result2.get('status')}, valence: {result2.get('valence')}")
    results.append(("scenario_2", result2.get("status") in ["processed", "accepted"]))
    
    # Scenario 3: 结果回流
    print("\n  Scenario 3: Result Feedback")
    event3 = Event(
        type="assistant_reply",
        actor="assistant",
        target="test_user",
        text="我已记住你说天气不错",
        meta={
            "source": "egocore_direct",
            "case_id": "scenario_3",
            "intent": "repair",
            "confidence": 0.9
        }
    )
    result3 = asyncio.run(process_event(event3))
    save_artifact("scenario_3_response", result3)
    print(f"    status: {result3.get('status')}, valence: {result3.get('valence')}")
    results.append(("scenario_3", result3.get("status") in ["processed", "accepted"]))
    
    # 汇总
    all_passed = all(passed for _, passed in results)
    print(f"\n  Results: {sum(1 for _, p in results if p)}/{len(results)} passed")
    
    return all_passed


def main():
    """主测试流程"""
    print("=" * 60)
    print("EgoCore → emotiond 直连验证")
    print("=" * 60)
    print(f"EgoCore: {EGOCORE_ROOT}")
    print(f"OpenEmotion: {OPENEMOTION_ROOT}")
    print(f"Artifacts: {ARTIFACT_DIR}")
    print("=" * 60)
    
    tests = [
        ("Module Import", test_module_import),
        ("Mock Mode", test_mock_mode),
        ("Direct Module Call", test_direct_module_call),
        ("Real HTTP Backend", test_adapter_with_real_backend),
        ("E2E Flow", test_e2e_flow),
    ]
    
    results = []
    
    for name, test_fn in tests:
        try:
            result = test_fn()
            if result is None:
                results.append((name, "SKIPPED"))
            elif result:
                results.append((name, "PASS"))
            else:
                results.append((name, "FAIL"))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, "FAIL"))
    
    # 汇总
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, status in results:
        symbol = "✅" if status == "PASS" else "⚠️" if status == "SKIPPED" else "❌"
        print(f"  {symbol} {name}: {status}")
    
    passed = sum(1 for _, s in results if s == "PASS")
    failed = sum(1 for _, s in results if s == "FAIL")
    skipped = sum(1 for _, s in results if s == "SKIPPED")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        print("\n❌ VALIDATION FAILED")
        return 1
    else:
        print("\n✅ VALIDATION PASSED")
        print(f"   Artifacts saved to: {ARTIFACT_DIR}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
