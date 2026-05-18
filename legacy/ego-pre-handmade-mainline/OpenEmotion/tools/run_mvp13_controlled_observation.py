#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
EGOCORE_ROOT = ROOT / "EgoCore"
OPENEMOTION_ROOT = ROOT / "OpenEmotion"
SCRIPTS_ROOT = ROOT / "scripts"
if str(EGOCORE_ROOT) not in sys.path:
    sys.path.insert(0, str(EGOCORE_ROOT))
if str(OPENEMOTION_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENEMOTION_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from openemotion.self_model import SelfModelReplay, SelfModelStore, create_default_self_model
from runtime_mainline_observation_common import (
    append_observation_records,
    run_runtime_mainline_session,
)
from telegram_mainline_common import init_runtime


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp13"
DEFAULT_IDENTITY_HANDLE = "openemotion"


def _git_commit_short() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _trim_text(text: Any, *, limit: int = 72) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _load_messages(args: argparse.Namespace) -> List[str]:
    messages: List[str] = list(args.message or [])
    if args.messages_file:
        content = Path(args.messages_file).read_text(encoding="utf-8")
        if args.messages_file.endswith(".json"):
            payload = json.loads(content)
            if not isinstance(payload, list):
                raise ValueError("messages-file JSON must be a list of strings")
            messages.extend(str(item).strip() for item in payload if str(item).strip())
        else:
            messages.extend(line.strip() for line in content.splitlines() if line.strip())
    if messages:
        return messages
    return [
        "如果记忆一直在，但每次处理它的主体都重新生成，那还是同一个自我吗？",
        "我怀疑我们把“记忆”误当成了“持续存在的证明”。",
        "你觉得呢",
    ]


def _build_state_snapshot(state: Any) -> Dict[str, Any]:
    chat_state = state.get_chat_state()
    return {
        "recent_user_turns": list(chat_state.recent_user_turns[-4:]),
        "recent_assistant_replies": list(chat_state.recent_assistant_replies[-4:]),
        "last_chat_act": chat_state.last_chat_act,
        "active_task_summary": state.build_active_task_summary(),
        "current_goal": state.current_goal,
        "task_status": state.task_status,
    }


def _build_observation_refs(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for record in records[-4:]:
        refs.append(
            {
                "kind": "runtime_mainline_ingress",
                "event_id": record.get("ingress_event_id"),
                "created_at": record.get("ingress_created_at"),
                "text_preview": _trim_text(record.get("ingress_text"), limit=56),
            }
        )
        refs.append(
            {
                "kind": "runtime_mainline_delivery",
                "event_id": record.get("delivery_event_id"),
                "created_at": record.get("delivery_created_at"),
                "text_preview": _trim_text(record.get("delivery_text"), limit=72),
                "reply_authority": record.get("reply_authority"),
                "reply_origin": record.get("reply_origin"),
            }
        )
    return refs


def _derive_unresolved_tensions(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not records:
        return []
    latest = records[-1]
    return [
        {
            "kind": "identity",
            "label": _trim_text(latest.get("ingress_text"), limit=48),
            "intensity": 0.82,
        }
    ]


def _derive_long_term_goals(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not records:
        return []
    latest = records[-1]
    return [
        {
            "label": f"cohere:{_trim_text(latest.get('ingress_text'), limit=32)}",
            "pressure": 0.68,
        }
    ]


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("self_model_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    latest_revision = dict(payload.get("latest_revision") or {})
    scenario = dict(payload.get("scenario_manifest") or {})
    lines = [
        "# MVP13 Controlled Observation Report",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- git_commit_short: `{payload.get('git_commit_short')}`",
        f"- session_id: `{payload.get('session_id')}`",
        f"- observation_count: `{payload.get('observation_count')}`",
        f"- verification_level: `{payload.get('verification_level')}`",
        f"- evidence_level: `{payload.get('evidence_level')}`",
        f"- status: `{payload.get('status')}`",
        "",
    ]
    if scenario:
        lines.extend(
            [
                "## Scenario",
                "",
                f"- scenario_id: `{scenario.get('scenario_id')}`",
                f"- source_class: `{scenario.get('source_class')}`",
                f"- source_ref: `{scenario.get('source_ref')}`",
                f"- dialogue_frame_target: `{scenario.get('dialogue_frame_target')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Developmental",
            "",
            f"- cycle_id: `{(payload.get('developmental_summary') or {}).get('cycle_id')}`",
            f"- gate_status: `{(payload.get('developmental_gate') or {}).get('status')}`",
            f"- self_model_delta_fields: `{payload.get('self_model_delta_fields')}`",
            "",
            "## Writeback",
            "",
            f"- gate_verdict: `{decision.get('gate_verdict')}`",
            f"- accepted: `{decision.get('accepted')}`",
            f"- changed_fields: `{decision.get('changed_fields')}`",
            f"- revision_id: `{latest_revision.get('revision_id')}`",
            f"- trace_reference: `{latest_revision.get('trace_reference')}`",
            "",
            "## Replay",
            "",
            f"- replay_valid: `{payload.get('replay_valid')}`",
            f"- revision_count: `{payload.get('revision_count')}`",
            "",
            "## Boundary",
            "",
            payload.get("boundary", ""),
            "",
        ]
    )
    return "\n".join(lines)


async def run_controlled_observation(
    *,
    messages: List[str],
    session_id: str,
    idle_seconds: float,
    output_json: Optional[Path],
    artifacts_dir: Optional[Path] = None,
    scenario_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP13 controlled observation")

    store = SelfModelStore(base_dir=artifacts_dir / "formal_self_model")
    if not store.exists(DEFAULT_IDENTITY_HANDLE):
        store.save(
            create_default_self_model(DEFAULT_IDENTITY_HANDLE),
            update_source="owner_bootstrap",
            trace_reference="mvp13:controlled_bootstrap",
            confidence_class="high",
        )
    runtime.proto_self_runtime.self_model_store = store

    runtime, state, records = await run_runtime_mainline_session(
        messages=messages,
        session_id=session_id,
        transport_source="runtime_harness",
        source="runtime_harness",
        runtime=runtime,
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    developmental_result = runtime.proto_self_runtime.process_developmental_tick(
        session_id=session_id,
        turn_id="turn_mvp13_controlled",
        state=state,
        observation_source="direct_real",
        trigger="idle",
        idle_seconds=idle_seconds,
        unresolved_tensions=_derive_unresolved_tensions(records),
        long_term_goals=_derive_long_term_goals(records),
        observation_refs=_build_observation_refs(records),
        state_snapshot=_build_state_snapshot(state),
        force_enable=True,
    )
    if developmental_result is None:
        raise RuntimeError("developmental_tick returned no result")

    writeback = dict(developmental_result.get("self_model_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    latest_revision = dict(writeback.get("revision") or {})
    replay = SelfModelReplay(store, identity_handle=DEFAULT_IDENTITY_HANDLE).replay()
    revision_log = store.load_revision_log(DEFAULT_IDENTITY_HANDLE)

    accepted = bool(decision.get("accepted")) and bool(latest_revision)
    payload = {
        "schema_version": "mvp13.controlled_observation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(),
        "session_id": session_id,
        "observation_count": len(records),
        "observation_log": str(observation_log),
        "developmental_summary": developmental_result.get("developmental_summary") or {},
        "developmental_gate": developmental_result.get("developmental_gate") or {},
        "self_model_delta": developmental_result.get("self_model_delta") or {},
        "self_model_delta_fields": sorted((developmental_result.get("self_model_delta") or {}).keys()),
        "self_model_writeback": writeback,
        "latest_revision": latest_revision or None,
        "revision_count": len(revision_log),
        "replay_valid": bool(getattr(replay, "valid_chain", False)),
        "owner_snapshot": store.load_snapshot(DEFAULT_IDENTITY_HANDLE) or {},
        "scenario_manifest": dict(scenario_manifest or {}) or None,
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled mainline-triggered formal owner writeback path. "
            "It does not claim E5 stability or live autonomous authority."
        ),
    }

    report_json = artifacts_dir / "mvp13_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp13_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_md = output_json.with_suffix(".md")
        output_md.write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first controlled MVP13 formal-owner mainline observation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp13:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument("--idle-seconds", type=float, default=900.0)
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp13_controlled_observation_current.json"),
    )
    args = parser.parse_args()

    payload = await run_controlled_observation(
        messages=_load_messages(args),
        session_id=args.session_id,
        idle_seconds=args.idle_seconds,
        output_json=Path(args.output_json),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
