from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from http.server import ThreadingHTTPServer

from app.dashboard.chat_service import DashboardChatNotFoundError, DashboardChatValidationError
from app.dashboard.index_builder import build_dashboard_indexes
from app.dashboard.server import DashboardDataStore, DashboardRequestHandler


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_sample(
    real_dir: Path,
    sample_id: str,
    *,
    oe_available: bool,
    events: list[dict] | None = None,
    response_plan_override: dict | None = None,
    normalized_runtime_summary: dict | None = None,
    chat_id: int = 8420019401,
    user_id: int = 8420019401,
    username: str | None = None,
) -> None:
    sample_dir = real_dir / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    ledger = {
        "sample_id": sample_id,
        "timestamp": "2026-03-27T10:00:00+00:00",
        "source_type": "real_channel",
        "replay_hash": "hash",
        "ids": {
            "session_id": "telegram:dm:1",
            "thread_id": "telegram:dm:1",
            "event_id": f"evt_{sample_id}",
        },
        "openemotion": {
            "result": {
                "identity_delta": {"identity_confidence_delta": 0.05},
                "self_model_delta": {"current_mode": "review"},
                "drives_delta": {"caution": 0.3},
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
                "subject_profile": "seed_v0_2",
                "reflection_trigger": "drive_spike",
                "cycle_delta": {
                    "closure_family_id": "family-a",
                    "outcome_signature": "success",
                    "repair_closure": False,
                },
            }
            if oe_available
            else {},
            "events": events or [],
        },
        "host": {
            "response_plan": {
                "status": "chat",
                "delivery_kind": "chat",
                "reply_length": 4,
                "reply_authority": "model_chat",
                "reply_origin": "chat_mainline",
                "reply_text": "hello",
            },
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
    raw_update = {
        "update_id": 1,
        "message": {
            "text": "hello",
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "username": username},
        },
    }
    ledger["inputs"] = {"raw_update": raw_update}
    _write_json(sample_dir / "ledger.json", ledger)
    _write_json(sample_dir / "raw_update.json", raw_update)
    if oe_available:
        _write_json(
            sample_dir / "normalized_event.json",
            {
                "event_id": f"evt_{sample_id}",
                "event": {"event_type": "user_message", "raw_text": "hello"},
                "conversation_summary": {"session_id": "telegram:dm:1", "thread_id": "telegram:dm:1"},
                "runtime_summary": normalized_runtime_summary
                or {
                    "primary_intent": "chat",
                    "interaction_kind": "chat",
                    "conversation_act": "light_chitchat",
                    "runtime_action": "chat",
                    "active_task": False,
                    "confirm_pending": False,
                },
            },
        )
        _write_json(sample_dir / "openemotion_result.json", ledger["openemotion"]["result"])
        _write_json(sample_dir / "openemotion_trace.json", ledger["openemotion"]["trace_payload"])
    response_plan = dict(ledger["host"]["response_plan"])
    if response_plan_override:
        response_plan.update(response_plan_override)
        ledger["host"]["response_plan"] = response_plan
        _write_json(sample_dir / "ledger.json", ledger)
    _write_json(sample_dir / "response_plan.json", response_plan)
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

    _make_sample(
        real_dir,
        "sample_20260327_100000_aaaaaaaa",
        oe_available=True,
        events=[
            {
                "stage": "ingress_kernel_trace",
                "payload": {
                    "subject_profile": "seed_v0_2",
                    "perceived": {"event_type": "user_event", "blocked": False, "active_task": False, "confirm_pending": False},
                    "policy_hint": {"urge_score": 0.44, "requires_approval": False},
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
        ],
    )
    _make_sample(
        real_dir,
        "sample_20260327_100100_bbbbbbbb",
        oe_available=False,
        chat_id=123,
        user_id=456,
        username="moonlight",
    )
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
        runs_all = json.loads(urlopen(f"{base}/api/dashboard/runs?source_view=all").read().decode("utf-8"))
        growth = json.loads(urlopen(f"{base}/api/dashboard/growth").read().decode("utf-8"))
        failures = json.loads(urlopen(f"{base}/api/dashboard/failures").read().decode("utf-8"))
        agency = json.loads(urlopen(f"{base}/api/dashboard/agency").read().decode("utf-8"))
        flow = json.loads(urlopen(f"{base}/api/dashboard/flow").read().decode("utf-8"))
        flow_all = json.loads(urlopen(f"{base}/api/dashboard/flow?source_view=all").read().decode("utf-8"))
        sample_flow = json.loads(
            urlopen(f"{base}/api/dashboard/samples/sample_20260327_100000_aaaaaaaa/flow").read().decode("utf-8")
        )
        sample = json.loads(
            urlopen(f"{base}/api/dashboard/samples/sample_20260327_100000_aaaaaaaa").read().decode("utf-8")
        )
        html = urlopen(f"{base}/runs").read().decode("utf-8")
        flow_html = urlopen(f"{base}/flow").read().decode("utf-8")
        sample_flow_html = urlopen(f"{base}/samples/sample_20260327_100000_aaaaaaaa/flow").read().decode("utf-8")
        agency_html = urlopen(f"{base}/agency").read().decode("utf-8")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert health["status"] == "ok"
    assert health["build_meta"]["source_view"] == "real"
    assert runs["records"]
    assert runs["summary"]["turn_count"] == 1
    assert runs_all["summary"]["turn_count"] == 2
    assert runs["recent_runs"]
    assert "charts" in runs
    assert growth["records"]
    assert growth["recent_growth"]
    assert "charts" in growth
    assert {item["sample_id"] for item in growth["records"]} == {"sample_20260327_100000_aaaaaaaa"}
    assert "gap_summary" in failures
    assert failures["summary"]["total_failures"] == 0
    assert agency["summary"]["turn_count"] == 1
    assert agency["latest_state"]["final_host_action"] == "file"
    assert agency["headline_code"] == "changed_after_result"
    assert agency["story_cards"]
    assert flow["sample_id"] == "sample_20260327_100000_aaaaaaaa"
    assert flow["chain_status"]["overall_status"] == "pass"
    assert flow_all["sample_id"] == "sample_20260327_100100_bbbbbbbb"
    assert flow_all["chain_status"]["overall_status"] == "host_only"
    assert sample_flow["sample_id"] == "sample_20260327_100000_aaaaaaaa"
    assert sample_flow["subject_summary"]["oe_available"] is True
    assert sample_flow["canonical_fields_summary"]["loaded_axes"] == []
    assert sample_flow["canonical_fields_summary"]["self_model_delta"]["current_mode"] == "review"
    assert sample_flow["canonical_fields_summary"]["final_delivered_text"]["preview"] == "hello"
    assert sample_flow["reply_evolution_summary"]["available"] is False
    assert sample_flow["reply_evolution_summary"]["reason"] == "chat_metadata_missing"
    assert sample_flow["host_arbitration_summary"]["reply_authority"] == "model_chat"
    assert sample["sample_id"] == "sample_20260327_100000_aaaaaaaa"
    assert "ledger.json" in sample["artifacts"]
    assert sample["semantic_summary"]["headline_code"] == "changed_after_result"
    assert sample["translated_summary"]["focus_goal"] == "inspect_target"
    assert 'id="locale-switch"' in html
    assert 'data-view="flow"' in flow_html
    assert 'data-view="flow"' in sample_flow_html
    assert 'data-view="agency"' in agency_html


def test_dashboard_flow_detail_surfaces_degraded_and_recent_result_binding(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"

    _make_sample(
        real_dir,
        "sample_20260327_100500_eeeeeeee",
        oe_available=True,
        response_plan_override={
            "status": "chat",
            "reply_authority": "host_degraded_fallback",
            "reply_origin": "chat_mainline",
            "metadata": {
                "parser_source": "semantic_parser",
                "request_mode": "analyze",
                "recent_result_context": {
                    "target_name": "bilili_lookalike.html",
                    "target_path": "D:/Project/AIProject/MyProject/Test2/bilili_lookalike.html",
                },
                "result_binding_source_turn": "turn_prev",
                "pending_result_continuation": {
                    "target_name": "bilili_lookalike.html",
                    "requested_mode": "analyze",
                    "status": "pending",
                },
                "correction_context": True,
            },
        },
        normalized_runtime_summary={
            "primary_intent": "chat",
            "interaction_kind": "chat",
            "conversation_act": "followup_reflection",
            "runtime_action": "chat",
            "active_task": False,
            "confirm_pending": False,
        },
    )

    store = DashboardDataStore(dashboard_dir=output_dir)
    detail = store.flow_detail("sample_20260327_100500_eeeeeeee")

    assert detail is not None
    assert detail["chain_status"]["overall_status"] == "degraded"
    assert detail["host_arbitration_summary"]["degraded"] is True
    assert detail["host_ingress_summary"]["recent_result_binding"] is True
    assert detail["host_ingress_summary"]["parser_source"] == "semantic_parser"
    assert detail["host_ingress_summary"]["request_mode"] == "analyze"
    assert detail["host_ingress_summary"]["continuation_mode"] == "analyze"
    assert detail["host_ingress_summary"]["continuation_status"] == "pending"
    assert detail["host_ingress_summary"]["correction_context"] is True
    assert detail["host_ingress_summary"]["recent_result_source_turn"] == "turn_prev"
    assert detail["reply_evolution_summary"]["available"] is False
    assert detail["reply_evolution_summary"]["reason"] == "degraded_chat_no_comparable_evolution"


def test_dashboard_flow_detail_distinguishes_subject_chain_from_self_model_gap(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"

    _make_sample(
        real_dir,
        "sample_20260327_101000_gapgap01",
        oe_available=True,
        events=[],
        normalized_runtime_summary={
            "primary_intent": "chat",
            "interaction_kind": "chat",
            "conversation_act": "light_chitchat",
            "runtime_action": "chat",
            "active_task": False,
            "confirm_pending": False,
            "self_model_context_source": "missing",
        },
    )

    sample_dir = real_dir / "sample_20260327_101000_gapgap01"
    trace_payload = json.loads((sample_dir / "openemotion_trace.json").read_text(encoding="utf-8"))
    trace_payload["constraint_summary"] = {
        "self_model_context": {"present": False},
        "developmental_self_context": {"present": True},
        "social_self_context": {"present": True},
        "embodied_self_context": {"present": True},
        "selfhood_integration_context": {"present": True},
        "initiative_self_context": {"present": True},
        "initiative_realization_context": {"present": True},
    }
    _write_json(sample_dir / "openemotion_trace.json", trace_payload)

    ledger = json.loads((sample_dir / "ledger.json").read_text(encoding="utf-8"))
    ledger["openemotion"]["trace_payload"] = trace_payload
    ledger["host"]["timeline"] = [
        {"stage": "openemotion_processed", "timestamp": "2026-03-27T10:10:01+00:00"},
        {"stage": "message_sent", "timestamp": "2026-03-27T10:10:02+00:00"},
    ]
    _write_json(sample_dir / "ledger.json", ledger)
    _write_json(sample_dir / "timeline.json", ledger["host"]["timeline"])

    store = DashboardDataStore(dashboard_dir=output_dir)
    detail = store.flow_detail("sample_20260327_101000_gapgap01")

    assert detail is not None
    assert detail["chain_status"]["overall_status"] == "pass"
    assert detail["subject_summary"]["subject_chain_connected"] is True
    assert detail["subject_summary"]["contexts_seen"]["self_model"] is False
    assert detail["subject_summary"]["self_model_context_source"] == "missing"
    assert detail["subject_summary"]["context_load_summary"]["loaded"] == [
        "developmental",
        "social",
        "embodied",
        "integration",
        "initiative",
        "initiative_realization",
    ]
    assert "self_model" in detail["subject_summary"]["context_load_summary"]["missing"]


def test_dashboard_flow_detail_surfaces_chat_reply_evolution_when_metadata_present(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"

    _make_sample(
        real_dir,
        "sample_20260327_101500_chatmeta",
        oe_available=True,
        response_plan_override={
            "status": "chat",
            "reply_authority": "model_chat",
            "reply_origin": "chat_mainline",
            "reply_text": "我觉得这轮回复更偏收束一些。",
            "chat_cadence_mode": "reply_now_normal",
            "metadata": {
                "chat_expression_hint": {
                    "reply_mode": "normal",
                    "tone_profile": "supportive",
                    "next_step_bias": "continue_thread",
                    "why": "recent reflective followup",
                },
                "response_tendency_summary": {
                    "preferred_mode": "ask",
                    "preferred_tone": "supportive",
                    "suggested_next_step": "continue_thread",
                },
                "memory_claim_reason": "current_session_grounded",
            },
        },
    )

    store = DashboardDataStore(dashboard_dir=output_dir)
    detail = store.flow_detail("sample_20260327_101500_chatmeta")

    assert detail is not None
    assert detail["reply_evolution_summary"]["available"] is True
    assert detail["reply_evolution_summary"]["reason"] is None
    assert detail["reply_evolution_summary"]["subject_influence"]["chat_expression_hint"]["reply_mode"] == "normal"
    assert detail["reply_evolution_summary"]["subject_influence"]["response_tendency_summary"]["preferred_tone"] == "supportive"
    assert detail["reply_evolution_summary"]["host_arbitration"]["reply_origin"] == "chat_mainline"
    assert detail["reply_evolution_summary"]["final_output"]["final_text_preview"] == "我觉得这轮回复更偏收束一些。"
    assert detail["canonical_fields_summary"]["host_arbitration_result"]["chat_cadence_mode"] == "reply_now_normal"
    assert detail["canonical_fields_summary"]["final_delivered_text"]["preview"] == "我觉得这轮回复更偏收束一些。"
    assert detail["canonical_fields_summary"]["final_delivered_text"]["capture_status"] == "captured"


def test_dashboard_flow_detail_keeps_reply_evolution_useful_when_text_preview_missing(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"

    _make_sample(
        real_dir,
        "sample_20260327_101520_chatmeta2",
        oe_available=True,
        response_plan_override={
            "status": "chat",
            "reply_authority": "model_chat",
            "reply_origin": "chat_mainline",
            "reply_text": None,
            "reply_length": 59,
            "chat_cadence_mode": "reply_now_normal",
            "metadata": {
                "chat_expression_hint": {
                    "reply_mode": "normal",
                    "tone_profile": "repairing",
                    "next_step_bias": "clarify_or_repair",
                    "why": "light_chitchat with elevated repair bias",
                },
                "response_tendency_summary": {
                    "preferred_mode": "defer",
                    "preferred_tone": "cautious",
                    "suggested_next_step": "clarify_or_repair",
                },
            },
        },
    )

    store = DashboardDataStore(dashboard_dir=output_dir)
    detail = store.flow_detail("sample_20260327_101520_chatmeta2")

    assert detail is not None
    assert detail["reply_evolution_summary"]["available"] is True
    assert detail["reply_evolution_summary"]["final_output"]["final_text_preview"] is None
    assert detail["reply_evolution_summary"]["final_output"]["final_text_capture_status"] == "missing_but_delivered"
    assert detail["reply_evolution_summary"]["final_output"]["reply_length"] == 4
    assert detail["output_summary"]["final_text_capture_status"] == "missing_but_delivered"
    assert detail["canonical_fields_summary"]["final_delivered_text"]["capture_status"] == "missing_but_delivered"


def test_dashboard_flow_detail_marks_task_mainline_reply_evolution_not_available(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"

    _make_sample(
        real_dir,
        "sample_20260327_101700_taskflow",
        oe_available=True,
        response_plan_override={
            "status": "completed_verified",
            "reply_authority": "host_terminal",
            "reply_origin": "task_mainline",
            "reply_text": "已完成 bilili_lookalike.html。",
            "metadata": {
                "response_tendency_summary": {
                    "preferred_mode": "ask",
                },
            },
        },
    )

    store = DashboardDataStore(dashboard_dir=output_dir)
    detail = store.flow_detail("sample_20260327_101700_taskflow")

    assert detail is not None
    assert detail["reply_evolution_summary"]["available"] is False
    assert detail["reply_evolution_summary"]["reason"] == "task_mainline_not_in_v1"


def test_dashboard_flow_detail_marks_host_only_reply_evolution_not_available(tmp_path: Path) -> None:
    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"

    _make_sample(real_dir, "sample_20260327_101900_hostonly", oe_available=False)

    store = DashboardDataStore(dashboard_dir=output_dir)
    detail = store.flow_detail("sample_20260327_101900_hostonly")

    assert detail is not None
    assert detail["reply_evolution_summary"]["available"] is False
    assert detail["reply_evolution_summary"]["reason"] == "host_only_no_subject_chat_evolution"


def test_dashboard_server_exposes_chat_tab_and_local_chat_api(tmp_path: Path) -> None:
    class _FakeChatService:
        def __init__(self) -> None:
            self.session_id = "dashboard:test:default"
            self.session_revision = 4
            self.detail = {
                "session": {
                    "session_id": self.session_id,
                    "session_name": "default",
                    "message_count": 2,
                    "turn_count": 1,
                    "created_at": "2026-04-10T12:00:00+00:00",
                    "updated_at": "2026-04-10T12:01:00+00:00",
                    "task_status": "chat",
                    "waiting_for_user_input": False,
                    "session_revision": self.session_revision,
                    "last_message_id": "msg_00002",
                },
                "transcript": [
                    {
                        "message_id": "msg_00001",
                        "role": "user",
                        "text": "hello",
                        "status": "received",
                        "delivery_kind": "ingress",
                        "created_at": "2026-04-10T12:00:00+00:00",
                    },
                    {
                        "message_id": "msg_00002",
                        "role": "assistant",
                        "text": "world",
                        "status": "chat",
                        "delivery_kind": "chat",
                        "created_at": "2026-04-10T12:00:01+00:00",
                    },
                ],
                "last_debug": {"trace_id": "trace-smoke", "delivery": {"text_preview": "world"}},
                "debug_history": {"msg_00002": {"trace_id": "trace-smoke", "delivery": {"text_preview": "world"}}},
                "session_state": {
                    "task_status": "chat",
                    "waiting_for_user_input": False,
                    "proto_self_scope": {
                        "state_scope": "experiment",
                        "experiment_id": "dashboard_local:test:default",
                        "owner": "dashboard_local",
                    },
                },
                "session_revision": self.session_revision,
                "has_update": True,
            }

        def list_sessions(self):
            return {
                "default_session_id": self.session_id,
                "sessions": [
                    {
                        "session_id": self.session_id,
                        "session_name": "default",
                        "message_count": 2,
                        "turn_count": 1,
                        "created_at": "2026-04-10T12:00:00+00:00",
                        "updated_at": "2026-04-10T12:01:00+00:00",
                        "task_status": "chat",
                        "waiting_for_user_input": False,
                        "session_revision": self.session_revision,
                        "last_message_id": "msg_00002",
                    }
                ],
            }

        def create_or_select_session(self, *, name=None, session_id=None):
            return {
                "session": {
                    "session_id": self.session_id,
                    "session_name": name or "default",
                    "session_revision": self.session_revision,
                },
                "session_state": {"task_status": "idle"},
                "session_revision": self.session_revision,
            }

        def get_session_payload(self, session_id, *, after_revision=None, wait_timeout_ms=None):
            if session_id != self.session_id:
                raise DashboardChatNotFoundError("unknown session")
            payload = dict(self.detail)
            payload["has_update"] = after_revision is None or int(after_revision) < self.session_revision
            payload["wait_timeout_ms"] = wait_timeout_ms
            return payload

        def send_message(self, session_id, text):
            if session_id != self.session_id:
                raise DashboardChatNotFoundError("unknown session")
            if not str(text or "").strip():
                raise DashboardChatValidationError("empty text")
            self.session_revision += 1
            return {
                "session": {
                    **self.detail["session"],
                    "session_revision": self.session_revision,
                    "last_message_id": "msg_00004",
                },
                "messages": {
                    "user": {
                        "message_id": "msg_00003",
                        "role": "user",
                        "text": text,
                        "status": "received",
                        "delivery_kind": "ingress",
                        "created_at": "2026-04-10T12:01:30+00:00",
                    },
                    "assistant": {
                        "message_id": "msg_00004",
                        "role": "assistant",
                        "text": "echo:" + text,
                        "status": "chat",
                        "delivery_kind": "chat",
                        "created_at": "2026-04-10T12:01:31+00:00",
                    },
                },
                "debug": {
                    "subject_gate": {"ingress": {"ok": True, "reason": "ok"}},
                    "output_check": {"passed": True},
                    "delivery": {"text_preview": "echo:" + text},
                },
                "session_state": {
                    "task_status": "chat",
                    "waiting_for_user_input": False,
                    "proto_self_scope": {
                        "state_scope": "experiment",
                        "experiment_id": "dashboard_local:test:default",
                        "owner": "dashboard_local",
                    },
                },
                "session_revision": self.session_revision,
                "has_update": True,
            }

    real_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
    failure_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "failure_cases"
    observation_dir = tmp_path / "artifacts" / "mvs_e5_observation"
    output_dir = tmp_path / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"
    validation_doc = tmp_path / "docs" / "TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md"
    validation_doc.parent.mkdir(parents=True, exist_ok=True)
    validation_doc.write_text("dashboard chat smoke\n", encoding="utf-8")
    observation_dir.mkdir(parents=True, exist_ok=True)
    _make_sample(real_dir, "sample_20260410_120000_chatseed", oe_available=True)
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
    DashboardRequestHandler.chat_service = _FakeChatService()
    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        html = urlopen(f"{base}/chat").read().decode("utf-8")
        sessions = json.loads(urlopen(f"{base}/api/dashboard/chat/sessions").read().decode("utf-8"))
        created = json.loads(
            urlopen(
                Request(
                    f"{base}/api/dashboard/chat/sessions",
                    data=json.dumps({"name": "smoke"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
            ).read().decode("utf-8")
        )
        detail = json.loads(
            urlopen(f"{base}/api/dashboard/chat/sessions/dashboard%3Atest%3Adefault").read().decode("utf-8")
        )
        waited = json.loads(
            urlopen(
                f"{base}/api/dashboard/chat/sessions/dashboard%3Atest%3Adefault?after_revision=4&wait_timeout_ms=50"
            ).read().decode("utf-8")
        )
        message = json.loads(
            urlopen(
                Request(
                    f"{base}/api/dashboard/chat/sessions/dashboard%3Atest%3Adefault/messages",
                    data=json.dumps({"text": "ping"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
            ).read().decode("utf-8")
        )
        try:
            urlopen(
                Request(
                    f"{base}/api/dashboard/chat/sessions/dashboard%3Atest%3Adefault/messages",
                    data=json.dumps({"text": ""}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
            )
            empty_status = None
        except HTTPError as exc:
            empty_status = exc.code
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        DashboardRequestHandler.chat_service = None

    assert 'data-view="chat"' in html
    assert "/static/dashboard_chat_state.js?v=" in html
    assert sessions["default_session_id"] == "dashboard:test:default"
    assert created["session"]["session_name"] == "smoke"
    assert detail["session"]["session_id"] == "dashboard:test:default"
    assert detail["session_revision"] == 4
    assert detail["debug_history"]["msg_00002"]["trace_id"] == "trace-smoke"
    assert waited["has_update"] is False
    assert waited["wait_timeout_ms"] == 50
    assert message["messages"]["assistant"]["text"] == "echo:ping"
    assert message["session_revision"] == 5
    assert message["debug"]["subject_gate"]["ingress"]["ok"] is True
    assert empty_status == 400
