from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Sequence


@dataclass(frozen=True)
class ToolDeliveryBridgeDecision:
    authority_source: str
    source: str
    applied_authority: Optional[str]
    tool_name: str
    success: bool
    target_path: Optional[str]
    artifact_refs: tuple[str, ...]
    delivery_channel: str
    requires_user_delivery: bool
    delivery_ready: bool
    delivery_gap: bool
    fidelity_mode: str
    fidelity_gap: bool
    delivery_kind: Optional[str]
    reply_preview: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_tool_delivery_bridge_decision(
    tool_result: Dict[str, Any] | None,
    *,
    reply_text: str = "",
    delivery_kind: Optional[str] = None,
    source: str,
    applied_authority: Optional[str] = None,
    fidelity_mode: Optional[str] = None,
    fidelity_gap: Optional[bool] = None,
) -> Optional[ToolDeliveryBridgeDecision]:
    payload = dict(tool_result or {})
    tool_name = str(payload.get("tool") or payload.get("tool_name") or "").strip()
    if not tool_name:
        return None

    metadata = dict(payload.get("metadata") or {})
    target_path = _first_non_empty(
        metadata.get("path"),
        metadata.get("target_path"),
        payload.get("cwd"),
    )
    artifact_refs = tuple(str(ref) for ref in _normalize_refs(payload, metadata))
    inline_output = str(payload.get("stdout") or payload.get("output") or "").strip()
    success = bool(payload.get("success"))

    if target_path or artifact_refs:
        delivery_channel = "artifact_or_path"
    elif inline_output:
        delivery_channel = "inline_output"
    else:
        delivery_channel = "none"

    requires_user_delivery = success and delivery_channel != "none"
    reply_preview = str(reply_text or "").strip()[:300]
    delivery_ready = requires_user_delivery and bool(reply_preview)
    delivery_gap = requires_user_delivery and not delivery_ready
    computed_fidelity_mode = fidelity_mode or _infer_fidelity_mode(
        delivery_channel=delivery_channel,
        reply_text=reply_text,
        inline_output=inline_output,
        delivery_ready=delivery_ready,
    )
    computed_fidelity_gap = (
        bool(fidelity_gap)
        if fidelity_gap is not None
        else requires_user_delivery and delivery_channel == "inline_output" and computed_fidelity_mode != "verbatim"
    )

    return ToolDeliveryBridgeDecision(
        authority_source="tools.delivery_bridge",
        source=source,
        applied_authority=applied_authority,
        tool_name=tool_name,
        success=success,
        target_path=target_path,
        artifact_refs=artifact_refs,
        delivery_channel=delivery_channel,
        requires_user_delivery=requires_user_delivery,
        delivery_ready=delivery_ready,
        delivery_gap=delivery_gap,
        fidelity_mode=computed_fidelity_mode,
        fidelity_gap=computed_fidelity_gap,
        delivery_kind=delivery_kind,
        reply_preview=reply_preview,
    )


def _normalize_refs(payload: Dict[str, Any], metadata: Dict[str, Any]) -> Sequence[str]:
    refs = payload.get("artifact_refs")
    if refs:
        return list(refs)
    metadata_refs = metadata.get("artifact_refs")
    if metadata_refs:
        return list(metadata_refs)
    return []


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _infer_fidelity_mode(
    *,
    delivery_channel: str,
    reply_text: str,
    inline_output: str,
    delivery_ready: bool,
) -> str:
    reply = str(reply_text or "").strip()
    body = str(inline_output or "").strip()
    if not delivery_ready:
        return "fallback"
    if delivery_channel != "inline_output":
        return "summary"
    if body and body in reply:
        return "verbatim"
    return "summary"
