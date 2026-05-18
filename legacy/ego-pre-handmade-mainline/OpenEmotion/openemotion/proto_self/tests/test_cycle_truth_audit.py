"""Cycle truth audit regression tests after the closure-sensitive upgrade."""

from __future__ import annotations

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


def _user_event(event_id: str, intent: str) -> KernelEvent:
    return KernelEvent(
        event_id=event_id,
        timestamp=f"2026-03-26T10:00:{event_id[-2:]}",
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent=intent,
        safety_context={"risk_level": "low"},
    )


def _tool_result_event(event_id: str, *, success: bool, risk_level: str = "medium") -> KernelEvent:
    return KernelEvent(
        event_id=event_id,
        timestamp=f"2026-03-26T11:00:{event_id[-2:]}",
        actor="system",
        source="runtime",
        event_type="tool_result",
        safety_context={"risk_level": risk_level},
        external_result={
            "success": success,
            "tool": "shell",
            "exit_code": 0 if success else 1,
            "error": None if success else "boom",
        },
    )


def _process_path(state: ProtoSelfState, events: list[KernelEvent]) -> list:
    outputs = []
    for event in events:
        outputs.append(process_event(state, event))
    return outputs


def test_cycle_identity_encodes_outcome_closure():
    """T1: success/failure 不得再命中同一 cycle_id。"""
    success_output = process_event(
        ProtoSelfState.empty(),
        _tool_result_event("tool-success-01", success=True, risk_level="medium"),
    )
    failure_output = process_event(
        ProtoSelfState.empty(),
        _tool_result_event("tool-failure-01", success=False, risk_level="medium"),
    )

    success_cycle = success_output.trace_payload["cycle_delta"]
    failure_cycle = failure_output.trace_payload["cycle_delta"]

    assert success_cycle["cycle_id"] != failure_cycle["cycle_id"]
    assert success_cycle["closure_family_id"] == failure_cycle["closure_family_id"]
    assert success_output.trace_payload["outcome_signature"] == "success"
    assert failure_output.trace_payload["outcome_signature"] == "failure"
    assert success_output.trace_payload["reflection_trigger"] is None
    assert failure_output.trace_payload["reflection_trigger"] == "external_failure"


def test_reordered_paths_share_order_invariance_candidate():
    """T2: 微顺序不同但 closure 等价时，应命中同一 family / order candidate。"""
    state_a = ProtoSelfState.empty()
    state_b = ProtoSelfState.empty()

    path_a = [
        _user_event("path-a-01", "读取文件"),
        _user_event("path-a-02", "状态查询"),
        _tool_result_event("path-a-03", success=True, risk_level="medium"),
    ]
    path_b = [
        _user_event("path-b-02", "状态查询"),
        _user_event("path-b-01", "读取文件"),
        _tool_result_event("path-b-03", success=True, risk_level="medium"),
    ]

    outputs_a = _process_path(state_a, path_a)
    outputs_b = _process_path(state_b, path_b)

    final_trace_a = outputs_a[-1].trace_payload
    final_trace_b = outputs_b[-1].trace_payload

    assert final_trace_a["cycle_delta"]["cycle_id"] == final_trace_b["cycle_delta"]["cycle_id"]
    assert final_trace_a["closure_family_id"] == final_trace_b["closure_family_id"]
    assert final_trace_a["order_invariance_candidate"] == final_trace_b["order_invariance_candidate"]
    assert len(state_a.cycle_store.signatures) == 3
    assert len(state_b.cycle_store.signatures) == 3


def test_outcome_changes_followup_bias_and_cycle_identity():
    """T3: outcome 既要改变 tendency，也要改变 cycle identity。"""
    success_state = ProtoSelfState.empty()
    failure_state = ProtoSelfState.empty()

    seed_event = _tool_result_event("seed-tool-01", success=True, risk_level="medium")
    process_event(success_state, seed_event)
    process_event(failure_state, seed_event)

    success_output = process_event(
        success_state,
        _tool_result_event("seed-tool-02", success=True, risk_level="medium"),
    )
    failure_output = process_event(
        failure_state,
        _tool_result_event("seed-tool-03", success=False, risk_level="medium"),
    )

    success_cycle = success_output.trace_payload["cycle_delta"]
    failure_cycle = failure_output.trace_payload["cycle_delta"]

    assert success_cycle["cycle_id"] != failure_cycle["cycle_id"]
    assert success_cycle["closure_family_id"] == failure_cycle["closure_family_id"]
    assert success_cycle["op"] == "strengthen"
    assert failure_cycle["op"] == "candidate"

    success_sig = success_state.cycle_store.signatures[success_cycle["cycle_id"]]
    failure_sig = failure_state.cycle_store.signatures[failure_cycle["cycle_id"]]
    assert success_sig.hits == 2
    assert failure_sig.hits == 1
    assert success_sig.promoted is False
    assert failure_sig.promoted is False

    success_followup = process_event(success_state, _user_event("followup-01", "继续"))
    failure_followup = process_event(failure_state, _user_event("followup-02", "继续"))

    assert success_followup.response_tendency.preferred_mode == "respond"
    assert failure_followup.response_tendency.preferred_mode == "repair"
    assert failure_output.trace_payload["reflection_trigger"] == "external_failure"


def test_open_one_off_trajectories_do_not_promote_long_term_cycles():
    """
    T4: 非闭合、一次性、多样事件不应轻易固化为长期 cycle。
    """
    state = ProtoSelfState.empty()
    events = [
        _user_event("open-01", "读取文件"),
        _user_event("open-02", "重启服务"),
        _user_event("open-03", "状态查询"),
        _user_event("open-04", "你好"),
    ]

    for event in events:
        process_event(state, event)

    signatures = list(state.cycle_store.signatures.values())
    assert len(signatures) == 4
    assert max(signature.hits for signature in signatures) == 1
    assert all(signature.promoted is False for signature in signatures)
    assert all(signature.outcome_signature == "unknown" for signature in signatures)
