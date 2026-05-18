"""
Proto-Self Kernel v1 Diagnostics

只读诊断脚本：用户无需深入源码即可查看关键状态。

功能：
- 显示 identity 状态
- 显示 self_model 状态
- 显示 drive_field 状态
- 显示 cycle_store 状态
- 显示 revision_counter
- 显示最近事件
- 显示已知风险警告

设计约束：
- 只读，不修改任何状态
- 不越权执行现实动作
- 输出格式人类可读
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# 诊断输出格式化
# ============================================================================

def print_header(title: str):
    print(f"\n{'=' * 50}")
    print(f" {title}")
    print('=' * 50)


def print_section(title: str):
    print(f"\n[{title}]")


def print_kv(key: str, value: Any, indent: int = 0):
    prefix = "  " * indent + "- " if indent else "- "
    if isinstance(value, float):
        print(f"{prefix}{key}: {value:.4f}")
    elif isinstance(value, list) and len(value) == 0:
        print(f"{prefix}{key}: []")
    elif isinstance(value, dict) and len(value) == 0:
        print(f"{prefix}{key}: {{}}")
    else:
        print(f"{prefix}{key}: {value}")


# ============================================================================
# 诊断函数
# ============================================================================

def diagnose_state_file(state_path: Optional[Path] = None) -> Dict[str, Any]:
    """诊断状态文件"""
    if state_path is None:
        # 默认路径
        state_path = Path(__file__).parent.parent.parent / "EgoCore" / "artifacts" / "proto_self_v1" / "state.json"

    result = {
        "state_file_exists": False,
        "state": None,
        "warnings": [],
    }

    if not state_path.exists():
        result["warnings"].append(f"状态文件不存在: {state_path}")
        return result

    result["state_file_exists"] = True

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
        result["state"] = state_data
    except Exception as e:
        result["warnings"].append(f"读取状态文件失败: {e}")

    return result


def diagnose_trace_file(trace_path: Optional[Path] = None) -> Dict[str, Any]:
    """诊断 trace 文件"""
    if trace_path is None:
        trace_path = Path(__file__).parent.parent.parent / "EgoCore" / "artifacts" / "proto_self_v1" / "trace.jsonl"

    result = {
        "trace_file_exists": False,
        "recent_events": [],
        "warnings": [],
    }

    if not trace_path.exists():
        result["warnings"].append(f"Trace 文件不存在: {trace_path}")
        return result

    result["trace_file_exists"] = True

    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-10:]  # 最近 10 条

        for line in lines:
            if line.strip():
                trace_entry = json.loads(line)
                result["recent_events"].append(trace_entry)
    except Exception as e:
        result["warnings"].append(f"读取 trace 文件失败: {e}")

    return result


def check_known_risks(state: Optional[Dict], trace: List[Dict]) -> List[Dict]:
    """检查已知风险"""
    risks = []

    if state is None:
        return risks

    cycle_store = state.get("cycle_store", {}).get("signatures", {})

    # 检查高风险 cycle 聚合
    for cycle_id, cycle in cycle_store.items():
        psi_bucket = cycle.get("psi_bucket", "")

        # 高风险操作 cycle
        if "file_risk_op" in psi_bucket:
            risks.append({
                "level": "HIGH",
                "type": "高风险操作聚合",
                "cycle_id": cycle_id,
                "psi_bucket": psi_bucket,
                "message": "删除类操作被聚合，可能无法区分临时文件和生产数据库",
            })

        # 检查 strength 过高
        if cycle.get("strength", 0) > 0.8:
            risks.append({
                "level": "MEDIUM",
                "type": "Cycle 强度过高",
                "cycle_id": cycle_id,
                "strength": cycle.get("strength"),
                "message": f"Cycle 强度达到 {cycle.get('strength'):.2f}，可能影响行为偏向",
            })

    # 检查 revision_counter
    revision_counter = state.get("revision_counter", 0)
    if revision_counter > 5:
        risks.append({
            "level": "LOW",
            "type": "Revision 计数较高",
            "revision_counter": revision_counter,
            "message": f"Revision counter = {revision_counter}，表示系统经历过多次失败",
        })

    return risks


def print_diagnostics(state_result: Dict, trace_result: Dict):
    """打印诊断结果"""
    print_header("Proto-Self Kernel v1 Diagnostics")
    print(f"\n时间: {datetime.now().isoformat()}")

    state = state_result.get("state")
    warnings = state_result.get("warnings", []) + trace_result.get("warnings", [])

    # 打印警告
    if warnings:
        print_section("Warnings")
        for w in warnings:
            print(f"  ⚠️ {w}")

    if state is None:
        print("\n❌ 无法读取状态，请检查 EgoCore 是否运行")
        return

    # Identity
    print_section("Identity")
    identity = state.get("identity", {})
    print_kv("confidence", identity.get("identity_confidence", 0.5))
    print_kv("roles", identity.get("core_roles", []))
    print_kv("commitments", identity.get("core_commitments", []))
    print_kv("boundaries", identity.get("core_boundaries", []))

    # Self Model
    print_section("Self Model")
    self_model = state.get("self_model", {})
    print_kv("current_mode", self_model.get("current_mode", "baseline"))
    print_kv("current_focus", self_model.get("current_focus"))
    print_kv("capabilities", self_model.get("capabilities", {}))

    # Drives
    print_section("Drives")
    drives = state.get("drives", {})
    print_kv("caution", drives.get("caution", 0.0))
    print_kv("curiosity", drives.get("curiosity", 0.0))
    print_kv("coherence_pressure", drives.get("coherence_pressure", 0.0))
    print_kv("completion_pressure", drives.get("completion_pressure", 0.0))

    # Cycle Store
    print_section("Cycles")
    cycle_store = state.get("cycle_store", {}).get("signatures", {})
    print_kv("total", len(cycle_store))

    for cycle_id, cycle in list(cycle_store.items())[:5]:  # 只显示前 5 个
        print(f"\n  cycle_{cycle_id[:16]}:")
        print_kv("psi_bucket", cycle.get("psi_bucket", ""), indent=2)
        print_kv("hits", cycle.get("hits", 0), indent=2)
        print_kv("strength", cycle.get("strength", 0.0), indent=2)
        print_kv("promoted", cycle.get("promoted", False), indent=2)

    # Revision Counter
    print_section("Revision Counter")
    print_kv("count", state.get("revision_counter", 0))

    # Recent Events
    print_section("Recent Events")
    recent_events = trace_result.get("recent_events", [])
    print_kv("count", len(recent_events))

    for event in recent_events[-5:]:  # 只显示最近 5 条
        event_id = event.get("event_id", "unknown")
        cycle_delta = event.get("trace_payload", {}).get("cycle_delta", {})
        cycle_id = cycle_delta.get("cycle_id", "N/A")
        op = cycle_delta.get("op", "N/A")
        print(f"  - {event_id}: cycle={cycle_id[:12] if cycle_id else 'N/A'}..., op={op}")

    # 已知风险检查
    risks = check_known_risks(state, trace_result.get("recent_events", []))
    if risks:
        print_section("Known Risks")
        for risk in risks:
            level_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk["level"], "⚪")
            print(f"  {level_icon} [{risk['level']}] {risk['type']}")
            print(f"      {risk['message']}")

    # 总结
    print_header("Summary")
    print_kv("状态文件", "✅ 存在" if state_result.get("state_file_exists") else "❌ 不存在")
    print_kv("Trace 文件", "✅ 存在" if trace_result.get("trace_file_exists") else "❌ 不存在")
    print_kv("Cycle 数量", len(cycle_store))
    print_kv("Revision Counter", state.get("revision_counter", 0))
    print_kv("已知风险", f"{len(risks)} 个")


def diagnose_mock_state():
    """使用 mock 状态进行诊断演示"""
    # 创建 mock 状态
    mock_state = {
        "identity": {
            "identity_confidence": 0.5,
            "core_roles": ["assistant"],
            "core_commitments": ["帮助用户"],
            "core_boundaries": ["不执行危险操作"],
        },
        "self_model": {
            "current_mode": "baseline",
            "current_focus": None,
            "capabilities": {"coding": 0.8},
        },
        "drives": {
            "caution": 0.0,
            "curiosity": 0.1,
            "coherence_pressure": 0.0,
            "completion_pressure": 0.0,
        },
        "cycle_store": {
            "signatures": {
                "30aa24ef0787e022": {
                    "cycle_id": "30aa24ef0787e022",
                    "psi_bucket": "telegram:user_message:file_read",
                    "phi_signature": "neutral",
                    "strength": 0.25,
                    "hits": 3,
                    "last_seen_ts": datetime.now().isoformat(),
                    "promoted": False,
                },
                "98bd0a1ae1b14728": {
                    "cycle_id": "98bd0a1ae1b14728",
                    "psi_bucket": "telegram:user_message:file_risk_op",
                    "phi_signature": "caution:+0.2",
                    "strength": 0.15,
                    "hits": 2,
                    "last_seen_ts": datetime.now().isoformat(),
                    "promoted": False,
                },
            }
        },
        "episodic_trace": [],
        "revision_counter": 0,
    }

    mock_trace = [
        {
            "event_id": "evt-001",
            "timestamp": datetime.now().isoformat(),
            "trace_payload": {
                "cycle_delta": {"cycle_id": "30aa24ef0787e022", "op": "strengthen"}
            }
        },
        {
            "event_id": "evt-002",
            "timestamp": datetime.now().isoformat(),
            "trace_payload": {
                "cycle_delta": {"cycle_id": "30aa24ef0787e022", "op": "strengthen"}
            }
        },
        {
            "event_id": "evt-003",
            "timestamp": datetime.now().isoformat(),
            "trace_payload": {
                "cycle_delta": {"cycle_id": "98bd0a1ae1b14728", "op": "candidate"}
            }
        },
    ]

    state_result = {
        "state_file_exists": True,
        "state": mock_state,
        "warnings": ["[演示模式] 使用 mock 状态数据"],
    }

    trace_result = {
        "trace_file_exists": True,
        "recent_events": mock_trace,
        "warnings": ["[演示模式] 使用 mock trace 数据"],
    }

    return state_result, trace_result


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Proto-Self Kernel v1 Diagnostics")
    parser.add_argument("--mock", action="store_true", help="使用 mock 状态演示")
    parser.add_argument("--state-file", type=str, help="状态文件路径")
    parser.add_argument("--trace-file", type=str, help="Trace 文件路径")
    args = parser.parse_args()

    print("=" * 60)
    print(" Proto-Self Kernel v1 Diagnostics")
    print(" 只读诊断工具 - 不修改任何状态")
    print("=" * 60)

    if args.mock:
        state_result, trace_result = diagnose_mock_state()
    else:
        state_path = Path(args.state_file) if args.state_file else None
        trace_path = Path(args.trace_file) if args.trace_file else None

        state_result = diagnose_state_file(state_path)
        trace_result = diagnose_trace_file(trace_path)

    print_diagnostics(state_result, trace_result)

    # 返回退出码
    if state_result.get("state") is None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
