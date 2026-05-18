from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Mapping


CLAIM_CEILING = (
    "lab-only permissioned runtime action contract; no real action execution, "
    "no desktop control, no external send, no runtime enablement, no live benefit, "
    "no consciousness, no alive status"
)

PERMISSION_SCHEMA_VERSION = "v7.stage7.permissioned_action.v1"

DECISION_ALLOW = "allow"
DECISION_ASK = "ask"
DECISION_BLOCK = "block"

DANGEROUS_ACTIONS = frozenset({"file_delete", "system_command", "external_send", "desktop_control"})
DEFAULT_ALLOWLIST = frozenset({"suggestion_to_action_handoff", "read_only_observation", "dry_run_plan"})


@dataclass(frozen=True)
class PermissionedActionSpec:
    action_id: str
    action_class: str
    description: str
    requires_user_approval: bool
    rollback_note: str
    audit_required: bool = True
    execution_enabled: bool = False
    schema_version: str = PERMISSION_SCHEMA_VERSION
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    action_id: str
    user_approved: bool
    approval_source: str
    evidence_refs: tuple[str, ...]
    claim_ceiling: str = CLAIM_CEILING

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return _jsonable(payload)


@dataclass(frozen=True)
class KillSwitchState:
    active: bool
    reason: str
    evidence_refs: tuple[str, ...]
    claim_ceiling: str = CLAIM_CEILING

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return _jsonable(payload)


@dataclass(frozen=True)
class AuditRecord:
    audit_id: str
    action_id: str
    decision: str
    reason: str
    rollback_note: str
    execution_enabled: bool
    no_action_executed: bool
    evidence_refs: tuple[str, ...]
    claim_ceiling: str = CLAIM_CEILING

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return _jsonable(payload)


@dataclass(frozen=True)
class PermissionDecision:
    action_spec: dict[str, Any]
    approval_request: dict[str, Any] | None
    kill_switch: dict[str, Any]
    decision: str
    reason: str
    audit_record: dict[str, Any]
    outcome_experience_surface: dict[str, Any]
    no_action_executed: bool = True
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class PermissionedActionProbeResult:
    sample_id: str
    decisions: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    trace: dict[str, Any]
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decisions"] = list(self.decisions)
        return _jsonable(payload)


def evaluate_permissioned_action(
    action: PermissionedActionSpec | Mapping[str, Any],
    *,
    approval: ApprovalRequest | Mapping[str, Any] | None = None,
    kill_switch: KillSwitchState | Mapping[str, Any] | None = None,
    allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
) -> PermissionDecision:
    spec = action if isinstance(action, PermissionedActionSpec) else permissioned_action_spec_from_mapping(action)
    active_kill_switch = (
        kill_switch
        if isinstance(kill_switch, KillSwitchState)
        else kill_switch_state_from_mapping(kill_switch or {"active": False, "reason": "inactive"})
    )
    approval_request = (
        approval
        if isinstance(approval, ApprovalRequest)
        else approval_request_from_mapping(approval) if approval is not None else None
    )
    decision, reason = _permission_decision(spec, approval_request, active_kill_switch, allowlist)
    audit = AuditRecord(
        audit_id=f"audit:{spec.action_id}:{decision}",
        action_id=spec.action_id,
        decision=decision,
        reason=reason,
        rollback_note=spec.rollback_note,
        execution_enabled=False,
        no_action_executed=True,
        evidence_refs=(
            f"permission:action:{spec.action_id}",
            *(approval_request.evidence_refs if approval_request else ()),
            *active_kill_switch.evidence_refs,
        ),
    )
    return PermissionDecision(
        action_spec=spec.to_dict(),
        approval_request=approval_request.to_dict() if approval_request else None,
        kill_switch=active_kill_switch.to_dict(),
        decision=decision,
        reason=reason,
        audit_record=audit.to_dict(),
        outcome_experience_surface={
            "can_record_outcome": decision in {DECISION_ALLOW, DECISION_ASK, DECISION_BLOCK},
            "writes_runtime_memory": False,
            "writes_openemotion_state": False,
            "writes_formal_evidence": False,
            "claim": "outcome can be proposed back to ExperienceMemory only by a later gated stage",
        },
    )


def run_permission_contract_probe(sample_id: str = "v7-stage-7:permission_contract") -> PermissionedActionProbeResult:
    kill_switch_off = KillSwitchState(active=False, reason="inactive", evidence_refs=(f"lab:{sample_id}:kill_off",))
    kill_switch_on = KillSwitchState(active=True, reason="operator kill switch enabled", evidence_refs=(f"lab:{sample_id}:kill_on",))
    decisions = (
        evaluate_permissioned_action(
            PermissionedActionSpec(
                action_id="action:delete-file",
                action_class="file_delete",
                description="delete a file",
                requires_user_approval=True,
                rollback_note="Restore from backup if explicitly approved and audited.",
            ),
            kill_switch=kill_switch_off,
        ),
        evaluate_permissioned_action(
            PermissionedActionSpec(
                action_id="action:handoff-suggestion",
                action_class="suggestion_to_action_handoff",
                description="offer a proposal for user-approved handoff",
                requires_user_approval=True,
                rollback_note="Do not hand off if approval is missing.",
            ),
            approval=ApprovalRequest(
                request_id="approval:missing",
                action_id="action:handoff-suggestion",
                user_approved=False,
                approval_source="operator_fixture",
                evidence_refs=(f"lab:{sample_id}:approval_missing",),
            ),
            kill_switch=kill_switch_off,
        ),
        evaluate_permissioned_action(
            PermissionedActionSpec(
                action_id="action:approved-read-only",
                action_class="read_only_observation",
                description="read-only observation handoff",
                requires_user_approval=True,
                rollback_note="Stop observation and discard copied summary.",
            ),
            approval=ApprovalRequest(
                request_id="approval:read-only",
                action_id="action:approved-read-only",
                user_approved=True,
                approval_source="operator_fixture",
                evidence_refs=(f"lab:{sample_id}:approval_read_only",),
            ),
            kill_switch=kill_switch_off,
        ),
        evaluate_permissioned_action(
            PermissionedActionSpec(
                action_id="action:kill-switch-test",
                action_class="read_only_observation",
                description="read-only observation while kill switch active",
                requires_user_approval=True,
                rollback_note="Stop immediately when kill switch is active.",
            ),
            approval=ApprovalRequest(
                request_id="approval:kill-switch-test",
                action_id="action:kill-switch-test",
                user_approved=True,
                approval_source="operator_fixture",
                evidence_refs=(f"lab:{sample_id}:approval_kill_test",),
            ),
            kill_switch=kill_switch_on,
        ),
    )
    decision_dicts = tuple(item.to_dict() for item in decisions)
    summary = {
        "unauthorized_block_count": sum(1 for item in decision_dicts if item["decision"] == DECISION_BLOCK),
        "ask_count": sum(1 for item in decision_dicts if item["decision"] == DECISION_ASK),
        "allow_count": sum(1 for item in decision_dicts if item["decision"] == DECISION_ALLOW),
        "audit_record_count": len(decision_dicts),
        "no_action_executed_rate": round(
            sum(1 for item in decision_dicts if item["no_action_executed"]) / len(decision_dicts),
            6,
        ),
        "all_auditable": all(bool(item.get("audit_record")) for item in decision_dicts),
        "outcome_surface_count": sum(1 for item in decision_dicts if item["outcome_experience_surface"]["can_record_outcome"]),
        "kill_switch_blocked": decision_dicts[-1]["decision"] == DECISION_BLOCK,
    }
    return PermissionedActionProbeResult(
        sample_id=sample_id,
        decisions=decision_dicts,
        summary=summary,
        trace={
            "sample_id": sample_id,
            "trace_sample_id": sample_id,
            "permission_decisions": list(decision_dicts),
            "summary": summary,
        },
    )


def build_permission_operator_report(output_path: Path) -> Path:
    result = run_permission_contract_probe()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_format_permission_report(result), encoding="utf-8")
    return output_path


def permissioned_action_spec_from_mapping(data: Mapping[str, Any]) -> PermissionedActionSpec:
    return PermissionedActionSpec(
        action_id=str(data.get("action_id") or "action:unknown"),
        action_class=str(data.get("action_class") or "unknown"),
        description=str(data.get("description") or ""),
        requires_user_approval=bool(data.get("requires_user_approval", True)),
        rollback_note=str(data.get("rollback_note") or "No rollback note supplied."),
        audit_required=bool(data.get("audit_required", True)),
        execution_enabled=bool(data.get("execution_enabled", False)),
    )


def approval_request_from_mapping(data: Mapping[str, Any]) -> ApprovalRequest:
    return ApprovalRequest(
        request_id=str(data.get("request_id") or "approval:unknown"),
        action_id=str(data.get("action_id") or "action:unknown"),
        user_approved=bool(data.get("user_approved", False)),
        approval_source=str(data.get("approval_source") or "unknown"),
        evidence_refs=tuple(str(item) for item in data.get("evidence_refs") or ()),
    )


def kill_switch_state_from_mapping(data: Mapping[str, Any]) -> KillSwitchState:
    return KillSwitchState(
        active=bool(data.get("active", False)),
        reason=str(data.get("reason") or "inactive"),
        evidence_refs=tuple(str(item) for item in data.get("evidence_refs") or ()),
    )


def _permission_decision(
    spec: PermissionedActionSpec,
    approval: ApprovalRequest | None,
    kill_switch: KillSwitchState,
    allowlist: frozenset[str],
) -> tuple[str, str]:
    if kill_switch.active:
        return DECISION_BLOCK, f"kill switch active: {kill_switch.reason}"
    if spec.action_class in DANGEROUS_ACTIONS:
        return DECISION_BLOCK, f"dangerous action class blocked: {spec.action_class}"
    if spec.action_class not in allowlist:
        return DECISION_BLOCK, f"action class not allowlisted: {spec.action_class}"
    if spec.requires_user_approval and (approval is None or not approval.user_approved):
        return DECISION_ASK, "user approval required before handoff"
    return DECISION_ALLOW, "permission contract allows proposal handoff only; execution remains disabled"


def _format_permission_report(result: PermissionedActionProbeResult) -> str:
    data = result.to_dict()
    summary = data["summary"]
    lines = [
        "# v7 Stage 7 Permissioned Runtime Action Contract Report",
        "",
        "This report is lab-only. It validates permission semantics without enabling real actions.",
        "",
        "## Summary",
        f"unauthorized_block_count = {summary['unauthorized_block_count']}",
        f"ask_count = {summary['ask_count']}",
        f"allow_count = {summary['allow_count']}",
        f"audit_record_count = {summary['audit_record_count']}",
        f"no_action_executed_rate = {summary['no_action_executed_rate']}",
        f"kill_switch_blocked = {_bool_text(summary['kill_switch_blocked'])}",
        f"claim_ceiling = {CLAIM_CEILING}",
        "",
        "## Decisions",
        json.dumps(data["decisions"], indent=2, sort_keys=True, ensure_ascii=False),
        "",
    ]
    return "\n".join(lines)


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
