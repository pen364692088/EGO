#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
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

from app.telegram_bot import TelegramBot, create_bot_from_config
from app.runtime_v2.initiative_scheduler import run_controlled_idle_scheduler
from app.runtime_v2.proactive_delivery import consume_pending_proactive_followup
from app.runtime_v2.proactive_outbox import enqueue_controlled_proactive_outbox
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
    delivery = dict(payload.get("delivery_result") or {})
    outbox = dict(payload.get("outbox_result") or {})
    telegram_result = dict(payload.get("telegram_transport_result") or {})
    first_sent = dict((telegram_result.get("sent_records") or [None])[0] or {})
    lines = [
        "# MVP12 Telegram Proactive Transport",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- session_id: `{payload.get('session_id')}`",
        f"- chat_id: `{payload.get('chat_id')}`",
        f"- simulated_idle_seconds: `{payload.get('simulated_idle_seconds')}`",
        f"- scheduler_status: `{scheduler.get('status')}`",
        f"- delivery_status: `{delivery.get('status')}`",
        f"- outbox_status: `{outbox.get('status')}`",
        f"- telegram_transport_status: `{telegram_result.get('status')}`",
        "",
        "## Telegram Send Record",
        "",
        f"- sent_records: `{len(telegram_result.get('sent_records') or [])}`",
        f"- transport_source: `{first_sent.get('transport_source')}`",
        f"- reply_authority: `{first_sent.get('reply_authority')}`",
        f"- reply_origin: `{first_sent.get('reply_origin')}`",
        f"- last_message_id: `{first_sent.get('last_message_id')}`",
        f"- reply_text: `{first_sent.get('reply_text')}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_proactive_telegram_transport_session(
    *,
    messages: List[str],
    session_id: str,
    chat_id: int,
    simulated_idle_seconds: float,
    output_json: Path,
    telegram_bot: Optional[TelegramBot] = None,
) -> Dict[str, Any]:
    runtime, state, records = await run_runtime_mainline_session(
        messages=messages,
        session_id=session_id,
        transport_source="runtime_harness",
        source="runtime_harness",
    )
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP12 Telegram proactive transport")

    last_activity_at = state.get_chat_state().last_activity_at
    if last_activity_at is None:
        raise RuntimeError("No chat activity timestamp available for Telegram proactive transport")

    bot = telegram_bot or create_bot_from_config()
    owns_bot_lifecycle = telegram_bot is None
    if owns_bot_lifecycle:
        bot.setup()
        assert bot.app is not None
        await bot.app.initialize()

    try:
        bot._runtime_states[session_id] = state
        bot._remember_session_transport_binding(session_id, chat_id)

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
        delivery_result = consume_pending_proactive_followup(
            session_id=session_id,
            state=state,
            now_ts=scheduler_now + 1.0,
            delivery_mode="controlled_artifact_only",
            transport_source="controlled_runner",
        )
        emitted_delivery = dict(delivery_result.to_dict().get("emitted_delivery") or {})
        outbox_result = enqueue_controlled_proactive_outbox(
            session_id=session_id,
            state=state,
            emitted_delivery=emitted_delivery,
            now_ts=scheduler_now + 2.0,
            outbox_lane="host_proactive_outbox",
        )
        telegram_transport_result = await bot.drain_pending_proactive_outbox_to_telegram(
            session_id,
            chat_id=chat_id,
            finalize_evidence=False,
        )
    finally:
        if owns_bot_lifecycle and bot.app is not None:
            await bot.app.shutdown()

    payload = {
        "schema_version": "mvp12.telegram_proactive_transport.v1",
        "generated_at": datetime.now().isoformat(),
        "session_id": session_id,
        "chat_id": chat_id,
        "observation_count": len(records),
        "simulated_idle_seconds": simulated_idle_seconds,
        "scheduler_result": scheduler_result.to_dict(),
        "delivery_result": delivery_result.to_dict(),
        "outbox_result": outbox_result.to_dict(),
        "telegram_transport_result": telegram_transport_result,
        "pending_proactive_followup": state.get_pending_proactive_followup(),
        "pending_proactive_outbox_events": state.peek_proactive_outbox_events(),
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(output_json.with_suffix(".md"), payload)
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Send an MVP12 host-governed proactive outbox event through Telegram transport.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument("--chat-id", type=int, required=True, help="Telegram chat ID to receive the proactive send")
    parser.add_argument("--session-id", default=None, help="Session ID to use; defaults to telegram:dm:<chat-id>")
    parser.add_argument("--idle-seconds", type=float, default=900.0)
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "telegram_proactive_transport_current.json"),
    )
    args = parser.parse_args()

    session_id = args.session_id or f"telegram:dm:{args.chat_id}"
    payload = await run_proactive_telegram_transport_session(
        messages=_load_messages(args),
        session_id=session_id,
        chat_id=args.chat_id,
        simulated_idle_seconds=args.idle_seconds,
        output_json=Path(args.output_json),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
