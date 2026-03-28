from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import urlopen

from http.server import ThreadingHTTPServer

from app.dashboard.index_builder import build_dashboard_indexes
from app.dashboard.server import DashboardDataStore, DashboardRequestHandler


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_sample(real_dir: Path, sample_id: str, *, oe_available: bool) -> None:
    sample_dir = real_dir / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    ledger = {
        "sample_id": sample_id,
        "timestamp": "2026-03-27T10:00:00+00:00",
        "replay_hash": "hash",
        "ids": {
            "session_id": "telegram:dm:1",
            "thread_id": "telegram:dm:1",
            "event_id": f"evt_{sample_id}",
        },
        "openemotion": {
            "result": {
                "memory_update": {"append_episode": True},
                "appraisal_state_delta": {"caution": 0.3},
                "reflection_note": {
                    "trigger": "drive_spike",
                    "diagnosis": "state change",
                    "proposed_adjustment": {"mode": "review"},
                    "promote_to_memory": False,
                },
                "response_tendency": {
                    "preferred_mode": "ask",
                    "preferred_tone": "cautious",
                    "certainty_bound": "bounded",
                    "suggested_next_step": "prioritize_closure",
                    "ask_needed": True,
                },
            }
            if oe_available
            else {},
            "trace_payload": {
                "reflection_trigger": "drive_spike",
                "cycle_delta": {
                    "closure_family_id": "family-a",
                    "outcome_signature": "success",
                    "repair_closure": False,
                },
            }
            if oe_available
            else {},
            "events": [],
        },
        "host": {
            "response_plan": {"status": "complete", "delivery_kind": "final", "reply_length": 4},
            "outbox_record": {"chat_id": 1, "message_id": 2, "text_length": 4, "success": True},
            "timeline": [{"stage": "message_sent", "timestamp": "2026-03-27T10:00:01+00:00"}],
        },
        "evidence_completeness": {
            "raw_update": True,
            "normalized_event": oe_available,
            "openemotion_result": oe_available,
            "openemotion_trace": oe_available,
            "response_plan": True,
            "outbox_record": True,
            "timeline": True,
            "tape": True,
            "replay": True,
        },
    }
    _write_json(sample_dir / "ledger.json", ledger)
    _write_json(sample_dir / "raw_update.json", {"update_id": 1})
    if oe_available:
        _write_json(sample_dir / "normalized_event.json", {"event_id": f"evt_{sample_id}"})
        _write_json(sample_dir / "openemotion_result.json", ledger["openemotion"]["result"])
        _write_json(sample_dir / "openemotion_trace.json", ledger["openemotion"]["trace_payload"])
    _write_json(sample_dir / "response_plan.json", ledger["host"]["response_plan"])
    _write_json(sample_dir / "outbox_record.json", ledger["host"]["outbox_record"])
    _write_json(sample_dir / "timeline.json", ledger["host"]["timeline"])
    _write_json(sample_dir / "tape.json", {"tape_id": f"tape_{sample_id}"})
    _write_json(sample_dir / "replay.json", {"sample_id": sample_id, "primary_ledger_ref": "ledger.json", "replay_hash": "hash"})
    (sample_dir / "summary.md").write_text("# summary\n", encoding="utf-8")


def test_dashboard_server_exposes_read_only_api(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    failure_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "failure_cases"
    observation_dir = tmp_path / "artifacts" / "mvs_e5_observation"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"
    validation_doc = tmp_path / "docs" / "TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md"
    validation_doc.parent.mkdir(parents=True, exist_ok=True)
    validation_doc.write_text("restore 仍缺\n", encoding="utf-8")

    _make_sample(real_dir, "sample_20260327_100000_aaaaaaaa", oe_available=True)
    _make_sample(real_dir, "sample_20260327_100100_bbbbbbbb", oe_available=False)
    observation_dir.mkdir(parents=True, exist_ok=True)
    (observation_dir / "OBSERVATION_SAMPLE_INDEX.md").write_text("### `/new`\n- sample_20260327_100000_aaaaaaaa\n", encoding="utf-8")
    (observation_dir / "MVS_E5_OBSERVATION_REPORT.md").write_text("- scripts/restart_egocore.sh --telegram\n", encoding="utf-8")

    build_dashboard_indexes(
        real_dir=real_dir,
        failure_dir=failure_dir,
        observation_dir=observation_dir,
        output_dir=output_dir,
        validation_doc=validation_doc,
    )

    DashboardRequestHandler.store = DashboardDataStore(
        dashboard_dir=output_dir,
        build_kwargs={
            "real_dir": real_dir,
            "failure_dir": failure_dir,
            "observation_dir": observation_dir,
            "validation_doc": validation_doc,
        },
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        health = json.loads(urlopen(f"{base}/api/dashboard/health").read().decode("utf-8"))
        runs = json.loads(urlopen(f"{base}/api/dashboard/runs").read().decode("utf-8"))
        growth = json.loads(urlopen(f"{base}/api/dashboard/growth").read().decode("utf-8"))
        failures = json.loads(urlopen(f"{base}/api/dashboard/failures").read().decode("utf-8"))
        sample = json.loads(
            urlopen(f"{base}/api/dashboard/samples/sample_20260327_100000_aaaaaaaa").read().decode("utf-8")
        )
        html = urlopen(f"{base}/runs").read().decode("utf-8")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert health["status"] == "ok"
    assert runs["records"]
    assert growth["records"]
    assert {item["sample_id"] for item in growth["records"]} == {"sample_20260327_100000_aaaaaaaa"}
    assert "gap_summary" in failures
    assert sample["sample_id"] == "sample_20260327_100000_aaaaaaaa"
    assert "ledger.json" in sample["artifacts"]
    assert "OpenEmotion Growth Dashboard v1" in html
