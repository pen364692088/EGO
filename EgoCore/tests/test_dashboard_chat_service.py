from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.dashboard.chat_service import DashboardChatService
from app.openemotion_hooks.subject_gate import SubjectGateVerdict
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
    ):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.call_count += 1
        try:
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
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
    assert subject_gate.calls and subject_gate.calls[0][0] == "ingress"


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
