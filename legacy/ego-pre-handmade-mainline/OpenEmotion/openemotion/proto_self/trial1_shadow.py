from __future__ import annotations

import os
from typing import Any, Dict


TRIAL1_FEATURE_FLAG_ENV = "EGO_ENABLE_MVS_TRIAL1_SHADOW"
TRIAL1_RUNTIME_FIELD = "trial1_shadow"

TRIAL1_BASELINE_ID = "trial1_baseline_proto_self_mainline"
TRIAL1_CANDIDATE_ID = "trial1_candidate_mvs_aligned_compact"
TRIAL1_ABLATION_MINUS_COUNTERFACTUAL_ID = "trial1_ablation_minus_counterfactual_writeback"
TRIAL1_ABLATION_MINUS_VIABILITY_ID = "trial1_ablation_minus_viability_pressure"
TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID = "trial1_ablation_minus_corrective_trace"
TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID = "trial1_ablation_counterfactual_public_path_sever"
TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID = "trial1_ablation_alternative_explanation_isolation"
TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID = "trial2_ablation_correction_public_path_sever"
TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID = "trial2_ablation_viability_public_path_sever"
TRIAL1_CHALLENGER_ID = "trial1_challenger_active_inference_self_model"

TRIAL1_ABLATION_IDS = (
    TRIAL1_ABLATION_MINUS_COUNTERFACTUAL_ID,
    TRIAL1_ABLATION_MINUS_VIABILITY_ID,
    TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
)

TRIAL1_DIAGNOSTIC_ABLATION_IDS = (
    TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
    TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
    TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID,
    TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID,
)

TRIAL1_SUPPORTED_VARIANT_IDS = {
    TRIAL1_BASELINE_ID,
    TRIAL1_CANDIDATE_ID,
    *TRIAL1_ABLATION_IDS,
    *TRIAL1_DIAGNOSTIC_ABLATION_IDS,
}

TRIAL1_SYNTHETIC_SOURCE_TYPES = {
    "synthetic",
    "simulated",
    "synthetic_audit",
    "synthetic_replay",
}

TRIAL1_BANNED_SOURCE_REF_MARKERS = (
    "SELF_AWARENESS_PROXY_EXPERIMENT_CURRENT",
    "SELF_AWARENESS_MVS_ALIGNMENT_CURRENT",
    "SELF_AWARENESS_LITERATURE_10K_CURRENT",
    "SELF_MODEL_OPERATIONAL_EVAL_CURRENT",
    "SELF_MODEL_SELECTION_ROBUSTNESS_CURRENT",
)

TRIAL1_REQUIRED_BUCKET_IDS = (
    "identity_continuity",
    "correction_override",
    "tension_driven_divergence",
    "failure_to_revision",
    "negative_controls",
    "restart_restore_boundary_cases",
)


def feature_flag_enabled() -> bool:
    return os.environ.get(TRIAL1_FEATURE_FLAG_ENV, "false").strip().lower() == "true"


def extract_trial1_shadow_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get(TRIAL1_RUNTIME_FIELD) or {})
    variant_id = str(raw.get("variant_id") or TRIAL1_BASELINE_ID)
    if variant_id not in TRIAL1_SUPPORTED_VARIANT_IDS and variant_id != TRIAL1_CHALLENGER_ID:
        variant_id = TRIAL1_BASELINE_ID
    raw["variant_id"] = variant_id
    raw["enabled"] = bool(raw.get("enabled"))
    raw["shadow_only"] = bool(raw.get("shadow_only"))
    return raw


def is_trial1_shadow_enabled(runtime_summary: Dict[str, Any] | None) -> bool:
    context = extract_trial1_shadow_context(runtime_summary)
    return feature_flag_enabled() and context.get("enabled") is True and context.get("shadow_only") is True


def resolve_trial1_variant_id(runtime_summary: Dict[str, Any] | None) -> str:
    return str(extract_trial1_shadow_context(runtime_summary).get("variant_id") or TRIAL1_BASELINE_ID)


def trial1_variant_uses_counterfactual(variant_id: str) -> bool:
    return variant_id in {
        TRIAL1_CANDIDATE_ID,
        TRIAL1_ABLATION_MINUS_VIABILITY_ID,
        TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
        TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
        TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID,
        TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID,
    }


def trial1_variant_uses_viability(variant_id: str) -> bool:
    return variant_id in {
        TRIAL1_CANDIDATE_ID,
        TRIAL1_ABLATION_MINUS_COUNTERFACTUAL_ID,
        TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
        TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
    }


def trial1_variant_uses_corrective_trace(variant_id: str) -> bool:
    return variant_id in {
        TRIAL1_CANDIDATE_ID,
        TRIAL1_ABLATION_MINUS_COUNTERFACTUAL_ID,
        TRIAL1_ABLATION_MINUS_VIABILITY_ID,
        TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
        TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
    }


def trial1_variant_uses_mvs_core(variant_id: str) -> bool:
    return variant_id in {
        TRIAL1_CANDIDATE_ID,
        *TRIAL1_ABLATION_IDS,
        *TRIAL1_DIAGNOSTIC_ABLATION_IDS,
    }


def normalize_trial1_action_family(value: str | None) -> str:
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


def derive_trial1_action_family(
    *,
    runtime_summary: Dict[str, Any] | None,
    event_type: str,
    external_result: Dict[str, Any] | None,
) -> str:
    context = extract_trial1_shadow_context(runtime_summary)
    explicit = normalize_trial1_action_family(context.get("action_family"))
    if explicit != "unknown":
        return explicit

    executed_action_prev = dict((runtime_summary or {}).get("executed_action_prev") or {})
    tool = str((external_result or {}).get("tool") or executed_action_prev.get("tool") or "").strip().lower()
    if tool:
        return normalize_trial1_action_family(f"tool:{tool}")

    kind = str(executed_action_prev.get("kind") or "").strip().lower()
    if kind:
        return normalize_trial1_action_family(f"action:{kind}")

    if event_type == "user_message":
        return "ingress:user_request"
    if event_type == "tool_result":
        return "tool:unknown"
    return normalize_trial1_action_family(f"observe:{event_type or 'unknown'}")


def build_trial1_probe_key(action_family: str) -> str:
    return normalize_trial1_action_family(action_family)


def build_trial1_contract(*, ablation_ids: tuple[str, ...] = TRIAL1_ABLATION_IDS) -> Dict[str, Any]:
    return {
        "baseline_id": TRIAL1_BASELINE_ID,
        "candidate_id": TRIAL1_CANDIDATE_ID,
        "ablation_ids": list(ablation_ids),
        "challenger_id": TRIAL1_CHALLENGER_ID,
        "supported_variant_ids": sorted(TRIAL1_SUPPORTED_VARIANT_IDS),
    }


def iter_trial1_cases(manifest: Dict[str, Any]) -> list[Dict[str, Any]]:
    cases: list[Dict[str, Any]] = []
    for bucket in list(manifest.get("buckets") or []):
        bucket_id = str(bucket.get("bucket_id") or "").strip()
        for case in list(bucket.get("cases") or []):
            item = dict(case)
            item["bucket_id"] = bucket_id
            cases.append(item)
    return cases


def find_trial1_manifest_leakage(manifest: Dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for case in iter_trial1_cases(manifest):
        case_id = str(case.get("case_id") or "unknown")
        source_type = str(case.get("source_type") or "").strip().lower()
        source_ref = str(case.get("source_ref") or "")
        if source_type in TRIAL1_SYNTHETIC_SOURCE_TYPES:
            errors.append(f"{case_id}: synthetic source_type is not allowed: {source_type}")
        lowered_ref = source_ref.lower()
        for marker in TRIAL1_BANNED_SOURCE_REF_MARKERS:
            if marker.lower() in lowered_ref:
                errors.append(f"{case_id}: source_ref leaks synthetic audit artifact: {marker}")
    return errors


def validate_trial1_manifest(manifest: Dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract = dict(manifest.get("runner_contract") or {})
    expected_contract = build_trial1_contract()
    for key in ("baseline_id", "candidate_id", "challenger_id"):
        if contract.get(key) != expected_contract.get(key):
            errors.append(f"runner_contract.{key} does not match canonical contract")
    if list(contract.get("ablation_ids") or []) != expected_contract["ablation_ids"]:
        errors.append("runner_contract.ablation_ids does not match canonical contract")

    bucket_ids = [str(bucket.get("bucket_id") or "") for bucket in list(manifest.get("buckets") or [])]
    if sorted(bucket_ids) != sorted(TRIAL1_REQUIRED_BUCKET_IDS):
        errors.append("bucket set does not match Trial-1 required bucket ids")

    seen_case_ids: set[str] = set()
    for case in iter_trial1_cases(manifest):
        case_id = str(case.get("case_id") or "").strip()
        if not case_id:
            errors.append("case_id is required for every Trial-1 case")
            continue
        if case_id in seen_case_ids:
            errors.append(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)
        if not list(case.get("steps") or []):
            errors.append(f"{case_id}: at least one step is required")

    errors.extend(find_trial1_manifest_leakage(manifest))
    return errors


def trial1_variant_uses_counterfactual_public_path(variant_id: str) -> bool:
    return variant_id in {
        TRIAL1_CANDIDATE_ID,
        TRIAL1_ABLATION_MINUS_VIABILITY_ID,
        TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
        TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID,
        TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID,
    }


def trial1_variant_uses_correction_public_path(variant_id: str) -> bool:
    return variant_id in {
        TRIAL1_CANDIDATE_ID,
        TRIAL1_ABLATION_MINUS_COUNTERFACTUAL_ID,
        TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
        TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID,
    }


def trial1_variant_uses_viability_public_path(variant_id: str) -> bool:
    return variant_id in {
        TRIAL1_CANDIDATE_ID,
        TRIAL1_ABLATION_MINUS_COUNTERFACTUAL_ID,
        TRIAL1_ABLATION_MINUS_CORRECTIVE_TRACE_ID,
        TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
        TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID,
    }
