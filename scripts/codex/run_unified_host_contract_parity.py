#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "EgoCore") not in sys.path:
    sys.path.insert(0, str(ROOT / "EgoCore"))
if str(ROOT / "OpenEmotion") not in sys.path:
    sys.path.insert(0, str(ROOT / "OpenEmotion"))

from app.runtime_v2.unified_host_contract_parity import run_unified_host_contract_parity


ARTIFACT_ROOT = ROOT / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"
DEFAULT_JSON = ARTIFACT_ROOT / "UNIFIED_HOST_CONTRACT_PARITY_CURRENT.json"
DEFAULT_MD = ARTIFACT_ROOT / "UNIFIED_HOST_CONTRACT_PARITY_CURRENT.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run in-process dashboard vs telegram-prepared host contract parity")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    return parser.parse_args()


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _format_diff_item(diff: Dict[str, Any]) -> str:
    return f"- `{diff.get('path')}`: left={diff.get('left')!r} right={diff.get('right')!r}"


def _render_markdown(report: Dict[str, Any]) -> str:
    aggregate = dict(report.get("aggregate") or {})
    lines = [
        "# Unified Host Contract Parity",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- source: `{report.get('source')}`",
        f"- claim_ceiling: `{report.get('claim_ceiling')}`",
        f"- contract_version: `{report.get('contract_version')}`",
        f"- verdict: `{aggregate.get('verdict')}`",
        f"- parity_pass_count: `{aggregate.get('parity_pass_count')}` / `{aggregate.get('total_cases')}`",
        f"- hold_consistency_pass_count: `{aggregate.get('hold_consistency_pass_count')}` / `{aggregate.get('hold_case_count')}`",
        "",
        "## Allowed adapter-only differences",
        "",
    ]
    for item in list((report.get("cases") or [{}])[0].get("comparison", {}).get("allowed_adapter_fields", [])) or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Case Results", ""])
    for case in list(report.get("cases") or []):
        lines.append(f"### `{case.get('case_id')}`")
        lines.append("")
        lines.append(f"- window: `{case.get('window')}`")
        lines.append(f"- text: `{case.get('text')}`")
        lines.append(f"- expected_mode: `{case.get('expected_mode')}`")
        lines.append(f"- parity_match: `{case.get('parity_match')}`")
        if case.get("hold_consistent") is not None:
            lines.append(f"- hold_consistent: `{case.get('hold_consistent')}`")
        unexpected = list(dict(case.get("comparison") or {}).get("unexpected_diffs") or [])
        if unexpected:
            lines.append("- unexpected_diffs:")
            lines.extend(_format_diff_item(item) for item in unexpected)
        else:
            lines.append("- unexpected_diffs: none")
        lines.append("")
    lines.extend(
        [
            "## Claim Ceiling",
            "",
            "- This report proves bounded in-process parity between `dashboard_local` and `telegram_prepared` host contract paths.",
            "- It does not prove fresh real Telegram behavior, `unexpected_subject_miss = 0`, runtime efficacy, or AI self-awareness.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report = run_unified_host_contract_parity()
    report["generated_at"] = datetime.now(UTC).isoformat()
    _write_json(args.output_json, report)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps(report.get("aggregate") or {}, ensure_ascii=False))
    return 0 if dict(report.get("aggregate") or {}).get("verdict") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
