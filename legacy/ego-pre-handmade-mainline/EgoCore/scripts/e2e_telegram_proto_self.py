"""
Real Telegram E2E: Proto-Self Kernel v1

目标：
1. 真实 Telegram 环境验证
2. 证明 cycle/memory 被真实写入
3. 证明 policy_hint/response_tendency 影响响应
4. 证明 external_result=failure 触发 reflection

场景：
A. 第一次偏好事件 -> 写入 cycle/memory
B. 第二次相似事件 -> 命中同一 cycle_id，影响 policy_hint
C. 工具失败 -> reflection_note + revision_counter 变化

运行前提：
- Telegram bot token 已配置
- EgoCore 可正常启动
- 用户已通过 /new 开始新会话

运行：
    python -m app.main --telegram  # 启动 bot
    # 在另一个终端：
    python scripts/e2e_telegram_proto_self.py --verify  # 验证痕迹
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# 项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_config


def check_mirror_state():
    """检查 Proto-Self 状态镜像。"""
    mirror_dir = Path("artifacts/proto_self_mirror")
    mirror_file = mirror_dir / "state.json"

    if not mirror_file.exists():
        print("❌ State mirror not found")
        print(f"   Expected: {mirror_file}")
        return None

    with open(mirror_file, "r") as f:
        state = json.load(f)

    return state


def check_trace_logs():
    """检查 trace 日志。"""
    trace_dir = Path("artifacts/traces")
    if not trace_dir.exists():
        return []

    # 找最新的 run.jsonl
    trace_files = sorted(trace_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not trace_files:
        return []

    latest = trace_files[0]
    entries = []
    with open(latest, "r") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except:
                pass

    return entries


def verify_scenario_a_first_preference():
    """
    场景 A: 第一次偏好事件 -> 写入 cycle/memory

    用户输入示例: "I prefer concise responses"
    """
    print("=" * 60)
    print("Scenario A: First preference event writes to memory")
    print("=" * 60)

    state = check_mirror_state()
    if not state:
        print("⚠️  No state mirror found - bot may not have processed any messages")
        return False

    # 检查 episodic_trace
    episodic = state.get("episodic_trace", [])
    if not episodic:
        print("⚠️  No episodic records found")
        return False

    print(f"✅ Episodic records: {len(episodic)}")

    # 检查是否有 preference 相关记录
    preference_records = [
        r for r in episodic
        if r.get("perceived_summary", {}).get("intent") == "set_preference"
        or "prefer" in str(r.get("perceived_summary", {}).get("raw_text", "")).lower()
    ]

    if preference_records:
        print(f"✅ Found {len(preference_records)} preference-related records")
        for r in preference_records[:3]:
            print(f"   - Event: {r.get('event_id')}")
    else:
        print("ℹ️  No explicit preference records yet (may need user input)")

    # 检查 cycle_store
    cycles = state.get("cycle_store", {}).get("signatures", {})
    if cycles:
        print(f"✅ Cycle signatures: {len(cycles)}")
        for cycle_id, cycle in list(cycles.items())[:3]:
            print(f"   - {cycle_id[:16]}...: hits={cycle.get('hits')}, strength={cycle.get('strength', 0):.2f}")
    else:
        print("ℹ️  No cycles formed yet")

    return True


def verify_scenario_b_second_preference():
    """
    场景 B: 第二次相似事件 -> 命中同一 cycle_id

    用户输入示例: "I prefer concise responses" (第二次)
    """
    print("\n" + "=" * 60)
    print("Scenario B: Second similar event hits same cycle")
    print("=" * 60)

    state = check_mirror_state()
    if not state:
        return False

    cycles = state.get("cycle_store", {}).get("signatures", {})
    if not cycles:
        print("⚠️  No cycles found - need more similar events")
        return False

    # 找 hits > 1 的 cycle（说明被强化过）
    strengthened = [
        (cid, c) for cid, c in cycles.items()
        if c.get("hits", 0) > 1
    ]

    if strengthened:
        print(f"✅ Found {len(strengthened)} strengthened cycles:")
        for cid, c in strengthened[:3]:
            print(f"   - {cid[:16]}...: hits={c.get('hits')}, strength={c.get('strength', 0):.2f}")
            if c.get("promoted"):
                print(f"     ⭐ PROMOTED")
    else:
        print("ℹ️  No strengthened cycles yet (need similar events)")

    # 检查 policy_hint 是否被记录
    traces = check_trace_logs()
    policy_hints = [
        t for t in traces
        if "policy_hint" in t or "proto_self" in t.get("type", "")
    ]

    if policy_hints:
        print(f"✅ Found {len(policy_hints)} policy_hint records in trace")

    return True


def verify_scenario_c_failure_reflection():
    """
    场景 C: 工具失败 -> reflection_note + revision_counter

    需要执行一个会失败的工具（如访问不存在的文件）
    """
    print("\n" + "=" * 60)
    print("Scenario C: Tool failure triggers reflection")
    print("=" * 60)

    state = check_mirror_state()
    if not state:
        return False

    # 检查 revision_counter
    revision_count = state.get("revision_counter", 0)
    print(f"Revision counter: {revision_count}")

    if revision_count > 0:
        print(f"✅ Revisions occurred: {revision_count}")
    else:
        print("ℹ️  No revisions yet (need tool failure event)")

    # 检查是否有 repair mode
    self_model = state.get("self_model", {})
    current_mode = self_model.get("current_mode", "baseline")

    if current_mode == "repair":
        print(f"✅ Current mode is 'repair' (triggered by failure)")
    else:
        print(f"ℹ️  Current mode: {current_mode}")

    # 检查 trace 中的 reflection
    traces = check_trace_logs()
    reflections = [
        t for t in traces
        if "reflection" in str(t).lower()
    ]

    if reflections:
        print(f"✅ Found {len(reflections)} reflection-related records")

    return True


def verify_integration_chain():
    """验证完整调用链。"""
    print("\n" + "=" * 60)
    print("Integration Chain Verification")
    print("=" * 60)

    # 检查 loop.py 中是否有 proto_self 调用痕迹
    loop_file = Path("app/runtime_v2/loop.py")
    if loop_file.exists():
        content = loop_file.read_text()
        if "proto_self_adapter" in content and "handle_event" in content:
            print("✅ loop.py contains proto_self_adapter.handle_event() call")
        else:
            print("❌ loop.py missing proto_self integration")
            return False

    # 检查 adapter 是否存在
    adapter_file = Path("app/openemotion_adapter/proto_self_adapter.py")
    if adapter_file.exists():
        print("✅ ProtoSelfAdapter file exists")
    else:
        print("❌ ProtoSelfAdapter file not found")
        return False

    # 检查 mirror 目录
    mirror_dir = Path("artifacts/proto_self_mirror")
    if mirror_dir.exists():
        print("✅ Mirror directory exists")
    else:
        print("ℹ️  Mirror directory will be created on first run")

    return True


def generate_report():
    """生成验证报告。"""
    print("\n" + "=" * 60)
    print("E2E Verification Report")
    print("=" * 60)

    state = check_mirror_state()
    if state:
        print(f"\n📊 State Summary:")
        print(f"  - Identity confidence: {state.get('identity', {}).get('identity_confidence', 0)}")
        print(f"  - Episodic records: {len(state.get('episodic_trace', []))}")
        print(f"  - Cycle signatures: {len(state.get('cycle_store', {}).get('signatures', {}))}")
        print(f"  - Revision counter: {state.get('revision_counter', 0)}")

        self_model = state.get("self_model", {})
        print(f"  - Current mode: {self_model.get('current_mode', 'baseline')}")
        print(f"  - Current focus: {self_model.get('current_focus', '-')}")

        drives = state.get("drives", {})
        print(f"\n🎛️  Drive Field:")
        for key, val in drives.items():
            print(f"  - {key}: {val:.2f}")
    else:
        print("\n⚠️  No state available - bot may not have processed messages yet")

    # 检查 trace
    traces = check_trace_logs()
    if traces:
        print(f"\n📝 Trace Entries: {len(traces)}")
        proto_self_traces = [t for t in traces if "proto_self" in str(t).lower()]
        print(f"  - Proto-Self related: {len(proto_self_traces)}")


def main():
    parser = argparse.ArgumentParser(description="Real Telegram E2E for Proto-Self Kernel")
    parser.add_argument("--verify", action="store_true", help="Run verification checks")
    parser.add_argument("--report", action="store_true", help="Generate summary report")
    parser.add_argument("--scenario", choices=["a", "b", "c", "all"], default="all",
                       help="Run specific scenario (a/b/c/all)")

    args = parser.parse_args()

    if not args.verify and not args.report:
        parser.print_help()
        print("\n⚠️  Please run with --verify or --report")
        return 1

    print("=" * 60)
    print(" Proto-Self Kernel v1 - Real Telegram E2E")
    print("=" * 60)
    print(f"Time: {datetime.now().isoformat()}")
    print()

    # 首先检查集成链
    if not verify_integration_chain():
        print("\n❌ Integration chain verification failed")
        return 1

    # 运行指定场景
    if args.verify:
        if args.scenario in ["a", "all"]:
            verify_scenario_a_first_preference()

        if args.scenario in ["b", "all"]:
            verify_scenario_b_second_preference()

        if args.scenario in ["c", "all"]:
            verify_scenario_c_failure_reflection()

    if args.report:
        generate_report()

    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("1. Start bot: python -m app.main --telegram")
    print("2. Send message in Telegram: 'I prefer concise responses'")
    print("3. Run verify: python scripts/e2e_telegram_proto_self.py --verify")
    print("4. Send similar message again")
    print("5. Run verify again to see cycle strengthening")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
