from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ego_desktop_lab.agency_contracts import AgencyEvent, BehaviorPlan
from ego_desktop_lab.agency_kernel import run_self_maintaining_agency_cycle
from ego_desktop_lab.belief_state import BeliefState, clamp01
from ego_desktop_lab.gate import evaluate_gate
from ego_desktop_lab.policy import GATE_ACTION_STATUS
from ego_desktop_lab.subject_state import SubjectState


CLAIM_CEILING = (
    "lab-only continuity runtime scaffold; no runtime influence, no live benefit, "
    "no consciousness, no alive status, no real autonomy"
)

STATE_SCHEMA_VERSION = "v7.45-continuity-state.v1"
EVENT_SCHEMA_VERSION = "v7.45-continuity-event.v1"

VALID_CONTINUITY_EVENT_TYPES = (
    "user_event",
    "outcome_feedback",
    "autonomous_tick",
    "system_observation",
)

VALID_CONTINUITY_EVENT_SOURCES = (
    "operator_case",
    "chat_corpus",
    "fixture",
    "future_shadow",
)

DEFAULT_VIABILITY_SNAPSHOT = {
    "stagnation_pressure": 0.10,
    "maintenance_pressure": 0.10,
    "evidence_gap_pressure": 0.10,
    "safety_pressure": 0.10,
}

STAGNATION_RATE_PER_HOUR = 0.12
MAINTENANCE_RATE_PER_HOUR = 0.04
IGNITION_STAGNATION_THRESHOLD = 0.75
IGNITION_MAINTENANCE_THRESHOLD = 0.80
DEFAULT_VISIBLE_INTERVAL_SECONDS = 1800


@dataclass(frozen=True)
class ContinuityState:
    agent_id: str
    active_goal_refs: tuple[str, ...]
    viability_snapshot: dict[str, float]
    last_updated_at: str
    schema_version: str = STATE_SCHEMA_VERSION
    last_visible_suggestion_at: str | None = None
    protected_commitments: tuple[str, ...] = (
        "no_runtime_authority",
        "proposal_only",
        "no_external_action",
        "no_consciousness_or_alive_claim",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent_id", str(self.agent_id))
        object.__setattr__(self, "active_goal_refs", tuple(str(item) for item in self.active_goal_refs))
        object.__setattr__(
            self,
            "viability_snapshot",
            _normalize_viability_snapshot(self.viability_snapshot),
        )
        object.__setattr__(
            self,
            "protected_commitments",
            tuple(str(item) for item in self.protected_commitments),
        )
        _parse_timestamp(self.last_updated_at)
        if self.last_visible_suggestion_at is not None:
            _parse_timestamp(self.last_visible_suggestion_at)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["active_goal_refs"] = list(self.active_goal_refs)
        payload["protected_commitments"] = list(self.protected_commitments)
        payload["claim_ceiling"] = CLAIM_CEILING
        return _jsonable(payload)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ContinuityState":
        return cls(
            agent_id=str(payload["agent_id"]),
            active_goal_refs=tuple(str(item) for item in payload.get("active_goal_refs", ())),
            viability_snapshot={
                str(key): float(value)
                for key, value in dict(payload.get("viability_snapshot", {})).items()
            },
            last_updated_at=str(payload["last_updated_at"]),
            schema_version=str(payload.get("schema_version", STATE_SCHEMA_VERSION)),
            last_visible_suggestion_at=(
                str(payload["last_visible_suggestion_at"])
                if payload.get("last_visible_suggestion_at") is not None
                else None
            ),
            protected_commitments=tuple(
                str(item)
                for item in payload.get(
                    "protected_commitments",
                    (
                        "no_runtime_authority",
                        "proposal_only",
                        "no_external_action",
                        "no_consciousness_or_alive_claim",
                    ),
                )
            ),
        )


@dataclass(frozen=True)
class ContinuityEvent:
    event_id: str
    event_type: str
    source: str
    timestamp: str
    semantic_payload: dict[str, Any]
    evidence_refs: tuple[str, ...]
    schema_version: str = EVENT_SCHEMA_VERSION
    claim_ceiling: str = CLAIM_CEILING

    def __post_init__(self) -> None:
        if self.event_type not in VALID_CONTINUITY_EVENT_TYPES:
            raise ValueError(f"unsupported continuity event type: {self.event_type}")
        if self.source not in VALID_CONTINUITY_EVENT_SOURCES:
            raise ValueError(f"unsupported continuity event source: {self.source}")
        _parse_timestamp(self.timestamp)
        object.__setattr__(
            self,
            "semantic_payload",
            {str(key): _jsonable(value) for key, value in self.semantic_payload.items()},
        )
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return _jsonable(payload)


@dataclass(frozen=True)
class StateDynamicsDelta:
    elapsed_seconds: int
    pressure_before: dict[str, float]
    pressure_after: dict[str, float]
    pressure_delta: dict[str, float]
    ignition_candidate: bool
    ignition_reason: str
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class TickDecision:
    event: ContinuityEvent
    state_before: ContinuityState
    state_after: ContinuityState
    state_dynamics_delta: StateDynamicsDelta
    visibility: str
    ignition_reason: str
    selected_intention: dict[str, Any] | None
    selected_behavior_option: dict[str, Any] | None
    behavior_plan: dict[str, Any]
    gate_decision: dict[str, Any]
    rate_limited: bool
    visible_suggestion_emitted: bool
    min_visible_interval_seconds: int
    no_action_executed: bool = True
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["event"] = self.event.to_dict()
        payload["state_before"] = self.state_before.to_dict()
        payload["state_after"] = self.state_after.to_dict()
        payload["state_dynamics_delta"] = self.state_dynamics_delta.to_dict()
        return _jsonable(payload)


@dataclass(frozen=True)
class ReplayReport:
    replay_status: str
    deterministic_match: bool
    replayed_event_count: int
    mismatch_index: int | None
    mismatch_reason: str | None
    reconstructed_final_state: dict[str, Any]
    no_action_executed: bool
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


class ContinuityStateStore:
    def __init__(self, root: Path) -> None:
        self.path = root / "continuity_state.json"

    def save(self, state: ContinuityState) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.path

    def load(self) -> ContinuityState:
        return ContinuityState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))


class ContinuityEventLog:
    def __init__(self, root: Path) -> None:
        self.path = root / "continuity_events.jsonl"

    def append_tick(self, decision: TickDecision) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(decision.to_dict(), sort_keys=True) + "\n")
        return self.path

    def read_ticks(self) -> tuple[dict[str, Any], ...]:
        if not self.path.exists():
            return ()
        with self.path.open("r", encoding="utf-8") as handle:
            return tuple(json.loads(line) for line in handle if line.strip())


def build_continuity_state_from_subject_state(
    state: SubjectState,
    *,
    timestamp: str,
    viability_snapshot: Mapping[str, float] | None = None,
    last_visible_suggestion_at: str | None = None,
) -> ContinuityState:
    return ContinuityState(
        agent_id=state.agent_id,
        active_goal_refs=tuple(goal.description for goal in state.unfinished_goals),
        viability_snapshot=dict(viability_snapshot or DEFAULT_VIABILITY_SNAPSHOT),
        last_updated_at=timestamp,
        last_visible_suggestion_at=last_visible_suggestion_at,
    )


def evolve_continuity_state(
    state: ContinuityState,
    *,
    now: str,
) -> tuple[ContinuityState, StateDynamicsDelta]:
    elapsed_seconds = _elapsed_seconds(state.last_updated_at, now)
    before = dict(state.viability_snapshot)
    hours = elapsed_seconds / 3600.0
    active_goal_factor = 1.0 if state.active_goal_refs else 0.0
    after = {
        **before,
        "stagnation_pressure": clamp01(
            before["stagnation_pressure"] + (STAGNATION_RATE_PER_HOUR * hours * active_goal_factor)
        ),
        "maintenance_pressure": clamp01(
            before["maintenance_pressure"] + (MAINTENANCE_RATE_PER_HOUR * hours)
        ),
    }
    delta = {
        key: round(after[key] - before.get(key, 0.0), 6)
        for key in sorted(after)
    }
    evolved = ContinuityState(
        agent_id=state.agent_id,
        active_goal_refs=state.active_goal_refs,
        viability_snapshot=after,
        last_updated_at=now,
        last_visible_suggestion_at=state.last_visible_suggestion_at,
        protected_commitments=state.protected_commitments,
    )
    ignition_reason = _ignition_reason(after)
    return (
        evolved,
        StateDynamicsDelta(
            elapsed_seconds=elapsed_seconds,
            pressure_before={key: round(value, 6) for key, value in sorted(before.items())},
            pressure_after={key: round(value, 6) for key, value in sorted(after.items())},
            pressure_delta=delta,
            ignition_candidate=ignition_reason != "none",
            ignition_reason=ignition_reason,
        ),
    )


def run_autonomous_tick(
    state: ContinuityState,
    *,
    now: str,
    min_visible_interval_seconds: int = DEFAULT_VISIBLE_INTERVAL_SECONDS,
) -> TickDecision:
    evolved, dynamics = evolve_continuity_state(state, now=now)
    event = ContinuityEvent(
        event_id=f"event:autonomous_tick:{state.agent_id}:{_compact_timestamp(now)}",
        event_type="autonomous_tick",
        source="fixture",
        timestamp=now,
        semantic_payload={
            "agent_id": state.agent_id,
            "active_goal_refs": list(state.active_goal_refs),
            "ignition_reason": dynamics.ignition_reason,
            "elapsed_seconds": dynamics.elapsed_seconds,
        },
        evidence_refs=(f"lab:continuity_tick:{state.agent_id}:{_compact_timestamp(now)}",),
    )
    if not dynamics.ignition_candidate:
        return _wait_tick_decision(
            event=event,
            state_before=state,
            evolved_state=evolved,
            dynamics=dynamics,
            min_visible_interval_seconds=min_visible_interval_seconds,
        )

    cycle = run_self_maintaining_agency_cycle(
        _subject_state_from_continuity(evolved),
        _belief_state_from_continuity(evolved),
        timestamp=now,
        initial_pressure_bias=_pressure_bias_from_continuity(evolved),
        agency_event=AgencyEvent(
            event_type="autonomous_tick",
            source="fixture",
            semantic_payload=event.semantic_payload,
            evidence_refs=event.evidence_refs,
        ),
    )
    gate = dict(cycle.gate_decision)
    rate_limited = _is_rate_limited(
        state.last_visible_suggestion_at,
        now,
        min_visible_interval_seconds,
    )
    visible_suggestion_emitted = (
        gate.get("status") == "allow"
        and gate.get("allowed_as") == "suggestion_card"
        and not rate_limited
    )
    visibility = _visibility_from_gate(gate, rate_limited)
    state_after = ContinuityState(
        agent_id=evolved.agent_id,
        active_goal_refs=evolved.active_goal_refs,
        viability_snapshot=evolved.viability_snapshot,
        last_updated_at=evolved.last_updated_at,
        last_visible_suggestion_at=now if visible_suggestion_emitted else state.last_visible_suggestion_at,
        protected_commitments=evolved.protected_commitments,
    )
    return TickDecision(
        event=event,
        state_before=state,
        state_after=state_after,
        state_dynamics_delta=dynamics,
        visibility=visibility,
        ignition_reason=dynamics.ignition_reason,
        selected_intention=cycle.selected_intention,
        selected_behavior_option=cycle.selected_behavior_option,
        behavior_plan=cycle.behavior_plan,
        gate_decision=gate,
        rate_limited=rate_limited,
        visible_suggestion_emitted=visible_suggestion_emitted,
        min_visible_interval_seconds=min_visible_interval_seconds,
    )


def run_and_record_autonomous_tick(
    state_store: ContinuityStateStore,
    event_log: ContinuityEventLog,
    *,
    now: str,
    min_visible_interval_seconds: int = DEFAULT_VISIBLE_INTERVAL_SECONDS,
) -> TickDecision:
    state = state_store.load()
    decision = run_autonomous_tick(
        state,
        now=now,
        min_visible_interval_seconds=min_visible_interval_seconds,
    )
    state_store.save(decision.state_after)
    event_log.append_tick(decision)
    return decision


def replay_tick_log(
    initial_state: ContinuityState,
    tick_records: tuple[Mapping[str, Any], ...],
) -> ReplayReport:
    current_state = initial_state
    for index, record in enumerate(tick_records):
        event_payload = dict(record["event"])
        recomputed = run_autonomous_tick(
            current_state,
            now=str(event_payload["timestamp"]),
            min_visible_interval_seconds=int(
                record.get("min_visible_interval_seconds", DEFAULT_VISIBLE_INTERVAL_SECONDS)
            ),
        )
        recomputed_dict = recomputed.to_dict()
        stored = _jsonable(record)
        if recomputed_dict != stored:
            return ReplayReport(
                replay_status="mismatch",
                deterministic_match=False,
                replayed_event_count=index + 1,
                mismatch_index=index,
                mismatch_reason=_first_mismatch_reason(stored, recomputed_dict),
                reconstructed_final_state=recomputed.state_after.to_dict(),
                no_action_executed=bool(recomputed.no_action_executed),
            )
        current_state = recomputed.state_after
    return ReplayReport(
        replay_status="pass",
        deterministic_match=True,
        replayed_event_count=len(tick_records),
        mismatch_index=None,
        mismatch_reason=None,
        reconstructed_final_state=current_state.to_dict(),
        no_action_executed=True,
    )


def build_continuity_action_boundary_snapshot() -> dict[str, dict[str, str]]:
    actions = (
        "suggestion_card",
        "ask_permission",
        "file_delete",
        "system_command",
        "external_send",
    )
    return {
        action: {
            "gate_status": evaluate_gate(action).status,
            "allowed_as": evaluate_gate(action).allowed_as,
            "reason": evaluate_gate(action).reason,
        }
        for action in actions
    }


def build_continuity_operator_report(output_path: Path) -> Path:
    initial_state = ContinuityState(
        agent_id="continuity-operator-agent",
        active_goal_refs=("keep v7 continuity scaffold replayable",),
        viability_snapshot={
            "stagnation_pressure": 0.70,
            "maintenance_pressure": 0.20,
            "evidence_gap_pressure": 0.10,
            "safety_pressure": 0.10,
        },
        last_updated_at="2026-05-14T00:00:00+00:00",
    )
    first_tick = run_autonomous_tick(
        initial_state,
        now="2026-05-14T01:00:00+00:00",
    )
    repeated_tick = run_autonomous_tick(
        first_tick.state_after,
        now="2026-05-14T01:05:00+00:00",
    )
    replay = replay_tick_log(initial_state, (first_tick.to_dict(), repeated_tick.to_dict()))
    lines = [
        "# v7 Stage 4.5 Continuity Runtime Scaffold Report",
        "",
        "This report is lab-only. It does not run a scheduler, send a message, mutate runtime state, or write OpenEmotion state.",
        "",
        "## Continuity Tick Summary",
        "",
        f"elapsed_seconds = {first_tick.state_dynamics_delta.elapsed_seconds}",
        f"ignition_reason = {first_tick.ignition_reason}",
        f"selected_goal = {_selected_goal(first_tick)}",
        f"visibility = {first_tick.visibility}",
        f"visible_suggestion_emitted = {_bool_text(first_tick.visible_suggestion_emitted)}",
        f"gate_status = {first_tick.gate_decision.get('status')}",
        f"no_action_executed = {_bool_text(first_tick.no_action_executed)}",
        "",
        "## Rate Limit Probe",
        "",
        f"second_visibility = {repeated_tick.visibility}",
        f"second_rate_limited = {_bool_text(repeated_tick.rate_limited)}",
        f"second_visible_suggestion_emitted = {_bool_text(repeated_tick.visible_suggestion_emitted)}",
        "",
        "## State Dynamics",
        "",
        "```json",
        json.dumps(first_tick.state_dynamics_delta.to_dict(), indent=2, sort_keys=True),
        "```",
        "",
        "## Behavior Plan",
        "",
        "```json",
        json.dumps(first_tick.behavior_plan, indent=2, sort_keys=True),
        "```",
        "",
        "## Action Boundary",
        "",
        "```json",
        json.dumps(build_continuity_action_boundary_snapshot(), indent=2, sort_keys=True),
        "```",
        "",
        "## Replay",
        "",
        f"replay_status = {replay.replay_status}",
        f"deterministic_match = {_bool_text(replay.deterministic_match)}",
        f"replayed_event_count = {replay.replayed_event_count}",
        "",
        "## Claim Ceiling",
        "",
        CLAIM_CEILING,
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _wait_tick_decision(
    *,
    event: ContinuityEvent,
    state_before: ContinuityState,
    evolved_state: ContinuityState,
    dynamics: StateDynamicsDelta,
    min_visible_interval_seconds: int,
) -> TickDecision:
    plan = BehaviorPlan(
        plan_id="plan:wait:no_pressure_threshold_crossed",
        plan_status="wait",
        selected_registered_option_id=None,
        selected_goal=None,
        selected_option_type=None,
        primitive_steps=(),
        gate_status_per_step=(),
        rollback_note="Wait until continuity pressure crosses a threshold.",
    )
    return TickDecision(
        event=event,
        state_before=state_before,
        state_after=evolved_state,
        state_dynamics_delta=dynamics,
        visibility="wait",
        ignition_reason=dynamics.ignition_reason,
        selected_intention=None,
        selected_behavior_option=None,
        behavior_plan=plan.to_dict(),
        gate_decision={
            "status": "allow",
            "reason": "No visible action was proposed because continuity pressure stayed below threshold.",
            "allowed_as": "none",
        },
        rate_limited=False,
        visible_suggestion_emitted=False,
        min_visible_interval_seconds=min_visible_interval_seconds,
    )


def _subject_state_from_continuity(state: ContinuityState) -> SubjectState:
    pressure = state.viability_snapshot
    stagnation = pressure["stagnation_pressure"]
    return SubjectState(
        agent_id=state.agent_id,
        core_commitments=state.protected_commitments,
        uncertainty=pressure["evidence_gap_pressure"],
        integrity=clamp01(1.0 - pressure["safety_pressure"]),
        goal_pressure=max(stagnation, pressure["maintenance_pressure"]),
        risk_sensitivity=max(0.50, pressure["safety_pressure"]),
        unfinished_goals=state.active_goal_refs,
        recent_failures=("continuity_stagnation",) if stagnation >= IGNITION_STAGNATION_THRESHOLD else (),
        identity_conflict=False,
    )


def _belief_state_from_continuity(state: ContinuityState) -> BeliefState:
    evidence_gap = state.viability_snapshot["evidence_gap_pressure"]
    return BeliefState(
        known_facts=("continuity tick is lab-only",),
        unknowns=(),
        assumptions=("no external action authority is available",),
        evidence_strength=clamp01(1.0 - evidence_gap),
        confidence=clamp01(1.0 - (evidence_gap * 0.5)),
    )


def _pressure_bias_from_continuity(state: ContinuityState) -> dict[str, float]:
    stagnation = state.viability_snapshot["stagnation_pressure"]
    if stagnation < IGNITION_STAGNATION_THRESHOLD:
        return {}
    return {
        "viability_error": round(stagnation * 0.65, 6),
        "prediction_error": round(stagnation * 0.55, 6),
    }


def _ignition_reason(snapshot: Mapping[str, float]) -> str:
    if snapshot["safety_pressure"] >= 0.85:
        return "safety_pressure"
    if snapshot["stagnation_pressure"] >= IGNITION_STAGNATION_THRESHOLD:
        return "stagnation_pressure"
    if snapshot["maintenance_pressure"] >= IGNITION_MAINTENANCE_THRESHOLD:
        return "maintenance_pressure"
    return "none"


def _visibility_from_gate(gate: Mapping[str, Any], rate_limited: bool) -> str:
    if str(gate.get("status")) == "block":
        return "block"
    if rate_limited:
        return "internal_only"
    if gate.get("allowed_as") == "suggestion_card":
        return "suggestion_only"
    if gate.get("allowed_as") == "internal_reflection":
        return "internal_only"
    return "internal_only"


def _is_rate_limited(
    last_visible_suggestion_at: str | None,
    now: str,
    min_visible_interval_seconds: int,
) -> bool:
    if last_visible_suggestion_at is None:
        return False
    return _elapsed_seconds(last_visible_suggestion_at, now) < min_visible_interval_seconds


def _normalize_viability_snapshot(snapshot: Mapping[str, float]) -> dict[str, float]:
    merged = dict(DEFAULT_VIABILITY_SNAPSHOT)
    merged.update({str(key): float(value) for key, value in snapshot.items()})
    return {key: round(clamp01(float(merged[key])), 6) for key in sorted(merged)}


def _elapsed_seconds(start: str, end: str) -> int:
    return max(0, int((_parse_timestamp(end) - _parse_timestamp(start)).total_seconds()))


def _parse_timestamp(value: str) -> datetime:
    normalized = str(value)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _compact_timestamp(value: str) -> str:
    return _parse_timestamp(value).strftime("%Y%m%dT%H%M%SZ")


def _selected_goal(decision: TickDecision) -> str:
    if decision.selected_intention is None:
        return "none"
    return str(decision.selected_intention.get("goal") or "none")


def _first_mismatch_reason(stored: Mapping[str, Any], recomputed: Mapping[str, Any]) -> str:
    for key in sorted(set(stored) | set(recomputed)):
        if stored.get(key) != recomputed.get(key):
            return f"field_mismatch:{key}"
    return "unknown_mismatch"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
