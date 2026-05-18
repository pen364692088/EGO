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

from app.runtime_v2.initiative_scheduler import run_controlled_idle_scheduler
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


def _write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    scheduler = dict(payload.get("scheduler_result") or {})
    pending = dict(payload.get("pending_proactive_followup") or {})
    verdict = dict((pending.get("initiative_verdict") or {}).get("output_verdict") or {})
    lines = [
        "# MVP12 Controlled Idle Scheduler",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- session_id: `{payload.get('session_id')}`",
        f"- simulated_idle_seconds: `{payload.get('simulated_idle_seconds')}`",
        f"- scheduler_status: `{scheduler.get('status')}`",
        f"- scheduler_reason: `{scheduler.get('reason')}`",
        "",
        "## Pending Draft",
        "",
        f"- pending_exists: `{bool(pending)}`",
        f"- created_at: `{pending.get('created_at')}`",
        f"- delivery_status: `{pending.get('delivery_status')}`",
        f"- draft_reply_text: `{verdict.get('reply_text')}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_idle_scheduler_session(
    *,
    messages: List[str],
    session_id: str,
    simulated_idle_seconds: float,
    output_json: Path,
) -> Dict[str, Any]:
    runtime, state, records = await run_runtime_mainline_session(
        messages=messages,
        session_id=session_id,
        transport_source="runtime_harness",
        source="runtime_harness",
    )
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP12 controlled idle scheduler")

    last_activity_at = state.get_chat_state().last_activity_at
    if last_activity_at is None:
        raise RuntimeError("No chat activity timestamp available for controlled idle scheduler")

    scheduler_now = last_activity_at + simulated_idle_seconds
    scheduler_result = run_controlled_idle_scheduler(
        session_id=session_id,
        state=state,
        proto_self_runtime=runtime.proto_self_runtime,
        now_ts=scheduler_now,
        min_idle_seconds=600.0,
        observation_source="direct_real",
        controlled_mode=True,
    )
    payload = {
        "schema_version": "mvp12.idle_scheduler.v1",
        "generated_at": datetime.now().isoformat(),
        "session_id": session_id,
        "observation_count": len(records),
        "simulated_idle_seconds": simulated_idle_seconds,
        "scheduler_result": scheduler_result.to_dict(),
        "pending_proactive_followup": state.get_pending_proactive_followup(),
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(output_json.with_suffix(".md"), payload)
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run controlled MVP12 idle scheduler and persist a pending proactive draft.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp12:idle_scheduler:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument("--idle-seconds", type=float, default=900.0)
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "idle_scheduler_current.json"),
    )
    args = parser.parse_args()

    payload = await run_idle_scheduler_session(
        messages=_load_messages(args),
        session_id=args.session_id,
        simulated_idle_seconds=args.idle_seconds,
        output_json=Path(args.output_json),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
