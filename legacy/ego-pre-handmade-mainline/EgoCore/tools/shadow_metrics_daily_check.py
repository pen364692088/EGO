#!/usr/bin/env python3
"""
Runtime Metrics Aggregator - Shadow Metrics Daily Check

每日观测脚本 - 从持久化 JSONL 事件文件读取

Usage: python tools/shadow_metrics_daily_check.py --date YYYY-MM-DD
       python tools/shadow_metrics_daily_check.py --today
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 观察窗口配置
OBSERVATION_START = datetime(2026, 3, 14, tzinfo=timezone.utc)
OBSERVATION_END = datetime(2026, 3, 28, tzinfo=timezone.utc)

# === 双层样本口径 ===
# Layer 1: 每日报告最小样本（小样本保护）
DAILY_MIN_SAMPLES = 20

# Layer 2: 14天 verdict 最小样本
VERDICT_MIN_SAMPLES = 100

# 切换门槛
THRESHOLDS = {
    "success_rate": 95.0,  # %
    "fallback_rate": 5.0,   # %
    "timeout_rate": 1.0,    # %
}


def get_events_from_file(date_str: str) -> dict:
    """从 JSONL 文件读取事件"""
    try:
        from runtime_metrics_aggregator.observability.shadow_events_logger import get_shadow_logger
        
        logger = get_shadow_logger()
        events = logger.get_events_for_date(date_str)
        stats = logger.get_stats_for_date(date_str)
        
        return {
            "events": events,
            "stats": stats,
        }
    except ImportError:
        return {"events": [], "stats": {}}


def calculate_metrics(data: dict) -> dict:
    """计算指标"""
    stats = data.get("stats", {})
    
    total = stats.get("total_events", 0)
    if total == 0:
        return {
            "total_calls": 0,
            "success_count": 0,
            "dropped_count": 0,
            "error_count": 0,
            "success_rate": 0.0,
            "dropped_rate": 0.0,
            "avg_latency_ms": 0.0,
            "user_impact_count": 0,
            "sample_sufficient": False,
            "insufficient_evidence": True,
        }
    
    return {
        "total_calls": total,
        "success_count": stats.get("stored_count", 0),
        "dropped_count": stats.get("dropped_count", 0),
        "error_count": stats.get("error_count", 0),
        "success_rate": stats.get("success_rate", 0.0),
        "dropped_rate": stats.get("dropped_rate", 0.0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0.0),
        "user_impact_count": stats.get("user_impact_count", 0),
        "sample_sufficient": total >= DAILY_MIN_SAMPLES,
        "insufficient_evidence": total < DAILY_MIN_SAMPLES,
        "sources": stats.get("sources", {}),
        "modules": stats.get("modules", {}),
    }


def classify_anomalies(metrics: dict) -> list:
    """异常归因分类"""
    anomalies = []
    
    # 小样本保护：样本不足时不做异常归因
    if metrics["insufficient_evidence"]:
        return anomalies
    
    if metrics["dropped_rate"] > THRESHOLDS["fallback_rate"]:
        anomalies.append({
            "type": "dropped_rate_high",
            "value": metrics["dropped_rate"],
            "threshold": THRESHOLDS["fallback_rate"],
            "category": "待归因",
            "suggestion": "需进一步分析 dropped 来源",
        })
    
    if metrics["error_count"] > 0:
        anomalies.append({
            "type": "errors_detected",
            "value": metrics["error_count"],
            "threshold": 0,
            "category": "待归因",
            "suggestion": "检查错误类型和来源",
        })
    
    if metrics["user_impact_count"] > 0:
        anomalies.append({
            "type": "user_impact",
            "value": metrics["user_impact_count"],
            "threshold": 0,
            "category": "严重",
            "suggestion": "用户可见影响，需要立即关注",
        })
    
    return anomalies


def check_thresholds(metrics: dict) -> dict:
    """检查门槛（带小样本保护）"""
    if metrics["insufficient_evidence"]:
        return {
            "success_rate": {"pass": None, "reason": "insufficient_evidence"},
            "dropped_rate": {"pass": None, "reason": "insufficient_evidence"},
            "all_pass": None,
            "_meta": {
                "total_samples": metrics["total_calls"],
                "min_samples": DAILY_MIN_SAMPLES,
                "insufficient_evidence": True,
            }
        }
    
    return {
        "success_rate": {
            "value": metrics["success_rate"],
            "threshold": THRESHOLDS["success_rate"],
            "pass": metrics["success_rate"] >= THRESHOLDS["success_rate"],
        },
        "dropped_rate": {
            "value": metrics["dropped_rate"],
            "threshold": THRESHOLDS["fallback_rate"],
            "pass": metrics["dropped_rate"] <= THRESHOLDS["fallback_rate"],
        },
        "all_pass": (
            metrics["success_rate"] >= THRESHOLDS["success_rate"] and
            metrics["dropped_rate"] <= THRESHOLDS["fallback_rate"]
        ),
        "_meta": {
            "total_samples": metrics["total_calls"],
            "min_samples": DAILY_MIN_SAMPLES,
            "insufficient_evidence": False,
        }
    }


def generate_daily_report(date_str: str, metrics: dict, anomalies: list, thresholds: dict) -> dict:
    """生成每日报告"""
    return {
        "date": date_str,
        "observation_window": {
            "start": OBSERVATION_START.isoformat(),
            "end": OBSERVATION_END.isoformat(),
            "day_number": (datetime.now(timezone.utc) - OBSERVATION_START).days + 1,
            "max_days": 14,
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "anomalies": anomalies,
        "recommendation": "继续观察" if not anomalies else "需要关注异常",
    }


def save_daily_report(report: dict, date_str: str):
    """保存每日报告"""
    output_dir = PROJECT_ROOT / "artifacts" / "verification" / "runtime-metrics-shadow"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    day_num = report["observation_window"]["day_number"]
    output_file = output_dir / f"day_{day_num:02d}.md"
    json_file = output_dir / f"day_{day_num:02d}.json"
    
    metrics = report["metrics"]
    thresholds = report["thresholds"]
    insufficient = metrics.get("insufficient_evidence", False)
    
    # 状态判断
    total = metrics["total_calls"]
    success_rate = metrics["success_rate"]
    dropped_rate = metrics["dropped_rate"]
    
    if insufficient:
        sample_status = f"⏳ ({total}/{DAILY_MIN_SAMPLES} - insufficient)"
        success_status = "⏳"
        dropped_status = "⏳"
    else:
        sample_status = "✅" if total >= DAILY_MIN_SAMPLES else f"⏳ ({total}/{DAILY_MIN_SAMPLES})"
        success_status = "✅" if success_rate >= THRESHOLDS["success_rate"] else "❌"
        dropped_status = "✅" if dropped_rate <= THRESHOLDS["fallback_rate"] else "❌"
    
    content = f"""# Shadow Observation - Day {day_num:02d}

## 日期
{date_str}

## 观察窗口
- 开始: {report['observation_window']['start']}
- 结束: {report['observation_window']['end']}
- 第 {report['observation_window']['day_number']} / {report['observation_window']['max_days']} 天

"""

    if insufficient:
        content += f"""⚠️ **INSUFFICIENT EVIDENCE** - 样本数低于门槛
   有效样本: {total} < {DAILY_MIN_SAMPLES}
   仅展示原始指标，不做门槛判定。

"""

    content += f"""---

## 指标

| 指标 | 值 | 门槛 | 状态 |
|------|-----|------|------|
| 有效样本数 | {total} | ≥ {DAILY_MIN_SAMPLES} (daily) / ≥ {VERDICT_MIN_SAMPLES} (verdict) | {sample_status} |
| 成功率 | {success_rate}% | ≥ {THRESHOLDS['success_rate']}% | {success_status} |
| dropped 比例 | {dropped_rate}% | ≤ {THRESHOLDS['fallback_rate']}% | {dropped_status} |
| 错误数 | {metrics['error_count']} | 0 | {"❌" if metrics['error_count'] > 0 else "✅"} |
| 平均延迟 | {metrics['avg_latency_ms']:.3f}ms | - | - |

## 来源分布

| 来源 | 调用数 |
|------|--------|
"""
    
    for src, count in metrics.get("sources", {}).items():
        content += f"| {src} | {count} |\n"
    
    if not metrics.get("sources"):
        content += "| 无数据 | - |\n"
    
    content += f"""
## 模块分布

| 模块 | 调用数 |
|------|--------|
"""
    
    for mod, count in metrics.get("modules", {}).items():
        content += f"| {mod} | {count} |\n"
    
    if not metrics.get("modules"):
        content += "| 无数据 | - |\n"
    
    content += f"""
## 异常归因

"""
    if report["anomalies"]:
        for a in report["anomalies"]:
            content += f"- **{a['type']}**: {a['value']} (门槛: {a['threshold']})\n"
            content += f"  - 归因: {a['category']}\n"
            content += f"  - 建议: {a['suggestion']}\n"
    else:
        content += "无异常\n"
    
    content += f"""
## 用户可见影响

| 项目 | 值 |
|------|-----|
| 有影响 | {"是" if metrics["user_impact_count"] > 0 else "否"} |
| 影响次数 | {metrics["user_impact_count"]} |

## 建议

"""
    if insufficient:
        content += f"""⏳ **INSUFFICIENT EVIDENCE**
   有效样本: {total}/{DAILY_MIN_SAMPLES}
   继续观察。样本 ≥ {DAILY_MIN_SAMPLES} 后才开始门槛判定。
"""
    else:
        content += report['recommendation']
    
    content += f"""

---
*生成时间: {datetime.now(timezone.utc).isoformat()}*
*数据来源: 持久化事件文件 (不依赖内存状态)*
*双层口径: daily_min={DAILY_MIN_SAMPLES}, verdict_min={VERDICT_MIN_SAMPLES}*
"""
    
    with open(output_file, "w") as f:
        f.write(content)
    
    # 保存 JSON
    with open(json_file, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 报告已保存: {output_file}")
    print(f"✅ JSON 已保存: {json_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Shadow Metrics Daily Check")
    parser.add_argument("--date", help="日期 (YYYY-MM-DD)", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()
    
    print(f"=== Shadow Metrics Daily Check ===")
    print(f"日期: {args.date}")
    print(f"数据来源: 持久化 JSONL 事件文件")
    print()
    
    # 从文件读取事件
    data = get_events_from_file(args.date)
    
    # 计算指标
    metrics = calculate_metrics(data)
    
    # 检查门槛（带小样本保护）
    thresholds = check_thresholds(metrics)
    
    # 异常归因
    anomalies = classify_anomalies(metrics)
    
    # 生成报告
    report = generate_daily_report(args.date, metrics, anomalies, thresholds)
    
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"样本数: {metrics['total_calls']}")
        print(f"成功率: {metrics['success_rate']}%")
        print(f"dropped: {metrics['dropped_rate']}%")
        print(f"错误数: {metrics['error_count']}")
        print(f"异常数: {len(anomalies)}")
        
        if metrics["insufficient_evidence"]:
            print(f"\n⏳ INSUFFICIENT EVIDENCE: {metrics['total_calls']}/{DAILY_MIN_SAMPLES} samples")
    
    # 保存报告
    save_daily_report(report, args.date)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
