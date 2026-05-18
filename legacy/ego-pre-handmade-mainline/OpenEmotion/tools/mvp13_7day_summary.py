#!/usr/bin/env python
"""
MVP13 7-Day Observation Summary

Generates final summary report after 7-day observation window.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def load_daily_metrics(base_dir: Path, days: int = 7) -> List[Dict[str, Any]]:
    """Load daily metrics from reports."""
    metrics_list = []
    for day in range(1, days + 1):
        metrics_path = base_dir / f"day_{day}_metrics.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                metrics_list.append(json.load(f))
        else:
            metrics_list.append(None)
    return metrics_list


def calculate_trends(metrics_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate trends from daily metrics."""
    valid_metrics = [m for m in metrics_list if m is not None]
    
    if not valid_metrics:
        return {
            "avg_success_rate": 0,
            "avg_invariant_violation_rate": 0,
            "avg_conversion_time_ms": 0,
            "trend_direction": "unknown",
        }
    
    avg_success_rate = sum(m.get("success_rate", 0) for m in valid_metrics) / len(valid_metrics)
    avg_invariant_violation_rate = sum(m.get("invariant_violation_rate", 0) for m in valid_metrics) / len(valid_metrics)
    avg_conversion_time = sum(m.get("avg_conversion_time_ms", 0) for m in valid_metrics) / len(valid_metrics)
    
    # Trend direction
    if len(valid_metrics) >= 2:
        first_half = valid_metrics[:len(valid_metrics)//2]
        second_half = valid_metrics[len(valid_metrics)//2:]
        
        first_sr = sum(m.get("success_rate", 0) for m in first_half) / len(first_half)
        second_sr = sum(m.get("success_rate", 0) for m in second_half) / len(second_half)
        
        if second_sr > first_sr + 0.01:
            trend_direction = "improving"
        elif second_sr < first_sr - 0.01:
            trend_direction = "degrading"
        else:
            trend_direction = "stable"
    else:
        trend_direction = "insufficient_data"
    
    return {
        "avg_success_rate": avg_success_rate,
        "avg_invariant_violation_rate": avg_invariant_violation_rate,
        "avg_conversion_time_ms": avg_conversion_time,
        "trend_direction": trend_direction,
    }


def generate_summary_report(
    mirror_trends: Dict[str, Any],
    artifact_trends: Dict[str, Any],
    mirror_metrics: List[Dict[str, Any]],
    artifact_metrics: List[Dict[str, Any]],
) -> str:
    """Generate 7-day summary report."""
    
    report = f"""# MVP13 7-Day Observation Summary

> 观察窗: 2026-03-13 ~ 2026-03-19
> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 1. 镜像稳定性总结

### 1.1 整体指标

| 指标 | 平均值 | 趋势 |
|------|--------|------|
| 成功率 | {mirror_trends['avg_success_rate']:.2%} | {mirror_trends['trend_direction']} |
| 不变量违规率 | {mirror_trends['avg_invariant_violation_rate']:.2%} | - |
| 转换时间 | {mirror_trends['avg_conversion_time_ms']:.2f} ms | - |

### 1.2 每日数据

| Day | 成功率 | 违规率 | 转换时间 |
|-----|--------|--------|----------|
"""
    
    for i, m in enumerate(mirror_metrics, 1):
        if m:
            report += f"| {i} | {m.get('success_rate', 0):.2%} | {m.get('invariant_violation_rate', 0):.2%} | {m.get('avg_conversion_time_ms', 0):.2f} ms |\n"
        else:
            report += f"| {i} | N/A | N/A | N/A |\n"
    
    report += f"""
---

## 2. MVP15 Artifact 质量总结

### 2.1 整体指标

| 指标 | 平均值 | 趋势 |
|------|--------|------|
| Artifact 数量 | {sum(m.get('total', 0) for m in artifact_metrics if m):.0f} | - |
| 空洞率 | {artifact_trends['avg_invariant_violation_rate']:.1%} | {artifact_trends['trend_direction']} |
| 信息增益 | {artifact_trends['avg_success_rate']:.2f} | - |

### 2.2 每日数据

| Day | Artifacts | 空洞率 | 信息增益 |
|-----|-----------|--------|----------|
"""
    
    for i, m in enumerate(artifact_metrics, 1):
        if m:
            report += f"| {i} | {m.get('total', 0)} | {m.get('empty_rate', 0):.1%} | {m.get('information_gain', 0):.2f} |\n"
        else:
            report += f"| {i} | N/A | N/A | N/A |\n"
    
    # Phase 2 readiness
    all_mirror_passed = all(
        m and m.get("success_rate", 0) > 0.95 and m.get("invariant_violation_rate", 1) < 0.01
        for m in mirror_metrics if m
    )
    all_artifact_passed = all(
        m and m.get("total", 0) > 0 and m.get("information_gain", 0) > 0.3
        for m in artifact_metrics if m
    )
    
    report += f"""
---

## 3. Phase 2 准入判定

### 3.1 准入条件

| 条件 | 要求 | 实际 | 状态 |
|------|------|------|------|
| 镜像成功率 | >95% | {mirror_trends['avg_success_rate']:.2%} | {'✅' if mirror_trends['avg_success_rate'] > 0.95 else '❌'} |
| 不变量违规率 | <1% | {mirror_trends['avg_invariant_violation_rate']:.2%} | {'✅' if mirror_trends['avg_invariant_violation_rate'] < 0.01 else '❌'} |
| Artifact 数量 | >0 | {sum(m.get('total', 0) for m in artifact_metrics if m)} | {'✅' if sum(m.get('total', 0) for m in artifact_metrics if m) > 0 else '❌'} |
| Artifact 信息增益 | >0.3 | {artifact_trends['avg_success_rate']:.2f} | {'✅' if artifact_trends['avg_success_rate'] > 0.3 else '❌'} |

### 3.2 最终判定

"""
    
    if all_mirror_passed and all_artifact_passed:
        report += """**裁决**: ✅ **PHASE 2 READY**

所有准入条件满足，建议进入 Phase 2（双写比对）。

**后续步骤**:
1. 人工审核 shadow artifacts 样本
2. 设置 `ENABLE_MVP13_DUAL_WRITE=true`
3. 开始 Phase 2 验证
4. 每日对比双写一致性
"""
    else:
        report += """**裁决**: ❌ **PHASE 2 NOT READY**

存在未满足的条件，需要继续观察或修复。

**建议**:
1. 检查未满足项的具体原因
2. 优化镜像或 artifact 生成逻辑
3. 延长观察期
"""
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror-reports", type=str, default="artifacts/mvp13/daily_reports")
    parser.add_argument("--artifact-reports", type=str, default="artifacts/mvp15/daily_reports")
    parser.add_argument("--output", type=str, default="artifacts/verification")
    args = parser.parse_args()
    
    print("=== MVP13 7-Day Observation Summary ===")
    
    # Load daily metrics
    mirror_metrics = load_daily_metrics(Path(args.mirror_reports))
    artifact_metrics = load_daily_metrics(Path(args.artifact_reports))
    
    # Calculate trends
    mirror_trends = calculate_trends(mirror_metrics)
    artifact_trends = calculate_trends(artifact_metrics)
    
    # Generate report
    report = generate_summary_report(
        mirror_trends,
        artifact_trends,
        mirror_metrics,
        artifact_metrics,
    )
    
    # Save report
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = output_dir / "MVP13_PHASE2_READINESS_REPORT.md"
    with open(report_path, "w") as f:
        f.write(report)
    
    # Also save as MIRROR_OBSERVATION_SUMMARY_7D.md
    summary_path = output_dir / "MIRROR_OBSERVATION_SUMMARY_7D.md"
    with open(summary_path, "w") as f:
        f.write(report)
    
    # Save artifact trend
    artifact_trend_path = output_dir / "MVP15_ARTIFACT_TREND_7D.md"
    with open(artifact_trend_path, "w") as f:
        f.write(f"# MVP15 Artifact Quality Trend (7-Day)\n\n")
        f.write(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(f"总 Artifacts: {sum(m.get('total', 0) for m in artifact_metrics if m)}\n")
        f.write(f"平均空洞率: {artifact_trends['avg_invariant_violation_rate']:.1%}\n")
        f.write(f"平均信息增益: {artifact_trends['avg_success_rate']:.2f}\n")
    
    print(f"\nReport saved to: {report_path}")
    print(f"Summary saved to: {summary_path}")
    print(f"Trend saved to: {artifact_trend_path}")


if __name__ == "__main__":
    main()
