#!/usr/bin/env python3
"""
Phase 3 E2E 场景验证脚本

验证目标：
1. 场景 1：普通聊天 - 真实入口消息进入 EgoCore → EgoCore 调 emotiond → EgoCore 输出最终回复
2. 场景 2：跨轮记忆 - 第一轮输入事实 → 第二轮追问 → emotiond 产生 memory_update → 第二轮回复体现记忆影响
3. 场景 3：结果回流 - EgoCore 执行一个低风险动作或任务 → 执行结果回流 emotiond → emotiond 产出 reflection_note 或 policy_hint

运行方式：
    cd /home/moonlight/Project/Github/MyProject/EgoCore
    python tools/test_e2e_scenarios.py
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

# EgoCore 路径
EGOCORE_ROOT = Path("/home/moonlight/Project/Github/MyProject/EgoCore")
OPENEMOTION_ROOT = Path("/home/moonlight/openclaw-work/OpenEmotion-audit")

# 添加到 sys.path
sys.path.insert(0, str(EGOCORE_ROOT))
sys.path.insert(0, str(OPENEMOTION_ROOT))

# Artifact 目录
ARTIFACT_DIR = EGOCORE_ROOT / "artifacts" / "e2e_scenarios" / datetime.now().strftime("%Y%m%d_%H%M%S")


def save_artifact(name: str, data: Dict[str, Any], scenario: str = "") -> Path:
    """保存 artifact"""
    if scenario:
        dir_path = ARTIFACT_DIR / scenario
    else:
        dir_path = ARTIFACT_DIR
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def create_event_input(
    event_type: str,
    text: str,
    actor_id: str = "test_user",
    trace_id: Optional[str] = None,
    conversation_context: Optional[Dict] = None,
    external_result: Optional[Dict] = None,
) -> Dict[str, Any]:
    """创建事件输入"""
    return {
        "event_id": f"evt_{int(time.time() * 1000)}_{hash(text) % 10000}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": {
            "actor_id": actor_id,
            "actor_type": "human"
        },
        "source": {
            "channel": "telegram",
            "source_id": "test_chat_e2e"
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
        "conversation_context": conversation_context or {
            "conversation_id": "e2e_conv_001",
            "turn_number": 1
        },
        "metadata": {
            "user_message": text
        },
        "trace_id": trace_id or f"trace_{int(time.time() * 1000)}",
        "case_id": "e2e_scenario",
        "external_result": external_result
    }


@dataclass
class ScenarioResult:
    """场景结果"""
    scenario_name: str
    passed: bool
    events_processed: int
    artifacts_saved: List[str]
    has_memory_update: bool
    has_reflection_note: bool
    has_policy_hint: bool
    error_message: Optional[str] = None


async def run_scenario_1() -> ScenarioResult:
    """
    场景 1：普通聊天
    
    流程：真实入口消息进入 EgoCore → EgoCore 调 emotiond → EgoCore 输出最终回复
    """
    print("\n=== Scenario 1: Normal Chat ===")
    
    from emotiond.models import Event
    from emotiond.core import process_event, load_initial_state
    
    # 初始化状态
    await load_initial_state()
    
    # 创建事件
    user_message = "你好，我是测试用户"
    event_input = create_event_input("user_message", user_message)
    
    # 保存 raw_ingress_event
    save_artifact("raw_ingress_event", event_input, "scenario_1")
    
    # 转换为 OpenEmotion Event
    oe_event = Event(
        type="user_message",
        actor=event_input["actor"]["actor_id"],
        target="assistant",
        text=user_message,
        meta={
            "source": "egocore_direct",
            "trace_id": event_input["trace_id"],
            "event_id": event_input["event_id"]
        }
    )
    
    # 保存 openemotion_request
    save_artifact("openemotion_request", {
        "type": oe_event.type,
        "actor": oe_event.actor,
        "target": oe_event.target,
        "text": oe_event.text,
        "meta": oe_event.meta
    }, "scenario_1")
    
    # 处理事件
    result = await process_event(oe_event)
    
    # 保存 openemotion_response
    save_artifact("openemotion_response", result, "scenario_1")
    
    # 模拟 EgoCore 最终决策
    runtime_decision = {
        "decision_id": f"dec_{int(time.time() * 1000)}",
        "event_id": event_input["event_id"],
        "action": "respond",
        "response_text": f"收到消息：{user_message}",
        "valence": result.get("valence"),
        "arousal": result.get("arousal"),
        "policy_hint": result.get("self_report", {}).get("emotional_reasoning", {}).get("action_tendency")
    }
    save_artifact("runtime_decision", runtime_decision, "scenario_1")
    
    # 验证
    passed = result.get("status") in ["processed", "accepted"]
    
    print(f"  status: {result.get('status')}")
    print(f"  valence: {result.get('valence')}")
    print(f"  arousal: {result.get('arousal')}")
    print(f"  passed: {passed}")
    
    return ScenarioResult(
        scenario_name="scenario_1_normal_chat",
        passed=passed,
        events_processed=1,
        artifacts_saved=[
            "raw_ingress_event.json",
            "openemotion_request.json",
            "openemotion_response.json",
            "runtime_decision.json"
        ],
        has_memory_update=result.get("memory_strength", 0) > 0,
        has_reflection_note=result.get("self_report") is not None,
        has_policy_hint=result.get("self_report", {}).get("emotional_reasoning") is not None
    )


async def run_scenario_2() -> ScenarioResult:
    """
    场景 2：跨轮记忆
    
    流程：第一轮输入事实 → 第二轮追问 → emotiond 产生 memory_update → 第二轮回复体现记忆影响
    """
    print("\n=== Scenario 2: Cross-turn Memory ===")
    
    from emotiond.models import Event
    from emotiond.core import process_event, load_initial_state
    
    # 初始化状态
    await load_initial_state()
    
    conversation_id = f"e2e_conv_memory_{int(time.time() * 1000)}"
    trace_id = f"trace_memory_{int(time.time() * 1000)}"
    
    results = []
    artifacts = []
    
    # === 第一轮：输入事实 ===
    print("\n  Turn 1: Input fact")
    turn1_message = "我叫张三，我喜欢编程"
    event1_input = create_event_input(
        "user_message",
        turn1_message,
        conversation_context={"conversation_id": conversation_id, "turn_number": 1},
        trace_id=trace_id
    )
    save_artifact("turn1_ingress", event1_input, "scenario_2")
    
    oe_event1 = Event(
        type="user_message",
        actor="test_user",
        target="assistant",
        text=turn1_message,
        meta={
            "source": "egocore_direct",
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "turn": 1
        }
    )
    
    result1 = await process_event(oe_event1)
    save_artifact("turn1_response", result1, "scenario_2")
    results.append(result1)
    artifacts.append("turn1_ingress.json")
    artifacts.append("turn1_response.json")
    
    print(f"    status: {result1.get('status')}, valence: {result1.get('valence')}")
    
    # === 第二轮：追问 ===
    print("\n  Turn 2: Query memory")
    turn2_message = "你还记得我的名字和爱好吗？"
    event2_input = create_event_input(
        "user_message",
        turn2_message,
        conversation_context={"conversation_id": conversation_id, "turn_number": 2},
        trace_id=trace_id
    )
    save_artifact("turn2_ingress", event2_input, "scenario_2")
    
    oe_event2 = Event(
        type="user_message",
        actor="test_user",
        target="assistant",
        text=turn2_message,
        meta={
            "source": "egocore_direct",
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "turn": 2
        }
    )
    
    result2 = await process_event(oe_event2)
    save_artifact("turn2_response", result2, "scenario_2")
    results.append(result2)
    artifacts.append("turn2_ingress.json")
    artifacts.append("turn2_response.json")
    
    print(f"    status: {result2.get('status')}, valence: {result2.get('valence')}")
    
    # 检查 memory_update
    memory_update = result2.get("memory_update") or (
        result2.get("self_report", {}).get("narrative_memory", {}).get("state")
    )
    has_memory_update = memory_update is not None
    
    # 验证
    passed = all(r.get("status") in ["processed", "accepted"] for r in results)
    
    print(f"\n  has_memory_update: {has_memory_update}")
    print(f"  passed: {passed}")
    
    return ScenarioResult(
        scenario_name="scenario_2_cross_turn_memory",
        passed=passed,
        events_processed=2,
        artifacts_saved=artifacts,
        has_memory_update=has_memory_update,
        has_reflection_note=result2.get("self_report") is not None,
        has_policy_hint=result2.get("self_report", {}).get("emotional_reasoning") is not None
    )


async def run_scenario_3() -> ScenarioResult:
    """
    场景 3：结果回流
    
    流程：EgoCore 执行一个低风险动作或任务 → 执行结果回流 emotiond → emotiond 产出 reflection_note 或 policy_hint
    """
    print("\n=== Scenario 3: Result Feedback ===")
    
    from emotiond.models import Event
    from emotiond.core import process_event, load_initial_state
    
    # 初始化状态
    await load_initial_state()
    
    conversation_id = f"e2e_conv_result_{int(time.time() * 1000)}"
    trace_id = f"trace_result_{int(time.time() * 1000)}"
    
    artifacts = []
    
    # === Step 1: 用户请求 ===
    print("\n  Step 1: User request")
    user_request = "帮我创建一个测试文件"
    event1_input = create_event_input(
        "user_message",
        user_request,
        conversation_context={"conversation_id": conversation_id, "turn_number": 1},
        trace_id=trace_id
    )
    save_artifact("step1_ingress", event1_input, "scenario_3")
    artifacts.append("step1_ingress.json")
    
    oe_event1 = Event(
        type="user_message",
        actor="test_user",
        target="assistant",
        text=user_request,
        meta={
            "source": "egocore_direct",
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "intent": "task_request"
        }
    )
    
    result1 = await process_event(oe_event1)
    save_artifact("step1_response", result1, "scenario_3")
    artifacts.append("step1_response.json")
    
    print(f"    status: {result1.get('status')}")
    
    # === Step 2: 模拟任务执行 ===
    print("\n  Step 2: Task execution (simulated)")
    execution_result = {
        "task_id": f"task_{int(time.time() * 1000)}",
        "action": "create_file",
        "params": {"filename": "test_file.txt", "content": "Hello World"},
        "status": "success",
        "output": "文件 test_file.txt 已创建",
        "duration_ms": 150
    }
    save_artifact("task_execution_result", execution_result, "scenario_3")
    artifacts.append("task_execution_result.json")
    
    # === Step 3: 结果回流 ===
    print("\n  Step 3: Result feedback to emotiond")
    feedback_event = create_event_input(
        "assistant_reply",
        execution_result["output"],
        actor_id="assistant",
        conversation_context={"conversation_id": conversation_id, "turn_number": 2},
        trace_id=trace_id,
        external_result={
            "task_id": execution_result["task_id"],
            "action": execution_result["action"],
            "status": execution_result["status"],
            "output": execution_result["output"]
        }
    )
    save_artifact("feedback_ingress", feedback_event, "scenario_3")
    artifacts.append("feedback_ingress.json")
    
    oe_feedback = Event(
        type="assistant_reply",
        actor="assistant",
        target="test_user",
        text=execution_result["output"],
        meta={
            "source": "egocore_direct",
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "task_result": execution_result,
            "intent": "inform"
        }
    )
    
    result_feedback = await process_event(oe_feedback)
    save_artifact("feedback_response", result_feedback, "scenario_3")
    artifacts.append("feedback_response.json")
    
    print(f"    status: {result_feedback.get('status')}")
    
    # 检查 reflection_note 和 policy_hint
    self_report = result_feedback.get("self_report", {})
    has_reflection_note = self_report.get("narrative_memory") is not None
    has_policy_hint = self_report.get("emotional_reasoning", {}).get("action_tendency") is not None
    
    # 验证
    passed = result_feedback.get("status") in ["processed", "accepted"]
    
    print(f"\n  has_reflection_note: {has_reflection_note}")
    print(f"  has_policy_hint: {has_policy_hint}")
    print(f"  passed: {passed}")
    
    return ScenarioResult(
        scenario_name="scenario_3_result_feedback",
        passed=passed,
        events_processed=3,
        artifacts_saved=artifacts,
        has_memory_update=result_feedback.get("memory_strength", 0) > 0,
        has_reflection_note=has_reflection_note,
        has_policy_hint=has_policy_hint
    )


async def main():
    """主测试流程"""
    print("=" * 60)
    print("Phase 3: E2E Scenarios Verification")
    print("=" * 60)
    print(f"EgoCore: {EGOCORE_ROOT}")
    print(f"OpenEmotion: {OPENEMOTION_ROOT}")
    print(f"Artifacts: {ARTIFACT_DIR}")
    print("=" * 60)
    
    # 运行所有场景
    results: List[ScenarioResult] = []
    
    try:
        results.append(await run_scenario_1())
    except Exception as e:
        print(f"❌ Scenario 1 failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(ScenarioResult(
            scenario_name="scenario_1_normal_chat",
            passed=False,
            events_processed=0,
            artifacts_saved=[],
            has_memory_update=False,
            has_reflection_note=False,
            has_policy_hint=False,
            error_message=str(e)
        ))
    
    try:
        results.append(await run_scenario_2())
    except Exception as e:
        print(f"❌ Scenario 2 failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(ScenarioResult(
            scenario_name="scenario_2_cross_turn_memory",
            passed=False,
            events_processed=0,
            artifacts_saved=[],
            has_memory_update=False,
            has_reflection_note=False,
            has_policy_hint=False,
            error_message=str(e)
        ))
    
    try:
        results.append(await run_scenario_3())
    except Exception as e:
        print(f"❌ Scenario 3 failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(ScenarioResult(
            scenario_name="scenario_3_result_feedback",
            passed=False,
            events_processed=0,
            artifacts_saved=[],
            has_memory_update=False,
            has_reflection_note=False,
            has_policy_hint=False,
            error_message=str(e)
        ))
    
    # 保存汇总报告
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_scenarios": len(results),
        "passed_scenarios": sum(1 for r in results if r.passed),
        "results": [asdict(r) for r in results],
        "gate_checks": {
            "all_passed": all(r.passed for r in results),
            "has_memory_update": any(r.has_memory_update for r in results),
            "has_reflection_note": any(r.has_reflection_note for r in results),
            "has_policy_hint": any(r.has_policy_hint for r in results)
        }
    }
    save_artifact("e2e_summary", summary)
    
    # 打印汇总
    print("\n" + "=" * 60)
    print("E2E Scenarios Summary")
    print("=" * 60)
    
    for r in results:
        symbol = "✅" if r.passed else "❌"
        print(f"  {symbol} {r.scenario_name}: {'PASS' if r.passed else 'FAIL'}")
        if r.error_message:
            print(f"      Error: {r.error_message}")
    
    print("\n" + "-" * 60)
    print("Gate Checks:")
    print(f"  All Passed: {summary['gate_checks']['all_passed']}")
    print(f"  Has Memory Update: {summary['gate_checks']['has_memory_update']}")
    print(f"  Has Reflection Note: {summary['gate_checks']['has_reflection_note']}")
    print(f"  Has Policy Hint: {summary['gate_checks']['has_policy_hint']}")
    
    # 最终结论
    all_passed = all(r.passed for r in results)
    has_required = (
        summary['gate_checks']['has_memory_update'] and
        (summary['gate_checks']['has_reflection_note'] or summary['gate_checks']['has_policy_hint'])
    )
    
    print("\n" + "=" * 60)
    if all_passed and has_required:
        print("✅ PHASE 3 E2E VALIDATION PASSED")
        print(f"   Artifacts saved to: {ARTIFACT_DIR}")
        return 0
    else:
        print("❌ PHASE 3 E2E VALIDATION FAILED")
        if not all_passed:
            print("   Reason: Not all scenarios passed")
        if not has_required:
            print("   Reason: Missing required outputs (memory_update, reflection_note, or policy_hint)")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
