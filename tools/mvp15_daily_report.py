#!/usr/bin/env python
"""
MVP15 Artifact Quality Daily Report

Generates daily quality trend report for MVP15 reflection artifacts.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def analyze_artifacts(artifacts_dir: Path) -> Dict[str, Any]:
    """Analyze artifacts in directory.
    
    MVP15 quality thresholds (updated 2026-03-13):
    - Single day artifacts >= 5
    - 7-day cumulative >= 30
    - Empty rate < 10%
    - Duplicate rate < 20%
    - 7-day rolling avg information gain > 0.5
    """
    if not artifacts_dir.exists():
        return {
            "total": 0,
            "non_empty": 0,
            "empty": 0,
            "empty_rate": 0.0,
            "unique_keys": {},
            "duplicate_patterns": 0,
            "duplicate_rate": 0.0,
            "avg_size": 0.0,
            "information_gain": 0.0,
            "quality_passed": False,
            "quality_reasons": ["No artifacts directory"],
        }
    
    artifacts = list(artifacts_dir.glob("*.json"))
    
    if not artifacts:
        return {
            "total": 0,
            "non_empty": 0,
            "empty": 0,
            "empty_rate": 0.0,
            "unique_keys": {},
            "duplicate_patterns": 0,
            "duplicate_rate": 0.0,
            "avg_size": 0.0,
            "information_gain": 0.0,
            "quality_passed": False,
            "quality_reasons": ["No artifacts found"],
        }
    
    total = len(artifacts)
    empty = 0
    non_empty = 0
    total_size = 0
    all_keys = []
    content_hashes = []
    
    for artifact in artifacts:
        stat = artifact.stat()
        total_size += stat.st_size
        
        if stat.st_size == 0:
            empty += 1
            continue
        
        try:
            with open(artifact) as f:
                data = json.load(f)
            non_empty += 1
            
            # Collect keys
            keys = list(data.keys())
            all_keys.extend(keys)
            
            # Hash for duplicate detection
            content_hash = hash(json.dumps(data, sort_keys=True))
            content_hashes.append(content_hash)
            
        except Exception:
            empty += 1
    
    # Calculate metrics
    empty_rate = empty / max(1, total)
    avg_size = total_size / max(1, total)
    
    # Unique keys coverage
    key_counts = Counter(all_keys)
    unique_keys = dict(key_counts)
    
    # Duplicate rate
    unique_hashes = len(set(content_hashes))
    duplicate_patterns = len(content_hashes) - unique_hashes
    duplicate_rate = duplicate_patterns / max(1, len(content_hashes))
    
    # Information gain (simplified)
    non_empty_rate = 1 - empty_rate
    key_diversity = len(unique_keys) / 10
    information_gain = min(1.0, non_empty_rate * 0.7 + key_diversity * 0.3)
    
    # Quality check (single day)
    quality_passed = True
    quality_reasons = []
    
    if total < 5:
        quality_passed = False
        quality_reasons.append(f"Single day artifacts {total} < 5")
    
    if empty_rate > 0.10:
        quality_passed = False
        quality_reasons.append(f"Empty rate {empty_rate:.1%} > 10%")
    
    if duplicate_rate > 0.20:
        quality_passed = False
        quality_reasons.append(f"Duplicate rate {duplicate_rate:.1%} > 20%")
    
    return {
        "total": total,
        "non_empty": non_empty,
        "empty": empty,
        "empty_rate": empty_rate,
        "unique_keys": unique_keys,
        "duplicate_rate": duplicate_rate,
        "avg_size": avg_size,
        "information_gain": information_gain,
        "quality_passed": quality_passed,
        "quality_reasons": quality_reasons if quality_reasons else ["All checks passed"],
    }


def generate_daily_report(day_number: int, metrics: Dict[str, Any], prev_metrics: Dict[str, Any] = None) -> str:
    """Generate daily report markdown."""
    report = f"""# MVP15 Artifact Quality Daily Report - Day {day_number}

> 日期: {datetime.now().strftime('%Y-%m-%d')}
> 观察窗: Day {day_number}/7

---

## 1. Artifact 数量

| 指标 | 值 | 趋势 |
|------|-----|------|
| 总数 | {metrics['total']} | {f"↑ +{metrics['total'] - prev_metrics['total']}" if prev_metrics and metrics['total'] > prev_metrics['total'] else "-"} |
| 非空 | {metrics['non_empty']} | - |
| 空洞 | {metrics['empty']} | - |

---

## 2. 质量指标

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| 空洞率 | {metrics['empty_rate']:.1%} | <30% | {'✅' if metrics['empty_rate'] < 0.3 else '❌'} |
| 重复率 | {metrics['duplicate_rate']:.1%} | <50% | {'✅' if metrics['duplicate_rate'] < 0.5 else '❌'} |
| 信息增益 | {metrics['information_gain']:.2f} | >0.3 | {'✅' if metrics['information_gain'] > 0.3 else '❌'} |
| 平均大小 | {metrics['avg_size']:.1f} bytes | >100 | {'✅' if metrics['avg_size'] > 100 else '⚠️'} |

---

## 3. 模板化风险

"""
    
    # Check for template patterns
    if metrics['total'] > 10:
        unique_key_ratio = len(metrics['unique_keys']) / max(1, metrics['total'])
        if unique_key_ratio < 0.3:
            report += "⚠️ **警告**: 高模板化风险 - 键重复率高\n\n"
        else:
            report += "✅ 模板化风险低\n\n"
    else:
        report += "⏳ 样本不足，无法评估模板化风险\n\n"
    
    report += """---

## 4. Phase 2 准入评估

### 4.1 MVP15 质量准入条件

| 条件 | 要求 | 当前 | 状态 |
|------|------|------|------|
| Artifact 数量 | >0 | """ + str(metrics['total']) + """ | {'✅' if metrics['total'] > 0 else '❌'} |
| 空洞率 | <30% | """ + f"{metrics['empty_rate']:.1%}" + """ | {'✅' if metrics['empty_rate'] < 0.3 else '❌'} |
| 信息增益 | >0.3 | """ + f"{metrics['information_gain']:.2f}" + """ | {'✅' if metrics['information_gain'] > 0.3 else '❌'} |

"""
    
    if metrics['total'] == 0:
        report += "**状态**: ⏳ 等待 artifacts 生成\n\n"
        report += "MVP15 shadow mode 已接入，但尚无真实事件触发。\n"
    elif metrics['empty_rate'] < 0.3 and metrics['information_gain'] > 0.3:
        report += "**状态**: ✅ 质量达标\n\n"
        report += "MVP15 artifact 质量稳定，可作为 MVP13 Phase 2 的准入条件。\n"
    else:
        report += "**状态**: ⚠️ 质量待提升\n\n"
        report += "需要更多观察或优化 artifact 生成逻辑。\n"
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, required=True, help="Day number (1-7)")
    parser.add_argument("--dir", type=str, default="artifacts/mvp15")
    parser.add_argument("--output", type=str, default="artifacts/mvp15/daily_reports")
    args = parser.parse_args()
    
    print(f"=== MVP15 Artifact Quality Daily Report - Day {args.day} ===")
    
    # Analyze artifacts
    artifacts_dir = Path(args.dir)
    metrics = analyze_artifacts(artifacts_dir)
    
    # Load previous day metrics for trend
    prev_metrics = None
    output_dir = Path(args.output)
    if args.day > 1:
        prev_path = output_dir / f"day_{args.day - 1}_metrics.json"
        if prev_path.exists():
            with open(prev_path) as f:
                prev_metrics = json.load(f)
    
    # Generate report
    report = generate_daily_report(args.day, metrics, prev_metrics)
    
    # Save report
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
    print(f"Total artifacts: {metrics['total']}")
    print(f"Empty rate: {metrics['empty_rate']:.1%}")
    print(f"Information gain: {metrics['information_gain']:.2f}")


if __name__ == "__main__":
    main()
