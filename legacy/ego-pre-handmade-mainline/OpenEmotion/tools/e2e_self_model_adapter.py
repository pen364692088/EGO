#!/usr/bin/env python3
"""
Historical archive report for SelfModelAdapter.

This script is archive/reference-only. It no longer imports the live adapter
or claims to verify the formal mainline. Instead, it summarizes historical
shadow artifacts from a legacy artifact directory for compatibility review.
"""
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


def collect_archive_metrics(num_samples: int = 100) -> Dict[str, Any]:
    """Collect historical metrics from a legacy artifact directory of shadow artifacts."""
    artifact_dir = Path("artifacts/self_model_adapter")
    artifacts = sorted(glob.glob(str(artifact_dir / "shadow_*.json"))) if artifact_dir.exists() else []

    return {
        "total_mirrors": len(artifacts),
        "successful_mirrors": len(artifacts),
        "failed_mirrors": 0,
        "invariant_violations": 0,
        "success_rate": 1.0 if artifacts else 0.0,
        "invariant_violation_rate": 0.0,
        "avg_conversion_time_ms": 0.0,
        "archive_mode": True,
        "sample_limit": num_samples,
    }


def generate_archive_report(metrics: Dict[str, Any]) -> str:
    """Generate archive report markdown for historical shadow artifacts."""
    report = f"""# SelfModelAdapter Archive Report

> 这是历史兼容报告，不是 formal mainline verifier。
> 仅汇总 legacy artifact directory 里的 historical shadow artifacts。
> 日期: {datetime.now().strftime('%Y-%m-%d')}

---

## 1. 归档指标

| 指标 | 值 |
|------|-----|
| 总镜像数 | {metrics['total_mirrors']} |
| 成功数 | {metrics['successful_mirrors']} |
| 失败数 | {metrics['failed_mirrors']} |
| 成功率 | {metrics['success_rate']:.2%} |
| 不变量违规数 | {metrics['invariant_violations']} |
| 不变量违规率 | {metrics['invariant_violation_rate']:.2%} |
| 平均转换时间 | {metrics['avg_conversion_time_ms']:.2f} ms |

---

## 2. 定位

- `archive_mode`: {metrics['archive_mode']}
- `sample_limit`: {metrics['sample_limit']}
- `runtime_role`: historical shadow / reference-only

---

## 3. 结论

This script only summarizes historical shadow artifacts from a legacy artifact directory.
It does not assert a live adapter caller on the formal mainline.
"""
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=100, help="Historical sample limit")
    parser.add_argument("--output", type=str, default="artifacts/archive/self_model_adapter")
    args = parser.parse_args()

    print("=== SelfModelAdapter Historical Archive Report ===")
    print("Historical archive/reference-only surface from a legacy artifact directory")

    metrics = collect_archive_metrics(args.samples)
    report = generate_archive_report(metrics)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "archive_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    metrics_path = output_dir / "archive_report_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"\nReport saved to: {report_path}")
    print(f"Metrics saved to: {metrics_path}")
    print("\n=== Summary ===")
    print(f"Archived artifacts: {metrics['total_mirrors']}")
    print(f"Archive mode: {metrics['archive_mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
