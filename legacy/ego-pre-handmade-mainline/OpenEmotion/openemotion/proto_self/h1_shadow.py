from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


H1_RUNTIME_FIELD = "h1_canonical_shadow"
H1_SHADOW_PREFIX = "shadow_h1::"
H1_DEFAULT_SUCCESS = 0.55
H1_GUARD_THRESHOLD = 0.35
H1_SOURCE = "canonical_shadow"


def extract_h1_shadow_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get(H1_RUNTIME_FIELD) or {})
    enabled = bool(raw.get("enabled"))
    shadow_only = bool(raw.get("shadow_only"))
    allowlisted = raw.get("allowlisted")
    if allowlisted is None:
        allowlisted = enabled
    return {
        "enabled": enabled,
        "shadow_only": shadow_only,
        "allowlisted": bool(allowlisted),
        "source": str(raw.get("source") or H1_SOURCE),
        "rollout_owner": str(raw.get("rollout_owner") or "egocore.runtime_v2"),
    }


def is_h1_shadow_enabled(runtime_summary: Dict[str, Any] | None) -> bool:
    context = extract_h1_shadow_context(runtime_summary)
    return (
        context.get("enabled") is True
        and context.get("shadow_only") is True
        and context.get("allowlisted") is True
    )


def normalize_h1_action_key(value: Any) -> str:
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


def resolve_h1_action_key(perceived: Mapping[str, Any]) -> str:
    return normalize_h1_action_key(perceived.get("action_class_seed"))


def is_h1_shadow_observable_path(perceived: Mapping[str, Any]) -> bool:
    event_type = str(perceived.get("event_type") or "").strip().lower()
    action_key = resolve_h1_action_key(perceived)
    if event_type not in {"tool_result", "exec_result"}:
        return False
    return action_key.startswith("tool:")


def build_h1_shadow_key(action_key: str) -> str:
    return f"{H1_SHADOW_PREFIX}{normalize_h1_action_key(action_key)}"


def is_h1_shadow_key(key: Any) -> bool:
    return str(key or "").startswith(H1_SHADOW_PREFIX)


def filter_live_counterfactual_entries(mapping: Mapping[str, Any] | None) -> Dict[str, float]:
    filtered: Dict[str, float] = {}
    for key, value in dict(mapping or {}).items():
        if is_h1_shadow_key(key):
            continue
        filtered[str(key)] = float(value)
    return filtered


def filter_live_correction_entries(mapping: Mapping[str, Any] | None) -> Dict[str, float]:
    filtered: Dict[str, float] = {}
    for key, value in dict(mapping or {}).items():
        if is_h1_shadow_key(key):
            continue
        filtered[str(key)] = float(value)
    return filtered


def _shadow_value(mapping: Mapping[str, Any] | None, action_key: str, default: float) -> float:
    if action_key == "unknown":
        return default
    shadow_key = build_h1_shadow_key(action_key)
    return float(dict(mapping or {}).get(shadow_key, default))


def build_shadow_h1_summary(
    *,
    state: Any,
    perceived: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    if not perceived.get("h1_shadow_active"):
        return None
    if not is_h1_shadow_observable_path(perceived):
        return None
    action_key = resolve_h1_action_key(perceived)
    if action_key == "unknown":
        return None
    context = extract_h1_shadow_context(perceived.get("runtime_summary"))
    predicted_success = _shadow_value(
        getattr(state.self_model, "counterfactual_success_by_action", {}),
        action_key,
        H1_DEFAULT_SUCCESS,
    )
    recent_correction_tag = _shadow_value(
        getattr(state.self_model, "recent_correction_tags", {}),
        action_key,
        0.0,
    )
    viability_pressure = float(getattr(state.drives, "viability_pressure", 0.0) or 0.0)
    would_guard = predicted_success < H1_GUARD_THRESHOLD
    return {
        "enabled": True,
        "shadow_only": True,
        "action_key": action_key,
        "predicted_success": round(predicted_success, 4),
        "threshold": H1_GUARD_THRESHOLD,
        "would_guard": would_guard,
        "would_ask": would_guard,
        "source": context.get("source") or H1_SOURCE,
        "neighboring_signals": {
            "recent_correction_tag": round(recent_correction_tag, 4),
            "viability_pressure": round(viability_pressure, 4),
        },
    }


def build_shadow_h1_confidence_meta(summary: Mapping[str, Any]) -> Dict[str, Any]:
    neighboring = dict(summary.get("neighboring_signals") or {})
    return {
        "shadow_h1_enabled": bool(summary.get("enabled")),
        "shadow_h1_action_key": str(summary.get("action_key") or ""),
        "shadow_h1_predicted_success": float(summary.get("predicted_success") or H1_DEFAULT_SUCCESS),
        "shadow_h1_threshold": float(summary.get("threshold") or H1_GUARD_THRESHOLD),
        "shadow_h1_would_guard": bool(summary.get("would_guard")),
        "shadow_h1_would_ask": bool(summary.get("would_ask")),
        "shadow_h1_recent_correction_tag": float(neighboring.get("recent_correction_tag") or 0.0),
        "shadow_h1_viability_pressure": float(neighboring.get("viability_pressure") or 0.0),
    }
