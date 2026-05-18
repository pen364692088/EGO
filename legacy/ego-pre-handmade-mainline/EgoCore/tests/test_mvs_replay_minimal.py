from __future__ import annotations

from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter
from app.openemotion_adapter.proto_self_state_store import ProtoSelfStateStore
from app.runtime_v2.proto_self_runtime import build_external_result_event, build_proto_self_ingress_event
from app.runtime_v2.state import RuntimeV2State


def _adapter(tmp_path):
    mirror_dir = tmp_path / "mirror"
    return ProtoSelfAdapter(
        mirror_dir=mirror_dir,
        state_store=ProtoSelfStateStore(
            root_dir=tmp_path / "proto_self_store",
            legacy_mirror_dir=mirror_dir,
        ),
    )


def _patch_mvs(payload, *, experiment_id: str, variant_id: str, action_family: str, safety: dict | None = None):
    runtime_summary = dict(payload.get("runtime_summary") or {})
    runtime_summary["state_scope"] = "experiment"
    runtime_summary["experiment_id"] = experiment_id
    runtime_summary["mvs_replay"] = {
        "enabled": True,
        "shadow_only": True,
        "variant_id": variant_id,
        "action_family": action_family,
    }
    payload["runtime_summary"] = runtime_summary
    if safety:
        payload["safety_context"] = dict(payload.get("safety_context") or {})
        payload["safety_context"].update(safety)
    return payload


def _preload_mvs_state(
    adapter: ProtoSelfAdapter,
    *,
    experiment_id: str,
    boundary_confidence: dict[str, float] | None = None,
):
    state = adapter.state_store.load_experiment_state(experiment_id)
    state.self_model.boundary_confidence_by_action = dict(boundary_confidence or {})
    adapter.state_store.save_experiment_state(experiment_id, state)


def test_mvs_candidate_uses_boundary_confidence_across_low_cue_followup(monkeypatch, tmp_path):
    monkeypatch.setenv("EGO_ENABLE_MVS_REPLAY_PROTOTYPE", "true")
    adapter = _adapter(tmp_path)
    experiment_id = "mvs.boundary.continuity"
    _preload_mvs_state(
        adapter,
        experiment_id=experiment_id,
        boundary_confidence={"tool:file": 0.18},
    )
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    candidate = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_001",
        source="replay",
        user_input="Continue the same bounded lane.",
        state=state,
    )
    candidate = _patch_mvs(
        candidate,
        experiment_id=experiment_id,
        variant_id="mvs_candidate_aligned_compact",
        action_family="tool:file",
    )
    candidate_result = adapter.handle_event(candidate)

    baseline = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_001",
        source="replay",
        user_input="Continue the same bounded lane.",
        state=state,
    )
    baseline = _patch_mvs(
        baseline,
        experiment_id=f"{experiment_id}.baseline",
        variant_id="mvs_baseline_proto_self_mainline",
        action_family="tool:file",
    )
    _preload_mvs_state(
        adapter,
        experiment_id=f"{experiment_id}.baseline",
        boundary_confidence={"tool:file": 0.18},
    )
    baseline_result = adapter.handle_event(baseline)

    assert candidate_result["policy_hint"]["mvs_boundary_guard"] == "low_boundary_confidence"
    assert candidate_result["policy_hint"]["ask_preferred"] is True
    assert "mvs_boundary_guard" not in baseline_result["policy_hint"]


def test_mvs_candidate_failure_trace_and_state_patches_are_replayable(monkeypatch, tmp_path):
    monkeypatch.setenv("EGO_ENABLE_MVS_REPLAY_PROTOTYPE", "true")
    adapter = _adapter(tmp_path)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    ingress = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_001",
        source="replay",
        user_input="Inspect the same shell task safely.",
        state=state,
    )
    ingress = _patch_mvs(
        ingress,
        experiment_id="mvs.failure.loop",
        variant_id="mvs_candidate_aligned_compact",
        action_family="tool:shell",
    )
    adapter.handle_event(ingress)

    failure = build_external_result_event(
        session_id="session:test",
        turn_id="turn_001",
        step=0,
        tool_result={"success": False, "tool": "shell", "exit_code": 126, "stderr": "permission denied"},
        state=state,
    )
    failure = _patch_mvs(
        failure,
        experiment_id="mvs.failure.loop",
        variant_id="mvs_candidate_aligned_compact",
        action_family="tool:shell",
    )
    failure_result = adapter.handle_event(failure)
    snapshot = adapter.state_store.load_experiment_state_v2("mvs.failure.loop").to_v1()
    trace = failure_result["trace_payload"]

    assert failure_result["memory_update"]["corrective_trace"]["actual_outcome"] == "blocked"
    assert snapshot.drives.viability_pressure > 0.0
    assert snapshot.self_model.counterfactual_success_by_action["tool:shell"] <= 0.18
    assert snapshot.self_model.boundary_confidence_by_action["tool:shell"] <= 0.18
    assert trace["predicted_outcome"] == 0.55
    assert trace["actual_outcome"] == "blocked"
    assert trace["adjustment_applied"] == "repair_and_request_replan"
    assert trace["next_guard"] == "request_replan"
    assert trace["replay_variant_id"] == "mvs_candidate_aligned_compact"


def test_mvs_challenger_partial_retry_uses_viability_guard_and_closes_repair(monkeypatch, tmp_path):
    monkeypatch.setenv("EGO_ENABLE_MVS_REPLAY_PROTOTYPE", "true")
    adapter = _adapter(tmp_path)
    experiment_id = "mvs.active_inference.partial"
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    ingress = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_001",
        source="replay",
        user_input="Try the same bounded repo operation.",
        state=state,
    )
    ingress = _patch_mvs(
        ingress,
        experiment_id=experiment_id,
        variant_id="mvs_challenger_active_inference_self_model",
        action_family="tool:repo",
    )
    adapter.handle_event(ingress)

    partial = build_external_result_event(
        session_id="session:test",
        turn_id="turn_001",
        step=0,
        tool_result={"partial": True, "tool": "repo", "stdout": "partial context restored"},
        state=state,
    )
    partial = _patch_mvs(
        partial,
        experiment_id=experiment_id,
        variant_id="mvs_challenger_active_inference_self_model",
        action_family="tool:repo",
    )
    partial_result = adapter.handle_event(partial)
    partial_snapshot = adapter.state_store.load_experiment_state_v2(experiment_id).to_v1()

    retry = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_002",
        source="replay",
        user_input="Retry after the partial result with the same bounded lane.",
        state=state,
    )
    retry = _patch_mvs(
        retry,
        experiment_id=experiment_id,
        variant_id="mvs_challenger_active_inference_self_model",
        action_family="tool:repo",
    )
    retry_result = adapter.handle_event(retry)

    success = build_external_result_event(
        session_id="session:test",
        turn_id="turn_002",
        step=1,
        tool_result={"success": True, "tool": "repo", "stdout": "ok"},
        state=state,
    )
    success = _patch_mvs(
        success,
        experiment_id=experiment_id,
        variant_id="mvs_challenger_active_inference_self_model",
        action_family="tool:repo",
    )
    success_result = adapter.handle_event(success)

    assert partial_snapshot.drives.viability_pressure >= 0.35
    assert partial_snapshot.self_model.uncertainty_by_action["tool:repo"] >= 0.68
    assert retry_result["policy_hint"]["guard_reason"] == "viability_pressure"
    assert retry_result["policy_hint"]["mvs_tension_active"] is True
    assert retry_result["policy_hint"]["mvs_active_inference_guard"] == "uncertainty_control"
    success_cycle = dict(
        success_result["trace_payload"].get("cycle_delta")
        or success_result["trace_payload"].get("cycles_delta")
        or {}
    )
    assert success_cycle["repair_closure"] is True
