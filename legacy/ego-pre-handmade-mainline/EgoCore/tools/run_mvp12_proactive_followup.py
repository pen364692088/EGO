#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


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

from app.runtime_v2.initiative_arbiter import evaluate_proactive_followup
from runtime_mainline_observation_common import run_runtime_mainline_session


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp12"


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
        "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？",
        "有主观能动性。",
        "我觉得是有了OS的操作员的感觉。",
    ]


def _trim_text(text: Any, *, limit: int = 72) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


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
            "kind": "reflective_thread",
            "label": _trim_text(latest.get("ingress_text"), limit=48),
            "intensity": 0.78,
        }
    ]


def _derive_long_term_goals(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not records:
        return []
    latest = records[-1]
    return [
        {
            "label": f"continue:{_trim_text(latest.get('ingress_text'), limit=32)}",
            "pressure": 0.74,
        }
    ]


def _write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    verdict = dict(payload.get("initiative_verdict") or {})
    selected = dict(verdict.get("selected_candidate") or {})
    lines = [
        "# MVP12 Proactive Followup Draft",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- session_id: `{payload.get('session_id')}`",
        f"- idle_seconds: `{payload.get('idle_seconds')}`",
        f"- verdict_status: `{verdict.get('status')}`",
        f"- verdict_reason: `{verdict.get('reason')}`",
        "",
        "## Draft",
        "",
        f"- delivery_ready: `{verdict.get('delivery_ready')}`",
        f"- draft_reply_text: `{verdict.get('draft_reply_text')}`",
        "",
        "## Candidate",
        "",
        f"- candidate_id: `{selected.get('candidate_id')}`",
        f"- candidate_type: `{selected.get('candidate_type')}`",
        f"- initiative_score: `{selected.get('initiative_score')}`",
        f"- source_cycle: `{selected.get('source_cycle')}`",
        "",
        "## Developmental",
        "",
        f"- cycle_id: `{(payload.get('developmental_summary') or {}).get('cycle_id')}`",
        f"- gate_status: `{(payload.get('developmental_summary') or {}).get('gate_status')}`",
        f"- background_thought_candidate_count: `{(payload.get('developmental_summary') or {}).get('background_thought_candidate_count')}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run controlled MVP12 proactive followup draft generation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp12:proactive:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument("--idle-seconds", type=float, default=900.0)
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "proactive_followup_current.json"),
    )
    args = parser.parse_args()

    payload = await run_proactive_followup_session(
        messages=_load_messages(args),
        session_id=args.session_id,
        idle_seconds=args.idle_seconds,
        output_json=Path(args.output_json),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


async def run_proactive_followup_session(
    *,
    messages: List[str],
    session_id: str,
    idle_seconds: float,
    output_json: Path,
) -> Dict[str, Any]:
    runtime, state, records = await run_runtime_mainline_session(
        messages=messages,
        session_id=session_id,
        transport_source="runtime_harness",
        source="runtime_harness",
    )
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP12 proactive followup draft")

    developmental_result = runtime.proto_self_runtime.process_developmental_tick(
        session_id=session_id,
        turn_id="turn_proactive_followup",
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

    verdict = evaluate_proactive_followup(
        state=state,
        developmental_result=developmental_result,
        idle_seconds=idle_seconds,
        controlled_mode=True,
    )
    payload = {
        "schema_version": "mvp12.proactive_followup.v1",
        "generated_at": datetime.now().isoformat(),
        "session_id": session_id,
        "idle_seconds": idle_seconds,
        "observation_count": len(records),
        "developmental_summary": dict(developmental_result.get("developmental_summary") or {}),
        "developmental_gate": dict(developmental_result.get("developmental_gate") or {}),
        "initiative_verdict": verdict.to_dict(),
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(output_json.with_suffix(".md"), payload)
    return payload


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
