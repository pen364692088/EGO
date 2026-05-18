"""P4 regression tests for real-mainline family alignment and repair closure."""

from __future__ import annotations

from pathlib import Path

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event
from openemotion.proto_self.state import ProtoSelfState as ProtoSelfStateModel
from openemotion.proto_self.trace_types import ProtoSelfTracePayload


REPO_ROOT = Path(__file__).resolve().parents[4]
REAL_SAMPLE_DIRS = [
    REPO_ROOT / "artifacts/telegram_real_mainline_v1/real_telegram/sample_20260326_230059_8ded092c",
    REPO_ROOT / "artifacts/telegram_real_mainline_v1/real_telegram/sample_20260326_230231_74277be4",
    REPO_ROOT / "artifacts/telegram_real_mainline_v1/real_telegram/sample_20260326_230256_0fbd5ecc",
]


def _user_event(event_id: str, text: str) -> KernelEvent:
    return KernelEvent(
        event_id=event_id,
        timestamp=f"2026-03-26T23:00:{event_id[-2:]}",
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent=text,
        raw_text=text,
        safety_context={"risk_level": "low"},
    )


def _tool_file_event(
    event_id: str,
    *,
    success: bool,
    risk_level: str,
    error: str | None = None,
) -> KernelEvent:
    return KernelEvent(
        event_id=event_id,
        timestamp=f"2026-03-26T23:01:{event_id[-2:]}",
        actor="system",
        source="runtime",
        event_type="tool_result",
        safety_context={"risk_level": risk_level},
        external_result={
            "success": success,
            "tool": "file",
            "exit_code": 0 if success else 1,
            "error": error,
        },
    )


def test_real_sample_artifacts_exist_for_p4_anchor():
    for sample_dir in REAL_SAMPLE_DIRS:
        assert sample_dir.exists(), f"missing real sample anchor: {sample_dir}"


def test_real_mainline_equivalent_retry_chain_lights_repair_closure():
    state = ProtoSelfState.empty()

    process_event(
        state,
        _user_event(
            "p4-real-01",
            r"读取 D:\Project\AIProject\MyProject\Test\missing_closure_probe.md 前 1 行",
        ),
    )
    blocked_output = process_event(
        state,
        _tool_file_event(
            "p4-real-02",
            success=False,
            risk_level="high",
            error="blocked: file not found",
        ),
    )
    process_event(
        state,
        _user_event(
            "p4-real-03",
            r"如果刚才失败了，现在读取 D:\Project\AIProject\MyProject\Test\CLAUDE.md 前 1 行",
        ),
    )
    retry_success = process_event(
        state,
        _tool_file_event("p4-real-04", success=True, risk_level="low"),
    )
    process_event(
        state,
        _user_event(
            "p4-real-05",
            r"再读取一次 D:\Project\AIProject\MyProject\Test\CLAUDE.md 前 1 行",
        ),
    )
    repeat_success = process_event(
        state,
        _tool_file_event("p4-real-06", success=True, risk_level="low"),
    )

    blocked_cycle = blocked_output.trace_payload["cycle_delta"]
    retry_cycle = retry_success.trace_payload["cycle_delta"]
    repeat_cycle = repeat_success.trace_payload["cycle_delta"]

    assert blocked_cycle["closure_family_id"] == retry_cycle["closure_family_id"]
    assert retry_cycle["closure_family_id"] == repeat_cycle["closure_family_id"]
    assert blocked_cycle["closure_signature"] != retry_cycle["closure_signature"]
    assert retry_cycle["repair_closure"] is True
    assert blocked_cycle["mode_signature"] == "repair"


def test_high_risk_blocked_and_low_risk_success_share_family_but_split_identity():
    blocked_state = ProtoSelfState.empty()
    success_state = ProtoSelfState.empty()

    blocked_output = process_event(
        blocked_state,
        _tool_file_event(
            "p4-family-01",
            success=False,
            risk_level="high",
            error="blocked: missing file",
        ),
    )
    success_output = process_event(
        success_state,
        _tool_file_event("p4-family-02", success=True, risk_level="low"),
    )

    blocked_cycle = blocked_output.trace_payload["cycle_delta"]
    success_cycle = success_output.trace_payload["cycle_delta"]

    assert blocked_cycle["closure_family_id"] == success_cycle["closure_family_id"]
    assert blocked_cycle["closure_signature"] != success_cycle["closure_signature"]
    assert blocked_cycle["psi_bucket"] != success_cycle["psi_bucket"]
    assert blocked_cycle["action_signature"] == success_cycle["action_signature"] == "tool:file"


def test_legacy_state_and_trace_loading_stay_compatible():
    legacy_state = ProtoSelfStateModel.from_dict(
        {
            "cycle_store": {
                "signatures": {
                    "legacy-cycle": {
                        "cycle_id": "legacy-cycle",
                        "psi_bucket": "runtime:tool_result:general",
                        "phi_signature": "neutral",
                    }
                }
            },
            "episodic_trace": [
                {
                    "event_id": "legacy-episode",
                    "perceived_summary": {"event_type": "tool_result"},
                    "external_result": {"success": False, "tool": "file"},
                }
            ],
        }
    )

    signature = legacy_state.cycle_store.signatures["legacy-cycle"]
    assert signature.closure_signature == "legacy-cycle"
    assert signature.closure_family_id == "legacy-cycle"
    assert signature.outcome_signature == "unknown"

    legacy_trace = ProtoSelfTracePayload.from_dict(
        {
            "event_id": "legacy-trace",
            "perceived": {"event_type": "tool_result"},
            "cycle_delta": {"cycle_id": "legacy-cycle"},
            "policy_hint": {},
        }
    )
    assert legacy_trace.event_id == "legacy-trace"
    assert legacy_trace.closure_signature == ""
    assert legacy_trace.closure_family_id == ""
