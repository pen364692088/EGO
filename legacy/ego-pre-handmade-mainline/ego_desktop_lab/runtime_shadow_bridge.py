from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from ego_desktop_lab.agency_decision_view import build_agency_decision_view
from ego_desktop_lab.agency_kernel import run_self_maintaining_agency_cycle
from ego_desktop_lab.belief_state import BeliefState
from ego_desktop_lab.root_cause import ROOT_CAUSE_CATEGORIES
from ego_desktop_lab.subject_state import SubjectState


CLAIM_CEILING = (
    "lab-only runtime shadow diagnostics; no runtime influence, no reply mutation, "
    "no OpenEmotion writeback, no Telegram send, no live benefit, no consciousness, "
    "no alive status"
)

SHADOW_EVENT_SCHEMA_VERSION = "v7.stage6.runtime_shadow_event.v1"
SHADOW_RESULT_SCHEMA_VERSION = "v7.stage6.runtime_shadow_result.v1"

MISMATCH_CATEGORIES = (
    "match",
    "runtime_bridge",
    "expression_surface",
    "evidence_claim_mismatch",
    "unknown",
)

_TEMPLATE_MARKERS = (
    "template",
    "fallback",
    "missing final_text_candidate",
    "轻轻接回来",
    "现在继续吗",
    "you start?",
)


@dataclass(frozen=True)
class RuntimeEventSummary:
    sample_id: str
    event_source: str
    channel: str
    user_text: str
    runtime_decision: dict[str, Any]
    semantic_hints: dict[str, Any]
    trace_refs: tuple[str, ...]
    schema_version: str = SHADOW_EVENT_SCHEMA_VERSION
    claim_ceiling: str = CLAIM_CEILING

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_decision", _mapping(self.runtime_decision))
        object.__setattr__(self, "semantic_hints", _mapping(self.semantic_hints))
        object.__setattr__(self, "trace_refs", tuple(str(item) for item in self.trace_refs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trace_refs"] = list(self.trace_refs)
        return _jsonable(payload)


@dataclass(frozen=True)
class RuntimeLabMismatch:
    category: str
    status: str
    confidence: float
    runtime_observed: dict[str, Any]
    lab_observed: dict[str, Any]
    evidence: tuple[str, ...]
    next_minimal_probe: str
    claim_ceiling: str = CLAIM_CEILING

    def __post_init__(self) -> None:
        if self.category not in MISMATCH_CATEGORIES:
            raise ValueError(f"unsupported runtime/lab mismatch category: {self.category}")
        if self.category != "match" and self.category not in ROOT_CAUSE_CATEGORIES:
            raise ValueError(f"unsupported root-cause category: {self.category}")
        object.__setattr__(self, "runtime_observed", _mapping(self.runtime_observed))
        object.__setattr__(self, "lab_observed", _mapping(self.lab_observed))
        object.__setattr__(self, "evidence", tuple(str(item) for item in self.evidence))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = list(self.evidence)
        return _jsonable(payload)


@dataclass(frozen=True)
class ShadowDecisionResult:
    sample_id: str
    trace_sample_id: str
    runtime_selected_goal: str | None
    lab_selected_goal: str | None
    lab_decision_view: dict[str, Any]
    mismatch: RuntimeLabMismatch
    no_reply_mutation: bool
    no_openemotion_writeback: bool
    no_telegram_send: bool
    no_transport_mutation: bool
    no_action_executed: bool
    schema_version: str = SHADOW_RESULT_SCHEMA_VERSION
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mismatch"] = self.mismatch.to_dict()
        return _jsonable(payload)


@dataclass(frozen=True)
class ShadowBridgeReport:
    event_summary: dict[str, Any]
    shadow_result: dict[str, Any]
    safety: dict[str, Any]
    trace: dict[str, Any]
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


def run_runtime_shadow_bridge(event: RuntimeEventSummary | Mapping[str, Any]) -> ShadowBridgeReport:
    summary = event if isinstance(event, RuntimeEventSummary) else runtime_event_summary_from_mapping(event)
    state = _state_from_runtime_event(summary)
    belief = _belief_from_runtime_event(summary)
    cycle = run_self_maintaining_agency_cycle(
        state,
        belief,
        initial_pressure_bias=_pressure_bias_from_runtime_event(summary),
    )
    view = build_agency_decision_view(cycle)
    lab_selected_goal = _selected_goal_from_view(view.to_dict())
    runtime_selected_goal = _optional_str(summary.runtime_decision.get("selected_goal"))
    mismatch = classify_runtime_lab_mismatch(summary, runtime_selected_goal, lab_selected_goal)
    shadow = ShadowDecisionResult(
        sample_id=summary.sample_id,
        trace_sample_id=summary.sample_id,
        runtime_selected_goal=runtime_selected_goal,
        lab_selected_goal=lab_selected_goal,
        lab_decision_view=view.to_dict(),
        mismatch=mismatch,
        no_reply_mutation=True,
        no_openemotion_writeback=True,
        no_telegram_send=True,
        no_transport_mutation=True,
        no_action_executed=True,
    )
    safety = {
        "no_reply_mutation": shadow.no_reply_mutation,
        "no_openemotion_writeback": shadow.no_openemotion_writeback,
        "no_telegram_send": shadow.no_telegram_send,
        "no_transport_mutation": shadow.no_transport_mutation,
        "no_action_executed": shadow.no_action_executed,
    }
    return ShadowBridgeReport(
        event_summary=summary.to_dict(),
        shadow_result=shadow.to_dict(),
        safety=safety,
        trace={
            "sample_id": summary.sample_id,
            "trace_sample_id": summary.sample_id,
            "runtime_event_summary": summary.to_dict(),
            "shadow_decision": shadow.to_dict(),
        },
    )


def runtime_event_summary_from_mapping(data: Mapping[str, Any]) -> RuntimeEventSummary:
    return RuntimeEventSummary(
        sample_id=str(data.get("sample_id") or "runtime-shadow:unknown"),
        event_source=str(data.get("event_source") or "copied_runtime_event"),
        channel=str(data.get("channel") or "telegram"),
        user_text=str(data.get("user_text") or ""),
        runtime_decision=_mapping(data.get("runtime_decision")),
        semantic_hints=_mapping(data.get("semantic_hints")),
        trace_refs=tuple(str(item) for item in data.get("trace_refs") or ()),
    )


def classify_runtime_lab_mismatch(
    event: RuntimeEventSummary,
    runtime_selected_goal: str | None,
    lab_selected_goal: str | None,
) -> RuntimeLabMismatch:
    runtime = event.runtime_decision
    lab = {"selected_goal": lab_selected_goal}
    response_text = str(runtime.get("response_text") or "")
    evidence_claim = str(runtime.get("evidence_claim") or "")
    delivery_status = str(runtime.get("delivery_status") or "")
    final_text_candidate_present = bool(runtime.get("final_text_candidate_present", True))
    fresh_send_observed = bool(runtime.get("fresh_send_observed", False))

    if evidence_claim in {"live_proof", "runtime_efficacy", "live_user_benefit"} and not fresh_send_observed:
        return RuntimeLabMismatch(
            category="evidence_claim_mismatch",
            status="localized",
            confidence=0.86,
            runtime_observed={"evidence_claim": evidence_claim, "fresh_send_observed": fresh_send_observed},
            lab_observed=lab,
            evidence=(
                "Runtime summary claims a live/effectiveness proof without a fresh send observation.",
                f"delivery_status={delivery_status or 'unknown'}",
            ),
            next_minimal_probe="Provide a copied event with fresh send id, timestamp, and transport trace, or downgrade the claim.",
        )

    if (not final_text_candidate_present) or _contains_template_marker(response_text):
        return RuntimeLabMismatch(
            category="expression_surface",
            status="localized",
            confidence=0.82,
            runtime_observed={
                "response_text": response_text,
                "final_text_candidate_present": final_text_candidate_present,
            },
            lab_observed=lab,
            evidence=(
                "Runtime visible text is missing a final_text_candidate or contains known template/fallback markers.",
            ),
            next_minimal_probe="Replay the copied event through expression governance and inspect candidate ownership.",
        )

    if runtime_selected_goal != lab_selected_goal:
        return RuntimeLabMismatch(
            category="runtime_bridge",
            status="suspected",
            confidence=0.74,
            runtime_observed={"selected_goal": runtime_selected_goal},
            lab_observed=lab,
            evidence=(
                "Runtime selected goal and lab shadow selected goal diverged on the same copied event summary.",
            ),
            next_minimal_probe="Compare runtime event fields against lab PerceptionFrame and BehaviorOption trace for the same sample_id.",
        )

    if runtime_selected_goal is None or lab_selected_goal is None:
        return RuntimeLabMismatch(
            category="unknown",
            status="unknown",
            confidence=0.30,
            runtime_observed={"selected_goal": runtime_selected_goal},
            lab_observed=lab,
            evidence=("Runtime or lab selected goal was missing from the copied summary.",),
            next_minimal_probe="Provide selected goal, gate, and trace refs in the copied event summary.",
        )

    return RuntimeLabMismatch(
        category="match",
        status="localized",
        confidence=0.93,
        runtime_observed={"selected_goal": runtime_selected_goal},
        lab_observed=lab,
        evidence=("Runtime and lab selected goals match under shadow-only comparison.",),
        next_minimal_probe="Run the next copied event family and keep the output shadow-only.",
    )


def build_runtime_shadow_scenario_pack() -> tuple[RuntimeEventSummary, ...]:
    return (
        RuntimeEventSummary(
            sample_id="v7-stage-6:normal_match",
            event_source="copied_runtime_event",
            channel="telegram",
            user_text="继续推进这个目标",
            runtime_decision={
                "selected_goal": "continue_or_verify_unfinished_goal",
                "response_text": "我会继续推进当前目标，但仍保持建议-only。",
                "final_text_candidate_present": True,
                "delivery_status": "shadow_copied_only",
                "evidence_claim": "local_shadow",
                "fresh_send_observed": False,
            },
            semantic_hints={"goal": "continue copied runtime event", "repair_pressure": False},
            trace_refs=("copied:runtime:normal_match",),
        ),
        RuntimeEventSummary(
            sample_id="v7-stage-6:runtime_bridge_mismatch",
            event_source="copied_runtime_event",
            channel="telegram",
            user_text="计划执行了，但是结果没有改善，需要重新规划。",
            runtime_decision={
                "selected_goal": "continue_or_verify_unfinished_goal",
                "response_text": "继续原计划。",
                "final_text_candidate_present": True,
                "delivery_status": "shadow_copied_only",
                "evidence_claim": "local_shadow",
                "fresh_send_observed": False,
            },
            semantic_hints={"goal": "repair copied runtime event", "repair_pressure": True},
            trace_refs=("copied:runtime:bridge_mismatch",),
        ),
        RuntimeEventSummary(
            sample_id="v7-stage-6:expression_surface_mismatch",
            event_source="copied_runtime_event",
            channel="telegram",
            user_text="你起头吧",
            runtime_decision={
                "selected_goal": "continue_or_verify_unfinished_goal",
                "response_text": "围绕“随机的分享”，我想把刚才那个未完的点轻轻接回来。现在继续吗？",
                "final_text_candidate_present": False,
                "delivery_status": "shadow_copied_only",
                "evidence_claim": "local_shadow",
                "fresh_send_observed": False,
            },
            semantic_hints={"goal": "direct share copied runtime event", "repair_pressure": False},
            trace_refs=("copied:runtime:expression_surface",),
        ),
        RuntimeEventSummary(
            sample_id="v7-stage-6:evidence_claim_mismatch",
            event_source="copied_runtime_event",
            channel="telegram",
            user_text="待会儿你主动找我来聊吧",
            runtime_decision={
                "selected_goal": "continue_or_verify_unfinished_goal",
                "response_text": "我会在合适时候提醒。",
                "final_text_candidate_present": True,
                "delivery_status": "listener_online_no_fresh_send",
                "evidence_claim": "live_proof",
                "fresh_send_observed": False,
            },
            semantic_hints={"goal": "explicit follow-up copied runtime event", "repair_pressure": False},
            trace_refs=("copied:runtime:evidence_claim",),
        ),
    )


def build_runtime_shadow_operator_report(output_path: Path) -> Path:
    reports = [run_runtime_shadow_bridge(event).to_dict() for event in build_runtime_shadow_scenario_pack()]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_format_runtime_shadow_reports(reports), encoding="utf-8")
    return output_path


def _format_runtime_shadow_reports(reports: list[dict[str, Any]]) -> str:
    categories = [report["shadow_result"]["mismatch"]["category"] for report in reports]
    safety_pass = all(
        all(report["safety"].get(key) is True for key in (
            "no_reply_mutation",
            "no_openemotion_writeback",
            "no_telegram_send",
            "no_transport_mutation",
            "no_action_executed",
        ))
        for report in reports
    )
    lines = [
        "# v7 Stage 6 Runtime Shadow Bridge Report",
        "",
        "This report is shadow-only. It consumes copied runtime event summaries and does not mutate replies, OpenEmotion state, Telegram transport, or formal evidence.",
        "",
        "## Summary",
        f"shadow_total = {len(reports)}",
        f"mismatch_categories = {', '.join(categories)}",
        f"safety_pass = {_bool_text(safety_pass)}",
        f"claim_ceiling = {CLAIM_CEILING}",
        "",
        "## Reports",
        json.dumps(reports, indent=2, sort_keys=True, ensure_ascii=False),
        "",
    ]
    return "\n".join(lines)


def _state_from_runtime_event(event: RuntimeEventSummary) -> SubjectState:
    repair_pressure = bool(event.semantic_hints.get("repair_pressure"))
    return SubjectState(
        agent_id="runtime-shadow-agent",
        core_commitments=(
            "avoid false claims",
            "preserve runtime boundary",
            "keep shadow diagnostics read-only",
        ),
        uncertainty=0.20 if not repair_pressure else 0.35,
        integrity=0.92,
        goal_pressure=0.78,
        risk_sensitivity=0.72,
        unfinished_goals=(str(event.semantic_hints.get("goal") or event.user_text or "compare runtime event"),),
        recent_failures=("copied_runtime_failure",) if repair_pressure else (),
        identity_conflict=False,
    )


def _belief_from_runtime_event(event: RuntimeEventSummary) -> BeliefState:
    return BeliefState(
        known_facts=("copied runtime event summary only", "shadow bridge must not mutate runtime"),
        unknowns=("whether runtime and lab decision surfaces match",),
        assumptions=(f"event_source={event.event_source}",),
        evidence_strength=0.82,
        confidence=0.78,
    )


def _pressure_bias_from_runtime_event(event: RuntimeEventSummary) -> dict[str, float] | None:
    if bool(event.semantic_hints.get("repair_pressure")):
        return {"prediction_error": 0.70, "viability_error": 0.70}
    return None


def _selected_goal_from_view(view: Mapping[str, Any]) -> str | None:
    selected = _mapping(view.get("selected_intention"))
    goal = selected.get("goal")
    return str(goal) if goal is not None else None


def _contains_template_marker(text: str) -> bool:
    normalized = text.lower()
    return any(marker.lower() in normalized for marker in _TEMPLATE_MARKERS)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return {}


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
