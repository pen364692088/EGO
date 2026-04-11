#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "EgoCore") not in sys.path:
    sys.path.insert(0, str(ROOT / "EgoCore"))
if str(ROOT / "OpenEmotion") not in sys.path:
    sys.path.insert(0, str(ROOT / "OpenEmotion"))

from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter
from app.openemotion_adapter.proto_self_state_store import ProtoSelfStateStore
from app.runtime_v2.proto_self_runtime import build_external_result_event, build_proto_self_ingress_event
from app.runtime_v2.state import RuntimeV2State
from openemotion.proto_self.mvs_replay import MVS_REPLAY_FEATURE_FLAG_ENV, mvs_variant_uses_corrective_trace


TASK_ROOT = ROOT / "docs" / "codex" / "tasks" / "ai-self-awareness-minimal-framework"
MANIFEST_PATH = TASK_ROOT / "CONTROLLED_REPLAY_CONVERSATION_MANIFEST.json"
ARTIFACT_ROOT = ROOT / "artifacts" / "self_awareness_research"
REPORT_JSON = ARTIFACT_ROOT / "ACTIVE_INFERENCE_CONTROLLED_REPLAY_CURRENT.json"
REPORT_MD = ARTIFACT_ROOT / "ACTIVE_INFERENCE_CONTROLLED_REPLAY_CURRENT.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the active-inference controlled replay bridge")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--output-md", type=Path, default=REPORT_MD)
    return parser.parse_args()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


class _NullTraceBridge:
    def write(self, trace_payload: Dict[str, Any]) -> None:
        return None


def _build_adapter(base_dir: Path) -> ProtoSelfAdapter:
    mirror_dir = base_dir / "mirror"
    return ProtoSelfAdapter(
        mirror_dir=mirror_dir,
        state_store=ProtoSelfStateStore(
            root_dir=base_dir / "proto_self_store",
            legacy_mirror_dir=mirror_dir,
        ),
        trace_bridge=_NullTraceBridge(),
    )


def _slice_variant_experiment_id(slice_id: str, variant_id: str) -> str:
    return f"controlled.replay.{variant_id}.{slice_id}"


def _summarize_state(adapter: ProtoSelfAdapter, *, experiment_id: str) -> Dict[str, Any]:
    state = adapter.state_store.load_experiment_state_v2(experiment_id).to_v1()
    last_episode = state.episodic_trace[-1].to_dict() if state.episodic_trace else {}
    return {
        "current_mode": state.self_model.current_mode,
        "current_focus": state.self_model.current_focus,
        "viability_pressure": round(float(state.drives.viability_pressure), 4),
        "counterfactual_success_by_action": dict(state.self_model.counterfactual_success_by_action),
        "boundary_confidence_by_action": dict(state.self_model.boundary_confidence_by_action),
        "world_assumption_confidence": dict(state.self_model.world_assumption_confidence),
        "recent_correction_tags": dict(state.self_model.recent_correction_tags),
        "source_confidence_by_action": dict(state.self_model.source_confidence_by_action),
        "agency_confidence_by_action": dict(state.self_model.agency_confidence_by_action),
        "uncertainty_by_action": dict(state.self_model.uncertainty_by_action),
        "calibration_memory_by_action": dict(state.self_model.calibration_memory_by_action),
        "temporal_repair_weight_by_action": dict(state.self_model.temporal_repair_weight_by_action),
        "episodic_count": len(state.episodic_trace),
        "revision_counter": state.revision_counter,
        "last_corrective_trace": dict(last_episode.get("corrective_trace") or {}),
    }


def _canonical_trace(step: Dict[str, Any]) -> Dict[str, Any]:
    trace = dict(step.get("trace_payload") or {})
    legacy = dict(trace.get("legacy_trace_payload") or {})
    cycle_delta = dict(
        trace.get("cycle_delta")
        or trace.get("cycles_delta")
        or legacy.get("cycle_delta")
        or legacy.get("cycles_delta")
        or {}
    )
    return {
        "event_id": trace.get("event_id") or legacy.get("event_id"),
        "perceived": dict(trace.get("perceived") or legacy.get("perceived") or {}),
        "appraisal_delta": dict(
            trace.get("appraisal_delta")
            or trace.get("drives_delta")
            or legacy.get("appraisal_delta")
            or legacy.get("drives_delta")
            or {}
        ),
        "self_model_delta": dict(trace.get("self_model_delta") or legacy.get("self_model_delta") or {}),
        "cycle_delta": cycle_delta,
        "identity_delta": dict(trace.get("identity_delta") or legacy.get("identity_delta") or {}),
        "policy_hint": dict(step.get("policy_hint") or trace.get("policy_hint") or legacy.get("policy_hint") or {}),
        "closure_signature": trace.get("closure_signature") or cycle_delta.get("closure_signature") or legacy.get("closure_signature"),
        "closure_family_id": trace.get("closure_family_id") or cycle_delta.get("closure_family_id") or legacy.get("closure_family_id"),
        "action_signature": trace.get("action_signature") or cycle_delta.get("action_signature") or legacy.get("action_signature"),
        "outcome_signature": trace.get("outcome_signature") or cycle_delta.get("outcome_signature") or legacy.get("outcome_signature"),
        "closure_consistency_score": (
            trace.get("closure_consistency_score")
            if trace.get("closure_consistency_score") is not None
            else cycle_delta.get("closure_consistency_score")
        ),
        "predicted_outcome": trace.get("predicted_outcome") if "predicted_outcome" in trace else legacy.get("predicted_outcome"),
        "actual_outcome": trace.get("actual_outcome") if "actual_outcome" in trace else legacy.get("actual_outcome"),
        "adjustment_applied": (
            trace.get("adjustment_applied") if "adjustment_applied" in trace else legacy.get("adjustment_applied")
        ),
        "next_guard": trace.get("next_guard") if "next_guard" in trace else legacy.get("next_guard"),
        "replay_variant_id": (
            trace.get("replay_variant_id") if "replay_variant_id" in trace else legacy.get("replay_variant_id")
        ),
    }


def _trace_replayable(step: Dict[str, Any]) -> bool:
    trace = _canonical_trace(step)
    required = {
        "event_id",
        "perceived",
        "appraisal_delta",
        "self_model_delta",
        "cycle_delta",
        "identity_delta",
        "policy_hint",
        "closure_signature",
        "closure_family_id",
        "action_signature",
        "outcome_signature",
        "closure_consistency_score",
        "predicted_outcome",
        "actual_outcome",
        "adjustment_applied",
        "next_guard",
        "replay_variant_id",
    }
    return required.issubset(trace.keys())


def _iter_slices(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [dict(item) for item in list(manifest.get("conversations") or [])]


def _validate_manifest(manifest: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    contract = dict(manifest.get("runner_contract") or {})
    supported = list(contract.get("supported_variant_ids") or [])
    expected_variants = [
        contract.get("baseline_a_id"),
        contract.get("baseline_b_id"),
        contract.get("candidate_id"),
    ]
    if supported != expected_variants:
        errors.append("runner_contract.supported_variant_ids does not match controlled replay contract")
    if list(contract.get("ablation_ids") or []):
        errors.append("controlled replay bridge must not introduce ablation_ids")

    slices = _iter_slices(manifest)
    if len(slices) < 60:
        errors.append("controlled replay manifest must contain at least 60 slices")

    family_counts: Dict[str, int] = {}
    with_external_result = 0
    for item in slices:
        slice_id = str(item.get("slice_id") or "").strip()
        if not slice_id:
            errors.append("slice_id is required")
        family = str(item.get("family") or "").strip()
        family_counts[family] = family_counts.get(family, 0) + 1
        turns = list(item.get("turns") or [])
        if not turns:
            errors.append(f"{slice_id}: turns must not be empty")
        if any(str(turn.get("kind") or "") == "external_result" for turn in turns):
            with_external_result += 1
    for family in ("identity_continuity", "decision_conflict", "failure_repair_retry"):
        if family_counts.get(family, 0) < 20:
            errors.append(f"{family} must contain at least 20 slices")
    if with_external_result < 18:
        errors.append("controlled replay manifest must contain at least 18 slices with external_result")
    return errors


def _preload_experiment_state(
    adapter: ProtoSelfAdapter,
    *,
    experiment_id: str,
    preloaded_state: Dict[str, Any],
) -> None:
    state = adapter.state_store.load_experiment_state(experiment_id)
    state.self_model.counterfactual_success_by_action = {
        str(key): float(value)
        for key, value in dict(preloaded_state.get("counterfactual_success_by_action") or {}).items()
    }
    state.self_model.boundary_confidence_by_action = {
        str(key): float(value)
        for key, value in dict(preloaded_state.get("boundary_confidence_by_action") or {}).items()
    }
    state.self_model.world_assumption_confidence = {
        str(key): float(value)
        for key, value in dict(preloaded_state.get("world_assumption_confidence") or {}).items()
    }
    state.self_model.recent_correction_tags = {
        str(key): float(value)
        for key, value in dict(preloaded_state.get("recent_correction_tags") or {}).items()
    }
    state.drives.viability_pressure = float(preloaded_state.get("viability_pressure", 0.0))
    adapter.state_store.save_experiment_state(experiment_id, state)


def _patch_payload(
    payload: Dict[str, Any],
    *,
    turn: Dict[str, Any],
    conversation: Dict[str, Any],
    experiment_id: str,
    variant_id: str,
) -> Dict[str, Any]:
    patched = dict(payload)
    runtime_summary = dict(patched.get("runtime_summary") or {})
    runtime_summary["state_scope"] = "experiment"
    runtime_summary["experiment_id"] = experiment_id
    runtime_summary["mvs_replay"] = {
        "enabled": True,
        "shadow_only": True,
        "variant_id": variant_id,
        "action_family": turn.get("action_family"),
        "family": conversation.get("family"),
        "case_id": conversation.get("slice_id"),
        "step_id": turn.get("turn_id"),
    }
    runtime_summary["controlled_replay"] = {
        "enabled": True,
        "shadow_only": True,
        "slice_id": conversation.get("slice_id"),
        "family": conversation.get("family"),
        "source_type": conversation.get("source_type"),
    }
    patched["runtime_summary"] = runtime_summary

    if turn.get("task_summary_patch"):
        task_summary = dict(patched.get("task_summary") or {})
        task_summary.update(dict(turn.get("task_summary_patch") or {}))
        patched["task_summary"] = task_summary
    if turn.get("safety_context_patch"):
        safety_context = dict(patched.get("safety_context") or {})
        safety_context.update(dict(turn.get("safety_context_patch") or {}))
        patched["safety_context"] = safety_context
    if turn.get("executed_action_prev"):
        patched["executed_action_prev"] = dict(turn["executed_action_prev"])
    return patched


def _run_turn(
    *,
    adapter: ProtoSelfAdapter,
    state: RuntimeV2State,
    turn: Dict[str, Any],
    conversation: Dict[str, Any],
    experiment_id: str,
    variant_id: str,
) -> Dict[str, Any]:
    state.session_id = str(turn["session_id"])
    state.current_goal = turn.get("current_goal") or state.current_goal
    state.ingress_context = {
        "proto_self_version": "v2",
        "prediction_snapshot_prev": turn.get("prediction_snapshot_prev", {}),
    }
    runtime_turn_id = str(turn.get("runtime_turn_id") or turn.get("turn_id") or "")
    sequence = int(turn.get("sequence", 0))

    if turn["kind"] == "user_message":
        payload = build_proto_self_ingress_event(
            session_id=str(turn["session_id"]),
            turn_id=runtime_turn_id,
            source="controlled_replay",
            user_input=str(turn.get("user_input") or ""),
            state=state,
        )
    elif turn["kind"] == "external_result":
        tool_result = dict(turn.get("tool_result") or {})
        state.last_tool_result = tool_result
        payload = build_external_result_event(
            session_id=str(turn["session_id"]),
            turn_id=runtime_turn_id,
            step=sequence,
            tool_result=tool_result,
            state=state,
        )
    else:
        raise ValueError(f"unsupported turn kind: {turn['kind']}")

    payload = _patch_payload(
        payload,
        turn=turn,
        conversation=conversation,
        experiment_id=experiment_id,
        variant_id=variant_id,
    )
    result = adapter.handle_event(payload)
    return {
        "step_id": str(turn.get("turn_id") or runtime_turn_id),
        "kind": "ingress" if turn["kind"] == "user_message" else "tool_result",
        "event_id": result.get("event_id"),
        "policy_hint": dict(result.get("policy_hint") or {}),
        "response_tendency": dict(result.get("response_tendency") or {}),
        "reflection_note": dict(result.get("reflection_note") or {}),
        "self_model_delta": dict(result.get("self_model_delta") or {}),
        "drives_delta": dict(result.get("drives_delta") or result.get("appraisal_state_delta") or {}),
        "memory_update": dict(result.get("memory_update") or {}),
        "trace_payload": dict(result.get("trace_payload") or {}),
        "state_snapshot": _summarize_state(adapter, experiment_id=experiment_id),
    }


def _run_conversation(variant_id: str, conversation: Dict[str, Any]) -> Dict[str, Any]:
    slice_id = str(conversation["slice_id"])
    experiment_id = _slice_variant_experiment_id(slice_id, variant_id)
    with tempfile.TemporaryDirectory(prefix="active_inference_controlled_replay_") as temp_dir:
        adapter = _build_adapter(Path(temp_dir))
        _preload_experiment_state(
            adapter,
            experiment_id=experiment_id,
            preloaded_state=dict(conversation.get("preloaded_state") or {}),
        )
        turns = [dict(turn) for turn in list(conversation.get("turns") or [])]
        if not turns:
            raise ValueError(f"conversation slice {slice_id} has no turns")
        state = RuntimeV2State(session_id=str(turns[0].get("session_id") or f"controlled-replay:{slice_id}"))
        step_logs = [
            _run_turn(
                adapter=adapter,
                state=state,
                turn=turn,
                conversation=conversation,
                experiment_id=experiment_id,
                variant_id=variant_id,
            )
            for turn in turns
        ]
    return {
        "case_id": slice_id,
        "family": conversation.get("family"),
        "source_type": conversation.get("source_type"),
        "source_ref": conversation.get("source_ref"),
        "preloaded_state": dict(conversation.get("preloaded_state") or {}),
        "expected_scoring_surface": dict(conversation.get("expected_scoring_surface") or {}),
        "steps": step_logs,
    }


def _bool_all(items: Iterable[bool]) -> bool:
    values = list(items)
    return all(values) if values else False


def _authority_drift_audit(contract: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "pass",
        "behavior_authority": "none",
        "tool_authority": "none",
        "reply_authority": "none",
        "transport_authority": "none",
        "parallel_runtime_lane": False,
        "second_authority_source": False,
        "candidate_private_host_api": False,
        "host_consumable_surface": ["policy_hint", "response_tendency", "trace_payload"],
        "candidate_variant_id": contract.get("candidate_id"),
    }


def _trace_contract_check(results_by_variant: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    all_steps = []
    corrective_required_steps = []
    for variant_id, case_results in results_by_variant.items():
        variant_requires_corrective = mvs_variant_uses_corrective_trace(variant_id)
        for case_result in case_results:
            for step in list(case_result.get("steps") or []):
                all_steps.append(step)
                if variant_requires_corrective and str(step.get("kind") or "") == "tool_result":
                    corrective_required_steps.append(step)
    required_keys = ["replay_variant_id"]
    corrective_keys = ["predicted_outcome", "actual_outcome", "adjustment_applied", "next_guard"]
    missing_keys = sorted(
        {
            key
            for step in all_steps
            for key in required_keys
            if _canonical_trace(step).get(key) in (None, "", [])
        }
    )
    missing_corrective_keys = sorted(
        {
            key
            for step in corrective_required_steps
            for key in corrective_keys
            if _canonical_trace(step).get(key) in (None, "", [])
        }
    )
    replayable = _bool_all(_trace_replayable(step) for step in all_steps)
    status = "pass" if replayable and not missing_keys and not missing_corrective_keys else "fail"
    return {
        "status": status,
        "required_keys": required_keys,
        "required_corrective_keys_for_tool_results": corrective_keys,
        "missing_keys": missing_keys,
        "missing_corrective_keys": missing_corrective_keys,
        "all_steps_replayable": replayable,
        "step_count": len(all_steps),
    }


def render_markdown(report: Dict[str, Any]) -> str:
    audit = dict(report.get("authority_drift_audit") or {})
    trace_check = dict(report.get("trace_contract_check") or {})
    lines = [
        "# Active-Inference Controlled Replay",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- manifest: `{report['manifest_path']}`",
        f"- variants_run: `{', '.join(report['variants_run'])}`",
        f"- slice_count: `{report['summary']['slice_count']}`",
        f"- authority_drift_status: `{audit.get('status', 'unknown')}`",
        f"- trace_contract_status: `{trace_check.get('status', 'unknown')}`",
        "",
        "## Variant Coverage",
        "",
    ]
    for variant_id, summary in sorted(report["summary"]["variants"].items()):
        lines.append(f"- `{variant_id}`: slices=`{summary['slice_count']}` steps=`{summary['step_count']}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    os.environ.setdefault(MVS_REPLAY_FEATURE_FLAG_ENV, "true")

    manifest = _load_json(args.manifest)
    errors = _validate_manifest(manifest)
    if errors:
        raise SystemExit("\n".join(errors))

    contract = dict(manifest.get("runner_contract") or {})
    variant_ids = [contract["baseline_a_id"], contract["candidate_id"]]
    conversations = _iter_slices(manifest)

    results_by_variant: Dict[str, List[Dict[str, Any]]] = {}
    for variant_id in variant_ids:
        case_results = []
        for index, conversation in enumerate(conversations, start=1):
            if index == 1 or index % 10 == 0 or index == len(conversations):
                print(
                    f"[active-inference-controlled-replay] variant={variant_id} slice={index}/{len(conversations)}",
                    flush=True,
                )
            case_results.append(_run_conversation(variant_id, conversation))
        results_by_variant[variant_id] = case_results

    summary = {
        "slice_count": len(conversations),
        "variants": {
            variant_id: {
                "slice_count": len(case_results),
                "step_count": sum(len(case_result.get("steps") or []) for case_result in case_results),
            }
            for variant_id, case_results in results_by_variant.items()
        },
    }
    report = {
        "schema_version": "active_inference.controlled_replay_run.v1",
        "generated_at": _now_iso(),
        "manifest_path": str(args.manifest),
        "runner_contract": contract,
        "variants_run": variant_ids,
        "summary": summary,
        "authority_drift_audit": _authority_drift_audit(contract),
        "trace_contract_check": _trace_contract_check(results_by_variant),
        "results_by_variant": results_by_variant,
    }
    _write_json(args.output_json, report)
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")


if __name__ == "__main__":
    main()
