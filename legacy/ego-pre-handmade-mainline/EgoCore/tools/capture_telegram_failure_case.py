#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _load_events(session_log_path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in session_log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def _find_turn(events: List[Dict[str, Any]], message_id: int) -> Dict[str, Any]:
    ingress = next(
        (event for event in events if event.get("kind") == "telegram_ingress" and event.get("message_id") == message_id),
        None,
    )
    if ingress is None:
        raise SystemExit(f"message_id={message_id} not found in telegram_ingress events")

    neighbors = [
        event for event in events
        if abs(int(event.get("message_id") or -1) - message_id) <= 2 or event.get("trace_id") == ingress.get("trace_id")
    ]
    return {"ingress": ingress, "neighbors": neighbors}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Telegram failure-case fixture draft from session logs.")
    parser.add_argument("--session-log", required=True, help="Path to data/session_logs/*.jsonl")
    parser.add_argument("--message-id", required=True, type=int, help="Telegram message_id of the failed turn")
    parser.add_argument("--case-id", required=True, help="Fixture case id")
    parser.add_argument("--out", default=None, help="Optional output path")
    args = parser.parse_args()

    session_log_path = Path(args.session_log).resolve()
    events = _load_events(session_log_path)
    turn = _find_turn(events, args.message_id)

    default_out = (
        session_log_path.parents[1]
        / "tests"
        / "fixtures"
        / "telegram_failure_cases"
        / f"{args.case_id}.json"
    )
    out_path = Path(args.out).resolve() if args.out else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ingress_payload = turn["ingress"].get("payload") or {}
    draft = {
        "case_id": args.case_id,
        "description": "TODO: fill real failure description",
        "initial_state": {
          "session_key": turn["ingress"]["session_key"],
          "task_status": "TODO",
          "waiting_for_user_input": True,
          "last_inferred_action": "TODO",
          "pending_artifacts": []
        },
        "turn": {
            "message_id": args.message_id,
            "text": ingress_payload.get("text_preview") or "",
        },
        "expected": {
            "runtime_action": "TODO",
            "primary_path": "TODO",
            "resolved_target_artifact_id": "TODO",
            "reply_text": "TODO"
        },
        "source": {
            "session_log": str(session_log_path),
            "message_id": args.message_id,
            "neighbor_events": turn["neighbors"],
        },
    }
    out_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
