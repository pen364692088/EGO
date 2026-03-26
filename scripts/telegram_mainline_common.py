#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

SCRIPT_DIR = Path(__file__).parent
EGO_ROOT = SCRIPT_DIR.parent
EGOCORE_ROOT = EGO_ROOT / "EgoCore"
OPENEMOTION_ROOT = EGO_ROOT / "OpenEmotion"

if str(EGOCORE_ROOT) not in sys.path:
    sys.path.insert(0, str(EGOCORE_ROOT))
if str(OPENEMOTION_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENEMOTION_ROOT))

if TYPE_CHECKING:
    from app.runtime_v2 import RuntimeV2Loop
    from app.telegram_evidence_collector import E4EvidenceSample, TelegramEvidenceCollector


@dataclass
class MainlineRunResult:
    run_id: str
    session_id: str
    evidence_level: str
    source_type: str
    channel: str
    sample_id: Optional[str]
    sample_dir: Optional[str]
    status: str
    reply_text: str
    passed: bool
    missing_evidence: list[str]
    timestamp: str


def init_runtime() -> "RuntimeV2Loop":
    try:
        from app.config import ConfigError, get_config, load_config
        from app.logger import init_logging
        from app.runtime_v2 import RuntimeV2Loop
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Missing Python dependency: {exc.name}. Install EgoCore requirements before running this script."
        ) from exc

    try:
        get_config()
    except ConfigError:
        load_config(
            config_dir=str(EGOCORE_ROOT / "config"),
            env_file=str(EGOCORE_ROOT / ".env"),
            validate=False,
        )
    config = get_config()
    init_logging(config.get("app.logging", {}))

    import app.runtime_v2.loop as loop_module

    if hasattr(loop_module, "_PROTO_SELF_ENABLED"):
        loop_module._PROTO_SELF_ENABLED = None

    return RuntimeV2Loop()


def build_telegram_update(
    text: str,
    *,
    user_id: int = 12345,
    chat_id: int = 67890,
    username: Optional[str] = "test_user",
    simulated: bool = False,
) -> Dict[str, Any]:
    message_id = int(datetime.now().timestamp() * 1000) % 1000000
    update = {
        "update_id": message_id,
        "message": {
            "message_id": message_id,
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": "Test",
                "username": username,
            },
            "chat": {
                "id": chat_id,
                "type": "private",
            },
            "date": int(datetime.now().timestamp()),
            "text": text,
        },
    }
    if simulated:
        update["_simulated"] = True
        update["_simulated_at"] = datetime.now().isoformat()
    return update


def build_outbox_record(update: Dict[str, Any], reply_text: str, *, simulated: bool) -> Dict[str, Any]:
    message = update.get("message", {})
    return {
        "chat_id": message.get("chat", {}).get("id"),
        "message_id": int(message.get("message_id", 0)) + 1,
        "date": datetime.now().isoformat(),
        "text_length": len(reply_text or ""),
        "success": True,
        "delivery_mode": "stubbed" if simulated else "captured",
    }


def sample_missing_evidence(sample: "E4EvidenceSample") -> list[str]:
    completeness = sample.check_completeness()
    return [key for key, present in completeness.items() if not present]


async def run_transport_scenario(
    *,
    text: str,
    artifacts_dir: Path,
    evidence_level: str,
    source_type: str,
    channel: str = "telegram",
    session_id: Optional[str] = None,
    user_id: int = 12345,
    chat_id: int = 67890,
    simulated_delivery: bool = True,
) -> MainlineRunResult:
    try:
        from app.telegram_evidence_collector import TelegramEvidenceCollector
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Missing Python dependency: {exc.name}. Install EgoCore requirements before running this script."
        ) from exc

    runtime = init_runtime()
    session = session_id or f"{source_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    update = build_telegram_update(
        text,
        user_id=user_id,
        chat_id=chat_id,
        simulated=simulated_delivery,
    )
    collector = TelegramEvidenceCollector(
        artifacts_dir=artifacts_dir,
        source_type=source_type,
        channel=channel,
        evidence_level=evidence_level,
    )
    collector.start_sample(update)
    result = await runtime.run_turn_typed(
        session_id=session,
        user_input=text,
        source=channel,
        evidence_collector=collector,
    )
    collector.capture_outbox_record(
        build_outbox_record(update, result.reply_text or "", simulated=simulated_delivery)
    )
    sample = collector.finalize_sample()
    missing = sample_missing_evidence(sample) if sample else ["sample_finalize_failed"]
    return MainlineRunResult(
        run_id=f"{source_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        session_id=session,
        evidence_level=evidence_level,
        source_type=source_type,
        channel=channel,
        sample_id=sample.sample_id if sample else None,
        sample_dir=str(artifacts_dir / sample.sample_id) if sample else None,
        status=result.status,
        reply_text=result.reply_text or "",
        passed=sample.is_complete() if sample else False,
        missing_evidence=missing,
        timestamp=datetime.now().isoformat(),
    )


def load_sample(sample_dir: Path) -> Dict[str, Any]:
    with open(sample_dir / "sample.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_replay_artifact(sample_dir: Path) -> None:
    replay_file = sample_dir / "replay.json"
    if replay_file.exists():
        return
    sample = load_sample(sample_dir)
    replay = sample.get("replay")
    if replay is None:
        replay = {
            "replay_id": f"replay_{sample.get('sample_id')}",
            "timestamp": datetime.now().isoformat(),
            "evidence_level": sample.get("evidence_level"),
            "source_type": sample.get("source_type"),
            "channel": sample.get("channel", "telegram"),
            "sample_id": sample.get("sample_id"),
            "raw_update_ref": "raw_update.json" if (sample_dir / "raw_update.json").exists() else None,
            "normalized_event_ref": "normalized_event.json" if (sample_dir / "normalized_event.json").exists() else None,
            "openemotion_result_ref": "openemotion_result.json" if (sample_dir / "openemotion_result.json").exists() else None,
            "response_plan_ref": "response_plan.json" if (sample_dir / "response_plan.json").exists() else None,
            "outbox_record_ref": "outbox_record.json" if (sample_dir / "outbox_record.json").exists() else None,
            "timeline_ref": "timeline.json" if (sample_dir / "timeline.json").exists() else None,
            "tape_ref": "tape.json" if (sample_dir / "tape.json").exists() else None,
            "replay_hash": sample.get("replay_hash"),
        }
    with open(replay_file, "w", encoding="utf-8") as handle:
        json.dump(replay, handle, indent=2, ensure_ascii=False)


def save_run_report(report_path: Path, payload: Dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)


def serialize_run_result(result: MainlineRunResult) -> Dict[str, Any]:
    return asdict(result)
