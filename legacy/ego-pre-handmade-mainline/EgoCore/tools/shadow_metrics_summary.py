#!/usr/bin/env python3
"""
Runtime Metrics Aggregator - Shadow 14-Day Summary

14天观察窗口汇总报告

Usage: python tools/shadow_metrics_summary.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 双层样本口径
DAILY_MIN_SAMPLES = 20
VERDICT_MIN_SAMPLES = 100

# 观察窗口
OBSERVATION_START = "2026-03-14"
OBSERVATION_END = "2026-03-28"
MAX_DAYS = 14

# 切换门槛
THRESHOLDS = {
    "success_rate": 95.0,
    "fallback_rate": 5.0,
    "timeout_rate": 1.0,
}


def load_daily_reports() -> list:
    """加载所有每日报告"""
    reports_dir = PROJECT_ROOT / "artifacts" / "verification" / "runtime-metrics-shadow"
    
    if not reports_dir.exists():
        return []
    
    reports = []
    for day_file in sorted(reports_dir.glob("day_*.json")):
        try:
            with open(day_file) as f:
                reports.append(json.load(f))
        except:
            pass
    
    return reports


def aggregate_metrics(reports: list) -> dict:
    """汇总所有报告的指标"""
    aggregated = {
        "total_days": len(reports),
        "total_samples": 0,
        "total_success": 0,
        "total_dropped": 0,
        "total_errors": 0,
        "days_with_sufficient_samples": 0,
        "daily_samples": [],
    }
    
    for report in reports:
        metrics = report.get("metrics", {})
        aggregated["total_samples"] += metrics.get("total_calls", 0)
        aggregated["total_success"] += metrics.get("success_count", 0)
        aggregated["total_dropped"] += metrics.get("dropped_count", 0)
        aggregated["total_errors"] += metrics.get("error_count", 0)
        
        if not metrics.get("insufficient_evidence", True):
            aggregated["days_with_sufficient_samples"] += 1
        
        aggregated["daily_samples"].append({
            "day": report.get("observation_window", {}).get("day_number", 0),
            "samples": metrics.get("total_calls", 0),
        })
    
    # 计算平均成功率
    if aggregated["total_samples"] > 0:
        aggregated["success_rate"] = (aggregated["total_success"] / aggregated["total_samples"]) * 100
        aggregated["dropped_rate"] = (aggregated["total_dropped"] / aggregated["total_samples"]) * 100
    else:
        aggregated["success_rate"] = 0.0
        aggregated["dropped_rate"] = 0.0
    
    return aggregated


def check_verdict(aggregated: dict) -> dict:
    """检查 verdict 条件"""
    sample_pass = aggregated["total_samples"] >= VERDICT_MIN_SAMPLES
    success_pass = aggregated["success_rate"] >= THRESHOLDS["success_rate"]
    dropped_pass = aggregated["dropped_rate"] <= THRESHOLDS["fallback_rate"]
    
    all_pass = sample_pass and success_pass and dropped_pass
    
    return {
        "sample_count": {
            "value": aggregated["total_samples"],
            "threshold": VERDICT_MIN_SAMPLES,
            "pass": sample_pass,
        },
        "success_rate": {
            "value": aggregated["success_rate"],
            "threshold": THRESHOLDS["success_rate"],
            "pass": success_pass,
        },
        "dropped_rate": {
            "value": aggregated["dropped_rate"],
            "threshold": THRESHOLDS["fallback_rate"],
            "pass": dropped_pass,
        },
        "all_pass": all_pass,
    }


def generate_verdict(verdict: dict) -> tuple:
    """生成 verdict 结论"""
    if not verdict["sample_count"]["pass"]:
        return "INSUFFICIENT_EVIDENCE", f"样本不足: {verdict['sample_count']['value']}/{VERDICT_MIN_SAMPLES}"
    
    if not verdict["all_pass"]:
        failed = [k for k, v in verdict.items() if isinstance(v, dict) and not v.get("pass", True)]
        return "THRESHOLD_VIOLATIONS", f"门槛违反: {', '.join(failed)}"
    
    return "PASS", "所有条件满足，可以切换到 pilot 模式"


def generate_summary_report(aggregated: dict, verdict: dict, verdict_result: tuple) -> str:
    """生成汇总报告"""
    verdict_code, verdict_reason = verdict_result
    
    lines = [
        f"# Shadow Metrics 14-Day Summary",
        "",
        f"**观察窗口**: {OBSERVATION_START} → {OBSERVATION_END}",
        f"**生成时间**: {datetime.now(timezone.utc).isoformat()}",
        "",
        "---",
        "",
        "## Verdict",
        "",
    ]
    
    if verdict_code == "PASS":
        lines.append("### ✅ PASS - 可以切换到 Pilot 模式")
    elif verdict_code == "INSUFFICIENT_EVIDENCE":
        lines.append("### ⏳ INSUFFICIENT EVIDENCE - 样本不足")
    else:
        lines.append("### ❌ THRESHOLD VIOLATIONS - 门槛违反")
    
    lines.append(f"**原因**: {verdict_reason}")
    
    lines.extend([
        "",
        "---",
        "",
        "## 汇总指标",
        "",
        "| 指标 | 值 | 门槛 | 状态 |",
        "|------|-----|------|------|",
    ])
    
    for name, check in verdict.items():
        if not isinstance(check, dict):
            continue
        
        status = "✅" if check["pass"] else "❌"
        val = check["value"]
        thr = check["threshold"]
        
        if name == "sample_count":
            lines.append(f"| 样本数 | {int(val)} | ≥{int(thr)} | {status} |")
        else:
            lines.append(f"| {name} | {val:.1f}% | {'≥' if 'success' in name else '≤'}{thr:.1f}% | {status} |")
    
    lines.extend([
        "",
        "---",
        "",
        "## 每日进度",
        "",
        "| 天 | 样本 | 累计 |",
        "|-----|------|------|",
    ])
    
    cumulative = 0
    for day_data in aggregated["daily_samples"]:
        cumulative += day_data["samples"]
        lines.append(f"| {day_data['day']:02d} | {day_data['samples']} | {cumulative} |")
    
    lines.extend([
        "",
        "---",
        "",
        "## 事件汇总",
        "",
        f"- 总天数: {aggregated['total_days']}/{MAX_DAYS}",
        f"- 总样本: {aggregated['total_samples']}",
        f"- 成功数: {aggregated['total_success']}",
        f"- Dropped: {aggregated['total_dropped']}",
        f"- 错误数: {aggregated['total_errors']}",
        f"- 样本充足天数: {aggregated['days_with_sufficient_samples']} (≥{DAILY_MIN_SAMPLES} 样本)",
        "",
        "---",
        "",
        "## 下一步",
        "",
    ])
    
    if verdict_code == "PASS":
        lines.extend([
            "1. 审核此报告",
            "2. 切换到 pilot 模式",
            "3. 继续观察 14 天",
        ])
    elif verdict_code == "INSUFFICIENT_EVIDENCE":
        lines.extend([
            "1. 继续观察",
            f"2. 目标样本: ≥{VERDICT_MIN_SAMPLES}",
        ])
    else:
        lines.extend([
            "1. 调查门槛违反原因",
            "2. 修复问题",
            "3. 重新评估",
        ])
    
    lines.extend([
        "",
        "---",
        "",
        f"*双层口径: daily_min={DAILY_MIN_SAMPLES}, verdict_min={VERDICT_MIN_SAMPLES}*",
    ])
    
    return "\n".join(lines)


def main():
    print("=== Shadow Metrics 14-Day Summary ===")
    print()
    
    # 加载每日报告
    reports = load_daily_reports()
    
    if not reports:
        print("❌ 未找到每日报告")
        return 1
    
    # 汇总指标
    aggregated = aggregate_metrics(reports)
    
    # 检查 verdict
    verdict = check_verdict(aggregated)
    
    # 生成结论
    verdict_result = generate_verdict(verdict)
    
    # 生成报告
    report_content = generate_summary_report(aggregated, verdict, verdict_result)
    
    # 保存
    output_dir = PROJECT_ROOT / "artifacts" / "verification" / "runtime-metrics-shadow"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "summary_14day.md"
    json_file = output_dir / "summary_14day.json"
    
    with open(output_file, "w") as f:
        f.write(report_content)
    
    json_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "observation_window": {
            "start": OBSERVATION_START,
            "end": OBSERVATION_END,
            "max_days": MAX_DAYS,
        },
        "aggregated": aggregated,
        "verdict": verdict,
        "verdict_result": {
            "code": verdict_result[0],
            "reason": verdict_result[1],
        },
    }
    
    with open(json_file, "w") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 汇总报告已保存: {output_file}")
    print(f"✅ JSON 已保存: {json_file}")
    print()
    print(f"天数: {aggregated['total_days']}/{MAX_DAYS}")
    print(f"样本: {aggregated['total_samples']}/{VERDICT_MIN_SAMPLES}")
    print(f"Verdict: {verdict_result[0]}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
