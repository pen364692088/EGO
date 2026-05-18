from __future__ import annotations

import json
from pathlib import Path

from app.dashboard.index_builder import build_dashboard_indexes, load_jsonl


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_sample(
    real_dir: Path,
    sample_id: str,
    *,
    timestamp: str,
    session_id: str,
    response_plan_status: str,
    completeness: dict[str, bool],
    result_payload: dict | None = None,
    trace_payload: dict | None = None,
    events: list[dict] | None = None,
    sample_payload: dict | None = None,
) -> None:
    sample_dir = real_dir / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)

    response_plan = {"status": response_plan_status, "delivery_kind": "final", "reply_length": 8}
    outbox_record = {"chat_id": 1, "message_id": 2, "text_length": 8, "success": True}
    timeline = [{"stage": "update_received", "timestamp": timestamp}]
    replay = {
        "sample_id": sample_id,
        "primary_ledger_ref": "ledger.json",
        "replay_hash": "abc123",
    }
    tape = {"tape_id": f"tape_{sample_id}", "timestamp": timestamp}
    raw_update = {"update_id": 1, "message": {"text": "hello"}}
    normalized_event = {
        "event_id": f"evt_{sample_id}",
        "conversation_context": {"session_id": session_id, "thread_id": session_id, "turn_id": "turn-1"},
    }
    ledger = {
        "sample_id": sample_id,
        "timestamp": timestamp,
        "replay_hash": "abc123",
        "ids": {
            "session_id": session_id,
            "thread_id": session_id,
            "event_id": normalized_event["event_id"],
        },
        "openemotion": {
            "result": result_payload or {},
            "trace_payload": trace_payload or {},
            "events": events or [],
        },
        "host": {
            "response_plan": response_plan if completeness.get("response_plan") else None,
            "outbox_record": outbox_record if completeness.get("outbox_record") else None,
            "timeline": timeline if completeness.get("timeline") else [],
        },
        "evidence_completeness": completeness,
    }
    _write_json(sample_dir / "ledger.json", ledger)

    file_map = {
        "raw_update.json": raw_update,
        "normalized_event.json": normalized_event,
        "openemotion_result.json": result_payload or {},
        "openemotion_trace.json": trace_payload or {},
        "response_plan.json": response_plan,
        "outbox_record.json": outbox_record,
        "timeline.json": timeline,
        "tape.json": tape,
        "replay.json": replay,
    }
    for filename, payload in file_map.items():
        key = filename.replace(".json", "")
        if completeness.get(key):
            _write_json(sample_dir / filename, payload)

    if sample_payload is not None:
        _write_json(sample_dir / "sample.json", sample_payload)

    (sample_dir / "summary.md").write_text(f"# {sample_id}\n", encoding="utf-8")


def test_build_dashboard_indexes_creates_required_indexes(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    failure_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "failure_cases"
    observation_dir = tmp_path / "artifacts" / "mvs_e5_observation"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"
    validation_doc = tmp_path / "docs" / "TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md"
    validation_doc.parent.mkdir(parents=True, exist_ok=True)
    validation_doc.write_text("restore 仍缺\n", encoding="utf-8")

    blocked_trace = {
        "reflection_trigger": "external_failure",
        "cycle_delta": {
            "closure_family_id": "family-a",
            "outcome_signature": "blocked",
            "repair_closure": False,
        },
    }
    success_trace = {
        "reflection_trigger": "drive_spike",
        "cycle_delta": {
            "closure_family_id": "family-a",
            "outcome_signature": "success",
            "repair_closure": True,
        },
    }
    result_payload = {
        "memory_update": {"append_episode": True, "cycle_promotion_candidate": "c1", "promote_reflection": False},
        "appraisal_state_delta": {"caution": 0.8},
        "reflection_note": {
            "trigger": "external_failure",
            "diagnosis": "need repair",
            "proposed_adjustment": {"mode": "repair"},
            "promote_to_memory": True,
        },
        "response_tendency": {
            "preferred_mode": "ask",
            "preferred_tone": "cautious",
            "certainty_bound": "bounded",
            "suggested_next_step": "prioritize_closure",
            "ask_needed": True,
        },
    }

    _make_sample(
        real_dir,
        "sample_20260327_100000_aaaaaaaa",
        timestamp="2026-03-27T10:00:00+00:00",
        session_id="telegram:dm:1",
        response_plan_status="complete",
        completeness={
            "raw_update": True,
            "normalized_event": True,
            "openemotion_result": True,
            "openemotion_trace": True,
            "response_plan": True,
            "outbox_record": True,
            "timeline": True,
            "tape": True,
            "replay": True,
        },
        result_payload=result_payload,
        trace_payload=blocked_trace,
    )
    _make_sample(
        real_dir,
        "sample_20260327_100100_bbbbbbbb",
        timestamp="2026-03-27T10:01:00+00:00",
        session_id="telegram:dm:1",
        response_plan_status="complete",
        completeness={
            "raw_update": True,
            "normalized_event": True,
            "openemotion_result": True,
            "openemotion_trace": True,
            "response_plan": True,
            "outbox_record": True,
            "timeline": True,
            "tape": True,
            "replay": True,
        },
        result_payload=result_payload,
        trace_payload=success_trace,
    )
    _make_sample(
        real_dir,
        "sample_20260327_100200_cccccccc",
        timestamp="2026-03-27T10:02:00+00:00",
        session_id="telegram:dm:1",
        response_plan_status="profile_rule_enforced",
        completeness={
            "raw_update": True,
            "normalized_event": False,
            "openemotion_result": False,
            "openemotion_trace": False,
            "response_plan": True,
            "outbox_record": True,
            "timeline": True,
            "tape": True,
            "replay": True,
        },
        result_payload=None,
        trace_payload=None,
    )
    _make_sample(
        real_dir,
        "sample_20260327_100250_dddddddd",
        timestamp="2026-03-27T10:02:50+00:00",
        session_id="telegram:dm:1",
        response_plan_status="complete",
        completeness={
            "raw_update": True,
            "normalized_event": False,
            "openemotion_result": False,
            "openemotion_trace": False,
            "response_plan": True,
            "outbox_record": True,
            "timeline": True,
            "tape": True,
            "replay": True,
        },
        result_payload=None,
        trace_payload=None,
    )

    failure_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        failure_dir / "failure_001.json",
        {
            "failure_id": "fail_001",
            "timestamp": "2026-03-27T12:00:00+00:00",
            "initial_cause_type": "test_gap",
            "artifact_path": "artifacts/telegram_real_mainline_v1/failure_cases/failure_001.json",
            "in_regression": False,
            "retested_after_fix": False,
            "expected": "complete bundle",
            "actual": "missing restore sample",
        },
    )

    observation_dir.mkdir(parents=True, exist_ok=True)
    (observation_dir / "OBSERVATION_SAMPLE_INDEX.md").write_text(
        """
### `/new` continuity
- sample_20260327_100000_aaaaaaaa

### restart continuity 跨证据链
- sample_20260327_100200_cccccccc
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (observation_dir / "MVS_E5_OBSERVATION_REPORT.md").write_text(
        "- scripts/restart_egocore.sh --telegram (PID 2586 -> 2657)\n",
        encoding="utf-8",
    )

    summary = build_dashboard_indexes(
        real_dir=real_dir,
        failure_dir=failure_dir,
        observation_dir=observation_dir,
        output_dir=output_dir,
        validation_doc=validation_doc,
    )

    assert summary.total_runs == 4
    runs = load_jsonl(output_dir / "runs.jsonl")
    growth = load_jsonl(output_dir / "growth_signals.jsonl")
    continuity = load_jsonl(output_dir / "continuity_observation.jsonl")
    failures = load_jsonl(output_dir / "failures.jsonl")
    runs_rollup = json.loads((output_dir / "runs_rollup.json").read_text(encoding="utf-8"))
    growth_rollup = json.loads((output_dir / "growth_rollup.json").read_text(encoding="utf-8"))
    failures_rollup = json.loads((output_dir / "failures_rollup.json").read_text(encoding="utf-8"))
    gap_summary = json.loads((output_dir / "gap_summary.json").read_text(encoding="utf-8"))

    host_only = next(item for item in runs if item["sample_id"] == "sample_20260327_100200_cccccccc")
    assert host_only["host_only"] is True
    assert host_only["oe_available"] is False
    assert "control_plane_host_only" in host_only["gap_types"]
    unexpected_host_only = next(item for item in runs if item["sample_id"] == "sample_20260327_100250_dddddddd")
    assert unexpected_host_only["host_only"] is True
    assert unexpected_host_only["oe_available"] is False
    assert "unexpected_pre_runtime_intercept" in unexpected_host_only["gap_types"]
    assert host_only["semantic"]["headline_code"] == "host_only_turn"

    assert {item["sample_id"] for item in growth} == {
        "sample_20260327_100000_aaaaaaaa",
        "sample_20260327_100100_bbbbbbbb",
    }
    assert growth[0]["semantic"]["headline_code"] in {
        "reflecting_on_result",
        "steady_growth",
        "repairing_after_failure",
    }

    continuity_map = {item["scenario"]: item for item in continuity}
    assert continuity_map["new"]["status"] == "direct_real"
    assert continuity_map["restart"]["status"] == "cross_evidence"
    assert continuity_map["restore"]["status"] == "missing"
    assert continuity_map["restore"]["sample_ids"] == []

    assert failures[0]["failure_id"] == "fail_001"
    assert failures[0]["semantic"]["headline_code"] == "evidence_missing"
    assert gap_summary["gap_type_counts"]["control_plane_host_only"] >= 1
    assert gap_summary["gap_type_counts"]["unexpected_pre_runtime_intercept"] >= 1
    assert runs_rollup["summary"]["turn_count"] == 4
    assert runs_rollup["recent_runs"][0]["semantic"]["headline_code"] == "host_only_turn"
    assert growth_rollup["summary"]["total_records"] == 2
    assert "growth_motion_distribution" in growth_rollup["charts"]
    assert failures_rollup["summary"]["total_failures"] == 1
    assert "top_blockers" in failures_rollup["charts"]

    assert (output_dir / "REAL_MAINLINE_CAPTURE_STATUS.md").exists()
    assert (output_dir / "CONTINUITY_OBSERVATION_LEDGER.md").exists()
    assert (output_dir / "PLASTICITY_REFLECTION_EVIDENCE.md").exists()
    assert (output_dir / "GAP_SUMMARY.md").exists()


def test_build_dashboard_indexes_emits_agency_rollup_and_mirror_fallback(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    failure_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "failure_cases"
    observation_dir = tmp_path / "artifacts" / "mvs_e5_observation"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"
    validation_doc = tmp_path / "docs" / "TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md"
    validation_doc.parent.mkdir(parents=True, exist_ok=True)
    validation_doc.write_text("restore 仍缺\n", encoding="utf-8")

    seed_events = [
        {
            "stage": "ingress_kernel_trace",
            "payload": {
                "subject_profile": "seed_v0_2",
                "perceived": {"event_type": "user_event", "blocked": False, "active_task": False, "confirm_pending": False},
                "policy_hint": {"urge_score": 0.42, "requires_approval": False},
                "candidate_actions": [{"action_type": "inspect_file"}],
                "governor_hint": {"status": "approved", "selected_action": {"action_type": "inspect_file"}},
                "seed_state_snapshot": {"focus_goal": {"current_focus": "inspect_target"}, "revision_counter": 3},
            },
        },
        {
            "stage": "external_result_kernel_trace",
            "payload": {
                "subject_profile": "seed_v0_2",
                "governor_hint": {"status": "exec_result"},
                "executed_action": {"action_type": "file"},
                "exec_result": {"status": "success"},
                "seed_state_snapshot": {"focus_goal": {"current_focus": "inspect_target"}, "revision_counter": 4},
            },
        },
    ]

    _make_sample(
        real_dir,
        "sample_20260329_175737_7ca3cfb6",
        timestamp="2026-03-29T17:57:38+00:00",
        session_id="telegram:dm:8420019401",
        response_plan_status="complete",
        completeness={
            "raw_update": True,
            "normalized_event": True,
            "openemotion_result": True,
            "openemotion_trace": True,
            "response_plan": True,
            "outbox_record": True,
            "timeline": True,
            "tape": True,
            "replay": True,
        },
        result_payload={"subject_profile": "seed_v0_2"},
        trace_payload={"subject_profile": "seed_v0_2"},
        events=seed_events,
    )

    _make_sample(
        real_dir,
        "sample_20260329_180000_abcd1234",
        timestamp="2026-03-29T18:00:00+00:00",
        session_id="telegram:dm:8420019401",
        response_plan_status="complete",
        completeness={
            "raw_update": True,
            "normalized_event": True,
            "openemotion_result": True,
            "openemotion_trace": True,
            "response_plan": True,
            "outbox_record": True,
            "timeline": True,
            "tape": True,
            "replay": True,
        },
        result_payload=None,
        trace_payload=None,
        sample_payload={
            "openemotion_result": {
                "subject_profile": "seed_v0_2",
                "policy_hint": {"urge_score": 0.0, "requires_approval": False},
                "candidate_actions": [],
                "trace_payload": {
                    "subject_profile": "seed_v0_2",
                    "perceived": {"event_type": "user_event", "blocked": False, "active_task": False, "confirm_pending": False},
                    "suppression_reason": "no_affordance",
                    "governor_hint": {"status": "none"},
                    "seed_state_snapshot": {"focus_goal": {"current_focus": "monitor"}, "revision_counter": 8},
                },
            }
        },
    )

    _make_sample(
        real_dir,
        "sample_20260329_180100_deadbeef",
        timestamp="2026-03-29T18:01:00+00:00",
        session_id="telegram:dm:8420019401",
        response_plan_status="profile_rule_enforced",
        completeness={
            "raw_update": True,
            "normalized_event": False,
            "openemotion_result": False,
            "openemotion_trace": False,
            "response_plan": True,
            "outbox_record": True,
            "timeline": True,
            "tape": True,
            "replay": True,
        },
    )

    build_dashboard_indexes(
        real_dir=real_dir,
        failure_dir=failure_dir,
        observation_dir=observation_dir,
        output_dir=output_dir,
        validation_doc=validation_doc,
    )

    agency_runs = load_jsonl(output_dir / "agency_runs.jsonl")
    agency_rollup = json.loads((output_dir / "agency_rollup.json").read_text(encoding="utf-8"))
    by_id = {item["sample_id"]: item for item in agency_runs}

    assert by_id["sample_20260329_175737_7ca3cfb6"]["evidence_source"] == "ledger_events"
    assert by_id["sample_20260329_175737_7ca3cfb6"]["candidate_actions"] == ["inspect_file"]
    assert by_id["sample_20260329_175737_7ca3cfb6"]["final_host_action"] == "file"
    assert by_id["sample_20260329_175737_7ca3cfb6"]["exec_result_type"] == "success"
    assert by_id["sample_20260329_175737_7ca3cfb6"]["semantic"]["headline_code"] == "changed_after_result"

    assert by_id["sample_20260329_180000_abcd1234"]["evidence_source"] == "sample_mirror"
    assert by_id["sample_20260329_180000_abcd1234"]["suppression_reason"] == "no_affordance"
    assert by_id["sample_20260329_180000_abcd1234"]["semantic"]["intent_code"] == "observe"

    assert agency_rollup["summary"]["turn_count"] == 2
    assert agency_rollup["latest_state"]["sample_id"] == "sample_20260329_180000_abcd1234"
    assert agency_rollup["excluded_counts"]["host_only"] == 1
    assert agency_rollup["headline_code"] == "wants_to_inspect"
    assert agency_rollup["story_cards"]
