#!/usr/bin/env python
"""
MVP13 Mirror Daily Report

Generates daily stability report for MVP13 mirror read mode.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.self_model import get_self_model_v0
from emotiond.self_model_mirror import SelfModelMirrorAdapter


def collect_daily_metrics(num_samples: int = 100) -> Dict[str, Any]:
    """Collect metrics for daily report."""
    adapter = SelfModelMirrorAdapter(enable=True)
    
    # Reset adapter for clean metrics
    adapter.metrics.total_mirrors = 0
    adapter.metrics.successful_mirrors = 0
    adapter.metrics.failed_mirrors = 0
    adapter.metrics.invariant_violations = 0
    adapter.metrics.avg_conversion_time_ms = 0.0
    adapter._mirror_history = []
    
    # Collect samples
    for i in range(num_samples):
        legacy = get_self_model_v0(f'daily_report_target_{i}')
        adapter.mirror_from_legacy(legacy)
    
    return adapter.get_metrics()


def check_empty_mirror_rate(adapter: SelfModelMirrorAdapter) -> float:
    """Check rate of empty mirrors (missing key fields)."""
    if not adapter._mirror_history:
        return 0.0
    
    empty_count = 0
    for entry in adapter._mirror_history:
        if not entry.get("success"):
            continue
        
        # Check if mirror has minimal fields
        # This is a placeholder - would need actual mirrored state to check
        # For now, assume success means non-empty
        pass
    
    return 0.0  # Placeholder


def check_field_missing_rate(adapter: SelfModelMirrorAdapter) -> Dict[str, float]:
    """Check rate of missing fields in mirrors."""
    # Placeholder - would need actual mirrored states to analyze
    return {
        "identity": 0.0,
        "behavioral_tendencies": 0.0,
        "capability_assessments": 0.0,
        "tension_biases": 0.0,
    }


def generate_daily_report(day_number: int, metrics: Dict[str, Any]) -> str:
    """Generate daily report markdown."""
    report = f"""# MVP13 Mirror Daily Report - Day {day_number}

> 日期: {datetime.now().strftime('%Y-%m-%d')}
> 观察窗: Day {day_number}/7

---

## 1. 核心指标

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| 总镜像数 | {metrics['total_mirrors']} | - | - |
| 成功数 | {metrics['successful_mirrors']} | - | - |
| 失败数 | {metrics['failed_mirrors']} | <5 | {'✅' if metrics['failed_mirrors'] < 5 else '❌'} |
| 成功率 | {metrics['success_rate']:.2%} | >95% | {'✅' if metrics['success_rate'] > 0.95 else '❌'} |
| 不变量违规数 | {metrics['invariant_violations']} | 0 | {'✅' if metrics['invariant_violations'] == 0 else '❌'} |
| 不变量违规率 | {metrics['invariant_violation_rate']:.2%} | <1% | {'✅' if metrics['invariant_violation_rate'] < 0.01 else '❌'} |

---

## 2. 性能指标

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| 平均转换时间 | {metrics['avg_conversion_time_ms']:.2f} ms | <10ms | {'✅' if metrics['avg_conversion_time_ms'] < 10 else '❌'} |

---

## 3. Phase 2 准入评估

### 3.1 当前状态

| 条件 | 要求 | 当前 | 状态 |
|------|------|------|------|
| 成功率 | >95% | {metrics['success_rate']:.2%} | {'✅' if metrics['success_rate'] > 0.95 else '❌'} |
| 不变量违规率 | <1% | {metrics['invariant_violation_rate']:.2%} | {'✅' if metrics['invariant_violation_rate'] < 0.01 else '❌'} |
| 运行天数 | ≥7 | {day_number} | {'✅' if day_number >= 7 else '⏳'} |

### 3.2 结论

"""
    if day_number < 7:
        report += "**状态**: ⏳ 观察期进行中\n\n"
        report += f"剩余天数: {7 - day_number}\n"
    elif metrics['success_rate'] > 0.95 and metrics['invariant_violation_rate'] < 0.01:
        report += "**状态**: ✅ 准入条件满足\n\n"
        report += "可以评估是否进入 Phase 2（双写比对）。\n"
    else:
        report += "**状态**: ❌ 准入条件未满足\n\n"
        report += "需要继续观察或修复问题。\n"
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, required=True, help="Day number (1-7)")
    parser.add_argument("--samples", type=int, default=100, help="Number of samples")
    parser.add_argument("--output", type=str, default="artifacts/mvp13/daily_reports")
    args = parser.parse_args()
    
    print(f"=== MVP13 Mirror Daily Report - Day {args.day} ===")
    
    # Collect metrics
    print(f"Collecting {args.samples} samples...")
    metrics = collect_daily_metrics(args.samples)
    
    # Generate report
    report = generate_daily_report(args.day, metrics)
    
    # Save report
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = output_dir / f"day_{args.day}.md"
    with open(report_path, "w") as f:
        f.write(report)
    
    # Save metrics JSON
    metrics_path = output_dir / f"day_{args.day}_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\nReport saved to: {report_path}")
    print(f"Metrics saved to: {metrics_path}")
    
    # Print summary
    print(f"\n=== Summary ===")
    print(f"Success rate: {metrics['success_rate']:.2%}")
    print(f"Invariant violations: {metrics['invariant_violations']}")
    print(f"Avg conversion time: {metrics['avg_conversion_time_ms']:.2f} ms")


if __name__ == "__main__":
    main()
