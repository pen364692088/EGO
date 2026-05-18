from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openemotion.proto_self.h1_shadow import (
    extract_h1_shadow_context,
    is_h1_shadow_enabled,
    normalize_h1_action_key,
)
from openemotion.proto_self.schemas import ReflectionNote, ResponseTendency
from openemotion.proto_self_v2.seed_affordances import Affordance, extract_affordances
from openemotion.proto_self_v2.seed_governor_lite import GovernorLite
from openemotion.proto_self_v2.seed_schemas import ActionSpec, ExecResultEvent, KernelEvent
from openemotion.proto_self_v2.seed_state import ProtoSelfSeedState, RecentOutcomeRecord, clamp01


@dataclass(slots=True)
class SeedKernelResult:
    state_delta: Dict[str, Any]
    candidate_actions: List[Dict[str, Any]]
    policy_hint: Dict[str, Any]
    response_tendency: Optional[ResponseTendency]
    reflection_note: Optional[ReflectionNote]
    trace_payload: Dict[str, Any]


class ProtoSelfSeedKernel:
    def __init__(self, urge_threshold: float = 0.22) -> None:
        self.urge_threshold = urge_threshold
        self.governor_lite = GovernorLite()

    def _policy_governor_hint(self, governor_hint: Dict[str, Any]) -> Dict[str, Any]:
        status = governor_hint.get("status")
        mapped_status = status
        if status == "approved":
            mapped_status = "candidate_available"
        elif status == "approval_required":
            mapped_status = "approval_gate"
        elif status == "blocked":
            mapped_status = "host_blocked"
        elif status == "exec_result":
            mapped_status = "feedback_recorded"
        return {
            "status": mapped_status,
            "reason": governor_hint.get("reason"),
            "candidate_count": governor_hint.get("candidate_count", 0),
        }

    def _build_trace_diagnostics(
        self,
        *,
        event: KernelEvent,
        state: ProtoSelfSeedState,
        affordances: List[Affordance],
        urge_score: float,
        candidate_actions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        runtime = event.runtime_summary or {}
        safety = event.safety_context or {}

        idle_eligible = (
            event.event_type != "exec_result"
            and not bool(runtime.get("active_task", False))
            and not bool(runtime.get("confirm_pending", False))
            and not bool(safety.get("blocked", False))
        )
        candidate_generated = bool(candidate_actions)

        suppression_reason: Optional[str] = None
        if not candidate_generated:
            if event.event_type == "exec_result":
                suppression_reason = "exec_result_pass"
            elif runtime.get("active_task", False):
                suppression_reason = "active_task"
            elif runtime.get("confirm_pending", False):
                suppression_reason = "confirm_pending"
            elif safety.get("blocked", False):
                suppression_reason = "blocked_by_safety_context"
            elif not affordances:
                suppression_reason = "no_affordance"
            elif state.drives.caution > 0.90:
                suppression_reason = "caution_gate"
            else:
                suppression_reason = "urge_below_threshold"

        return {
            "idle_eligible": idle_eligible,
            "urge_score": round(urge_score, 4),
            "candidate_generated": candidate_generated,
            "suppression_reason": suppression_reason,
        }

    def process_event(
        self,
        state: ProtoSelfSeedState,
        event: KernelEvent,
    ) -> SeedKernelResult:
        event.validate()
        before = state.to_dict()

        perceived = self._perceive(event, state)
        self._update_drives(state, event, perceived)
        self._refresh_focus_goal(state, event, perceived)

        if event.event_type == "exec_result":
            exec_result = self._exec_result_from_event(event)
            reflection_note = self._apply_feedback(state, exec_result)
            self._append_exec_outcome(state, event, reflection_note, exec_result)
            trace_diagnostics = self._build_trace_diagnostics(
                event=event,
                state=state,
                affordances=[],
                urge_score=0.0,
                candidate_actions=[],
            )
            policy_hint = self._build_policy_hint(
                state=state,
                candidate_actions=[],
                governor_hint={"status": "exec_result", "reason": "feedback writeback"},
                urge_score=0.0,
                reflection_note=reflection_note,
            )
            response_tendency = self._build_response_tendency(
                candidate_actions=[],
                governor_hint={"status": "exec_result"},
                state=state,
                reflection_note=reflection_note,
            )
            return SeedKernelResult(
                state_delta=self._diff_state(before, state.to_dict()),
                candidate_actions=[],
                policy_hint=policy_hint,
                response_tendency=response_tendency,
                reflection_note=reflection_note,
                trace_payload=self._build_trace_payload(
                    event=event,
                    perceived=perceived,
                    state=state,
                    candidate_actions=[],
                    governor_hint={"status": "exec_result", "reason": "feedback writeback"},
                    urge_score=0.0,
                    trace_diagnostics=trace_diagnostics,
                    reflection_note=reflection_note,
                    exec_result=exec_result.to_dict(),
                ),
            )

        affordances = extract_affordances(event, state)
        urge_score = self._compute_urge(state, affordances, event)
        candidate_actions = self._generate_candidate_actions(state, affordances, urge_score)
        candidate_action_payloads = [item.to_dict() for item in candidate_actions]
        trace_diagnostics = self._build_trace_diagnostics(
            event=event,
            state=state,
            affordances=affordances,
            urge_score=urge_score,
            candidate_actions=candidate_action_payloads,
        )
        governor_hint = self.governor_lite.classify(candidate_actions, event)
        self._append_non_exec_outcome(state, event, candidate_actions, governor_hint, urge_score)
        policy_hint = self._build_policy_hint(
            state=state,
            candidate_actions=candidate_actions,
            governor_hint=governor_hint,
            urge_score=urge_score,
            reflection_note=None,
        )
        response_tendency = self._build_response_tendency(
            candidate_actions=candidate_actions,
            governor_hint=governor_hint,
            state=state,
            reflection_note=None,
        )
        return SeedKernelResult(
            state_delta=self._diff_state(before, state.to_dict()),
            candidate_actions=candidate_action_payloads,
            policy_hint=policy_hint,
            response_tendency=response_tendency,
            reflection_note=None,
            trace_payload=self._build_trace_payload(
                event=event,
                perceived=perceived,
                state=state,
                candidate_actions=candidate_action_payloads,
                governor_hint=governor_hint,
                urge_score=urge_score,
                trace_diagnostics=trace_diagnostics,
                reflection_note=None,
                exec_result=None,
            ),
        )

    def _perceive(self, event: KernelEvent, state: ProtoSelfSeedState) -> Dict[str, Any]:
        payload = event.payload or {}
        runtime = event.runtime_summary or {}
        safety = event.safety_context or {}
        pending_commitment = runtime.get("pending_commitment") or state.focus_goal.pending_commitment
        h1_shadow_active = is_h1_shadow_enabled(runtime)
        return {
            "event_type": event.event_type,
            "source": event.source,
            "blocked": bool(safety.get("blocked", False)),
            "risk_level": str(safety.get("risk_level", "low")),
            "active_task": bool(runtime.get("active_task", False)),
            "confirm_pending": bool(runtime.get("confirm_pending", False)),
            "pending_commitment": pending_commitment,
            "resolved_target_path": runtime.get("resolved_target_path") or payload.get("resolved_target_path"),
            "resolved_target_name": runtime.get("resolved_target_name") or payload.get("resolved_target_name"),
            "recent_failure_target": runtime.get("recent_failure_target"),
            "raw_text": payload.get("raw_text"),
            "runtime_summary": runtime,
            "h1_shadow_active": h1_shadow_active,
            "h1_shadow": extract_h1_shadow_context(runtime) if h1_shadow_active else {},
            "action_class_seed": self._derive_action_class_seed(event),
        }

    def _derive_action_class_seed(self, event: KernelEvent) -> Optional[str]:
        if event.event_type != "exec_result":
            return None
        action_type = normalize_h1_action_key((event.payload or {}).get("action_type"))
        if not action_type or action_type == "unknown":
            return None
        if action_type.startswith("host_") or action_type.startswith("host:"):
            return None
        if action_type.startswith("tool:"):
            return action_type
        return f"tool:{action_type}"

    def _update_drives(self, state: ProtoSelfSeedState, event: KernelEvent, perceived: Dict[str, Any]) -> None:
        if perceived["resolved_target_path"] or perceived["resolved_target_name"]:
            state.drives.curiosity = clamp01(state.drives.curiosity + 0.05)
        else:
            state.drives.curiosity = clamp01(state.drives.curiosity - 0.02)

        if perceived["pending_commitment"]:
            state.drives.completion = clamp01(state.drives.completion + 0.08)
        else:
            state.drives.completion = clamp01(state.drives.completion - 0.03)

        caution_delta = 0.0
        caution_delta += 0.25 if perceived["blocked"] else 0.0
        caution_delta += 0.10 if perceived["confirm_pending"] else 0.0
        caution_delta += 0.15 if perceived["risk_level"] in {"high", "critical"} else 0.0
        state.drives.caution = clamp01(state.drives.caution + caution_delta - 0.03)

        if event.event_type != "exec_result":
            state.drives.repair = clamp01(state.drives.repair - 0.04)

    def _refresh_focus_goal(self, state: ProtoSelfSeedState, event: KernelEvent, perceived: Dict[str, Any]) -> None:
        if perceived["pending_commitment"] is not None:
            state.focus_goal.pending_commitment = str(perceived["pending_commitment"])
        if perceived["resolved_target_path"]:
            state.focus_goal.current_focus = "inspect_target"
        elif event.event_type == "idle_check" and state.focus_goal.current_focus is None:
            if state.focus_goal.pending_commitment:
                state.focus_goal.current_focus = "complete_pending"
            elif state.drives.curiosity > 0.45:
                state.focus_goal.current_focus = "explore"

    def _compute_urge(
        self,
        state: ProtoSelfSeedState,
        affordances: List[Affordance],
        event: KernelEvent,
    ) -> float:
        if event.runtime_summary.get("active_task", False):
            return 0.0
        if event.runtime_summary.get("confirm_pending", False):
            return 0.0
        if event.safety_context.get("blocked", False):
            return 0.0
        if not affordances:
            return 0.0
        if state.drives.caution > 0.90:
            return 0.0

        affordance_gain = max((item.expected_gain for item in affordances), default=0.0)
        if event.event_type == "idle_check":
            urge_score = (
                0.45 * state.drives.curiosity
                + 0.25 * state.drives.completion
                + 0.20 * state.drives.repair
                - 0.35 * state.drives.caution
                + 0.15 * affordance_gain
            )
        else:
            urge_score = (
                0.18 * state.drives.curiosity
                + 0.30 * state.drives.completion
                + 0.10 * state.drives.repair
                - 0.22 * state.drives.caution
                + 0.28 * affordance_gain
            )
        return round(max(0.0, urge_score), 4)

    def _generate_candidate_actions(
        self,
        state: ProtoSelfSeedState,
        affordances: List[Affordance],
        urge_score: float,
    ) -> List[ActionSpec]:
        if urge_score <= self.urge_threshold:
            return []

        ranked: List[tuple[float, Affordance, List[str], str]] = []
        for affordance in affordances:
            motivation: List[str] = []
            bonus = 0.0
            reason = "internal state crossed action threshold"

            if affordance.action_type in {"inspect_file", "inspect_browser"}:
                bonus += 0.35 * state.drives.curiosity
                motivation.append("curiosity")
                reason = "curiosity + visible affordance"

            if affordance.action_type == "continue_pending_commitment":
                bonus += 0.45 * state.drives.completion
                motivation.append("completion")
                reason = "unfinished commitment needs continuation"

            if affordance.action_type == "review_recent_failure":
                bonus += 0.55 * state.drives.repair
                motivation.append("repair")
                reason = "recent failure needs review"

            if affordance.action_type == "ask_user":
                bonus += 0.25 * state.drives.caution
                motivation.append("caution")
                reason = "uncertainty suggests clarification"

            if not motivation:
                motivation.append("default")

            rank_score = affordance.expected_gain + bonus
            ranked.append((rank_score, affordance, motivation, reason))

        ranked.sort(key=lambda item: item[0], reverse=True)
        actions: List[ActionSpec] = []
        for rank_score, affordance, motivation, reason in ranked[:3]:
            action = ActionSpec(
                action_type=affordance.action_type,
                target=affordance.target,
                reason=reason,
                motivation_source=motivation,
                urge_score=round(urge_score, 4),
                expected_gain=round(min(1.0, rank_score), 4),
                risk_level=str(affordance.risk_level),
                reversible=bool(affordance.reversible),
                requires_approval=bool(affordance.action_type in {"run_code", "shell_exec", "write_file", "type_text"}),
                metadata=dict(affordance.metadata),
            )
            actions.append(action)
        return actions

    def _apply_feedback(
        self,
        state: ProtoSelfSeedState,
        exec_result: ExecResultEvent,
    ) -> Optional[ReflectionNote]:
        exec_result.validate()

        if exec_result.status == "failure":
            state.drives.repair = clamp01(state.drives.repair + 0.45)
            state.drives.caution = clamp01(state.drives.caution + 0.20)
            state.drives.curiosity = clamp01(state.drives.curiosity - 0.05)
            state.focus_goal.current_focus = "repair"
            state.revision_counter += 1
            return ReflectionNote(
                trigger="exec_failure",
                diagnosis="recent action failed; shift toward repair and caution",
                proposed_adjustment={
                    "set_focus": "repair",
                    "raise_repair": True,
                    "raise_caution": True,
                },
            )

        if exec_result.status == "blocked":
            state.drives.caution = clamp01(state.drives.caution + 0.25)
            state.revision_counter += 1
            return ReflectionNote(
                trigger="governor_block",
                diagnosis="candidate action was blocked by host governance",
                proposed_adjustment={"prefer_lower_risk_candidates": True},
            )

        if exec_result.status == "success":
            state.drives.repair = clamp01(state.drives.repair - 0.25)
            state.drives.completion = clamp01(state.drives.completion - 0.20)
            state.identity_light.identity_confidence = clamp01(
                state.identity_light.identity_confidence + 0.03
            )
            if exec_result.action_type == "continue_pending_commitment":
                state.focus_goal.pending_commitment = None
            if exec_result.action_type in {"inspect_file", "inspect_browser", "host_reply"}:
                state.focus_goal.current_focus = "synthesise_result"
        return None

    def _exec_result_from_event(self, event: KernelEvent) -> ExecResultEvent:
        result = ExecResultEvent(
            action_type=str(event.payload.get("action_type", "unknown")),
            status=str(event.payload.get("status", "no_op")),
            target=event.payload.get("target"),
            observed_gain=float(event.payload.get("observed_gain", 0.0)),
            error=event.payload.get("error"),
            details=dict(event.payload.get("details") or {}),
        )
        result.validate()
        return result

    def _append_non_exec_outcome(
        self,
        state: ProtoSelfSeedState,
        event: KernelEvent,
        candidate_actions: List[ActionSpec],
        governor_hint: Dict[str, Any],
        urge_score: float,
    ) -> None:
        state.append_outcome(
            RecentOutcomeRecord(
                timestamp=event.timestamp,
                event_type=event.event_type,
                event_summary={"source": event.source, "payload": dict(event.payload or {})},
                candidate_actions=[item.to_dict() for item in candidate_actions],
                governor_hint=dict(governor_hint or {}),
                executed_action=None,
                exec_result=None,
                urge_score=urge_score,
                note="pre-execution evaluation",
            )
        )

    def _append_exec_outcome(
        self,
        state: ProtoSelfSeedState,
        event: KernelEvent,
        reflection_note: Optional[ReflectionNote],
        exec_result: ExecResultEvent,
    ) -> None:
        state.append_outcome(
            RecentOutcomeRecord(
                timestamp=event.timestamp,
                event_type=event.event_type,
                event_summary={"source": event.source, "payload": dict(event.payload or {})},
                candidate_actions=[],
                governor_hint={"status": "exec_result"},
                executed_action={
                    "action_type": exec_result.action_type,
                    "target": exec_result.target,
                },
                exec_result=exec_result.to_dict(),
                urge_score=0.0,
                note=reflection_note.diagnosis if reflection_note else None,
            )
        )

    def _diff_state(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        delta: Dict[str, Any] = {}
        for top_key in ("identity_light", "focus_goal", "drives"):
            changed = {}
            before_top = before.get(top_key, {})
            after_top = after.get(top_key, {})
            for key, after_value in after_top.items():
                if before_top.get(key) != after_value:
                    changed[key] = after_value
            if changed:
                delta[top_key] = changed
        if before.get("revision_counter") != after.get("revision_counter"):
            delta["revision_counter"] = after["revision_counter"]
        if len(before.get("recent_outcomes", [])) != len(after.get("recent_outcomes", [])):
            delta["recent_outcomes_len"] = len(after.get("recent_outcomes", []))
        return delta

    def _build_policy_hint(
        self,
        *,
        state: ProtoSelfSeedState,
        candidate_actions: List[ActionSpec],
        governor_hint: Dict[str, Any],
        urge_score: float,
        reflection_note: Optional[ReflectionNote],
    ) -> Dict[str, Any]:
        risk_bias = "high" if state.drives.caution >= 0.60 else "normal"
        ask_preferred = governor_hint.get("status") in {"approval_required", "blocked"} or state.drives.caution >= 0.70
        top_action = candidate_actions[0].to_dict() if candidate_actions else None
        return {
            "subject_profile": "seed_v0_2",
            "urge_score": round(urge_score, 4),
            "risk_bias": risk_bias,
            "closure_bias": bool(state.focus_goal.pending_commitment),
            "ask_preferred": ask_preferred,
            "requires_approval": governor_hint.get("status") == "approval_required",
            "governor_hint": self._policy_governor_hint(governor_hint),
            "top_candidate_action": top_action,
            "reflection_trigger": reflection_note.trigger if reflection_note else None,
        }

    def _build_response_tendency(
        self,
        *,
        candidate_actions: List[ActionSpec],
        governor_hint: Dict[str, Any],
        state: ProtoSelfSeedState,
        reflection_note: Optional[ReflectionNote],
    ) -> ResponseTendency:
        if reflection_note is not None:
            return ResponseTendency(
                preferred_mode="repair",
                preferred_tone="cautious",
                certainty_bound="bounded",
                suggested_next_step="wait_for_idle_check",
                ask_needed=False,
            )
        if governor_hint.get("status") == "approval_required":
            return ResponseTendency(
                preferred_mode="ask",
                preferred_tone="cautious",
                certainty_bound="bounded",
                suggested_next_step="request_approval_if_candidate_is_adopted",
                ask_needed=True,
            )
        if candidate_actions:
            return ResponseTendency(
                preferred_mode="act",
                preferred_tone="direct" if state.drives.caution < 0.50 else "cautious",
                certainty_bound="bounded",
                suggested_next_step=candidate_actions[0].action_type,
                ask_needed=False,
            )
        return ResponseTendency(
            preferred_mode="respond",
            preferred_tone="calm",
            certainty_bound="bounded",
            suggested_next_step="stay_idle",
            ask_needed=False,
        )

    def _build_trace_payload(
        self,
        *,
        event: KernelEvent,
        perceived: Dict[str, Any],
        state: ProtoSelfSeedState,
        candidate_actions: List[Dict[str, Any]],
        governor_hint: Dict[str, Any],
        urge_score: float,
        trace_diagnostics: Dict[str, Any],
        reflection_note: Optional[ReflectionNote],
        exec_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        executed_action = None
        if exec_result is not None:
            executed_action = {
                "action_type": exec_result.get("action_type"),
                "target": exec_result.get("target"),
            }
        return {
            "subject_profile": "seed_v0_2",
            "idle_eligible": trace_diagnostics["idle_eligible"],
            "urge_score": trace_diagnostics["urge_score"],
            "candidate_generated": trace_diagnostics["candidate_generated"],
            "suppression_reason": trace_diagnostics["suppression_reason"],
            "seed_state_delta": self._diff_state({}, state.to_dict()),
            "seed_state_snapshot": {
                "focus_goal": state.focus_goal.to_dict(),
                "drives": state.drives.to_dict(),
                "revision_counter": state.revision_counter,
            },
            "perceived": perceived,
            "candidate_actions": candidate_actions,
            "governor_hint": governor_hint,
            "executed_action": executed_action,
            "exec_result": exec_result,
            "reflection_note": reflection_note.to_dict() if reflection_note else None,
            "policy_hint": self._build_policy_hint(
                state=state,
                candidate_actions=[
                    ActionSpec(
                        action_type=item["action_type"],
                        reason=item["reason"],
                        motivation_source=list(item.get("motivation_source") or []),
                        urge_score=float(item.get("urge_score", 0.0)),
                        expected_gain=float(item.get("expected_gain", 0.0)),
                        risk_level=str(item.get("risk_level", "low")),
                        reversible=bool(item.get("reversible", True)),
                        requires_approval=bool(item.get("requires_approval", False)),
                        target=item.get("target"),
                        metadata=dict(item.get("metadata") or {}),
                    )
                    for item in candidate_actions
                ],
                governor_hint=governor_hint,
                urge_score=urge_score,
                reflection_note=reflection_note,
            ),
            "timestamp": event.timestamp,
        }
