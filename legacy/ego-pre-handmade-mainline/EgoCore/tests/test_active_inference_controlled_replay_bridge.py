from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_ROOT = ROOT / "docs" / "codex" / "tasks" / "ai-self-awareness-minimal-framework"
MANIFEST_PATH = TASK_ROOT / "CONTROLLED_REPLAY_CONVERSATION_MANIFEST.json"
RUNNER_PATH = ROOT / "scripts" / "codex" / "run_active_inference_controlled_replay.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_controlled_replay_manifest_is_canonical_and_minimum_sized() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "active_inference.controlled_replay_manifest.v1"
    assert manifest["runner_contract"] == {
        "baseline_a_id": "mvs_baseline_proto_self_mainline",
        "baseline_b_id": "baseline_chat_surface",
        "candidate_id": "mvs_challenger_active_inference_self_model",
        "ablation_ids": [],
        "supported_variant_ids": [
            "mvs_baseline_proto_self_mainline",
            "baseline_chat_surface",
            "mvs_challenger_active_inference_self_model",
        ],
    }
    assert manifest["slice_count"] >= 60
    assert manifest["family_counts"] == {
        "identity_continuity": 20,
        "decision_conflict": 20,
        "failure_repair_retry": 20,
    }
    slices = list(manifest.get("conversations") or [])
    assert sum(1 for item in slices if item.get("has_external_result")) >= 18
    assert all(item.get("slice_id") for item in slices)
    assert all(item.get("turns") for item in slices)


def test_trace_contract_check_requires_corrective_fields_only_for_corrective_variants() -> None:
    module = _load_module(RUNNER_PATH, "active_inference_controlled_replay_runner")
    trace_contract_check = module._trace_contract_check

    baseline_ingress_step = {
        "kind": "ingress",
        "policy_hint": {"ask_preferred": True},
        "trace_payload": {
            "event_id": "evt_ingress",
            "perceived": {"boundary_state": "boundary_touched"},
            "drives_delta": {},
            "self_model_delta": {},
            "cycles_delta": {
                "closure_signature": "sig_ingress",
                "closure_family_id": "fam_ingress",
                "action_signature": "tool:file",
                "outcome_signature": "unknown",
                "closure_consistency_score": 0.75,
            },
            "replay_variant_id": "mvs_challenger_active_inference_self_model",
        },
    }
    baseline_tool_result_step = {
        "kind": "tool_result",
        "policy_hint": {"guard_reason": "viability_pressure"},
        "trace_payload": {
            "event_id": "evt_tool_baseline",
            "perceived": {"boundary_state": "elevated_risk"},
            "drives_delta": {"viability_pressure": 0.6},
            "self_model_delta": {"current_mode": "repair"},
            "cycles_delta": {
                "closure_signature": "sig_tool_baseline",
                "closure_family_id": "fam_tool_baseline",
                "action_signature": "tool:file",
                "outcome_signature": "blocked",
                "closure_consistency_score": 0.8,
                "repair_closure": False,
            },
            "predicted_outcome": None,
            "actual_outcome": None,
            "adjustment_applied": None,
            "next_guard": None,
            "replay_variant_id": "mvs_baseline_proto_self_mainline",
        },
    }
    challenger_ingress_step = {
        "kind": "ingress",
        "policy_hint": {"ask_preferred": True},
        "trace_payload": {
            "event_id": "evt_ingress_challenger",
            "perceived": {"boundary_state": "boundary_touched"},
            "drives_delta": {},
            "self_model_delta": {},
            "cycles_delta": {
                "closure_signature": "sig_ingress_challenger",
                "closure_family_id": "fam_ingress_challenger",
                "action_signature": "tool:file",
                "outcome_signature": "unknown",
                "closure_consistency_score": 0.75,
            },
            "replay_variant_id": "mvs_challenger_active_inference_self_model",
        },
    }
    challenger_tool_result_step = {
        "kind": "tool_result",
        "policy_hint": {"guard_reason": "viability_pressure"},
        "trace_payload": {
            "event_id": "evt_tool",
            "perceived": {"boundary_state": "elevated_risk"},
            "drives_delta": {"viability_pressure": 0.6},
            "self_model_delta": {"current_mode": "repair"},
            "cycles_delta": {
                "closure_signature": "sig_tool",
                "closure_family_id": "fam_tool",
                "action_signature": "tool:file",
                "outcome_signature": "blocked",
                "closure_consistency_score": 0.8,
                "repair_closure": False,
            },
            "predicted_outcome": 0.55,
            "actual_outcome": "blocked",
            "adjustment_applied": "repair_and_request_replan",
            "next_guard": "request_replan",
            "replay_variant_id": "mvs_challenger_active_inference_self_model",
        },
    }

    check = trace_contract_check(
        {
            "mvs_baseline_proto_self_mainline": [{"steps": [baseline_ingress_step, baseline_tool_result_step]}],
            "mvs_challenger_active_inference_self_model": [{"steps": [challenger_ingress_step, challenger_tool_result_step]}],
        }
    )

    assert check["status"] == "pass"
    assert check["missing_keys"] == []
    assert check["missing_corrective_keys"] == []
