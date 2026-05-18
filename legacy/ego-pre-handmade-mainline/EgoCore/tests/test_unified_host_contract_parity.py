from __future__ import annotations

from app.runtime_v2.unified_channel_contract import (
    HOST_CONTRACT_SNAPSHOT_VERSION,
    build_host_contract_snapshot,
    compare_host_contract_snapshots,
)
from app.runtime_v2.unified_host_contract_parity import PARITY_WINDOWS, run_unified_host_contract_parity


def test_compare_host_contract_snapshots_ignores_adapter_only_fields() -> None:
    left = {
        "contract_version": HOST_CONTRACT_SNAPSHOT_VERSION,
        "adapter": {
            "channel": "api",
            "source_kind": "dashboard_local",
            "raw_event_present": True,
            "transport_meta": {"session_id": "dashboard:test:parity"},
        },
        "request": {"session_key": "s", "user_input": "hi", "effective_user_input": "hi"},
        "ingress": {"runtime_action": "chat", "pre_runtime": {"should_return_early": False}},
        "turn": {"reply_text": "hello", "reply_authority": "model_chat"},
        "egress": {"should_send": True, "delivery_kind": "chat", "user_visible_text": "hello"},
    }
    right = {
        "contract_version": HOST_CONTRACT_SNAPSHOT_VERSION,
        "adapter": {
            "channel": "telegram",
            "source_kind": "telegram_prepared",
            "raw_event_present": False,
            "transport_meta": {"chat_id": 123},
        },
        "request": {"session_key": "s", "user_input": "hi", "effective_user_input": "hi"},
        "ingress": {"runtime_action": "chat", "pre_runtime": {"should_return_early": False}},
        "turn": {"reply_text": "hello", "reply_authority": "model_chat"},
        "egress": {"should_send": True, "delivery_kind": "chat", "user_visible_text": "hello"},
    }

    comparison = compare_host_contract_snapshots(left, right)

    assert comparison["match"] is True
    assert comparison["unexpected_diffs"] == []
    assert comparison["left_adapter"]["channel"] == "api"
    assert comparison["right_adapter"]["channel"] == "telegram"


def test_compare_host_contract_snapshots_detects_canonical_drift() -> None:
    left = {
        "contract_version": HOST_CONTRACT_SNAPSHOT_VERSION,
        "request": {"session_key": "s", "user_input": "hi", "effective_user_input": "hi"},
        "turn": {"reply_text": "hello", "reply_authority": "model_chat"},
    }
    right = {
        "contract_version": HOST_CONTRACT_SNAPSHOT_VERSION,
        "request": {"session_key": "s", "user_input": "hi", "effective_user_input": "hi"},
        "turn": {"reply_text": "different", "reply_authority": "model_chat"},
    }

    comparison = compare_host_contract_snapshots(left, right)

    assert comparison["match"] is False
    assert any(item["path"] == "turn.reply_text" for item in comparison["unexpected_diffs"])


def test_build_host_contract_snapshot_handles_partial_inputs() -> None:
    snapshot = build_host_contract_snapshot()

    assert snapshot["contract_version"] == HOST_CONTRACT_SNAPSHOT_VERSION
    assert "request" not in snapshot
    assert "turn" not in snapshot


def test_run_unified_host_contract_parity_reports_pass() -> None:
    report = run_unified_host_contract_parity()
    aggregate = dict(report.get("aggregate") or {})
    cases = list(report.get("cases") or [])

    assert report["source"] == "dashboard_local_vs_telegram_prepared_inprocess"
    assert report["claim_ceiling"] == "host_contract_only"
    assert aggregate["verdict"] == "pass"
    assert aggregate["parity_pass_count"] == aggregate["total_cases"] == len(cases)
    assert aggregate["hold_case_count"] == len(PARITY_WINDOWS["hold_probe_window"])
    assert aggregate["hold_consistency_pass_count"] == aggregate["hold_case_count"]
    assert any(case["expected_mode"] == "hold_for_followup" and case["hold_consistent"] is True for case in cases)
