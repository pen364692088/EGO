#!/usr/bin/env python3
"""
Telegram Bot API E2E Test Harness - Telegram Outbound Probe (v2)

使用真实 Telegram Bot API 进行 bot 侧 outbound probe。
**它不会生成 user -> bot 的真实 ingress 更新**，因此不能单独作为
`/new` / `restart` / `restore` 这类 O1 直接样本的采集工具。
**只发送消息，不轮询 getUpdates**（避免与 EgoCore 冲突）。
通过本地 artifact 验证结果：
- logs/proto_self_trace.jsonl
- artifacts/proto_self_mirror/state.json
- EgoCore 运行日志

Usage:
    # 发送单条 bot 侧消息，通过本地 artifact 验证
    python scripts/telegram_bot_api_e2e.py --token "YOUR_BOT_TOKEN" --chat-id 123456789 --message "读取文件 /tmp/test.txt"

    # 运行预定义测试套件（仍是 bot 侧 outbound probe）
    python scripts/telegram_bot_api_e2e.py --token "YOUR_BOT_TOKEN" --chat-id 123456789 --suite file_read

    # 验证 Proto-Self cycle（通过本地 state）
    python scripts/telegram_bot_api_e2e.py --token "YOUR_BOT_TOKEN" --chat-id 123456789 --message "读取文件" --verify-cycle

    # 指定等待时间（让 EgoCore 处理 bot 侧消息）
    python scripts/telegram_bot_api_e2e.py --token "YOUR_BOT_TOKEN" --chat-id 123456789 --message "测试" --wait-time 10

Environment:
    也可以从环境变量读取配置：
    - TELEGRAM_BOT_TOKEN: Bot token
    - TELEGRAM_CHAT_ID: Target chat ID

Outputs:
    - bot 侧消息发送状态
    - 本地 artifact 验证结果
    - Proto-Self trace/state 变化
    - Pass/fail verdict

Constraints:
    - 仅使用 Bot API (python-telegram-bot)，不使用 TDLib/Telethon
    - 只能创建 bot -> user 消息，不能替代真实用户入站消息
    - **不轮询 getUpdates**（避免与 EgoCore 冲突）
    - 通过本地 artifact 验证结果
    - 测试逻辑在 harness 层，不侵入主体
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    print("[ERROR] python-telegram-bot not installed. Run: pip install python-telegram-bot")
    sys.exit(1)


class TelegramBotAPIE2E:
    """
    真实 Telegram Bot API outbound probe 工具。

    职责：
    - 使用 Bot API 发送 bot 侧消息
    - 通过本地 artifact 观察处理结果
    - 验证回复内容和格式
    - 检查 Proto-Self trace/state
    """

    def __init__(self, token: str, chat_id: int):
        """Initialize with Bot token and target chat ID."""
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=token)
        self.test_results: List[Dict[str, Any]] = []
        self.session_id = f"e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Local artifact paths
        self.trace_file = Path("logs/proto_self_trace.jsonl")
        self.state_mirror_path = Path("artifacts/proto_self_mirror/state.json")

    async def send_message(self, text: str, wait_time: int = 10) -> Dict[str, Any]:
        """
        发送 bot 侧消息，等待 EgoCore 处理，通过本地 artifact 验证。

        注意：
        - 这不会制造 user -> bot 的真实 Telegram ingress
        - 不能用来证明 `/new` / `restart` / `restore` 的 O1 直接样本

        Args:
            text: 要发送的消息文本
            wait_time: 等待 EgoCore 处理的秒数

        Returns:
            包含发送状态、本地验证结果的字典
        """
        result = {
            "input": text,
            "sent": False,
            "message_id": None,
            "elapsed_seconds": 0,
            "passed": False,
            "errors": [],
            "verification": {}
        }

        print(f"\n[TEST] {text[:80]}")
        start_time = time.time()

        # 记录发送前的状态
        pre_state = self._read_state()
        pre_revision = pre_state.get("revision_counter", 0)
        pre_trace_count = self._count_trace_entries()

        try:
            # 发送消息（不轮询 getUpdates）
            sent_message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=None  # 纯文本，避免格式问题
            )
            result["sent"] = True
            result["message_id"] = sent_message.message_id
            result["sent_at"] = datetime.now().isoformat()
            print(f"[SENT] message_id={sent_message.message_id}")

            # 等待 EgoCore 处理消息
            print(f"[WAIT] Waiting {wait_time}s for EgoCore to process...")
            await asyncio.sleep(wait_time)

            # 通过本地 artifact 验证
            print(f"[VERIFY] Checking local artifacts...")
            verification = self._verify_via_artifacts(text, pre_revision, pre_trace_count)
            result["verification"] = verification

            # 判断是否通过
            result["passed"] = result["sent"] and verification.get("state_changed", False)

            if result["passed"]:
                print(f"[PASS] State changed: revision {pre_revision} -> {verification.get('revision', 0)}")
            else:
                print(f"[WARN] State may not have changed (revision still {pre_revision})")

            result["elapsed_seconds"] = round(time.time() - start_time, 2)

        except TelegramError as e:
            result["errors"].append(f"telegram_error: {e}")
            print(f"[ERROR] Telegram API error: {e}")
        except Exception as e:
            result["errors"].append(f"exception: {e}")
            print(f"[ERROR] {e}")

        self.test_results.append(result)
        return result

    def _read_state(self) -> Dict[str, Any]:
        """读取当前 state mirror。"""
        try:
            if self.state_mirror_path.exists():
                with open(self.state_mirror_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read state: {e}")
        return {}

    def _count_trace_entries(self) -> int:
        """统计 trace 条目数。"""
        try:
            if self.trace_file.exists():
                with open(self.trace_file, 'r', encoding='utf-8') as f:
                    return sum(1 for _ in f)
        except Exception:
            pass
        return 0

    def _verify_via_artifacts(self, input_text: str, pre_revision: int, pre_trace_count: int) -> Dict[str, Any]:
        """通过本地 artifact 验证处理结果。"""
        verification = {
            "pre_revision": pre_revision,
            "post_revision": pre_revision,
            "revision_delta": 0,
            "state_changed": False,
            "trace_added": 0,
            "cycles_found": []
        }

        # 读取当前状态
        state = self._read_state()
        post_revision = state.get("revision_counter", pre_revision)
        verification["post_revision"] = post_revision
        verification["revision_delta"] = post_revision - pre_revision
        verification["state_changed"] = post_revision > pre_revision

        # 统计 trace 变化
        post_trace_count = self._count_trace_entries()
        verification["trace_added"] = post_trace_count - pre_trace_count
        verification["pre_trace_count"] = pre_trace_count
        verification["post_trace_count"] = post_trace_count

        # 检查相关 cycle
        cycles = state.get("cycle_store", {}).get("signatures", {})
        for cycle_id, cycle in cycles.items():
            # 检查是否与输入相关
            psi_bucket = cycle.get("psi_bucket", "")
            if any(kw in input_text.lower() for kw in ["读取", "查看", "检查", "read"]):
                if "file_read" in psi_bucket:
                    verification["cycles_found"].append({
                        "cycle_id": cycle_id,
                        "psi_bucket": psi_bucket,
                        "hits": cycle.get("hits", 0),
                        "strength": cycle.get("strength", 0),
                        "promoted": cycle.get("promoted", False)
                    })

        return verification

    async def _poll_for_reply(self, last_offset: int, timeout: int) -> Optional[Dict[str, Any]]:
        """
        轮询 getUpdates 等待 Bot 回复。

        Args:
            last_offset: 之前最后一条消息的 offset
            timeout: 最大等待时间

        Returns:
            回复消息的字典，或 None 如果超时
        """
        start = time.time()
        check_interval = 1.0  # 每秒检查一次

        while time.time() - start < timeout:
            try:
                # 获取新消息
                updates = await self.bot.get_updates(
                    offset=last_offset + 1,
                    limit=10,
                    timeout=5
                )

                for update in updates:
                    if update.update_id > last_offset:
                        last_offset = update.update_id

                    message = update.message or update.edited_message
                    if not message:
                        continue

                    # 只关注目标 chat 的回复
                    if message.chat.id != self.chat_id:
                        continue

                    # 检查是否是 Bot 的回复（来自 Bot 自己）
                    if message.from_user and message.from_user.is_bot:
                        return {
                            "message_id": message.message_id,
                            "text": message.text or "",
                            "from": {
                                "id": message.from_user.id,
                                "username": message.from_user.username,
                                "is_bot": message.from_user.is_bot
                            },
                            "date": message.date.isoformat() if hasattr(message.date, 'isoformat') else str(message.date)
                        }

            except Exception as e:
                print(f"[WARN] Poll error: {e}")

            await asyncio.sleep(check_interval)

        return None

    async def verify_proto_self_state(self, input_text: str) -> Dict[str, Any]:
        """
        验证 Proto-Self 状态（读取本地 state mirror）。

        注意：这要求 EgoCore 在本地运行并写入 state mirror。
        """
        result = {"passed": False, "checks": {}}

        # 等待一小段时间让 state 写入
        await asyncio.sleep(0.5)

        try:
            if not self.state_mirror_path.exists():
                result["checks"]["state_exists"] = False
                result["errors"] = ["state_mirror_not_found"]
                return result

            with open(self.state_mirror_path, 'r', encoding='utf-8') as f:
                state = json.load(f)

            result["checks"]["state_exists"] = True
            result["checks"]["revision_counter"] = state.get("revision_counter", 0)

            # 检查 cycles
            cycles = state.get("cycle_store", {}).get("signatures", {})
            result["checks"]["cycle_count"] = len(cycles)

            # 检查 trace
            trace_count = 0
            if self.trace_file.exists():
                with open(self.trace_file, 'r', encoding='utf-8') as f:
                    trace_count = sum(1 for _ in f)
            result["checks"]["trace_entries"] = trace_count

            # 基础通过条件
            result["passed"] = result["checks"]["state_exists"] and result["checks"]["revision_counter"] > 0

        except Exception as e:
            result["checks"]["error"] = str(e)

        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get test run summary."""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.get("passed", False))
        failed = total - passed

        total_time = sum(r.get("elapsed_seconds", 0) for r in self.test_results)

        return {
            "session_id": self.session_id,
            "chat_id": self.chat_id,
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "total_time_seconds": round(total_time, 2),
            "timestamp": datetime.now().isoformat()
        }

    def print_summary(self) -> None:
        """Print test summary."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("Telegram Bot API E2E Test Summary")
        print("=" * 60)
        print(f"Session ID: {summary['session_id']}")
        print(f"Chat ID: {summary['chat_id']}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Pass Rate: {summary['pass_rate']:.1%}")
        print(f"Total Time: {summary['total_time_seconds']}s")
        print("=" * 60)


# 预定义测试套件
TEST_SUITES = {
    "file_read": {
        "name": "File Read Test Suite",
        "description": "测试文件读取场景",
        "tests": [
            {"text": "[E2E] 读取文件 /tmp/e2e_test_hello.txt", "expected_contains": None},
        ]
    },
    "external_failure": {
        "name": "External Failure Reflection Suite",
        "description": "测试外部失败触发 reflection",
        "tests": [
            {"text": "[E2E] 读取不存在的文件 /tmp/e2e_not_exist_xyz.txt", "expected_contains": None},
        ]
    },
    "cycle_strengthen": {
        "name": "Cycle Strengthen Suite",
        "description": "测试 cycle strengthen（需要连续发送相似消息）",
        "tests": [
            {"text": "[E2E-CYCLE-1] 查看文件 /tmp/e2e_cycle_test.txt", "expected_contains": None},
            {"text": "[E2E-CYCLE-2] 检查文件 /tmp/e2e_cycle_test.txt", "expected_contains": None},
            {"text": "[E2E-CYCLE-3] 读取文件 /tmp/e2e_cycle_test.txt", "expected_contains": None},
        ]
    },
    "smoke": {
        "name": "Smoke Test Suite",
        "description": "基础冒烟测试",
        "tests": [
            {"text": "[E2E-SMOKE] 状态查询", "expected_contains": None},
            {"text": "[E2E-SMOKE] 帮助", "expected_contains": None},
        ]
    }
}


async def run_single_message(args) -> int:
    """Run single message test."""
    harness = TelegramBotAPIE2E(token=args.token, chat_id=args.chat_id)

    result = await harness.send_message(args.message, wait_time=args.wait_time)

    # 如果请求验证 Proto-Self
    if args.verify_cycle:
        print("[VERIFY] Checking Proto-Self state...")
        verification = await harness.verify_proto_self_state(args.message)
        result["proto_self_verification"] = verification
        print(f"[VERIFY] State exists: {verification['checks'].get('state_exists', False)}")
        print(f"[VERIFY] Revision counter: {verification['checks'].get('revision_counter', 0)}")
        print(f"[VERIFY] Cycles: {verification['checks'].get('cycle_count', 0)}")

    harness.print_summary()

    return 0 if result.get("passed", False) else 1


async def run_suite(args) -> int:
    """Run predefined test suite."""
    suite_name = args.suite
    if suite_name not in TEST_SUITES:
        print(f"[ERROR] Unknown suite: {suite_name}")
        print(f"Available suites: {', '.join(TEST_SUITES.keys())}")
        return 1

    suite = TEST_SUITES[suite_name]
    harness = TelegramBotAPIE2E(token=args.token, chat_id=args.chat_id)

    print(f"\n[Suite] {suite['name']}")
    print(f"[Suite] {suite['description']}")
    print(f"[Suite] {len(suite['tests'])} test(s)")

    for i, test in enumerate(suite['tests'], 1):
        text = test['text']
        expected = test.get('expected_contains')

        print(f"\n[Test {i}/{len(suite['tests'])}]")
        result = await harness.send_message(text, wait_time=args.wait_time)

        if expected and expected not in (result.get('reply') or ''):
            result['passed'] = False
            result['errors'].append(f"expected_content_missing: {expected}")

        # 套件间间隔，避免 rate limit
        if i < len(suite['tests']):
            await asyncio.sleep(2)

    harness.print_summary()
    return 0 if harness.get_summary()['failed'] == 0 else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Telegram Bot API outbound probe harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 单条消息测试
    %(prog)s --token "YOUR_BOT_TOKEN" --chat-id 123456789 --message "读取文件 /tmp/test.txt"

    # 使用环境变量
    export TELEGRAM_BOT_TOKEN="your_token"
    export TELEGRAM_CHAT_ID="123456789"
    %(prog)s --message "状态查询"

    # 运行测试套件
    %(prog)s --token "YOUR_BOT_TOKEN" --chat-id 123456789 --suite file_read

    # 验证 Proto-Self cycle
    %(prog)s --message "读取文件" --verify-cycle

Available Suites:
    file_read       - 文件读取测试
    external_failure - 外部失败 reflection 测试
    cycle_strengthen - Cycle strengthen 测试（发送3条相似消息）
    smoke           - 基础冒烟测试
        """
    )

    parser.add_argument("--token", "-t",
                        default=os.environ.get("TELEGRAM_BOT_TOKEN"),
                        help="Telegram Bot Token (or env: TELEGRAM_BOT_TOKEN)")
    parser.add_argument("--chat-id", "-c", type=int,
                        default=int(os.environ.get("TELEGRAM_CHAT_ID", 0)) if os.environ.get("TELEGRAM_CHAT_ID") else None,
                        help="Target Chat ID (or env: TELEGRAM_CHAT_ID)")
    parser.add_argument("--message", "-m", help="Single message to send")
    parser.add_argument("--suite", "-s", choices=list(TEST_SUITES.keys()),
                        help="Run predefined test suite")
    parser.add_argument("--wait-time", "-w", type=int, default=10,
                        help="Wait time for EgoCore to process (default: 10)")
    parser.add_argument("--verify-cycle", "-v", action="store_true",
                        help="Verify Proto-Self cycle state after test")

    args = parser.parse_args()

    # Validate required arguments
    if not args.token:
        parser.error("请提供 --token 或设置 TELEGRAM_BOT_TOKEN 环境变量")
    if not args.chat_id:
        parser.error("请提供 --chat-id 或设置 TELEGRAM_CHAT_ID 环境变量")

    # Validate mode
    if not args.message and not args.suite:
        parser.error("请指定 --message 或 --suite")

    # Run appropriate mode
    print("[INFO] This harness sends bot-side outbound messages only.")
    print("[INFO] It cannot create user->bot ingress updates for O1 direct sample capture.")

    if args.suite:
        return asyncio.run(run_suite(args))
    else:
        return asyncio.run(run_single_message(args))


if __name__ == "__main__":
    sys.exit(main())
