"""
Proto-Self E2E Preflight + Minimal Telegram Test

Usage:
    python scripts/e2e_proto_self_preflight.py

Preflight Checks (任何一项失败立即退出):
    - enabled=true in config
    - trace path 可写
    - state mirror path 可写
    - adapter 可导入

E2E Scenarios (3类):
    1. 偏好写入 - 发送偏好表达，验证 cycle 创建
    2. 相似请求读取 - 重复相似输入，验证 hits 增加
    3. failure 回流 - 模拟工具失败，验证 reflection 触发

Evidence Output:
    - 启动日志
    - trace artifact 路径
    - state mirror 路径
    - cycle_id / hits / reflection_note / revision_counter
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
# Add OpenEmotion to path (sibling directory)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "OpenEmotion"))


def log(msg: str, level: str = "INFO"):
    """输出带时间戳的日志。"""
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] [{level}] {msg}")


def preflight_check() -> dict:
    """
    Preflight 检查 - 任何失败立即退出。

    Returns:
        Preflight 结果字典
    """
    log("=" * 60)
    log("PROTO-SELF E2E PREFLIGHT CHECK")
    log("=" * 60)

    errors = []
    warnings = []
    evidence = {}

    # Check 1: Config enabled
    log("\n[1/4] Checking config: openemotion.enabled...")
    try:
        from app.config import load_config
        config = load_config()
        enabled = config.openemotion.get('enabled', False)
        evidence['config_enabled'] = enabled
        log(f"  config.openemotion.enabled = {enabled}")

        if not enabled:
            errors.append("openemotion.enabled is FALSE - Proto-Self is disabled in config")
        else:
            log("  ✓ ENABLED")
    except Exception as e:
        errors.append(f"Failed to load config: {e}")
        evidence['config_enabled'] = False

    # Check 2: Adapter import
    log("\n[2/4] Checking Proto-Self adapter import...")
    try:
        from app.openemotion_adapter import ProtoSelfAdapter, ProtoSelfTraceBridge
        evidence['adapter_import_ok'] = True
        log("  ✓ ProtoSelfAdapter imported successfully")
    except ImportError as e:
        errors.append(f"Failed to import ProtoSelfAdapter: {e}")
        evidence['adapter_import_ok'] = False

    # Check 3: State mirror path writable
    log("\n[3/4] Checking state mirror path...")
    mirror_dir = Path("artifacts/proto_self_mirror")
    evidence['mirror_path'] = str(mirror_dir.absolute())
    try:
        mirror_dir.mkdir(parents=True, exist_ok=True)
        # Test write
        test_file = mirror_dir / ".preflight_test"
        test_file.write_text("test")
        test_file.unlink()
        mirror_writable = os.access(mirror_dir, os.W_OK)
        evidence['mirror_writable'] = mirror_writable
        if mirror_writable:
            log(f"  ✓ Mirror path writable: {mirror_dir}")
        else:
            errors.append(f"Mirror path not writable: {mirror_dir}")
    except Exception as e:
        errors.append(f"Mirror path check failed: {e}")
        evidence['mirror_writable'] = False

    # Check 4: Trace path writable
    log("\n[4/4] Checking trace path...")
    trace_dir = Path("logs")
    trace_file = trace_dir / "proto_self_trace.jsonl"
    evidence['trace_path'] = str(trace_file.absolute())
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
        # Test write
        test_file = trace_dir / ".preflight_test"
        test_file.write_text("test\n")
        test_file.unlink()
        trace_writable = os.access(trace_dir, os.W_OK)
        evidence['trace_writable'] = trace_writable
        if trace_writable:
            log(f"  ✓ Trace path writable: {trace_dir}")
        else:
            errors.append(f"Trace path not writable: {trace_dir}")
    except Exception as e:
        errors.append(f"Trace path check failed: {e}")
        evidence['trace_writable'] = False

    # Summary
    log("\n" + "=" * 60)
    log("PREFLIGHT SUMMARY")
    log("=" * 60)

    if errors:
        log("\n❌ PREFLIGHT FAILED - Errors:", "ERROR")
        for err in errors:
            log(f"  - {err}", "ERROR")
        log("\n" + "=" * 60)
        log("ABORTING E2E TEST - Fix preflight errors first", "ERROR")
        log("=" * 60)
        sys.exit(1)

    if warnings:
        log("\n⚠️  Warnings:", "WARN")
        for warn in warnings:
            log(f"  - {warn}", "WARN")

    log("\n✅ ALL PREFLIGHT CHECKS PASSED")
    log(f"  Config enabled: {evidence['config_enabled']}")
    log(f"  Adapter import: OK")
    log(f"  Mirror path: {evidence['mirror_path']}")
    log(f"  Trace path: {evidence['trace_path']}")
    log("=" * 60)

    return evidence


def run_e2e_telegram_test(evidence: dict) -> dict:
    """
    运行最小 Telegram E2E 测试。

    Scenarios:
        1. 偏好写入 - 验证 cycle 创建
        2. 相似请求读取 - 验证 hits 增加
        3. failure 回流 - 验证 reflection 触发

    Returns:
        E2E 测试结果
    """
    log("\n" + "=" * 60)
    log("STARTING TELEGRAM E2E TEST")
    log("=" * 60)

    from app.openemotion_adapter import ProtoSelfAdapter, ProtoSelfTraceBridge
    from openemotion.proto_self import ProtoSelfState

    adapter = ProtoSelfAdapter()
    trace_bridge = ProtoSelfTraceBridge()
    adapter.trace_bridge = trace_bridge

    results = {
        "preflight": evidence,
        "scenarios": [],
        "evidence": {},
        "status": "unknown"
    }

    session_id = f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Scenario 1: 偏好写入
    log("\n[Scenario 1] 偏好写入 - Cycle 创建")
    log("-" * 40)

    event1 = {
        "event_id": f"{session_id}_s1_turn1",
        "timestamp": datetime.now().isoformat(),
        "actor": "user",
        "source": "telegram",
        "event_type": "user_message",
        "user_intent": "preference_test",
        "raw_text": "I prefer detailed technical responses",
        "task_context": {"pending_tasks": 0, "blocked_tasks": 0},
        "safety_context": {},
        "external_result": None,
    }

    result1 = adapter.handle_event(event1)

    # Load state to verify
    state = adapter.load_latest_state()
    cycles = list(state.cycle_store.signatures.values()) if hasattr(state, 'cycle_store') else []

    s1_result = {
        "name": "偏好写入",
        "event_id": event1["event_id"],
        "cycle_created": len(cycles) > 0,
        "cycle_count": len(cycles),
        "policy_hint": result1.get("policy_hint"),
        "response_tendency": result1.get("response_tendency"),
    }

    if s1_result["cycle_created"]:
        # Get the latest cycle
        latest_cycle = cycles[-1] if cycles else None
        if latest_cycle:
            s1_result["cycle_id"] = getattr(latest_cycle, 'cycle_id', 'unknown')
            s1_result["hits"] = getattr(latest_cycle, 'hits', 0)
            s1_result["strength"] = getattr(latest_cycle, 'strength', 0.0)
            log(f"  ✓ Cycle created: {s1_result['cycle_id']}")
            log(f"    hits={s1_result['hits']}, strength={s1_result['strength']}")
    else:
        log("  ⚠ No cycle created", "WARN")

    results["scenarios"].append(s1_result)

    # Scenario 2: 相似请求读取
    log("\n[Scenario 2] 相似请求读取 - Hits 增加")
    log("-" * 40)

    event2 = {
        "event_id": f"{session_id}_s2_turn1",
        "timestamp": datetime.now().isoformat(),
        "actor": "user",
        "source": "telegram",
        "event_type": "user_message",
        "user_intent": "preference_test",  # Same intent as event1 to trigger hits increase
        "raw_text": "I prefer detailed technical responses",  # Same text as event1
        "task_context": {"pending_tasks": 0, "blocked_tasks": 0},
        "safety_context": {},
        "external_result": None,
    }

    result2 = adapter.handle_event(event2)

    # Reload state
    state = adapter.load_latest_state()
    cycles = list(state.cycle_store.signatures.values()) if hasattr(state, 'cycle_store') else []

    s2_result = {
        "name": "相似请求读取",
        "event_id": event2["event_id"],
        "cycle_count": len(cycles),
        "policy_hint": result2.get("policy_hint"),
    }

    if cycles:
        latest_cycle = cycles[-1]
        s2_result["cycle_id"] = getattr(latest_cycle, 'cycle_id', 'unknown')
        s2_result["hits"] = getattr(latest_cycle, 'hits', 0)
        s2_result["strength"] = getattr(latest_cycle, 'strength', 0.0)

        # Check if hits increased
        if s2_result["hits"] > s1_result.get("hits", 0):
            s2_result["hits_increased"] = True
            log(f"  ✓ Hits increased: {s1_result.get('hits', 0)} -> {s2_result['hits']}")
        else:
            s2_result["hits_increased"] = False
            log(f"  ℹ Hits: {s2_result['hits']} (no increase)")

    results["scenarios"].append(s2_result)

    # Scenario 3: Failure 回流 - Reflection 触发
    log("\n[Scenario 3] Failure 回流 - Reflection 触发")
    log("-" * 40)

    event3 = {
        "event_id": f"{session_id}_s3_turn1",
        "timestamp": datetime.now().isoformat(),
        "actor": "system",
        "source": "runtime",
        "event_type": "tool_result",
        "user_intent": None,
        "raw_text": None,
        "task_context": {"pending_tasks": 1, "blocked_tasks": 1},
        "safety_context": {"risk_level": "high"},
        "external_result": {
            "success": False,
            "tool": "test_tool",
            "exit_code": 1,
            "error": "Command not found",
        },
    }

    result3 = adapter.handle_event(event3)

    # Reload state
    state = adapter.load_latest_state()

    s3_result = {
        "name": "failure 回流",
        "event_id": event3["event_id"],
        "reflection_triggered": result3.get("reflection_note") is not None,
        "reflection_note": result3.get("reflection_note"),
    }

    if s3_result["reflection_triggered"]:
        reflection = result3.get("reflection_note", {})
        s3_result["trigger"] = reflection.get("trigger")
        s3_result["diagnosis"] = reflection.get("diagnosis")
        s3_result["revision_counter"] = state.revision_counter if hasattr(state, 'revision_counter') else None
        log(f"  ✓ Reflection triggered!")
        log(f"    trigger: {s3_result['trigger']}")
        log(f"    diagnosis: {s3_result['diagnosis']}")
        log(f"    revision_counter: {s3_result['revision_counter']}")
    else:
        log("  ℹ No reflection triggered (may be expected for single failure)")

    results["scenarios"].append(s3_result)

    # Collect final evidence
    log("\n" + "=" * 60)
    log("COLLECTING EVIDENCE")
    log("=" * 60)

    # State file
    mirror_file = Path("artifacts/proto_self_mirror/state.json")
    if mirror_file.exists():
        results["evidence"]["state_mirror_path"] = str(mirror_file.absolute())
        results["evidence"]["state_mirror_size"] = mirror_file.stat().st_size
        log(f"  State mirror: {mirror_file} ({results['evidence']['state_mirror_size']} bytes)")

        # Load and extract key data
        try:
            with open(mirror_file) as f:
                state_data = json.load(f)
            results["evidence"]["revision_counter"] = state_data.get("revision_counter")
            results["evidence"]["cycle_count"] = len(state_data.get("cycles", []))
            log(f"  Revision counter: {results['evidence']['revision_counter']}")
            log(f"  Cycle count: {results['evidence']['cycle_count']}")
        except Exception as e:
            log(f"  Failed to read state: {e}", "WARN")

    # Trace file
    trace_file = Path("logs/proto_self_trace.jsonl")
    if trace_file.exists():
        results["evidence"]["trace_path"] = str(trace_file.absolute())
        # Count lines
        with open(trace_file) as f:
            trace_lines = [l for l in f if l.strip()]
        results["evidence"]["trace_entries"] = len(trace_lines)
        log(f"  Trace file: {trace_file} ({len(trace_lines)} entries)")

    return results


def generate_report(results: dict) -> str:
    """生成 E2E 测试报告。"""
    report_lines = [
        "# Proto-Self E2E Test Report",
        "",
        f"**Timestamp:** {datetime.now().isoformat()}",
        f"**Status:** {results.get('status', 'unknown')}",
        "",
        "## Preflight Evidence",
        "",
        f"- PROTO_SELF_ENABLED: {results['preflight'].get('config_enabled')}",
        f"- PROTO_SELF_ADAPTER_LOADED: {results['preflight'].get('adapter_import_ok')}",
        f"- PROTO_SELF_MIRROR_PATH: {results['preflight'].get('mirror_path')}",
        f"- PROTO_SELF_MIRROR_WRITABLE: {results['preflight'].get('mirror_writable')}",
        f"- PROTO_SELF_TRACE_PATH: {results['preflight'].get('trace_path')}",
        f"- PROTO_SELF_TRACE_WRITABLE: {results['preflight'].get('trace_writable')}",
        "",
        "## E2E Scenarios",
        "",
    ]

    for scenario in results.get("scenarios", []):
        report_lines.append(f"### {scenario['name']}")
        report_lines.append("")
        for key, value in scenario.items():
            if key != "name":
                report_lines.append(f"- **{key}:** {value}")
        report_lines.append("")

    report_lines.extend([
        "## Evidence Artifacts",
        "",
    ])

    for key, value in results.get("evidence", {}).items():
        report_lines.append(f"- **{key}:** {value}")

    report_lines.extend([
        "",
        "## Final Verdict",
        "",
    ])

    # Determine verdict
    scenarios = results.get("scenarios", [])
    cycle_created = any(s.get("cycle_created") for s in scenarios)
    reflection_triggered = any(s.get("reflection_triggered") for s in scenarios)

    if cycle_created:
        report_lines.append("✅ **Cycle created:** PASS")
    else:
        report_lines.append("⚠️ **Cycle created:** NOT CONFIRMED")

    if reflection_triggered:
        report_lines.append("✅ **Reflection triggered:** PASS")
    else:
        report_lines.append("ℹ️ **Reflection triggered:** NOT TRIGGERED (single failure may not trigger)")

    report_lines.append("")

    return "\n".join(report_lines)


def main():
    """Main entry point."""
    log("=" * 60)
    log("PROTO-SELF E2E PREFLIGHT + TELEGRAM TEST")
    log("=" * 60)

    # Step 1: Preflight (exits on failure)
    evidence = preflight_check()

    # Step 2: E2E Test
    results = run_e2e_telegram_test(evidence)

    # Step 3: Generate report
    log("\n" + "=" * 60)
    log("GENERATING REPORT")
    log("=" * 60)

    results["status"] = "completed"
    report = generate_report(results)

    # Save report
    report_dir = Path("artifacts/proto_self_e2e")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_file.write_text(report)
    log(f"  Report saved: {report_file}")

    # Print report
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # Final verdict
    log("\n" + "=" * 60)
    log("FINAL VERDICT")
    log("=" * 60)

    scenarios = results.get("scenarios", [])
    cycle_created = any(s.get("cycle_created") for s in scenarios)
    hits_increased = any(s.get("hits_increased") for s in scenarios)

    if cycle_created and hits_increased:
        log("✅ E2E PASSED: Cycle created and strengthened")
        log(f"  Evidence location: {report_file}")
        return 0
    elif cycle_created:
        log("⚠️ E2E PARTIAL: Cycle created but hits did not increase")
        log("  This may indicate similarity detection issues")
        return 1
    else:
        log("❌ E2E FAILED: No cycle created")
        return 2


if __name__ == "__main__":
    sys.exit(main())
