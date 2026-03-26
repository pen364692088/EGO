#!/usr/bin/env python3
"""
Telegram 真实主链验证 v1 - Integration E2E (E3)

目的:
- 在受控环境下复用同一条 runtime 主链
- 让 E3 与 E4 只在传输证据来源上不同，不在主体逻辑上分叉
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from telegram_mainline_common import (
    EGO_ROOT,
    init_runtime,
    run_transport_scenario,
    save_run_report,
    serialize_run_result,
)

ARTIFACTS_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "integration"


async def run_update_contract_check() -> dict:
    runtime = init_runtime()
    from app.openemotion_adapter.event_builder import build_from_telegram_update

    update = {
        "update_id": 99999,
        "message": {
            "message_id": 1,
            "from": {"id": 123456, "is_bot": False, "first_name": "Test", "username": "test_user"},
            "chat": {"id": 123456, "type": "private"},
            "date": int(datetime.now().timestamp()),
            "text": "状态查询",
        },
    }
    event = build_from_telegram_update(update)
    passed = (
        event is not None
        and event.get("source") == "telegram"
        and event.get("event_type") == "user_message"
    )
    return {
        "test_id": "E3-UPDATE-001",
        "test_name": "update_contract",
        "passed": passed,
        "artifact": {
            "raw_update": update,
            "normalized_event": event,
        },
        "what_it_proves": "受控环境中的 Telegram update 契约仍与主链兼容",
        "what_it_does_not_prove": "真实 Telegram 渠道稳定",
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram Integration E2E (E3)")
    parser.add_argument("--session", help="Session ID")
    parser.add_argument("--quick", action="store_true", help="只跑最小场景")
    args = parser.parse_args()

    scenarios = ["你好", "状态查询", "读取文件 test.txt"]
    if args.quick:
        scenarios = scenarios[:1]

    print("\n" + "=" * 70)
    print(" Telegram Real Mainline Validation v1 - Integration E2E (E3)")
    print("=" * 70)
    print("\n[INFO] Evidence Level: E3 (integration)")
    print("[INFO] Allowed: 集成验证通过、具备真实主链验证条件")
    print("[INFO] Forbidden: 正式生效、稳定运行、已接主链")

    results = []
    passed = 0

    try:
        contract_result = await run_update_contract_check()
        results.append(contract_result)
        if contract_result["passed"]:
            passed += 1

        for index, text in enumerate(scenarios, start=1):
            run = await run_transport_scenario(
                text=text,
                artifacts_dir=ARTIFACTS_DIR,
                evidence_level="E3",
                source_type="integration",
                session_id=args.session or f"integration_{index}",
                simulated_delivery=True,
            )
            payload = serialize_run_result(run)
            payload["what_it_proves"] = "受控环境中通过相同 runtime 主链完成输入到输出的闭环"
            payload["what_it_does_not_prove"] = "真实 Telegram 主链稳定"
            results.append(payload)
            print(
                f"  [{'PASS' if run.passed else 'FAIL'}] "
                f"sample={run.sample_id} status={run.status} missing={','.join(run.missing_evidence) or '-'}"
            )
            if run.passed:
                passed += 1
    except RuntimeError as exc:
        print(f"\n[FAIL] {exc}")
        return 2

    report = {
        "run_id": f"integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "evidence_level": "E3",
        "source_type": "integration",
        "channel": "telegram",
        "session_id": args.session or "integration_default",
        "total_tests": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
        "allowed_conclusions": [
            "集成验证通过",
            "具备真实主链验证条件",
            "主链候选可用",
        ],
        "forbidden_conclusions": [
            "已接主链",
            "已启用",
            "正式生效",
            "稳定运行",
        ],
    }

    report_file = ARTIFACTS_DIR / f"report_{report['run_id']}.json"
    save_run_report(report_file, report)

    print("\n" + "=" * 70)
    print(f" Results: {passed}/{len(results)} passed")
    print(f" Report: {report_file}")
    print("=" * 70 + "\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
