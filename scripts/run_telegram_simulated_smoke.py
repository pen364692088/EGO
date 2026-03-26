#!/usr/bin/env python3
"""
Telegram 真实主链验证 v1 - Simulated Smoke (E2)

目的:
- 复用与真实 Telegram 一致的 runtime 主链和证据采集结构
- 只替换传输层，不替换主体逻辑
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime

from telegram_mainline_common import (
    EGO_ROOT,
    run_transport_scenario,
    save_run_report,
    serialize_run_result,
)

ARTIFACTS_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "simulated"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram Simulated Smoke (E2)")
    parser.add_argument("--quick", action="store_true", help="只跑最小场景")
    args = parser.parse_args()

    scenarios = [
        "你好",
        "读取文件 test.txt",
        "我现在要做一个高风险文件改动，你第一步会怎么做？",
    ]
    if args.quick:
        scenarios = scenarios[:1]

    print("\n" + "=" * 70)
    print(" Telegram Real Mainline Validation v1 - Simulated Smoke (E2)")
    print("=" * 70)
    print("\n[INFO] Evidence Level: E2 (simulated)")
    print("[INFO] Allowed: 模拟验证通过、脚本级通过")
    print("[INFO] Forbidden: 已接主链、已启用、已生效")

    results = []
    passed = 0
    try:
        for index, text in enumerate(scenarios, start=1):
            run = await run_transport_scenario(
                text=text,
                artifacts_dir=ARTIFACTS_DIR,
                evidence_level="E2",
                source_type="simulated",
                session_id=f"simulated_smoke_{index}",
                simulated_delivery=True,
            )
            results.append(serialize_run_result(run))
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
        "run_id": f"simulated_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "evidence_level": "E2",
        "source_type": "simulated",
        "channel": "telegram",
        "total_tests": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
        "allowed_conclusions": [
            "模拟验证通过",
            "脚本级通过",
            "具备真实链路回归价值",
        ],
        "forbidden_conclusions": [
            "已接主链",
            "已启用",
            "已生效",
            "verified_mainline_e2e",
        ],
    }

    report_file = ARTIFACTS_DIR / f"smoke_{report['run_id']}.json"
    save_run_report(report_file, report)

    print("\n" + "=" * 70)
    print(f" Results: {passed}/{len(results)} passed")
    print(f" Report: {report_file}")
    print("=" * 70 + "\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
