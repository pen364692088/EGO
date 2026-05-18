#!/usr/bin/env python3
"""
Telegram Simulator Harness - Local E2E Testing without Telegram Network

模拟 Telegram 消息入口，用于本地测试 EgoCore Runtime 主链。
无需真实 Telegram 网络连接，直接调用 RuntimeV2Loop。

Usage:
    # 单条消息测试
    python scripts/telegram_sim_harness.py --message "读取文件 /tmp/test.txt"

    # 批量测试（场景文件）
    python scripts/telegram_sim_harness.py --scenario scripts/test_scenarios/file_read.json

    # 交互模式
    python scripts/telegram_sim_harness.py --interactive

    # 指定 session id
    python scripts/telegram_sim_harness.py --message "状态查询" --session test_session_001

    # 验证 Proto-Self cycle
    python scripts/telegram_sim_harness.py --message "读取文件 /tmp/test.txt" --verify-cycle

Outputs:
    - Bot reply text
    - Trace artifact (logs/telegram_sim_trace.jsonl)
    - State mirror diff (artifacts/proto_self_mirror/state.json)
    - Pass/fail result

Constraints:
    - 复用现有 Telegram/runtime 主链 (RuntimeV2Loop)
    - 测试逻辑不塞进主体本体
    - 不破坏双核边界
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add OpenEmotion to path for proto_self imports
OPENEMOTION_PATH = Path(__file__).parent.parent.parent / "OpenEmotion"
if OPENEMOTION_PATH.exists():
    sys.path.insert(0, str(OPENEMOTION_PATH))

from app.config import load_config, get_config
from app.logger import init_logging

# Runtime v2 imports
from app.runtime_v2 import RuntimeV2Loop, RuntimeV2TelegramBridge

# Import adapter to force initialization
try:
    from app.openemotion_adapter import ProtoSelfAdapter
except ImportError:
    ProtoSelfAdapter = None


class TelegramSimulator:
    """
    模拟 Telegram 消息的本地测试工具。

    职责：
    - 模拟 Telegram update 结构
    - 调用 RuntimeV2Loop 处理消息
    - 收集输出和 trace
    - 验证预期结果
    """

    def __init__(self, session_id: Optional[str] = None):
        """Initialize simulator with optional session ID."""
        self.session_id = session_id or f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.loop: Optional[RuntimeV2Loop] = None
        self.bridge = RuntimeV2TelegramBridge()
        self.trace: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []

        # Artifacts paths
        self.trace_file = Path("logs/telegram_sim_trace.jsonl")
        self.state_mirror_path = Path("artifacts/proto_self_mirror/state.json")

        # Ensure directories exist
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_mirror_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> bool:
        """Initialize runtime components."""
        try:
            # Load config first - must use get_config() to set global config
            from app.config import load_config, get_config
            load_config()  # This loads and caches the config
            config = get_config()  # Get the cached config
            init_logging(config.get('app.logging', {}))

            # Force re-check of Proto-Self enabled status
            from app.runtime_v2.loop import _PROTO_SELF_ENABLED
            import app.runtime_v2.loop as loop_module
            if hasattr(loop_module, '_PROTO_SELF_ENABLED'):
                loop_module._PROTO_SELF_ENABLED = None  # Reset to force recheck

            # Initialize RuntimeV2Loop (this creates Proto-Self adapter if enabled)
            self.loop = RuntimeV2Loop()

            # Force status display
            proto_self_enabled = self.loop.proto_self_adapter is not None
            print(f"[INIT] Simulator initialized")
            print(f"[INIT] Session ID: {self.session_id}")
            print(f"[INIT] Proto-Self enabled: {proto_self_enabled}")

            # Debug info
            if proto_self_enabled:
                print(f"[INIT] Mirror dir: {self.loop.proto_self_adapter.mirror_dir}")

            return True
        except Exception as e:
            print(f"[ERROR] Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _build_simulated_update(self, text: str, user_id: int = 12345, chat_id: int = 67890) -> Dict[str, Any]:
        """
        构建模拟的 Telegram update 结构。

        保持与真实 Telegram update 兼容的字段，方便测试逻辑复用。
        """
        message_id = int(datetime.now().timestamp() * 1000) % 1000000

        return {
            "update_id": message_id,
            "message": {
                "message_id": message_id,
                "from": {
                    "id": user_id,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "test_user"
                },
                "chat": {
                    "id": chat_id,
                    "first_name": "Test",
                    "type": "private"
                },
                "date": int(datetime.now().timestamp()),
                "text": text
            },
            "_simulated": True,
            "_simulated_at": datetime.now().isoformat()
        }

    async def send_message(self, text: str, verify_cycle: bool = False) -> Dict[str, Any]:
        """
        发送模拟消息并获取回复。

        Args:
            text: 用户消息文本
            verify_cycle: 是否验证 Proto-Self cycle 状态

        Returns:
            包含回复文本、状态、trace 的结果字典
        """
        if not self.loop:
            raise RuntimeError("Simulator not initialized. Call initialize() first.")

        update = self._build_simulated_update(text)
        timestamp = datetime.now().isoformat()

        print(f"\n[INPUT] {text[:80]}")

        # Record pre-state for diff
        pre_state = self._capture_state()

        try:
            # Process through RuntimeV2Loop (same as real Telegram path)
            result = await self.loop.run_turn_typed(
                session_id=self.session_id,
                user_input=text
            )

            # Capture output
            reply_text = result.reply_text or ""
            status = result.status

            # Record trace
            trace_entry = {
                "timestamp": timestamp,
                "session_id": self.session_id,
                "update_id": update["update_id"],
                "input_text": text,
                "reply_text": reply_text,
                "status": status,
                "task_status": result.state.task_status if result.state else None
            }
            self.trace.append(trace_entry)
            self._write_trace(trace_entry)

            # Build result
            test_result = {
                "input": text,
                "reply": reply_text,
                "status": status,
                "passed": True,
                "errors": []
            }

            # Verify cycle if requested
            if verify_cycle and self.loop.proto_self_adapter:
                cycle_check = self._verify_cycle_state(text)
                test_result["cycle_verification"] = cycle_check
                if not cycle_check.get("passed", False):
                    test_result["passed"] = False
                    test_result["errors"].append("cycle_verification_failed")

            self.results.append(test_result)

            print(f"[REPLY] {reply_text[:120] if reply_text else '(no reply)'}")
            print(f"[STATUS] {status}")

            return test_result

        except Exception as e:
            error_result = {
                "input": text,
                "reply": "",
                "status": "error",
                "passed": False,
                "errors": [str(e)]
            }
            self.results.append(error_result)

            print(f"[ERROR] {e}")
            return error_result

    def _capture_state(self) -> Dict[str, Any]:
        """Capture current Proto-Self state for diff."""
        if not self.loop or not self.loop.proto_self_adapter:
            return {}

        try:
            # Read state mirror if exists
            if self.state_mirror_path.exists():
                with open(self.state_mirror_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _verify_cycle_state(self, input_text: str) -> Dict[str, Any]:
        """Verify Proto-Self cycle state for input."""
        result = {"passed": False, "checks": {}}

        try:
            state = self._capture_state()
            cycles = state.get("cycle_store", {}).get("signatures", {})

            # Check if any cycle exists
            result["checks"]["has_cycles"] = len(cycles) > 0
            result["checks"]["cycle_count"] = len(cycles)

            # Look for relevant cycle based on input
            intent = self._classify_intent(input_text)
            psi_bucket = f"telegram:user_message:{intent}"

            found_cycle = None
            for cycle_id, cycle in cycles.items():
                if cycle.get("psi_bucket") == psi_bucket:
                    found_cycle = cycle
                    break

            result["checks"]["target_intent"] = intent
            result["checks"]["target_psi_bucket"] = psi_bucket
            result["checks"]["found_matching_cycle"] = found_cycle is not None

            if found_cycle:
                result["checks"]["cycle_hits"] = found_cycle.get("hits", 0)
                result["checks"]["cycle_strength"] = found_cycle.get("strength", 0.0)
                result["checks"]["cycle_promoted"] = found_cycle.get("promoted", False)

            # Overall pass if we have cycles and found matching
            result["passed"] = len(cycles) > 0 and (found_cycle is not None or intent == "general")

        except Exception as e:
            result["checks"]["error"] = str(e)

        return result

    def _classify_intent(self, text: str) -> str:
        """Simple intent classification for verification."""
        text_lower = text.lower()

        if any(p in text_lower for p in ["删除", "删掉", "delet", "remove", "清空", "truncate", "修改", "替换", "覆盖"]):
            return "file_risk_op"
        if any(p in text_lower for p in ["读取", "查看", "检查", "read", "cat ", "head ", "tail "]):
            return "file_read"
        if any(p in text_lower for p in ["状态", "status", "进度", "progress", "情况"]):
            return "status_query"
        if any(p in text_lower for p in ["启动", "停止", "重启", "start", "stop", "restart", "service"]):
            return "service_control"
        if any(p in text_lower for p in ["测试", "验证", "test", "verify", "check"]):
            return "test_verify"
        return "general"

    def _write_trace(self, entry: Dict[str, Any]) -> None:
        """Write trace entry to file."""
        try:
            with open(self.trace_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[WARN] Failed to write trace: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get test run summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("passed", False))
        failed = total - passed

        return {
            "session_id": self.session_id,
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "trace_file": str(self.trace_file),
            "state_mirror": str(self.state_mirror_path) if self.state_mirror_path.exists() else None
        }

    def print_summary(self) -> None:
        """Print test summary."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("Telegram Simulator Test Summary")
        print("=" * 60)
        print(f"Session ID: {summary['session_id']}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Pass Rate: {summary['pass_rate']:.1%}")
        print(f"Trace File: {summary['trace_file']}")
        print(f"State Mirror: {summary['state_mirror'] or 'Not available'}")
        print("=" * 60)


async def run_single_message(args) -> int:
    """Run single message test."""
    sim = TelegramSimulator(session_id=args.session)

    if not await sim.initialize():
        return 1

    result = await sim.send_message(args.message, verify_cycle=args.verify_cycle)
    sim.print_summary()

    return 0 if result.get("passed", False) else 1


async def run_interactive(args) -> int:
    """Run interactive mode."""
    sim = TelegramSimulator(session_id=args.session)

    if not await sim.initialize():
        return 1

    print("\n" + "=" * 60)
    print("Telegram Simulator - Interactive Mode")
    print("=" * 60)
    print("Commands:")
    print("  :quit, :q  - Exit simulator")
    print("  :status    - Show session status")
    print("  :reset     - Reset session")
    print("  :summary   - Show test summary")
    print("=" * 60)

    while True:
        try:
            text = input("\n[You] ").strip()

            if text in [":quit", ":q"]:
                break
            if text == ":status":
                print(f"Session: {sim.session_id}")
                print(f"Tests run: {len(sim.results)}")
                continue
            if text == ":reset":
                sim.loop.reset_session(sim.session_id)
                print("Session reset")
                continue
            if text == ":summary":
                sim.print_summary()
                continue
            if not text:
                continue

            await sim.send_message(text, verify_cycle=args.verify_cycle)

        except KeyboardInterrupt:
            break
        except EOFError:
            break

    sim.print_summary()
    return 0


async def run_scenario(args) -> int:
    """Run scenario file."""
    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        print(f"[ERROR] Scenario file not found: {scenario_path}")
        return 1

    try:
        with open(scenario_path, 'r', encoding='utf-8') as f:
            scenario = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in scenario file: {e}")
        return 1

    session_id = scenario.get("session_id") or args.session
    sim = TelegramSimulator(session_id=session_id)

    if not await sim.initialize():
        return 1

    print(f"\n[SCENARIO] {scenario.get('name', 'Unnamed')}")
    print(f"[SCENARIO] {scenario.get('description', '')}")

    messages = scenario.get("messages", [])
    for i, msg in enumerate(messages, 1):
        text = msg.get("text", "")
        expected = msg.get("expected_contains")

        print(f"\n[STEP {i}/{len(messages)}] {text[:60]}")

        result = await sim.send_message(text, verify_cycle=args.verify_cycle)

        # Check expected content
        if expected and expected not in result.get("reply", ""):
            print(f"[WARN] Expected '{expected}' not in reply")
            result["passed"] = False
            result["errors"].append(f"expected_content_missing: {expected}")

    sim.print_summary()
    return 0 if sim.get_summary()["failed"] == 0 else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Telegram Simulator Harness - Local E2E Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 单条消息测试
    %(prog)s --message "读取文件 /tmp/test.txt"

    # 验证 Proto-Self cycle
    %(prog)s --message "读取文件 /tmp/test.txt" --verify-cycle

    # 交互模式
    %(prog)s --interactive

    # 批量场景测试
    %(prog)s --scenario scripts/test_scenarios/file_read.json
        """
    )

    parser.add_argument("--message", "-m", help="Single message to send")
    parser.add_argument("--session", "-s", help="Session ID (default: auto-generated)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--scenario", help="Scenario JSON file to run")
    parser.add_argument("--verify-cycle", "-v", action="store_true",
                        help="Verify Proto-Self cycle state after each message")

    args = parser.parse_args()

    # Validate arguments
    if sum([bool(args.message), args.interactive, bool(args.scenario)]) != 1:
        parser.error("请指定以下之一: --message, --interactive, 或 --scenario")

    # Run appropriate mode
    if args.message:
        return asyncio.run(run_single_message(args))
    elif args.interactive:
        return asyncio.run(run_interactive(args))
    elif args.scenario:
        return asyncio.run(run_scenario(args))

    return 1


if __name__ == "__main__":
    sys.exit(main())
