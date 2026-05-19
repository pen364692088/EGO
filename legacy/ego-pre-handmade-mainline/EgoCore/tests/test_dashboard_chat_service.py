from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import app.dashboard.chat_service as chat_service_module
from app.dashboard.chat_service import DashboardChatService
from app.openemotion_hooks.subject_gate import SubjectGateVerdict
from app.runtime_v2.unified_channel_contract import UnifiedIngressBundle
from app.telegram_runtime_bridge import TelegramRuntimeBridge
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


def _patch_semantic_to_heuristic(monkeypatch, bridge: TelegramRuntimeBridge) -> None:
    async def fake_semantic(text, state, llm_client=None):
        return bridge.inspect_ingress(text, state)

    monkeypatch.setattr(bridge, "inspect_ingress_semantic", fake_semantic)


class _AllowSubjectGate:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def process_ingress(self, **kwargs):
        self.calls.append(("ingress", kwargs))
        return SubjectGateVerdict.allow(stage="ingress")

    def finalize_host_owned_result(self, **kwargs):
        self.calls.append(("finalize", kwargs))
        return SubjectGateVerdict.allow(stage="response_plan")


class _DelayedSubjectGate(_AllowSubjectGate):
    def __init__(self, *, delay_seconds: float) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    def process_ingress(self, **kwargs):
        time.sleep(self.delay_seconds)
        return super().process_ingress(**kwargs)


class _BlockingSubjectGate:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def process_ingress(self, **kwargs):
        self.calls.append(("ingress", kwargs))
        return SubjectGateVerdict.block(stage="ingress", reason="hooks_disabled", reply_text="blocked by subject gate")

    def finalize_host_owned_result(self, **kwargs):
        self.calls.append(("finalize", kwargs))
        return SubjectGateVerdict.allow(stage="response_plan")


class _CountingRunner:
    def __init__(self, *, delay_seconds: float = 0.0) -> None:
        self.delay_seconds = delay_seconds
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.call_count = 0

    async def run_turn(
        self,
        *,
        session_key: str,
        user_input: str,
        state,
        source: str = "telegram",
        evidence_collector=None,
        loop_phase_probe=None,
    ):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.call_count += 1
        try:
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if callable(loop_phase_probe):
                loop_phase_probe(
                    {
                        "session_id": session_key,
                        "turn_id": "turn-1",
                        "generation_id": 0,
                        "phase": "chat_reply_engine_reply",
                        "engine_phase": "await_generate_result",
                        "chat_compaction_mode": (state.ingress_context or {}).get("chat_compaction_mode"),
                        "status": "started",
                        "started_at": "2026-04-13T00:00:00Z",
                        "elapsed_ms": None,
                        "error_kind": None,
                        "error_message": None,
                    }
                )
                loop_phase_probe(
                    {
                        "session_id": session_key,
                        "turn_id": "turn-1",
                        "generation_id": 0,
                        "phase": "chat_reply_engine_reply",
                        "engine_phase": "await_generate_result",
                        "chat_compaction_mode": (state.ingress_context or {}).get("chat_compaction_mode"),
                        "status": "completed",
                        "started_at": "2026-04-13T00:00:00Z",
                        "elapsed_ms": 5,
                        "error_kind": None,
                        "error_message": None,
                    }
                )
            count = int(getattr(state, "_dashboard_reply_count", 0) or 0) + 1
            state._dashboard_reply_count = count
            state.task_status = "chat"
            state.waiting_for_user_input = False
            return TelegramTurnResult(
                status="chat",
                state=state,
                reply=TelegramTurnReply(
                    reply_text=f"reply {count}: {user_input}",
                    delivery_kind="chat",
                    status="chat",
                    metadata={
                        "reply_origin": "chat_mainline",
                        "chat_expression_hint": {"reply_mode": "normal", "tone_profile": "supportive"},
                        "response_tendency_summary": {"preferred_mode": "ask", "preferred_tone": "supportive"},
                    },
                ),
            )
        finally:
            with self.lock:
                self.active -= 1


def _collect_probe_events():
    events = []

    def _probe(event):
        events.append(dict(event))

    return events, _probe


def test_dashboard_chat_service_keeps_named_sessions_continuous_and_isolated(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    runner = _CountingRunner()
    subject_gate = _AllowSubjectGate()
    service = DashboardChatService(
        bridge=bridge,
        runner=runner,
        subject_gate=subject_gate,
        llm_client_resolver=lambda: None,
    )

    default_id = service.ensure_session("default").session_id
    other_id = service.ensure_session("other").session_id

    first = service.send_message(default_id, "hello")
    second = service.send_message(default_id, "follow up")
    other = service.send_message(other_id, "hello from other session")

    default_payload = service.get_session_payload(default_id)
    other_payload = service.get_session_payload(other_id)

    assert first["messages"]["assistant"]["text"] == "reply 1: hello"
    assert second["messages"]["assistant"]["text"] == "reply 2: follow up"
    assert other["messages"]["assistant"]["text"] == "reply 1: hello from other session"
    assert default_payload["session"]["turn_count"] == 2
    assert other_payload["session"]["turn_count"] == 1
    assert len(default_payload["transcript"]) == 4
    assert len(other_payload["transcript"]) == 2
    assert default_payload["session_revision"] == 3
    assert other_payload["session_revision"] == 2
    assert default_payload["session_state"]["proto_self_scope"]["state_scope"] == "experiment"
    assert other_payload["session_state"]["proto_self_scope"]["state_scope"] == "experiment"
    assert (
        default_payload["session_state"]["proto_self_scope"]["experiment_id"]
        != other_payload["session_state"]["proto_self_scope"]["experiment_id"]
    )
    assert second["debug"]["response_plan"]["reply_authority"] == "model_chat"
    assert second["debug"]["output_check"]["passed"] is True
    assert second["debug"]["host_contract"]["turn"]["reply_authority"] == "model_chat"
    assert second["debug"]["host_contract"]["turn"]["proto_self_context"]["available"] is False
    assert subject_gate.calls and subject_gate.calls[0][0] == "ingress"


def test_dashboard_chat_service_merges_per_turn_ingress_overrides(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    service = DashboardChatService(
        bridge=bridge,
        runner=_CountingRunner(),
        subject_gate=_AllowSubjectGate(),
        llm_client_resolver=lambda: None,
    )

    session = service.ensure_session("ingress-override")
    payload = service.send_message(
        session.session_id,
        "hello",
        ingress_overrides={
            "chat_compaction_mode": "stage3_stance_only",
            "chat_output_contract": {
                "mode": "minimal_markers",
                "required_any_of_token_groups": [["OPTION_A", "OPTION_B"]],
            }
        },
    )

    assert payload["messages"]["assistant"]["text"] == "reply 1: hello"
    assert session.state.ingress_context["chat_compaction_mode"] == "stage3_stance_only"
    assert session.state.ingress_context["chat_output_contract"]["mode"] == "minimal_markers"
    assert session.state.ingress_context["chat_output_contract"]["required_any_of_token_groups"] == [
        ["OPTION_A", "OPTION_B"]
    ]


def test_dashboard_chat_service_blocks_before_runtime_when_subject_gate_rejects(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    runner = _CountingRunner()
    subject_gate = _BlockingSubjectGate()
    service = DashboardChatService(
        bridge=bridge,
        runner=runner,
        subject_gate=subject_gate,
        llm_client_resolver=lambda: None,
    )

    session_id = service.ensure_session("blocked").session_id
    payload = service.send_message(session_id, "this should block")

    assert payload["messages"]["assistant"]["text"] == "blocked by subject gate"
    assert payload["debug"]["subject_gate"]["ingress"]["ok"] is False
    assert payload["debug"]["response_plan"] is None
    assert runner.call_count == 0


def test_dashboard_chat_service_serializes_parallel_messages_per_session(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    runner = _CountingRunner(delay_seconds=0.05)
    service = DashboardChatService(
        bridge=bridge,
        runner=runner,
        subject_gate=_AllowSubjectGate(),
        llm_client_resolver=lambda: None,
    )

    session_id = service.ensure_session("serial").session_id
    texts = ["first", "second"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: service.send_message(session_id, item), texts))

    payload = service.get_session_payload(session_id)

    assert runner.max_active == 1
    assert len(results) == 2
    assert len(payload["transcript"]) == 4
    assert payload["session"]["turn_count"] == 2


def test_dashboard_chat_service_waits_for_revision_updates_and_wakes_on_new_message(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    runner = _CountingRunner(delay_seconds=0.01)
    service = DashboardChatService(
        bridge=bridge,
        runner=runner,
        subject_gate=_AllowSubjectGate(),
        llm_client_resolver=lambda: None,
    )

    session = service.ensure_session("waiter")
    assert session.session_revision == 1

    ready = threading.Event()

    def _wait_for_update():
        ready.set()
        return service.get_session_payload(session.session_id, after_revision=1, wait_timeout_ms=500)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_wait_for_update)
        assert ready.wait(timeout=0.2) is True
        time.sleep(0.05)
        assert future.done() is False

        send_payload = service.send_message(session.session_id, "hello after wait")
        waited_payload = future.result(timeout=1.0)

    assert send_payload["session_revision"] == 2
    assert waited_payload["has_update"] is True
    assert waited_payload["session_revision"] == 2
    assert waited_payload["transcript"][-1]["text"] == "reply 1: hello after wait"
    assert waited_payload["session_state"]["proto_self_scope"]["state_scope"] == "experiment"


def test_dashboard_chat_service_phase_probe_marks_build_unified_ingress(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    events, probe = _collect_probe_events()
    runner = _CountingRunner()
    service = DashboardChatService(
        bridge=bridge,
        runner=runner,
        subject_gate=_AllowSubjectGate(),
        llm_client_resolver=lambda: None,
        phase_probe=probe,
    )

    async def fake_build_unified_ingress(request, state, *, bridge, llm_client=None):
        await asyncio.sleep(0.01)
        decision = bridge.inspect_ingress(request.effective_user_input, state)
        ingress_context = bridge.build_ingress_context(decision, state)
        pre_runtime_action = bridge.plan_pre_runtime(decision, state)
        return UnifiedIngressBundle(
            request=request,
            semantic_decision=decision,
            ingress_context=ingress_context,
            pre_runtime_action=pre_runtime_action,
            normalized_turn_obj=getattr(decision, "_normalized_turn", None),
        )

    monkeypatch.setattr(chat_service_module, "build_unified_ingress", fake_build_unified_ingress)
    session_id = service.ensure_session("probe-build-ingress").session_id

    payload = service.send_message(session_id, "hello")

    phase_events = [event for event in events if event["phase"] == "build_unified_ingress"]
    assert payload["messages"]["assistant"]["text"] == "reply 1: hello"
    assert [event["status"] for event in phase_events] == ["started", "completed"]
    assert phase_events[-1]["elapsed_ms"] is not None


def test_dashboard_chat_service_phase_probe_marks_subject_gate_process_ingress(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    events, probe = _collect_probe_events()
    service = DashboardChatService(
        bridge=bridge,
        runner=_CountingRunner(),
        subject_gate=_DelayedSubjectGate(delay_seconds=0.01),
        llm_client_resolver=lambda: None,
        phase_probe=probe,
    )

    session_id = service.ensure_session("probe-subject-gate").session_id
    payload = service.send_message(session_id, "hello")

    phase_events = [event for event in events if event["phase"] == "subject_gate_process_ingress"]
    assert payload["messages"]["assistant"]["text"] == "reply 1: hello"
    assert [event["status"] for event in phase_events] == ["started", "completed"]
    assert phase_events[-1]["elapsed_ms"] is not None


def test_dashboard_chat_service_phase_probe_marks_runner_run_turn(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    events, probe = _collect_probe_events()
    runner = _CountingRunner(delay_seconds=0.01)
    service = DashboardChatService(
        bridge=bridge,
        runner=runner,
        subject_gate=_AllowSubjectGate(),
        llm_client_resolver=lambda: None,
        phase_probe=probe,
    )

    session_id = service.ensure_session("probe-runner").session_id
    payload = service.send_message(session_id, "hello")

    phase_events = [event for event in events if event["phase"] == "runner_run_turn"]
    assert payload["messages"]["assistant"]["text"] == "reply 1: hello"
    assert [event["status"] for event in phase_events] == ["started", "completed"]
    assert phase_events[-1]["elapsed_ms"] is not None


def test_dashboard_chat_service_phase_probe_carries_loop_subdetail(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    events, probe = _collect_probe_events()
    runner = _CountingRunner(delay_seconds=0.01)
    service = DashboardChatService(
        bridge=bridge,
        runner=runner,
        subject_gate=_AllowSubjectGate(),
        llm_client_resolver=lambda: None,
        phase_probe=probe,
    )

    session_id = service.ensure_session("probe-loop-subdetail").session_id
    payload = service.send_message(
        session_id,
        "hello",
        ingress_overrides={"chat_compaction_mode": "stage3_stance_only"},
    )

    loop_events = [
        event
        for event in events
        if event.get("service_phase") == "runner_run_turn" and event.get("phase") == "chat_reply_engine_reply"
    ]

    assert payload["messages"]["assistant"]["text"] == "reply 1: hello"
    assert [event["status"] for event in loop_events] == ["started", "completed"]
    assert all(event.get("trace_id") for event in loop_events)
    assert all(event.get("engine_phase") == "await_generate_result" for event in loop_events)
    assert all(event.get("chat_compaction_mode") == "stage3_stance_only" for event in loop_events)
