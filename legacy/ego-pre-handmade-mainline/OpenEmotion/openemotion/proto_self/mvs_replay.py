from __future__ import annotations

import os
from typing import Any, Dict


MVS_REPLAY_FEATURE_FLAG_ENV = "EGO_ENABLE_MVS_REPLAY_PROTOTYPE"
LEGACY_TRIAL1_FEATURE_FLAG_ENV = "EGO_ENABLE_MVS_TRIAL1_SHADOW"
MVS_REPLAY_RUNTIME_FIELD = "mvs_replay"
LEGACY_TRIAL1_RUNTIME_FIELD = "trial1_shadow"

MVS_BASELINE_A_ID = "mvs_baseline_proto_self_mainline"
MVS_BASELINE_B_ID = "baseline_chat_surface"
MVS_CANDIDATE_ID = "mvs_candidate_aligned_compact"
MVS_ABLATION_MINUS_COUNTERFACTUAL_ID = "mvs_minus_counterfactual_writeback"
MVS_ABLATION_MINUS_VIABILITY_ID = "mvs_minus_viability_pressure"
MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID = "mvs_minus_corrective_trace"
MVS_ABLATION_MINUS_BOUNDARY_ID = "mvs_minus_boundary_confidence"
MVS_CHALLENGER_ID = "mvs_challenger_active_inference_self_model"

LEGACY_TRIAL1_BASELINE_ID = "trial1_baseline_proto_self_mainline"
LEGACY_TRIAL1_CANDIDATE_ID = "trial1_candidate_mvs_aligned_compact"
LEGACY_TRIAL1_ABLATION_MINUS_COUNTERFACTUAL_ID = "trial1_ablation_minus_counterfactual_writeback"
LEGACY_TRIAL1_ABLATION_MINUS_VIABILITY_ID = "trial1_ablation_minus_viability_pressure"
LEGACY_TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID = "trial1_ablation_minus_corrective_trace"
LEGACY_TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID = (
    "trial1_ablation_counterfactual_public_path_sever"
)
LEGACY_TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID = (
    "trial1_ablation_alternative_explanation_isolation"
)
LEGACY_TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID = (
    "trial2_ablation_correction_public_path_sever"
)
LEGACY_TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID = (
    "trial2_ablation_viability_public_path_sever"
)
LEGACY_TRIAL1_CHALLENGER_ID = "trial1_challenger_active_inference_self_model"

LEGACY_TO_CANONICAL_VARIANT_IDS = {
    LEGACY_TRIAL1_BASELINE_ID: MVS_BASELINE_A_ID,
    LEGACY_TRIAL1_CANDIDATE_ID: MVS_CANDIDATE_ID,
    LEGACY_TRIAL1_ABLATION_MINUS_COUNTERFACTUAL_ID: MVS_ABLATION_MINUS_COUNTERFACTUAL_ID,
    LEGACY_TRIAL1_ABLATION_MINUS_VIABILITY_ID: MVS_ABLATION_MINUS_VIABILITY_ID,
    LEGACY_TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID: MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
    LEGACY_TRIAL1_CHALLENGER_ID: MVS_CHALLENGER_ID,
}

LEGACY_DIAGNOSTIC_VARIANT_IDS = {
    LEGACY_TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
    LEGACY_TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
    LEGACY_TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID,
    LEGACY_TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID,
}

MVS_REQUIRED_FAMILY_IDS = (
    "identity_continuity",
    "decision_conflict",
    "failure_repair_retry",
)

MVS_SUPPORTED_VARIANT_IDS = {
    MVS_BASELINE_A_ID,
    MVS_CANDIDATE_ID,
    MVS_ABLATION_MINUS_COUNTERFACTUAL_ID,
    MVS_ABLATION_MINUS_VIABILITY_ID,
    MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
    MVS_ABLATION_MINUS_BOUNDARY_ID,
    MVS_CHALLENGER_ID,
    *LEGACY_TO_CANONICAL_VARIANT_IDS.keys(),
    *LEGACY_DIAGNOSTIC_VARIANT_IDS,
}

MVS_SYNTHETIC_SOURCE_TYPES = {
    "synthetic",
    "simulated",
    "synthetic_audit",
    "synthetic_replay",
}

MVS_BANNED_SOURCE_REF_MARKERS = (
    "SELF_AWARENESS_PROXY_EXPERIMENT_CURRENT",
    "SELF_AWARENESS_MVS_ALIGNMENT_CURRENT",
    "SELF_AWARENESS_LITERATURE_10K_CURRENT",
    "SELF_MODEL_OPERATIONAL_EVAL_CURRENT",
    "SELF_MODEL_SELECTION_ROBUSTNESS_CURRENT",
)


def feature_flag_enabled() -> bool:
    return any(
        os.environ.get(env_name, "false").strip().lower() == "true"
        for env_name in (MVS_REPLAY_FEATURE_FLAG_ENV, LEGACY_TRIAL1_FEATURE_FLAG_ENV)
    )


def normalize_mvs_variant_id(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return MVS_BASELINE_A_ID
    if raw in LEGACY_TO_CANONICAL_VARIANT_IDS:
        return LEGACY_TO_CANONICAL_VARIANT_IDS[raw]
    if raw in {
        MVS_BASELINE_A_ID,
        MVS_CANDIDATE_ID,
        MVS_ABLATION_MINUS_COUNTERFACTUAL_ID,
        MVS_ABLATION_MINUS_VIABILITY_ID,
        MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        MVS_ABLATION_MINUS_BOUNDARY_ID,
        MVS_CHALLENGER_ID,
    }:
        return raw
    if raw in LEGACY_DIAGNOSTIC_VARIANT_IDS:
        return raw
    return MVS_BASELINE_A_ID


def extract_mvs_replay_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    runtime_summary = dict(runtime_summary or {})
    raw = dict(
        runtime_summary.get(MVS_REPLAY_RUNTIME_FIELD)
        or runtime_summary.get(LEGACY_TRIAL1_RUNTIME_FIELD)
        or {}
    )
    raw_variant = str(raw.get("variant_id") or MVS_BASELINE_A_ID)
    raw["variant_id"] = normalize_mvs_variant_id(raw_variant)
    raw["raw_variant_id"] = raw_variant
    raw["enabled"] = bool(raw.get("enabled"))
    raw["shadow_only"] = bool(raw.get("shadow_only"))
    return raw


def is_mvs_replay_enabled(runtime_summary: Dict[str, Any] | None) -> bool:
    context = extract_mvs_replay_context(runtime_summary)
    return feature_flag_enabled() and context.get("enabled") is True and context.get("shadow_only") is True


def resolve_mvs_variant_id(runtime_summary: Dict[str, Any] | None) -> str:
    return str(extract_mvs_replay_context(runtime_summary).get("variant_id") or MVS_BASELINE_A_ID)


def normalize_mvs_action_family(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unknown"
    safe = []
    for char in raw:
        if char.isalnum() or char in {":", "-", "_", "."}:
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe) or "unknown"


def derive_mvs_action_family(
    *,
    runtime_summary: Dict[str, Any] | None,
    event_type: str,
    external_result: Dict[str, Any] | None,
) -> str:
    context = extract_mvs_replay_context(runtime_summary)
    explicit = normalize_mvs_action_family(context.get("action_family"))
    if explicit != "unknown":
        return explicit

    executed_action_prev = dict((runtime_summary or {}).get("executed_action_prev") or {})
    tool = str((external_result or {}).get("tool") or executed_action_prev.get("tool") or "").strip().lower()
    if tool:
        return normalize_mvs_action_family(f"tool:{tool}")

    kind = str(executed_action_prev.get("kind") or "").strip().lower()
    if kind:
        return normalize_mvs_action_family(f"action:{kind}")

    if event_type == "user_message":
        return "ingress:user_request"
    if event_type == "tool_result":
        return "tool:unknown"
    return normalize_mvs_action_family(f"observe:{event_type or 'unknown'}")


def build_mvs_probe_key(action_family: str) -> str:
    return normalize_mvs_action_family(action_family)


def build_mvs_contract() -> Dict[str, Any]:
    return {
        "baseline_a_id": MVS_BASELINE_A_ID,
        "baseline_b_id": MVS_BASELINE_B_ID,
        "candidate_id": MVS_CANDIDATE_ID,
        "ablation_ids": [
            MVS_ABLATION_MINUS_COUNTERFACTUAL_ID,
            MVS_ABLATION_MINUS_VIABILITY_ID,
            MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
            MVS_ABLATION_MINUS_BOUNDARY_ID,
        ],
        "challenger_id": MVS_CHALLENGER_ID,
        "supported_variant_ids": sorted(MVS_SUPPORTED_VARIANT_IDS),
    }


def iter_mvs_cases(manifest: Dict[str, Any]) -> list[Dict[str, Any]]:
    cases: list[Dict[str, Any]] = []
    episode_items = list(manifest.get("episodes") or [])
    if episode_items:
        for episode in episode_items:
            item = dict(episode)
            item["case_id"] = str(item.get("case_id") or item.get("episode_id") or "").strip()
            item["family"] = str(item.get("family") or "").strip()
            if "steps" not in item:
                step = dict(item.get("kernel_event") or {})
                item["steps"] = [step] if step else []
            cases.append(item)
        return cases
    for bucket in list(manifest.get("buckets") or []):
        family_id = str(bucket.get("bucket_id") or "").strip()
        for case in list(bucket.get("cases") or []):
            item = dict(case)
            item["family"] = family_id
            cases.append(item)
    return cases


def find_mvs_manifest_leakage(manifest: Dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for case in iter_mvs_cases(manifest):
        case_id = str(case.get("case_id") or "unknown")
        source_type = str(case.get("source_type") or "").strip().lower()
        source_ref = str(case.get("source_ref") or "")
        if source_type in MVS_SYNTHETIC_SOURCE_TYPES:
            errors.append(f"{case_id}: synthetic source_type is not allowed: {source_type}")
        lowered_ref = source_ref.lower()
        for marker in MVS_BANNED_SOURCE_REF_MARKERS:
            if marker.lower() in lowered_ref:
                errors.append(f"{case_id}: source_ref leaks synthetic audit artifact: {marker}")
    return errors


def validate_mvs_manifest(manifest: Dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract = dict(manifest.get("runner_contract") or {})
    expected_contract = build_mvs_contract()
    for key in ("baseline_a_id", "baseline_b_id", "candidate_id", "challenger_id"):
        if contract.get(key) != expected_contract.get(key):
            errors.append(f"runner_contract.{key} does not match canonical contract")
    if list(contract.get("ablation_ids") or []) != expected_contract["ablation_ids"]:
        errors.append("runner_contract.ablation_ids does not match canonical contract")

    family_counts: Dict[str, int] = {}
    total_cases = 0
    cases_with_external_result = 0
    seen_case_ids: set[str] = set()
    for case in iter_mvs_cases(manifest):
        total_cases += 1
        family_id = str(case.get("family") or "").strip()
        family_counts[family_id] = family_counts.get(family_id, 0) + 1

        case_id = str(case.get("case_id") or "").strip()
        if not case_id:
            errors.append("case_id is required for every MVS replay case")
            continue
        if case_id in seen_case_ids:
            errors.append(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)

        steps = list(case.get("steps") or [])
        if not steps:
            errors.append(f"{case_id}: at least one step is required")
        if any(step.get("kind") == "tool_result" for step in steps):
            cases_with_external_result += 1
        if "expected_scoring_surface" not in case:
            errors.append(f"{case_id}: expected_scoring_surface is required")

    for family_id in MVS_REQUIRED_FAMILY_IDS:
        if family_counts.get(family_id, 0) < 20:
            errors.append(f"{family_id}: expected at least 20 cases")
    if total_cases < 60:
        errors.append("manifest must contain at least 60 replay episodes")
    if total_cases > 0 and cases_with_external_result / total_cases < 0.30:
        errors.append("at least 30% of cases must include external_result/tool_result steps")

    errors.extend(find_mvs_manifest_leakage(manifest))
    return errors


def mvs_variant_uses_counterfactual(variant_id: str) -> bool:
    normalized = normalize_mvs_variant_id(variant_id)
    return normalized in {
        MVS_CANDIDATE_ID,
        MVS_CHALLENGER_ID,
        MVS_ABLATION_MINUS_VIABILITY_ID,
        MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        MVS_ABLATION_MINUS_BOUNDARY_ID,
    } or variant_id in {
        LEGACY_TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
        LEGACY_TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
        LEGACY_TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID,
        LEGACY_TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID,
    }


def mvs_variant_uses_viability(variant_id: str) -> bool:
    normalized = normalize_mvs_variant_id(variant_id)
    return normalized in {
        MVS_CANDIDATE_ID,
        MVS_CHALLENGER_ID,
        MVS_ABLATION_MINUS_COUNTERFACTUAL_ID,
        MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        MVS_ABLATION_MINUS_BOUNDARY_ID,
    } or variant_id in {
        LEGACY_TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
        LEGACY_TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
    }


def mvs_variant_uses_corrective_trace(variant_id: str) -> bool:
    normalized = normalize_mvs_variant_id(variant_id)
    return normalized in {
        MVS_CANDIDATE_ID,
        MVS_CHALLENGER_ID,
        MVS_ABLATION_MINUS_COUNTERFACTUAL_ID,
        MVS_ABLATION_MINUS_VIABILITY_ID,
        MVS_ABLATION_MINUS_BOUNDARY_ID,
    } or variant_id in {
        LEGACY_TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
        LEGACY_TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
    }


def mvs_variant_uses_boundary_confidence(variant_id: str) -> bool:
    normalized = normalize_mvs_variant_id(variant_id)
    return normalized in {
        MVS_CANDIDATE_ID,
        MVS_CHALLENGER_ID,
        MVS_ABLATION_MINUS_COUNTERFACTUAL_ID,
        MVS_ABLATION_MINUS_VIABILITY_ID,
        MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
    }


def mvs_variant_uses_mvs_core(variant_id: str) -> bool:
    normalized = normalize_mvs_variant_id(variant_id)
    return normalized in {
        MVS_CANDIDATE_ID,
        MVS_CHALLENGER_ID,
        MVS_ABLATION_MINUS_COUNTERFACTUAL_ID,
        MVS_ABLATION_MINUS_VIABILITY_ID,
        MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        MVS_ABLATION_MINUS_BOUNDARY_ID,
    } or variant_id in LEGACY_DIAGNOSTIC_VARIANT_IDS


def mvs_variant_uses_active_inference_core(variant_id: str) -> bool:
    return normalize_mvs_variant_id(variant_id) == MVS_CHALLENGER_ID


def mvs_variant_uses_counterfactual_public_path(variant_id: str) -> bool:
    if variant_id == LEGACY_TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID:
        return False
    return mvs_variant_uses_counterfactual(variant_id)


def mvs_variant_uses_correction_public_path(variant_id: str) -> bool:
    if variant_id == LEGACY_TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID:
        return False
    if variant_id == LEGACY_TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID:
        return False
    normalized = normalize_mvs_variant_id(variant_id)
    if normalized == MVS_ABLATION_MINUS_CORRECTIVE_TRACE_ID:
        return False
    return mvs_variant_uses_corrective_trace(variant_id)


def mvs_variant_uses_viability_public_path(variant_id: str) -> bool:
    if variant_id == LEGACY_TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID:
        return False
    if variant_id == LEGACY_TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID:
        return False
    normalized = normalize_mvs_variant_id(variant_id)
    if normalized == MVS_ABLATION_MINUS_VIABILITY_ID:
        return False
    return mvs_variant_uses_viability(variant_id)


def mvs_variant_uses_boundary_public_path(variant_id: str) -> bool:
    normalized = normalize_mvs_variant_id(variant_id)
    if normalized == MVS_ABLATION_MINUS_BOUNDARY_ID:
        return False
    return mvs_variant_uses_boundary_confidence(variant_id)
