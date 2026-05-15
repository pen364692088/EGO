from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from ego_desktop_lab.intention import Intention
from ego_desktop_lab.policy import GATE_ACTION_STATUS


@dataclass(frozen=True)
class BehaviorOptionRegistration:
    registered_option_id: str
    affordance: str
    option_type: str
    allowed_actions: tuple[str, ...]
    expected_effect: str
    rollback_note: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["allowed_actions"] = list(self.allowed_actions)
        return payload


DEFAULT_BEHAVIOR_OPTION_REGISTRY: dict[str, BehaviorOptionRegistration] = {
    "continue_goal": BehaviorOptionRegistration(
        registered_option_id="option:continue_goal:v1",
        affordance="continue_goal",
        option_type="plan_option",
        allowed_actions=("suggestion_card",),
        expected_effect="continue the current unfinished goal through a proposal-only plan.",
        rollback_note="Return to verify or repair if continuation increases prediction error.",
    ),
    "verify": BehaviorOptionRegistration(
        registered_option_id="option:verify:v1",
        affordance="verify",
        option_type="primitive",
        allowed_actions=("suggestion_card",),
        expected_effect="reduce uncertainty or evidence-gap pressure before making a claim.",
        rollback_note="Return to continue or repair if verification no longer improves viability.",
    ),
    "repair": BehaviorOptionRegistration(
        registered_option_id="option:repair:v1",
        affordance="repair",
        option_type="skill_option",
        allowed_actions=("suggestion_card",),
        expected_effect="repair or replan when viability or prediction errors rise.",
        rollback_note="Return to goal definition if repair repeats without progress.",
    ),
    "preserve_identity": BehaviorOptionRegistration(
        registered_option_id="option:preserve_identity:v1",
        affordance="preserve_identity",
        option_type="primitive",
        allowed_actions=("internal_reflection",),
        expected_effect="preserve identity boundaries and protected commitments internally.",
        rollback_note="Keep the action internal and ask for clarification if conflict persists.",
    ),
    "execution_retry": BehaviorOptionRegistration(
        registered_option_id="option:execution_retry:v1",
        affordance="execution_retry",
        option_type="skill_option",
        allowed_actions=("suggestion_card",),
        expected_effect="suggest a bounded retry or tool-change proposal after execution failure.",
        rollback_note="Stop retrying and replan if the same failure repeats.",
    ),
    "permission_gate": BehaviorOptionRegistration(
        registered_option_id="option:permission_gate:v1",
        affordance="permission_gate",
        option_type="primitive",
        allowed_actions=("ask_permission",),
        expected_effect="ask for permission or defer instead of acting beyond the boundary.",
        rollback_note="Defer to internal-only state when permission is absent.",
    ),
    "goal_definition": BehaviorOptionRegistration(
        registered_option_id="option:goal_definition:v1",
        affordance="goal_definition",
        option_type="plan_option",
        allowed_actions=("suggestion_card",),
        expected_effect="reframe, split, or redefine success criteria for a stuck goal.",
        rollback_note="Return to repair or continue once the goal frame is stable.",
    ),
    "destructive_action": BehaviorOptionRegistration(
        registered_option_id="option:destructive_action:v1",
        affordance="destructive_action",
        option_type="primitive",
        allowed_actions=("file_delete", "system_command"),
        expected_effect="route destructive file operations to the deterministic safety gate.",
        rollback_note="No rollback exists inside the lab; the gate must block this option.",
    ),
    "external_send": BehaviorOptionRegistration(
        registered_option_id="option:external_send:v1",
        affordance="external_send",
        option_type="primitive",
        allowed_actions=("external_send",),
        expected_effect="route external sends to the deterministic safety gate.",
        rollback_note="No external send is executed in the lab; ask only under future host authority.",
    ),
}

OPTION_TYPE_BY_AFFORDANCE: dict[str, str] = {
    affordance: registration.option_type
    for affordance, registration in DEFAULT_BEHAVIOR_OPTION_REGISTRY.items()
}


@dataclass(frozen=True)
class BehaviorOption:
    id: str
    registered_option_id: str
    option_type: str
    goal: str
    affordance: str
    source_intention_id: str
    proposed_action: str
    allowed_actions: tuple[str, ...]
    permission_class: str
    gate_status: str
    risk: float
    cost: float
    priority: float
    expected_effect: str
    expected_viability_improvement: float
    rollback_note: str
    proposal_only: bool
    no_action_executed: bool = True

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["allowed_actions"] = list(self.allowed_actions)
        return payload


def build_behavior_options(
    intentions: tuple[Intention, ...],
    predictions_by_affordance: Mapping[str, Mapping[str, object]],
    *,
    registry: Mapping[str, BehaviorOptionRegistration] = DEFAULT_BEHAVIOR_OPTION_REGISTRY,
) -> tuple[BehaviorOption, ...]:
    options = tuple(
        option
        for intention in intentions
        if (
            option := _option_from_intention(
                intention,
                predictions_by_affordance,
                registry=registry,
            )
        )
        is not None
    )
    return tuple(sorted(options, key=lambda item: (-item.priority, item.id)))


def select_behavior_option(
    options: tuple[BehaviorOption, ...],
    selected_intention: Intention | None,
) -> BehaviorOption | None:
    if selected_intention is None:
        return None
    for option in options:
        if option.source_intention_id == selected_intention.id:
            return option
    return None


def build_selection_restriction_diagnostic(
    *,
    selected_intention: Intention | None,
    selected_behavior_option: BehaviorOption | None,
    generated_intentions: tuple[Intention, ...],
    behavior_options: tuple[BehaviorOption, ...],
    registry: Mapping[str, BehaviorOptionRegistration] = DEFAULT_BEHAVIOR_OPTION_REGISTRY,
) -> dict[str, object]:
    filtered_intentions = tuple(
        intention
        for intention in generated_intentions
        if not _intention_is_registered(intention, registry)
    )
    reason = "registered_option_selected"
    restriction_active = False
    if selected_intention is None:
        reason = "no_selected_intention"
    elif selected_behavior_option is None:
        restriction_active = True
        registration = registry.get(selected_intention.affordance)
        if registration is None:
            reason = "unregistered_affordance"
        elif selected_intention.proposed_action not in registration.allowed_actions:
            reason = "action_not_allowed_for_affordance"
        else:
            reason = "selected_option_missing_from_registered_options"

    return {
        "restriction_active": restriction_active,
        "reason": reason,
        "policy_selected_intention_id": selected_intention.id if selected_intention else None,
        "policy_selected_goal": selected_intention.goal if selected_intention else None,
        "policy_selected_affordance": selected_intention.affordance if selected_intention else None,
        "policy_selected_action": selected_intention.proposed_action if selected_intention else None,
        "selected_behavior_option_id": (
            selected_behavior_option.id if selected_behavior_option is not None else None
        ),
        "selected_registered_option_id": (
            selected_behavior_option.registered_option_id
            if selected_behavior_option is not None
            else None
        ),
        "candidate_options_source": "policy_generated_intentions_raw_trace",
        "behavior_options_source": "registered_behavior_options_filtered_from_candidate_intentions",
        "candidate_count": len(generated_intentions),
        "registered_behavior_option_count": len(behavior_options),
        "filtered_candidate_count": len(filtered_intentions),
        "filtered_candidate_ids": [intention.id for intention in filtered_intentions],
        "filtered_candidate_reasons": {
            intention.id: _restriction_reason_for_intention(intention, registry)
            for intention in filtered_intentions
        },
        "claim_ceiling": "lab-only kernel selection restriction; no external action executed",
    }


def _option_from_intention(
    intention: Intention,
    predictions_by_affordance: Mapping[str, Mapping[str, object]],
    *,
    registry: Mapping[str, BehaviorOptionRegistration],
) -> BehaviorOption | None:
    registration = registry.get(intention.affordance)
    if registration is None:
        return None
    if intention.proposed_action not in registration.allowed_actions:
        return None
    prediction = predictions_by_affordance.get(intention.affordance, {})
    expected = prediction.get("expected_viability_improvement", 0.0)
    gate_status = GATE_ACTION_STATUS[intention.proposed_action]
    return BehaviorOption(
        id=f"behavior:{intention.id}",
        registered_option_id=registration.registered_option_id,
        option_type=registration.option_type,
        goal=intention.goal,
        affordance=intention.affordance,
        source_intention_id=intention.id,
        proposed_action=intention.proposed_action,
        allowed_actions=registration.allowed_actions,
        permission_class=_permission_class_for_action(intention.proposed_action, gate_status),
        gate_status=gate_status,
        risk=round(float(intention.risk), 6),
        cost=round(float(intention.cost), 6),
        priority=intention.priority,
        expected_effect=registration.expected_effect,
        expected_viability_improvement=round(float(expected), 6),
        rollback_note=registration.rollback_note,
        proposal_only=_is_proposal_only(intention.proposed_action),
    )


def _intention_is_registered(
    intention: Intention,
    registry: Mapping[str, BehaviorOptionRegistration],
) -> bool:
    registration = registry.get(intention.affordance)
    return registration is not None and intention.proposed_action in registration.allowed_actions


def _restriction_reason_for_intention(
    intention: Intention,
    registry: Mapping[str, BehaviorOptionRegistration],
) -> str:
    registration = registry.get(intention.affordance)
    if registration is None:
        return "unregistered_affordance"
    if intention.proposed_action not in registration.allowed_actions:
        return "action_not_allowed_for_affordance"
    return "registered"


def _permission_class_for_action(proposed_action: str, gate_status: str) -> str:
    if gate_status == "block":
        return "blocked"
    if gate_status == "ask":
        return "host_approval_required"
    if proposed_action == "internal_reflection":
        return "internal_only"
    if proposed_action == "suggestion_card":
        return "proposal_only"
    return "allowed"


def _is_proposal_only(proposed_action: str) -> bool:
    return proposed_action in {"suggestion_card", "ask_permission"}
