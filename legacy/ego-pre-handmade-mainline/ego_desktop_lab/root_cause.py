from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Mapping


CLAIM_CEILING = (
    "lab-only root-cause observability; no runtime influence, no live benefit, "
    "no consciousness, no alive status"
)

ROOT_CAUSE_CATEGORIES = (
    "input_misread",
    "viability_bad_signal",
    "prediction_wrong",
    "policy_ranking_wrong",
    "gate_mismatch",
    "plasticity_noop",
    "expression_surface",
    "runtime_bridge",
    "evidence_claim_mismatch",
    "unknown",
)

_STAGE_LADDER = (
    ("boundary", "ownership and action boundary"),
    ("viability", "viability pressure snapshot"),
    ("prediction", "affordance prediction"),
    ("ranking", "option ranking"),
    ("gate", "host gate result"),
    ("plasticity", "next-cycle learning delta"),
    ("root_cause", "failure localization"),
)

TICKET_STATUSES = (
    "localized",
    "suspected",
    "unknown",
    "needs_live_probe",
)

_TEMPLATE_MARKERS = (
    "template",
    "fallback",
    "missing candidate",
    "missing final_text_candidate",
    "rejected candidate",
    "now continue",
    "continue now",
    "qingqing",
    "轻轻接回来",
    "现在继续吗",
)


@dataclass(frozen=True)
class RootCauseTrace:
    input_summary: str | None
    decision_source: str
    viability: dict[str, Any]
    affordances: tuple[str, ...]
    predictions_by_affordance: dict[str, Any]
    ranking: tuple[dict[str, Any], ...]
    selected_option: dict[str, Any] | None
    selected_intention: dict[str, Any] | None
    gate_decision: dict[str, Any]
    outcome: dict[str, Any] | None
    plasticity_update: dict[str, Any] | None
    next_cycle_delta: dict[str, Any]
    no_action_executed: bool
    claim_ceiling: str
    debug_refs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FailureTicket:
    ticket_id: str
    status: str
    category: str
    confidence: float
    expected: Any
    observed: Any
    trace_diff: dict[str, Any]
    evidence: tuple[str, ...]
    next_minimal_probe: str
    cannot_prove: tuple[str, ...]
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_root_cause_trace(
    cycle_result: Mapping[str, Any] | Any,
    *,
    input_summary: str | None = None,
    outcome: Mapping[str, Any] | Any | None = None,
    decision_source: str = "SelfMaintainingAgencyCycleResult",
) -> RootCauseTrace:
    """Build a read-only root-cause trace from an existing lab decision result.

    This function intentionally does not call the agency kernel, policy, gate, or
    reducer. It only normalizes a prior result into a compact operator trace.
    """

    data = _to_dict(cycle_result)
    predictions = _mapping(data.get("predictions_by_affordance"))
    candidate_options = tuple(
        _mapping(item) for item in data.get("candidate_options") or data.get("behavior_options") or ()
    )
    ranking = _ranking_from_options(candidate_options)
    return RootCauseTrace(
        input_summary=input_summary,
        decision_source=decision_source,
        viability=_mapping(data.get("viability_snapshot") or data.get("viability")),
        affordances=tuple(sorted({str(key) for key in predictions} | _affordances_from_options(candidate_options))),
        predictions_by_affordance=predictions,
        ranking=ranking,
        selected_option=_optional_mapping(
            data.get("selected_behavior_option") or data.get("selected_option")
        ),
        selected_intention=_optional_mapping(data.get("selected_intention")),
        gate_decision=_mapping(data.get("gate_decision")),
        outcome=_optional_dict(outcome),
        plasticity_update=_optional_mapping(data.get("plasticity_update")),
        next_cycle_delta=_mapping(data.get("next_cycle_delta")),
        no_action_executed=bool(data.get("no_action_executed", True)),
        claim_ceiling=CLAIM_CEILING,
        debug_refs={
            "source_claim_ceiling": data.get("claim_ceiling"),
            "evidence_log_path": data.get("evidence_log_path"),
            "read_only": True,
            "recomputed_decision": False,
        },
    )


def diagnose_failure(
    cycle_result_or_trace: Mapping[str, Any] | Any,
    *,
    expected: Any,
    observed: Any,
    input_summary: str | None = None,
    outcome: Mapping[str, Any] | Any | None = None,
) -> FailureTicket:
    trace = (
        cycle_result_or_trace
        if isinstance(cycle_result_or_trace, RootCauseTrace)
        else build_root_cause_trace(
            cycle_result_or_trace,
            input_summary=input_summary,
            outcome=outcome,
        )
    )
    trace_diff = _build_trace_diff(trace, expected=expected, observed=observed)
    category, status, confidence, evidence, probe = _classify_failure(
        trace,
        expected=expected,
        observed=observed,
        trace_diff=trace_diff,
    )
    return FailureTicket(
        ticket_id=_ticket_id(trace, expected, observed, category),
        status=status,
        category=category,
        confidence=confidence,
        expected=_jsonable(expected),
        observed=_jsonable(observed),
        trace_diff=trace_diff,
        evidence=evidence,
        next_minimal_probe=probe,
        cannot_prove=(
            "runtime efficacy",
            "live user benefit",
            "consciousness or alive status",
            "EgoCore/OpenEmotion state mutation correctness",
        ),
    )


def format_failure_ticket(ticket: FailureTicket | Mapping[str, Any]) -> str:
    data = _to_dict(ticket)
    lines = [
        "# Root-Cause Failure Ticket",
        "",
        f"ticket_id: {data.get('ticket_id')}",
        f"status: {data.get('status')}",
        f"category: {data.get('category')}",
        f"confidence: {data.get('confidence')}",
        "",
        "## What Broke",
        _json_block({"expected": data.get("expected"), "observed": data.get("observed")}),
        "",
        "## Evidence",
        _json_block(data.get("evidence")),
        "",
        "## Trace Diff",
        _json_block(data.get("trace_diff")),
        "",
        "## Next Minimal Probe",
        str(data.get("next_minimal_probe")),
        "",
        "## Cannot Prove",
        _json_block(data.get("cannot_prove")),
        "",
        "## Claim Ceiling",
        str(data.get("claim_ceiling") or CLAIM_CEILING),
        "",
    ]
    return "\n".join(lines)


def build_root_cause_operator_report(ticket: FailureTicket | Mapping[str, Any]) -> str:
    return format_failure_ticket(ticket)


def build_operator_observability_report(
    cycle_result_or_view: Mapping[str, Any] | Any,
    *,
    trace: RootCauseTrace | Mapping[str, Any] | None = None,
    ticket: FailureTicket | Mapping[str, Any] | None = None,
    input_summary: str | None = None,
    outcome: Mapping[str, Any] | Any | None = None,
) -> str:
    view = _build_operator_view(cycle_result_or_view)
    trace_obj = (
        trace
        if isinstance(trace, RootCauseTrace)
        else build_root_cause_trace(
            trace if trace is not None else cycle_result_or_view,
            input_summary=input_summary,
            outcome=outcome,
        )
    )
    ticket_data = _to_dict(ticket) if ticket is not None else {}
    trace_diff = _mapping(ticket_data.get("trace_diff"))
    current_gate = _current_stage_gate(ticket_data.get("category"))
    lines = [
        "# v7 Stage 0 Operator Observability Report",
        "",
        "This report is lab-only and read-only. It consumes existing `SelfMaintainingAgencyCycleResult`, `AgencyDecisionView`, `RootCauseTrace`, and `FailureTicket` surfaces only.",
        "It does not recompute selected option, policy, or gate, and it has no runtime influence.",
        "",
        "## Boundary",
        _json_block(view.get("boundary")),
        "",
        "## Viability",
        _json_block(view.get("viability")),
        "",
        "## Prediction",
        _json_block(view.get("predictions_by_affordance")),
        "",
        "## Ranking",
        _json_block(trace_obj.ranking),
        "",
        "## Gate",
        _json_block(view.get("gate_decision")),
        "",
        "## Plasticity",
        _json_block(view.get("plasticity_update")),
        "",
        "## Root Cause",
        _json_block(
            {
                "category": ticket_data.get("category", "unknown"),
                "status": ticket_data.get("status", "unknown"),
                "confidence": ticket_data.get("confidence", "unknown"),
                "evidence": ticket_data.get("evidence", ("unknown",)),
            }
        ),
        "",
        "## Before / After Decision",
        _json_block(_before_after_decision_summary(trace_obj, trace_diff)),
        "",
        "## Stage Ladder",
        _stage_ladder_block(current_gate),
        "",
        "## Current Gate",
        _json_block(
            {
                "stage": current_gate,
                "selected_goal": trace_obj.selected_option.get("goal") if trace_obj.selected_option else None,
                "gate_status": trace_obj.gate_decision.get("status", "unknown"),
                "gate_allowed_as": trace_obj.gate_decision.get("allowed_as", "unknown"),
                "no_action_executed": trace_obj.no_action_executed,
            }
        ),
        "",
        "## Next Probe",
        str(ticket_data.get("next_minimal_probe", "unknown")),
        "",
        "## Claim Ceiling",
        str(ticket_data.get("claim_ceiling") or trace_obj.claim_ceiling or CLAIM_CEILING),
        "",
    ]
    return "\n".join(lines)


def _classify_failure(
    trace: RootCauseTrace,
    *,
    expected: Any,
    observed: Any,
    trace_diff: Mapping[str, Any],
) -> tuple[str, str, float, tuple[str, ...], str]:
    text = _searchable_text(expected, observed, trace.outcome)
    if _is_expression_surface_failure(text, observed):
        return (
            "expression_surface",
            "localized",
            0.86,
            (
                "Observed final-text/template marker is outside policy selection.",
                "Trace gate and selected option remain readable; failure is on visible expression surface.",
            ),
            "Probe final_text_candidate ownership and output_check hold/retry behavior with one minimal replay.",
        )

    if _is_listener_without_live_send(observed, text):
        return (
            "evidence_claim_mismatch",
            "needs_live_probe",
            0.83,
            (
                "Listener health marker is not equivalent to fresh proactive-send evidence.",
                "Observed soak/live-send marker is missing, waiting, or false.",
            ),
            "Run one fresh allowlisted live window and compare listener health, soak status, and send marker separately.",
        )

    if _has_insufficient_trace(trace):
        return (
            "unknown",
            "unknown",
            0.20,
            (
                "Trace is missing enough decision fields for layer localization.",
                "No strong expression, runtime, or evidence marker was present.",
            ),
            "Capture a RootCauseTrace from SelfMaintainingAgencyCycleResult or AgencyDecisionView before diagnosing.",
        )

    if _is_gate_failure(trace, text):
        return (
            "gate_mismatch",
            "localized",
            0.78,
            (
                "Expected/observed text refers to allow/block/ask mismatch.",
                f"Gate status in trace is {trace.gate_decision.get('status')}.",
            ),
            "Replay the same selected option against the gate and inspect the allowed_as/status pair only.",
        )

    if _is_outcome_failure(trace, text, observed):
        selected_changed = bool(trace.next_cycle_delta.get("selected_intention_changed"))
        prediction_error_delta = _float_from_mapping(trace.plasticity_update, "prediction_error_delta")
        if prediction_error_delta > 0:
            return (
                "prediction_wrong",
                "localized",
                0.79,
                (
                    "Outcome failure produced positive prediction_error_delta.",
                    "Plasticity changed the next-cycle tendency.",
                ),
                _deterministic_replay_probe(trace, observed),
            )
        if not selected_changed:
            return (
                "policy_ranking_wrong",
                "suspected",
                0.70,
                (
                    "Outcome indicates failure but selected intention did not change.",
                    "Ranking may not be responding to negative feedback.",
                ),
                "Run one controlled negative outcome replay and inspect priority_delta_by_goal plus rank_delta_by_goal.",
            )
        return (
            "policy_ranking_wrong",
            "suspected",
            0.64,
            (
                "Outcome indicates failure and ranking changed, but prediction-error evidence is weak.",
                "Policy movement should be checked against expected ranking deltas.",
            ),
            "Compare before/after ranking under a stable seed and inspect the top-two option scores.",
        )

    if trace.plasticity_update is None and trace.next_cycle_delta.get("plasticity_applied") is False:
        return (
            "plasticity_noop",
            "suspected",
            0.56,
            (
                "No plasticity update is present.",
                "Next-cycle delta says plasticity was not applied.",
            ),
            "Provide an OutcomeRecord and rerun the lab-only agency cycle without writing repo evidence.",
        )

    return (
        "unknown",
        "unknown",
        0.25,
        (
            "Trace exists but no configured classifier matched the observed failure.",
            "This ticket should not guess a deeper layer.",
        ),
        "Add one narrower expected/observed marker or capture the failing layer's raw trace fields.",
    )


def _build_trace_diff(trace: RootCauseTrace, *, expected: Any, observed: Any) -> dict[str, Any]:
    delta = trace.next_cycle_delta
    plasticity = trace.plasticity_update or {}
    return {
        "input_summary": trace.input_summary,
        "before_selected_goal": delta.get("before_selected_goal"),
        "after_selected_goal": delta.get("after_selected_goal"),
        "selected_intention_changed": delta.get("selected_intention_changed"),
        "selected_goal": _selected_goal(trace),
        "gate_status": trace.gate_decision.get("status"),
        "gate_allowed_as": trace.gate_decision.get("allowed_as"),
        "plasticity_applied": delta.get("plasticity_applied"),
        "prediction_error_delta": plasticity.get("prediction_error_delta"),
        "strategy_success_delta": plasticity.get("strategy_success_delta"),
        "rank_delta_by_goal": delta.get("rank_delta_by_goal"),
        "priority_delta_by_goal": delta.get("priority_delta_by_goal"),
        "expected_marker": _marker(expected),
        "observed_marker": _marker(observed),
        "no_action_executed": trace.no_action_executed,
        "recomputed_decision": False,
    }


def _before_after_decision_summary(
    trace: RootCauseTrace,
    trace_diff: Mapping[str, Any],
) -> dict[str, Any]:
    delta = trace.next_cycle_delta
    plasticity = trace.plasticity_update or {}
    return {
        "before_selected_goal": trace_diff.get("before_selected_goal")
        or delta.get("before_selected_goal"),
        "after_selected_goal": trace_diff.get("after_selected_goal")
        or delta.get("after_selected_goal"),
        "selected_intention_changed": trace_diff.get("selected_intention_changed")
        if "selected_intention_changed" in trace_diff
        else delta.get("selected_intention_changed"),
        "rank_delta_by_goal": trace_diff.get("rank_delta_by_goal")
        or delta.get("rank_delta_by_goal"),
        "ranking_transition_by_goal": delta.get("ranking_transition_by_goal"),
        "priority_delta_by_goal": trace_diff.get("priority_delta_by_goal")
        or delta.get("priority_delta_by_goal"),
        "pressure_transition": delta.get("pressure_transition"),
        "prediction_error_delta": trace_diff.get("prediction_error_delta")
        if "prediction_error_delta" in trace_diff
        else plasticity.get("prediction_error_delta"),
        "no_action_executed": trace_diff.get("no_action_executed")
        if "no_action_executed" in trace_diff
        else trace.no_action_executed,
    }


def _deterministic_replay_probe(trace: RootCauseTrace, observed: Any) -> str:
    outcome = trace.outcome or {}
    observed_effect = observed.get("actual_effect") if isinstance(observed, Mapping) else None
    fixture = str(observed_effect or outcome.get("actual_effect") or "negative_outcome")
    before = str(trace.next_cycle_delta.get("before_selected_goal") or "unknown")
    after = str(trace.next_cycle_delta.get("after_selected_goal") or "unknown")
    return (
        f"Replay {fixture} fixture and verify before={before}, after={after}, "
        "prediction_error_delta > 0, ranking delta deterministic, and "
        "no_action_executed=true."
    )


def _ranking_from_options(options: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    ranked: list[dict[str, Any]] = []
    for index, option in enumerate(options, start=1):
        ranked.append(
            {
                "rank": int(option.get("rank") or index),
                "id": option.get("id"),
                "goal": option.get("goal"),
                "affordance": option.get("affordance"),
                "priority": option.get("priority"),
                "gate_status": option.get("gate_status"),
            }
        )
    return tuple(sorted(ranked, key=lambda item: (int(item["rank"]), str(item.get("id")))))


def _is_expression_surface_failure(text: str, observed: Any) -> bool:
    if isinstance(observed, Mapping):
        if observed.get("final_text_candidate") in {None, "", False} and (
            observed.get("fallback_text") or observed.get("template_like")
        ):
            return True
        if observed.get("surface") == "expression" or observed.get("layer") == "expression_surface":
            return True
    return any(marker in text for marker in _TEMPLATE_MARKERS)


def _is_listener_without_live_send(observed: Any, text: str) -> bool:
    if isinstance(observed, Mapping):
        listener = str(observed.get("listener_status") or observed.get("status") or "").lower()
        soak = str(observed.get("soak_status") or observed.get("soak_reason") or "").lower()
        fresh_send = observed.get("fresh_send_observed")
        if listener in {"online", "armed"} and fresh_send is False:
            return True
        if listener in {"online", "armed"} and soak in {"waiting", "autodrain_start_not_observed"}:
            return True
    return (
        ("listener" in text or "telegram" in text)
        and ("online" in text or "armed" in text)
        and (
            "no fresh" in text
            or "waiting" in text
            or "autodrain_start_not_observed" in text
            or "fresh_send_observed: false" in text
        )
    )


def _is_gate_failure(trace: RootCauseTrace, text: str) -> bool:
    if not trace.gate_decision:
        return False
    return "gate" in text and any(marker in text for marker in ("allow", "block", "ask", "mismatch"))


def _is_outcome_failure(trace: RootCauseTrace, text: str, observed: Any) -> bool:
    if isinstance(observed, Mapping):
        score = observed.get("success_score")
        if isinstance(score, (int, float)) and float(score) < 0.4:
            return True
        actual_effect = str(observed.get("actual_effect") or "").lower()
        if "fail" in actual_effect or "regression" in actual_effect:
            return True
    return (
        "fail" in text
        or "regression" in text
        or "did not improve" in text
        or _float_from_mapping(trace.plasticity_update, "strategy_success_delta") < 0
    )


def _has_insufficient_trace(trace: RootCauseTrace) -> bool:
    return (
        not trace.viability
        and not trace.predictions_by_affordance
        and not trace.ranking
        and trace.selected_option is None
        and trace.selected_intention is None
        and not trace.next_cycle_delta
    )


def _selected_goal(trace: RootCauseTrace) -> str | None:
    if trace.selected_option and trace.selected_option.get("goal"):
        return str(trace.selected_option.get("goal"))
    if trace.selected_intention and trace.selected_intention.get("goal"):
        return str(trace.selected_intention.get("goal"))
    return None


def _affordances_from_options(options: tuple[dict[str, Any], ...]) -> set[str]:
    return {str(option["affordance"]) for option in options if option.get("affordance")}


def _ticket_id(trace: RootCauseTrace, expected: Any, observed: Any, category: str) -> str:
    payload = {
        "category": category,
        "expected": _jsonable(expected),
        "observed": _jsonable(observed),
        "trace": trace.to_dict(),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"rc-{digest[:12]}"


def _marker(value: Any) -> str:
    text = _searchable_text(value)
    return text[:160]


def _searchable_text(*values: Any) -> str:
    return " ".join(json.dumps(_jsonable(value), sort_keys=True, default=str) for value in values).lower()


def _float_from_mapping(value: Mapping[str, Any] | None, key: str) -> float:
    if not isinstance(value, Mapping):
        return 0.0
    try:
        return float(value.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _to_dict(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return _to_dict(value.to_dict())
    if is_dataclass(value):
        return _to_dict(asdict(value))
    raise TypeError("root-cause observability requires a mapping or to_dict() object")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return {}


def _optional_mapping(value: Any) -> dict[str, Any] | None:
    mapped = _mapping(value)
    return mapped or None


def _optional_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Mapping) or hasattr(value, "to_dict") or is_dataclass(value):
        return _to_dict(value)
    return {"value": _jsonable(value)}


def _json_block(value: Any) -> str:
    return json.dumps(_jsonable(value), indent=2, sort_keys=True)


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


def _build_operator_view(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    data = _to_dict(value)
    if {"boundary", "viability", "predictions_by_affordance", "gate_decision"} <= set(data):
        return data
    from ego_desktop_lab.agency_decision_view import build_agency_decision_view

    return build_agency_decision_view(value).to_dict()


def _current_stage_gate(category: Any) -> str:
    mapping = {
        "input_misread": "boundary",
        "viability_bad_signal": "viability",
        "prediction_wrong": "prediction",
        "policy_ranking_wrong": "ranking",
        "gate_mismatch": "gate",
        "plasticity_noop": "plasticity",
        "expression_surface": "root_cause",
        "runtime_bridge": "root_cause",
        "evidence_claim_mismatch": "root_cause",
        "unknown": "unknown",
        None: "unknown",
    }
    return str(mapping.get(category, "unknown"))


def _stage_ladder_block(current_gate: str) -> str:
    lines = []
    for stage_key, stage_label in _STAGE_LADDER:
        marker = "current" if stage_key == current_gate else "observed"
        lines.append(f"- {stage_key}: {stage_label} [{marker}]")
    if current_gate == "unknown":
        lines.append("- unknown: insufficient trace for narrower stage localization [current]")
    return "\n".join(lines)
