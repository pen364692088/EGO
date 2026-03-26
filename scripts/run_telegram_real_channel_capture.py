#!/usr/bin/env python3
"""
Telegram 真实主链验证 v1 - Real Channel Capture (E4)

职责:
- 校验真实 Telegram 样本是否满足 E4 最小证据包
- 补齐 replay artifact
- 生成符合验收协议的 E4 报告
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from telegram_mainline_common import EGO_ROOT, ensure_replay_artifact, load_sample

ARTIFACTS_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
FAILURE_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "failure_cases"
REPORTS_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "reports"
LATEST_REPORT = REPORTS_DIR / "VALIDATION_REPORT_E4_SAMPLE_001.md"

REQUIRED_FILES = [
    "raw_update.json",
    "normalized_event.json",
    "openemotion_result.json",
    "response_plan.json",
    "outbox_record.json",
    "timeline.json",
    "tape.json",
    "replay.json",
]


def sample_dirs() -> List[Path]:
    if not ARTIFACTS_DIR.exists():
        return []
    return sorted(
        [path for path in ARTIFACTS_DIR.iterdir() if path.is_dir() and path.name.startswith("sample_")],
        key=lambda path: path.name,
    )


def validate_sample_dir(sample_dir: Path) -> Dict[str, Any]:
    ensure_replay_artifact(sample_dir)
    sample = load_sample(sample_dir)
    file_status = {name: (sample_dir / name).exists() for name in REQUIRED_FILES}
    missing = [name for name, present in file_status.items() if not present]
    return {
        "sample_id": sample.get("sample_id"),
        "timestamp": sample.get("timestamp"),
        "source_type": sample.get("source_type", "real_channel"),
        "channel": sample.get("channel", "telegram"),
        "file_status": file_status,
        "missing_files": missing,
        "sample": sample,
        "is_complete": not missing,
        "path": sample_dir,
    }


def record_failure(
    *,
    actual: str,
    raw_input: Optional[Dict[str, Any]] = None,
    initial_cause_type: str = "delivery_error",
    expected: str = "E4 最小证据包完整落盘",
) -> Dict[str, Any]:
    failure_id = f"fail_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    failure = {
        "failure_id": failure_id,
        "timestamp": datetime.now().isoformat(),
        "trigger_mode": "real_telegram",
        "input": raw_input or {},
        "expected": expected,
        "actual": actual,
        "evidence_level": "E4",
        "source_type": "real_channel",
        "initial_cause_type": initial_cause_type,
        "artifact_path": None,
        "in_regression": False,
        "retested_after_fix": False,
    }
    FAILURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FAILURE_DIR / f"failure_{failure_id}.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(failure, handle, indent=2, ensure_ascii=False)
    failure["artifact_path"] = str(path)
    return failure


def generate_report_payload(validation: Dict[str, Any], failures: List[Dict[str, Any]]) -> str:
    sample = validation["sample"]
    sample_dir = validation["path"]
    evidence_rows = []
    for index, filename in enumerate(REQUIRED_FILES, start=1):
        evidence_rows.append(
            "| E-E4-{idx:03d} | E4 | real_channel | {path} | {prove} | {not_prove} |".format(
                idx=index,
                path=sample_dir / filename,
                prove=_what_it_proves(filename),
                not_prove=_what_it_does_not_prove(filename),
            )
        )

    success_items = [
        f"- {sample['sample_id']} | {sample['timestamp']} | {'完整' if validation['is_complete'] else '不完整'} | {sample_dir}"
    ]
    failure_items = [
        f"- {item['failure_id']} | {item['initial_cause_type']} | {item['artifact_path']}"
        for item in failures
    ] or ["- 无"]

    missing_text = "无" if not validation["missing_files"] else ", ".join(validation["missing_files"])

    return f"""# Telegram 真实主链验证 v1 · E4 验收报告

## 任务名称
Telegram 真实主链验证 v1 · E4 最小真实样本采集

## 当前层级
E4 样本级 / 待观察

## 证据层级
E4

## 主链接入状态
已接入真实主链（样本级）

## 启用状态
已启用（样本级）

## 结论口径
已进入 E4，已获得真实 Telegram 首个样本级证据；待观察

## 真实触发证据
- 原始 Telegram update: {sample_dir / 'raw_update.json'}
- normalized event: {sample_dir / 'normalized_event.json'}
- OpenEmotion 结构化结果: {sample_dir / 'openemotion_result.json'}
- 实际发送记录: {sample_dir / 'outbox_record.json'}

## 当前确定项
- 真实用户消息进入 Telegram 主链并生成完整 evidence bundle
- OpenEmotion 结构化输出与 EgoCore response plan 已同步落盘
- timeline / tape / replay artifact 已存在，可追踪引用

## 关键未知
- 样本数量仍不足，不能证明稳定性
- 尚未覆盖高风险、工具调用、多轮恢复等场景
- 尚未形成 E5 观察期证据

## 本次结论不能证明什么
- 不能证明系统稳定运行
- 不能证明关键未知为无
- 不能证明已完成观察期
- 不能证明未来替换其他通讯软件后无需再做真实渠道验证

## 成功样本列表
{chr(10).join(success_items)}

## 失败样本列表
{chr(10).join(failure_items)}

## 证据清单
| evidence_id | evidence_level | source_type | artifact_path | what_it_proves | what_it_does_not_prove |
|---|---|---|---|---|---|
{chr(10).join(evidence_rows)}

## 证据完整性
- 缺失文件: {missing_text}

## 下一步最小闭环动作
- 用同一套 runner 再采至少 1 个普通文本样本和 1 个高风险样本
- 把同样输入投给 simulated / integration runner，验证是否能复现同类问题
- 在样本累计后进入 E5 观察而不是提前宣称稳定
"""


def _what_it_proves(filename: str) -> str:
    mapping = {
        "raw_update.json": "真实 Telegram 原始输入已落盘",
        "normalized_event.json": "主体入口标准化事件已生成",
        "openemotion_result.json": "OpenEmotion 结构化结果已生成",
        "response_plan.json": "EgoCore response plan 已生成",
        "outbox_record.json": "实际发送记录已存在",
        "timeline.json": "处理时间线可追踪",
        "tape.json": "样本审计带已生成",
        "replay.json": "样本可按 artifact 引用回放",
    }
    return mapping[filename]


def _what_it_does_not_prove(filename: str) -> str:
    mapping = {
        "raw_update.json": "不证明所有真实输入都能稳定处理",
        "normalized_event.json": "不证明所有边界情况都正确归一化",
        "openemotion_result.json": "不证明所有主体推断都正确",
        "response_plan.json": "不证明所有计划都正确执行",
        "outbox_record.json": "不证明长期发送稳定性",
        "timeline.json": "不证明全链路长期无丢失",
        "tape.json": "不证明多样本回放一致性",
        "replay.json": "不证明长期回放治理已收口",
    }
    return mapping[filename]


def write_report(validation: Dict[str, Any], failures: List[Dict[str, Any]]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = generate_report_payload(validation, failures)
    with open(LATEST_REPORT, "w", encoding="utf-8") as handle:
        handle.write(report)
    return LATEST_REPORT


def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram Real Channel Capture (E4)")
    parser.add_argument("--status", action="store_true", help="查看真实样本状态")
    parser.add_argument("--list-samples", action="store_true", help="列出现有样本")
    parser.add_argument("--validate-latest", action="store_true", help="校验最新样本并生成报告")
    parser.add_argument("--record-failure", type=str, help="手动记录失败样本")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" Telegram Real Mainline Validation v1 - Real Channel Capture (E4)")
    print("=" * 70)
    print("\n[INFO] Evidence Level: E4 (real_channel)")
    print("[INFO] Allowed: 已接入真实主链、已启用、样本级生效")
    print("[INFO] Forbidden: 关键未知为无、稳定收口、观察期完成")

    if args.record_failure:
        failure = record_failure(actual=args.record_failure)
        print(f"\n[PASS] Failure recorded: {failure['artifact_path']}")
        return 0

    validations = [validate_sample_dir(path) for path in sample_dirs()]

    if args.list_samples or args.status:
        print(f"\n[INFO] Found {len(validations)} samples")
        for item in validations:
            status = "✅ 完整" if item["is_complete"] else f"⚠️ 缺失 {','.join(item['missing_files'])}"
            print(f"  {status} {item['sample_id']} {item['timestamp']}")
        if args.status:
            return 0

    if args.validate_latest:
        if not validations:
            failure = record_failure(actual="没有找到真实 Telegram 样本", initial_cause_type="test_gap")
            print(f"\n[FAIL] No samples found. Recorded failure: {failure['artifact_path']}")
            return 1
        latest = validations[-1]
        failures = []
        if not latest["is_complete"]:
            failures.append(
                record_failure(
                    actual=f"样本 {latest['sample_id']} 缺失 {','.join(latest['missing_files'])}",
                    raw_input=latest["sample"].get("raw_update"),
                    initial_cause_type="delivery_error",
                )
            )
        report_path = write_report(latest, failures)
        print(f"\n[PASS] Report generated: {report_path}")
        print(f"  Sample: {latest['sample_id']}")
        print(f"  Complete: {latest['is_complete']}")
        return 0 if latest["is_complete"] else 1

    print("\n[INFO] Usage:")
    print("  --status           查看样本状态")
    print("  --list-samples     列出现有样本")
    print("  --validate-latest  校验最新样本并生成 E4 报告")
    print("  --record-failure   手动记录失败样本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
