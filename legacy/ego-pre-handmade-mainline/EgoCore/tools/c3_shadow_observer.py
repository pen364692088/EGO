#!/usr/bin/env python3
"""
C3. 极简观察脚本 - 只收 4 个指标

指标:
1. /cycle 命中率
2. event_stored = true 比例
3. fallback /interpret 触发率
4. 低质量兜底回复占比

用法:
    python tools/c3_shadow_observer.py --date 2026-03-19

输出:
    artifacts/verification/c3_shadow/daily/YYYY-MM-DD.json
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

# 配置
ARTIFACT_DIR = Path("/home/moonlight/Project/Github/MyProject/EgoCore/artifacts/verification/c3_shadow/daily")
LOG_DIR = Path("/home/moonlight/Project/Github/MyProject/EgoCore/logs")


def analyze_day(target_date: date) -> dict:
    """分析指定日期的指标"""
    
    # 初始化计数器
    stats = {
        "total_requests": 0,
        "cycle_hits": 0,
        "fallback_hits": 0,
        "event_stored_true": 0,
        "event_stored_false": 0,
        "low_quality_replies": 0,
    }
    
    # 低质量兜底回复关键词
    low_quality_markers = [
        "具体指哪部分",
        "你说的是",
        "展开讲讲",
        "没太跟上",
        "指的是什么",
    ]
    
    # 读取 C1 验证报告（如果有）
    c1_reports = list(Path("/home/moonlight/Project/Github/MyProject/EgoCore/artifacts/verification/ws_c1").glob("c1_verification_*.json"))
    
    for report_path in c1_reports:
        try:
            report = json.loads(report_path.read_text())
            report_date = datetime.fromisoformat(report["timestamp"]).date()
            
            if report_date == target_date:
                for result in report.get("results", []):
                    stats["total_requests"] += 1
                    
                    data = result.get("diagnostic_data", {})
                    memory_update = data.get("memory_update", {})
                    
                    # /cycle 命中（所有 C1 测试都走 /cycle）
                    stats["cycle_hits"] += 1
                    
                    # event_stored
                    if memory_update.get("event_stored", False):
                        stats["event_stored_true"] += 1
                    else:
                        stats["event_stored_false"] += 1
                    
                    # 低质量兜底回复
                    response = result.get("response", "")
                    if any(marker in response for marker in low_quality_markers):
                        stats["low_quality_replies"] += 1
                        
        except Exception as e:
            print(f"Warning: Failed to parse {report_path}: {e}")
    
    # 计算比率
    total = stats["total_requests"]
    
    if total > 0:
        cycle_rate = stats["cycle_hits"] / total
        event_stored_rate = stats["event_stored_true"] / total
        fallback_rate = stats["fallback_hits"] / total if stats["fallback_hits"] > 0 else 0.0
        low_quality_rate = stats["low_quality_replies"] / total
    else:
        cycle_rate = 0.0
        event_stored_rate = 0.0
        fallback_rate = 0.0
        low_quality_rate = 0.0
    
    return {
        "date": target_date.isoformat(),
        "generated_at": datetime.now().isoformat(),
        "raw_counts": stats,
        "metrics": {
            "cycle_hit_rate": round(cycle_rate, 4),
            "event_stored_rate": round(event_stored_rate, 4),
            "fallback_rate": round(fallback_rate, 4),
            "low_quality_rate": round(low_quality_rate, 4),
        },
        "status": "ok" if total > 0 else "no_data",
    }


def save_report(report: dict) -> Path:
    """保存报告"""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = report["date"]
    report_path = ARTIFACT_DIR / f"{date_str}.json"
    
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report_path


def print_summary(report: dict):
    """打印汇总"""
    print(f"\n{'='*50}")
    print(f"C3 Shadow Observation: {report['date']}")
    print(f"{'='*50}")
    
    if report["status"] == "no_data":
        print("No data available for this date.")
        return
    
    stats = report["raw_counts"]
    metrics = report["metrics"]
    
    print(f"\nRaw Counts:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  /cycle hits: {stats['cycle_hits']}")
    print(f"  Fallback hits: {stats['fallback_hits']}")
    print(f"  Event stored (true): {stats['event_stored_true']}")
    print(f"  Event stored (false): {stats['event_stored_false']}")
    print(f"  Low quality replies: {stats['low_quality_replies']}")
    
    print(f"\nMetrics:")
    print(f"  /cycle hit rate: {metrics['cycle_hit_rate']*100:.1f}%")
    print(f"  Event stored rate: {metrics['event_stored_rate']*100:.1f}%")
    print(f"  Fallback rate: {metrics['fallback_rate']*100:.1f}%")
    print(f"  Low quality rate: {metrics['low_quality_rate']*100:.1f}%")
    
    # 健康判断
    print(f"\nHealth Check:")
    if metrics["cycle_hit_rate"] >= 0.95:
        print("  ✅ /cycle hit rate healthy (>=95%)")
    else:
        print("  ⚠️  /cycle hit rate low (<95%)")
    
    if metrics["fallback_rate"] <= 0.05:
        print("  ✅ Fallback rate healthy (<=5%)")
    else:
        print("  ⚠️  Fallback rate high (>5%)")
    
    if metrics["low_quality_rate"] <= 0.30:
        print("  ✅ Low quality rate acceptable (<=30%)")
    else:
        print("  ⚠️  Low quality rate high (>30%)")
    
    print(f"\n{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="C3 Shadow Observer - Minimal 4-metric monitoring")
    parser.add_argument("--date", type=str, default=date.today().isoformat(),
                        help="Date to analyze (YYYY-MM-DD)")
    args = parser.parse_args()
    
    target_date = date.fromisoformat(args.date)
    
    print(f"Analyzing {target_date}...")
    
    report = analyze_day(target_date)
    report_path = save_report(report)
    
    print_summary(report)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
