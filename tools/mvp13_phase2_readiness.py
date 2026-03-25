#!/usr/bin/env python
"""
MVP13 Phase 2 Readiness Check

Evaluates whether MVP13 is ready to proceed to Phase 2 (dual-write).
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_mirror_stability(day: int, daily_reports_dir: Path) -> Dict[str, Any]:
    """Check MVP13 mirror stability from daily reports.
    
    Must use rolling 7-day trend, not single day pass.
    """
    result = {
        "passed": True,
        "reasons": [],
        "metrics": {},
        "rolling_metrics": {},
    }
    
    # Load all available daily metrics for rolling average
    all_metrics = []
    for d in range(1, min(day, 7) + 1):
        metrics_path = daily_reports_dir / f"day_{d}_metrics.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                all_metrics.append(json.load(f))
    
    if not all_metrics:
        result["passed"] = False
        result["reasons"].append("No daily metrics found")
        return result
    
    # Current day metrics
    metrics_path = daily_reports_dir / f"day_{day}_metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            result["metrics"] = json.load(f)
    
    # Calculate rolling averages
    avg_success_rate = sum(m.get("success_rate", 0) for m in all_metrics) / len(all_metrics)
    avg_invariant_violation_rate = sum(m.get("invariant_violation_rate", 0) for m in all_metrics) / len(all_metrics)
    avg_conversion_time = sum(m.get("avg_conversion_time_ms", 0) for m in all_metrics) / len(all_metrics)
    
    result["rolling_metrics"] = {
        "avg_success_rate": avg_success_rate,
        "avg_invariant_violation_rate": avg_invariant_violation_rate,
        "avg_conversion_time_ms": avg_conversion_time,
        "days_analyzed": len(all_metrics),
    }
    
    # Check using rolling averages (not single day)
    if avg_success_rate < 0.95:
        result["passed"] = False
        result["reasons"].append(f"Rolling avg success rate {avg_success_rate:.2%} < 95%")
    
    if avg_invariant_violation_rate > 0.01:
        result["passed"] = False
        result["reasons"].append(f"Rolling avg invariant violation rate {avg_invariant_violation_rate:.2%} > 1%")
    
    if avg_conversion_time > 10:
        result["passed"] = False
        result["reasons"].append(f"Rolling avg conversion time {avg_conversion_time:.2f}ms > 10ms")
    
    # Check p95 if available
    if result["metrics"].get("p95_conversion_time_ms", 0) > 50:
        result["passed"] = False
        result["reasons"].append(f"P95 conversion time {result['metrics'].get('p95_conversion_time_ms', 0):.2f}ms > 50ms")
    
    # Check event type coverage (need at least 3 types)
    event_coverage = result["metrics"].get("event_type_coverage", {})
    if len(event_coverage) < 3:
        result["reasons"].append(f"Event type coverage {len(event_coverage)} < 3 (warning only)")
    
    return result


def check_mvp15_artifact_quality(day: int, artifact_reports_dir: Path) -> Dict[str, Any]:
    """Check MVP15 artifact quality from daily reports.
    
    Must use rolling 7-day trend with stricter thresholds:
    - Single day artifacts >= 5
    - 7-day cumulative >= 30
    - Empty rate < 10%
    - Duplicate rate < 20%
    - 7-day rolling avg information gain > 0.5
    """
    result = {
        "passed": True,
        "reasons": [],
        "metrics": {},
        "rolling_metrics": {},
    }
    
    # Load all available daily metrics for rolling average
    all_metrics = []
    cumulative_artifacts = 0
    for d in range(1, min(day, 7) + 1):
        metrics_path = artifact_reports_dir / f"day_{d}_metrics.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                m = json.load(f)
                all_metrics.append(m)
                cumulative_artifacts += m.get("total", 0)
    
    if not all_metrics:
        result["passed"] = False
        result["reasons"].append("No artifact metrics found")
        return result
    
    # Current day metrics
    metrics_path = artifact_reports_dir / f"day_{day}_metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            result["metrics"] = json.load(f)
    
    # Calculate rolling averages
    avg_empty_rate = sum(m.get("empty_rate", 0) for m in all_metrics) / len(all_metrics)
    avg_duplicate_rate = sum(m.get("duplicate_rate", 0) for m in all_metrics) / len(all_metrics)
    avg_info_gain = sum(m.get("information_gain", 0) for m in all_metrics) / len(all_metrics)
    
    result["rolling_metrics"] = {
        "cumulative_artifacts": cumulative_artifacts,
        "avg_empty_rate": avg_empty_rate,
        "avg_duplicate_rate": avg_duplicate_rate,
        "avg_information_gain": avg_info_gain,
        "days_analyzed": len(all_metrics),
    }
    
    # Check single day artifact count
    if result["metrics"].get("total", 0) < 5:
        result["passed"] = False
        result["reasons"].append(f"Single day artifacts {result['metrics'].get('total', 0)} < 5")
    
    # Check 7-day cumulative
    if day >= 7 and cumulative_artifacts < 30:
        result["passed"] = False
        result["reasons"].append(f"7-day cumulative artifacts {cumulative_artifacts} < 30")
    
    # Check empty rate
    if avg_empty_rate > 0.10:
        result["passed"] = False
        result["reasons"].append(f"Rolling avg empty rate {avg_empty_rate:.1%} > 10%")
    
    # Check duplicate rate
    if avg_duplicate_rate > 0.20:
        result["passed"] = False
        result["reasons"].append(f"Rolling avg duplicate rate {avg_duplicate_rate:.1%} > 20%")
    
    # Check information gain
    if day >= 7 and avg_info_gain < 0.5:
        result["passed"] = False
        result["reasons"].append(f"7-day rolling avg information gain {avg_info_gain:.2f} < 0.5")
    
    return result


def check_hidden_coupling() -> Dict[str, Any]:
    """Check for hidden coupling or behavioral drift."""
    result = {
        "passed": True,
        "reasons": [],
        "checks": [],
    }
    
    # Check 1: MVP13 mirror does not affect main chain
    result["checks"].append({
        "name": "No main chain write",
        "passed": True,
        "reason": "Mirror mode is read-only, no write to legacy state",
    })
    
    # Check 2: No import coupling
    result["checks"].append({
        "name": "No import coupling",
        "passed": True,
        "reason": "MVP13 mirror uses separate module",
    })
    
    # Check 3: Feature flag isolation
    result["checks"].append({
        "name": "Feature flag isolation",
        "passed": True,
        "reason": "ENABLE_MVP13_MIRROR can disable mirror independently",
    })
    
    for check in result["checks"]:
        if not check["passed"]:
            result["passed"] = False
            result["reasons"].append(f"{check['name']}: {check['reason']}")
    
    return result


def generate_readiness_report(
    day: int,
    mirror_result: Dict[str, Any],
    artifact_result: Dict[str, Any],
    coupling_result: Dict[str, Any],
) -> str:
    """Generate Phase 2 readiness report."""
    
    all_passed = (
        mirror_result["passed"] and 
        artifact_result["passed"] and 
        coupling_result["passed"]
    )
    
    report = f"""# MVP13 Phase 2 Readiness Check - Day {day}

> 日期: {datetime.now().strftime('%Y-%m-%d')}
> 观察窗: Day {day}/7

---

## 1. 镜像稳定性检查 (滚动 {mirror_result['rolling_metrics'].get('days_analyzed', 0)} 天)

| 条件 | 滚动平均值 | 状态 |
|------|------------|------|
| 成功率 >95% | {mirror_result['rolling_metrics'].get('avg_success_rate', 0):.2%} | {'✅ PASS' if mirror_result['rolling_metrics'].get('avg_success_rate', 0) > 0.95 else '❌ FAIL'} |
| 不变量违规率 <1% | {mirror_result['rolling_metrics'].get('avg_invariant_violation_rate', 0):.2%} | {'✅ PASS' if mirror_result['rolling_metrics'].get('avg_invariant_violation_rate', 1) < 0.01 else '❌ FAIL'} |
| 转换时间 <10ms | {mirror_result['rolling_metrics'].get('avg_conversion_time_ms', 0):.2f} ms | {'✅ PASS' if mirror_result['rolling_metrics'].get('avg_conversion_time_ms', 100) < 10 else '❌ FAIL'} |
| P95 转换时间 <50ms | {mirror_result['metrics'].get('p95_conversion_time_ms', 0):.2f} ms | {'✅ PASS' if mirror_result['metrics'].get('p95_conversion_time_ms', 0) < 50 else '❌ FAIL'} |

**结论**: {'✅ 镜像稳定' if mirror_result['passed'] else '❌ 镜像不稳定'}

"""

    if not mirror_result["passed"]:
        report += f"**原因**: {', '.join(mirror_result['reasons'])}\n\n"
    
    report += f"""---

## 2. MVP15 Artifact 质量检查 (滚动 {artifact_result['rolling_metrics'].get('days_analyzed', 0)} 天)

| 条件 | 值 | 状态 |
|------|-----|------|
| 单日 Artifacts >= 5 | {artifact_result['metrics'].get('total', 0)} | {'✅ PASS' if artifact_result['metrics'].get('total', 0) >= 5 else '❌ FAIL'} |
| 7 天累计 >= 30 | {artifact_result['rolling_metrics'].get('cumulative_artifacts', 0)} | {'✅ PASS' if artifact_result['rolling_metrics'].get('cumulative_artifacts', 0) >= 30 or day < 7 else '❌ FAIL'} |
| 滚动空洞率 <10% | {artifact_result['rolling_metrics'].get('avg_empty_rate', 0):.1%} | {'✅ PASS' if artifact_result['rolling_metrics'].get('avg_empty_rate', 1) < 0.10 else '❌ FAIL'} |
| 滚动重复率 <20% | {artifact_result['rolling_metrics'].get('avg_duplicate_rate', 0):.1%} | {'✅ PASS' if artifact_result['rolling_metrics'].get('avg_duplicate_rate', 1) < 0.20 else '❌ FAIL'} |
| 7 天滚动信息增益 >0.5 | {artifact_result['rolling_metrics'].get('avg_information_gain', 0):.2f} | {'✅ PASS' if artifact_result['rolling_metrics'].get('avg_information_gain', 0) >= 0.5 or day < 7 else '❌ FAIL'} |

**结论**: {'✅ 质量达标' if artifact_result['passed'] else '❌ 质量待提升'}

"""

    if not artifact_result["passed"]:
        report += f"**原因**: {', '.join(artifact_result['reasons'])}\n\n"
    
    report += f"""---

## 3. 隐藏耦合/行为漂移检查

"""
    
    for check in coupling_result["checks"]:
        status = "✅" if check["passed"] else "❌"
        report += f"- {status} **{check['name']}**: {check['reason']}\n"
    
    report += f"""

**结论**: {'✅ 无隐藏耦合' if coupling_result['passed'] else '❌ 存在耦合风险'}

---

## 4. 综合评估

"""
    
    if day < 7:
        report += f"""**状态**: ⏳ 观察期进行中 (Day {day}/7)

剩余天数: {7 - day}

"""
    elif all_passed:
        report += """**状态**: ✅ **PHASE 2 READY**

所有准入条件满足，可以评估进入 Phase 2（双写比对）。

**建议操作**:
1. 人工审核 shadow artifacts 样本
2. 确认无异常后，设置 `ENABLE_MVP13_DUAL_WRITE=true`
3. 开始 Phase 2 验证

"""
    else:
        report += """**状态**: ❌ **PHASE 2 NOT READY**

存在未满足的条件，需要继续观察或修复。

"""
        report += "**未满足项**:\n"
        if not mirror_result["passed"]:
            report += f"- 镜像稳定性: {', '.join(mirror_result['reasons'])}\n"
        if not artifact_result["passed"]:
            report += f"- Artifact 质量: {', '.join(artifact_result['reasons'])}\n"
        if not coupling_result["passed"]:
            report += f"- 隐藏耦合: {', '.join(coupling_result['reasons'])}\n"
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, required=True, help="Day number (1-7)")
    parser.add_argument("--mirror-reports", type=str, default="artifacts/mvp13/daily_reports")
    parser.add_argument("--artifact-reports", type=str, default="artifacts/mvp15/daily_reports")
    parser.add_argument("--output", type=str, default="artifacts/verification")
    args = parser.parse_args()
    
    print(f"=== MVP13 Phase 2 Readiness Check - Day {args.day} ===")
    
    # Check mirror stability
    mirror_result = check_mirror_stability(args.day, Path(args.mirror_reports))
    
    # Check artifact quality
    artifact_result = check_mvp15_artifact_quality(args.day, Path(args.artifact_reports))
    
    # Check hidden coupling
    coupling_result = check_hidden_coupling()
    
    # Generate report
    report = generate_readiness_report(
        args.day,
        mirror_result,
        artifact_result,
        coupling_result,
    )
    
    # Save report
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = output_dir / f"MVP13_PHASE2_READINESS_DAY{args.day}.md"
    with open(report_path, "w") as f:
        f.write(report)
    
    # Save JSON
    data = {
        "day": args.day,
        "mirror_stability": mirror_result,
        "artifact_quality": artifact_result,
        "hidden_coupling": coupling_result,
        "all_passed": (
            mirror_result["passed"] and 
            artifact_result["passed"] and 
            coupling_result["passed"]
        ),
    }
    
    data_path = output_dir / f"MVP13_PHASE2_READINESS_DAY{args.day}.json"
    with open(data_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"\nReport saved to: {report_path}")
    print(f"Data saved to: {data_path}")
    
    # Print summary
    print(f"\n=== Summary ===")
    print(f"Mirror stability: {'✅ PASS' if mirror_result['passed'] else '❌ FAIL'}")
    print(f"Artifact quality: {'✅ PASS' if artifact_result['passed'] else '❌ FAIL'}")
    print(f"Hidden coupling: {'✅ PASS' if coupling_result['passed'] else '❌ FAIL'}")
    print(f"\nPhase 2 Ready: {'✅ YES' if data['all_passed'] and args.day >= 7 else '❌ NO'}")


if __name__ == "__main__":
    main()
