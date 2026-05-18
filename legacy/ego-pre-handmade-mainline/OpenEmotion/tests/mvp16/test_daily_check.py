from __future__ import annotations

import json
from pathlib import Path

import pytest

from emotiond.developmental import get_developmental_manager, reset_developmental_manager
from tools.mvp16_daily_check import (
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_PASS,
    check_admission_inputs,
    check_continuity,
    check_invariants,
    check_metrics,
)


def _write_sample(
    sample_root: Path,
    sample_name: str,
    *,
    text: str,
    timestamp: str,
    session_id: str,
) -> None:
    sample_dir = sample_root / sample_name
    sample_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "sample_id": sample_name,
        "timestamp": timestamp,
        "source_type": "real_channel",
        "channel": "telegram",
        "raw_update": {
            "update_id": abs(hash(sample_name)) % 100000,
            "message": {
                "message_id": abs(hash(f"{sample_name}:message")) % 100000,
                "date": timestamp,
                "chat": {"id": 8420019401, "type": "private"},
                "from": {"id": 8420019401, "is_bot": False, "username": "moonlight"},
                "text": text,
            },
        },
        "normalized_event": {
            "schema_version": "proto_self.v2",
            "event_id": f"evt_{sample_name}",
            "event": {"raw_text": text},
            "conversation_context": {
                "session_id": session_id,
                "thread_id": session_id,
                "turn_id": f"turn_{sample_name}",
            },
            "conversation_summary": {
                "session_id": session_id,
                "thread_id": session_id,
                "turn_id": f"turn_{sample_name}",
            },
        },
        "openemotion_result": {"schema_version": "proto_self.output.v2", "event_id": f"evt_{sample_name}"},
        "openemotion_trace": {"schema_version": "proto_self.trace.v2", "event_id": f"evt_{sample_name}"},
        "response_plan": {"status": "command_result", "delivery_kind": "reply", "reply_length": len(text)},
        "outbox_record": {
            "chat_id": 8420019401,
            "message_id": abs(hash(f"{sample_name}:reply")) % 100000,
            "date": timestamp,
            "text_length": len(text),
            "success": True,
        },
    }
    ledger = {
        "sample_id": sample_name,
        "timestamp": timestamp,
        "source_type": "real_channel",
        "channel": "telegram",
        "ids": {"session_id": session_id, "thread_id": session_id, "turn_id": f"turn_{sample_name}"},
        "inputs": {
            "raw_update": payload["raw_update"],
            "normalized_event": payload["normalized_event"],
        },
        "openemotion": {
            "result": payload["openemotion_result"],
            "trace_payload": payload["openemotion_trace"],
        },
        "host": {
            "response_plan": payload["response_plan"],
            "outbox_record": payload["outbox_record"],
        },
    }
    replay = {"replay_id": f"replay_{sample_name}", "sample_id": sample_name}

    (sample_dir / "sample.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (sample_dir / "ledger.json").write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    (sample_dir / "replay.json").write_text(json.dumps(replay, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_pass_dataset(sample_root: Path) -> None:
    _write_sample(
        sample_root,
        "sample_20260328_191541_743c02b0",
        text="/new",
        timestamp="2026-03-28T19:15:41+00:00",
        session_id="telegram:dm:8420019401",
    )
    _write_sample(
        sample_root,
        "sample_20260328_191554_f778b476",
        text="你好啊",
        timestamp="2026-03-28T19:15:54+00:00",
        session_id="telegram:dm:8420019401",
    )
    _write_sample(
        sample_root,
        "sample_20260328_192536_a18d7479",
        text="你叫什么名字?",
        timestamp="2026-03-28T19:25:36+00:00",
        session_id="telegram:dm:8420019401",
    )
    _write_sample(
        sample_root,
        "sample_20260329_091500_eeee1111",
        text="/new",
        timestamp="2026-03-29T09:15:00+00:00",
        session_id="telegram:dm:8420019401",
    )
    _write_sample(
        sample_root,
        "sample_20260329_091510_ffff2222",
        text="今天心情如何?",
        timestamp="2026-03-29T09:15:10+00:00",
        session_id="telegram:dm:8420019401:reset-2",
    )


class TestDailyCheckAdmissionSemantics:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        reset_developmental_manager()
        yield
        reset_developmental_manager()

    def test_daily_check_stays_blocked_without_real_mainline_projection(self, tmp_path):
        manager = get_developmental_manager(state_path=tmp_path / "state.json")
        manager.record_episode("manual", "MVP16")
        manager.update_metric("continuity_score", 0.9)

        continuity = check_continuity()
        metrics = check_metrics()
        invariants = check_invariants()
        admission = check_admission_inputs()

        assert continuity["status"] == STATUS_INSUFFICIENT_EVIDENCE
        assert metrics["status"] == STATUS_INSUFFICIENT_EVIDENCE
        assert invariants["status"] == STATUS_INSUFFICIENT_EVIDENCE
        assert admission["status"] == STATUS_INSUFFICIENT_EVIDENCE

    def test_daily_check_passes_when_minimum_admission_inputs_exist(self, tmp_path):
        state_path = tmp_path / "developmental_state.json"
        sample_root = tmp_path / "real_telegram"
        observation_dir = tmp_path / "observation"
        _build_pass_dataset(sample_root)

        manager = get_developmental_manager(state_path=state_path)
        manager.sync_real_projection_from_sample_artifacts(
            sample_artifacts_dir=sample_root,
            observation_dir=observation_dir,
        )

        continuity = check_continuity()
        metrics = check_metrics()
        invariants = check_invariants()
        admission = check_admission_inputs()

        assert continuity["status"] == STATUS_PASS
        assert continuity["real_episode_count"] == 3
        assert continuity["real_session_count"] == 2
        assert continuity["real_day_count"] == 2
        assert metrics["status"] == STATUS_PASS
        assert invariants["status"] == STATUS_PASS
        assert admission["status"] == STATUS_PASS
        assert admission["admission_inputs_present"] is True
