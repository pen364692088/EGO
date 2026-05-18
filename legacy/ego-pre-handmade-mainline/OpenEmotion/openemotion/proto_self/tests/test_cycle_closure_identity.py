"""Closure-sensitive cycle identity tests."""

from __future__ import annotations

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


def _tool_event(event_id: str, *, success: bool, tool: str = "shell", risk_level: str = "medium") -> KernelEvent:
    return KernelEvent(
        event_id=event_id,
        timestamp=f"2026-03-27T09:00:{event_id[-2:]}",
        actor="system",
        source="runtime",
        event_type="tool_result",
        safety_context={"risk_level": risk_level},
        external_result={
            "success": success,
            "tool": tool,
            "exit_code": 0 if success else 1,
            "error": None if success else "boom",
        },
    )


def test_success_failure_same_bucket_split_cycle_identity():
    state_success = ProtoSelfState.empty()
    state_failure = ProtoSelfState.empty()

    success_output = process_event(state_success, _tool_event("split-01", success=True))
    failure_output = process_event(state_failure, _tool_event("split-02", success=False))

    assert success_output.trace_payload["closure_signature"] != failure_output.trace_payload["closure_signature"]
    assert success_output.trace_payload["closure_family_id"] == failure_output.trace_payload["closure_family_id"]
    assert success_output.trace_payload["action_signature"] == failure_output.trace_payload["action_signature"] == "tool:shell"


def test_repair_closure_strengthens_and_promotes():
    state = ProtoSelfState.empty()
    success_cycle_id = None

    for idx in range(6):
        process_event(state, _tool_event(f"repair-fail-{idx:02d}", success=False))
        success_output = process_event(state, _tool_event(f"repair-success-{idx:02d}", success=True))
        success_cycle_id = success_output.trace_payload["cycle_delta"]["cycle_id"]

    assert success_cycle_id is not None
    signature = state.cycle_store.signatures[success_cycle_id]
    assert signature.mode_signature == "repair"
    assert signature.outcome_signature == "success"
    assert signature.hits == 6
    assert signature.promoted is True


def test_order_invariance_minimal_family_match():
    def _run_path(read_first: bool) -> dict:
        state = ProtoSelfState.empty()
        first_intent = "读取文件" if read_first else "状态查询"
        second_intent = "状态查询" if read_first else "读取文件"
        process_event(
            state,
            KernelEvent(
                event_id=f"path-{read_first}-01",
                timestamp="2026-03-27T10:00:01",
                actor="user",
                source="telegram",
                event_type="user_message",
                user_intent=first_intent,
            ),
        )
        process_event(
            state,
            KernelEvent(
                event_id=f"path-{read_first}-02",
                timestamp="2026-03-27T10:00:02",
                actor="user",
                source="telegram",
                event_type="user_message",
                user_intent=second_intent,
            ),
        )
        output = process_event(state, _tool_event(f"path-{read_first}-03", success=True))
        return output.trace_payload

    trace_a = _run_path(True)
    trace_b = _run_path(False)

    assert trace_a["closure_family_id"] == trace_b["closure_family_id"]
    assert trace_a["order_invariance_candidate"] == trace_b["order_invariance_candidate"]


def test_non_closure_unknown_outcomes_do_not_promote():
    state = ProtoSelfState.empty()
    for idx in range(8):
        process_event(
            state,
            KernelEvent(
                event_id=f"non-closure-{idx:02d}",
                timestamp=f"2026-03-27T11:00:{idx:02d}",
                actor="user",
                source="telegram",
                event_type="user_message",
                user_intent="你好",
            ),
        )

    signatures = list(state.cycle_store.signatures.values())
    assert len(signatures) >= 1
    assert all(signature.outcome_signature == "unknown" for signature in signatures)
    assert max(signature.hits for signature in signatures) < 8
    assert all(signature.promoted is False for signature in signatures)
