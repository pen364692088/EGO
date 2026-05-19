from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


RESULT_SCHEMA_VERSION = "subject_system_v1.result.v1"


@dataclass
class SubjectIdentityInvariants:
    identity_handle: str = ""
    tool_authority_boundary: Dict[str, Any] = field(default_factory=dict)
    limitations: list[Dict[str, Any]] = field(default_factory=list)
    active_goals: list[Dict[str, Any]] = field(default_factory=list)
    standing_commitments: list[Dict[str, Any]] = field(default_factory=list)
    confidence_by_domain: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_handle": self.identity_handle,
            "tool_authority_boundary": dict(self.tool_authority_boundary),
            "limitations": list(self.limitations),
            "active_goals": list(self.active_goals),
            "standing_commitments": list(self.standing_commitments),
            "confidence_by_domain": dict(self.confidence_by_domain),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any] | None) -> "SubjectIdentityInvariants":
        payload = dict(raw or {})
        return cls(
            identity_handle=str(payload.get("identity_handle") or ""),
            tool_authority_boundary=dict(payload.get("tool_authority_boundary") or {}),
            limitations=list(payload.get("limitations") or []),
            active_goals=list(payload.get("active_goals") or []),
            standing_commitments=list(payload.get("standing_commitments") or []),
            confidence_by_domain=dict(payload.get("confidence_by_domain") or {}),
        )


@dataclass
class SubjectSystemV1Result:
    schema_version: str = RESULT_SCHEMA_VERSION
    source_kernel: str = "openemotion.proto_self_v2"
    identity_invariants: SubjectIdentityInvariants = field(default_factory=SubjectIdentityInvariants)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    memory_update: Dict[str, Any] = field(default_factory=dict)
    appraisal_state_delta: Dict[str, Any] = field(default_factory=dict)
    reflection_writeback_candidate: Optional[Dict[str, Any]] = None
    policy_hint: Dict[str, Any] = field(default_factory=dict)
    response_tendency: Optional[Dict[str, Any]] = None
    host_proactive_candidate: Optional[Dict[str, Any]] = None
    trace_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_kernel": self.source_kernel,
            "identity_invariants": self.identity_invariants.to_dict(),
            "self_model_delta": dict(self.self_model_delta),
            "memory_update": dict(self.memory_update),
            "appraisal_state_delta": dict(self.appraisal_state_delta),
            "reflection_writeback_candidate": (
                dict(self.reflection_writeback_candidate) if self.reflection_writeback_candidate else None
            ),
            "policy_hint": dict(self.policy_hint),
            "response_tendency": dict(self.response_tendency) if self.response_tendency is not None else None,
            "host_proactive_candidate": (
                dict(self.host_proactive_candidate) if self.host_proactive_candidate is not None else None
            ),
            "trace_payload": dict(self.trace_payload),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any] | None) -> "SubjectSystemV1Result":
        payload = dict(raw or {})
        return cls(
            schema_version=str(payload.get("schema_version") or RESULT_SCHEMA_VERSION),
            source_kernel=str(payload.get("source_kernel") or "openemotion.proto_self_v2"),
            identity_invariants=SubjectIdentityInvariants.from_dict(payload.get("identity_invariants")),
            self_model_delta=dict(payload.get("self_model_delta") or {}),
            memory_update=dict(payload.get("memory_update") or {}),
            appraisal_state_delta=dict(payload.get("appraisal_state_delta") or {}),
            reflection_writeback_candidate=(
                dict(payload.get("reflection_writeback_candidate") or {})
                if payload.get("reflection_writeback_candidate") is not None
                else None
            ),
            policy_hint=dict(payload.get("policy_hint") or {}),
            response_tendency=(
                dict(payload.get("response_tendency") or {})
                if payload.get("response_tendency") is not None
                else None
            ),
            host_proactive_candidate=(
                dict(payload.get("host_proactive_candidate") or {})
                if payload.get("host_proactive_candidate") is not None
                else None
            ),
            trace_payload=dict(payload.get("trace_payload") or {}),
        )
