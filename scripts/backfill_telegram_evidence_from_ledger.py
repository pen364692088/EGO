#!/usr/bin/env python3
"""
Safely backfill Telegram evidence mirrors from authoritative ledger.json.

Scope:
- only writes files that can be reconstructed from existing host ledger data
- never invents OpenEmotion semantics outside ledger contents
- may infer a minimal host response_plan from outbox_record when host delivery happened
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

EGO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REAL_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _materialize_from_ledger(sample_dir: Path, *, write: bool) -> Dict[str, Any]:
    ledger_path = sample_dir / "ledger.json"
    if not ledger_path.exists():
        return {"sample_id": sample_dir.name, "changed": [], "missing_in_ledger": ["ledger.json"]}

    ledger = _load_json(ledger_path)
    inputs = ledger.get("inputs") or {}
    openemotion = ledger.get("openemotion") or {}
    host = ledger.get("host") or {}

    changed = []
    missing_in_ledger = []

    mirror_map = {
        "normalized_event.json": inputs.get("normalized_event"),
        "openemotion_result.json": openemotion.get("result"),
        "openemotion_trace.json": openemotion.get("trace_payload"),
        "response_plan.json": host.get("response_plan"),
        "outbox_record.json": host.get("outbox_record"),
        "timeline.json": host.get("timeline"),
    }

    for filename, payload in mirror_map.items():
        target = sample_dir / filename
        if target.exists():
            continue
        if payload:
            if write:
                _save_json(target, payload)
            changed.append(filename)
        else:
            missing_in_ledger.append(filename)

    response_plan_path = sample_dir / "response_plan.json"
    outbox = host.get("outbox_record") or {}
    if not response_plan_path.exists() and outbox:
        inferred_plan = {
            "status": "delivered_without_explicit_plan",
            "delivery_kind": "final",
            "reply_length": int(outbox.get("text_length") or 0),
            "inferred": True,
        }
        if write:
            _save_json(response_plan_path, inferred_plan)
        changed.append("response_plan.json[inferred]")

    if write:
        _refresh_compatibility_mirrors(sample_dir)

    return {
        "sample_id": sample_dir.name,
        "changed": changed,
        "missing_in_ledger": missing_in_ledger,
    }


def _refresh_compatibility_mirrors(sample_dir: Path) -> None:
    ledger = _load_json(sample_dir / "ledger.json")
    sample_json_path = sample_dir / "sample.json"
    sample_data = _load_json(sample_json_path) if sample_json_path.exists() else {}

    sample_data["normalized_event"] = _load_optional_json(sample_dir / "normalized_event.json")
    sample_data["openemotion_result"] = _load_optional_json(sample_dir / "openemotion_result.json")
    sample_data["openemotion_trace"] = _load_optional_json(sample_dir / "openemotion_trace.json")
    sample_data["response_plan"] = _load_optional_json(sample_dir / "response_plan.json")
    sample_data["outbox_record"] = _load_optional_json(sample_dir / "outbox_record.json")
    sample_data["timeline"] = _load_optional_json(sample_dir / "timeline.json") or []
    sample_data["tape"] = _load_optional_json(sample_dir / "tape.json")
    sample_data["replay"] = _load_optional_json(sample_dir / "replay.json")
    sample_data["ledger"] = ledger
    sample_data["ledger_ref"] = "ledger.json"
    sample_data["authority"] = "compatibility_mirror"

    completeness = {
        "raw_update": (sample_dir / "raw_update.json").exists(),
        "normalized_event": (sample_dir / "normalized_event.json").exists(),
        "openemotion_result": (sample_dir / "openemotion_result.json").exists(),
        "openemotion_trace": (sample_dir / "openemotion_trace.json").exists(),
        "response_plan": (sample_dir / "response_plan.json").exists(),
        "outbox_record": (sample_dir / "outbox_record.json").exists(),
        "timeline": (sample_dir / "timeline.json").exists(),
        "tape": (sample_dir / "tape.json").exists(),
        "replay": (sample_dir / "replay.json").exists(),
    }
    sample_data["evidence_completeness"] = completeness
    _save_json(sample_json_path, sample_data)


def _load_optional_json(path: Path) -> Any:
    if not path.exists():
        return None
    return _load_json(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Telegram evidence mirrors from ledger.json")
    parser.add_argument("--sample-id", action="append", dest="sample_ids", help="Specific sample id(s) to backfill")
    parser.add_argument("--window-from", default="20260326", help="Only process sample ids whose date chunk >= this value")
    parser.add_argument("--write", action="store_true", help="Actually write files")
    args = parser.parse_args()

    sample_dirs = sorted(path for path in DEFAULT_REAL_DIR.iterdir() if path.is_dir() and path.name.startswith("sample_"))
    if args.sample_ids:
        wanted = set(args.sample_ids)
        sample_dirs = [path for path in sample_dirs if path.name in wanted]
    else:
        sample_dirs = [path for path in sample_dirs if path.name.split("_")[1] >= args.window_from]

    reports = [_materialize_from_ledger(path, write=args.write) for path in sample_dirs]
    changed = [r for r in reports if r["changed"]]

    print(json.dumps(
        {
            "write": args.write,
            "processed": len(reports),
            "changed_samples": len(changed),
            "changed": changed,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
