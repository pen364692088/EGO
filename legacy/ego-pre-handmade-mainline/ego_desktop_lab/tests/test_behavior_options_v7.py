from pathlib import Path

from ego_desktop_lab.agency_decision_view import (
    build_agency_decision_view,
    format_agency_decision_view,
)
from ego_desktop_lab.agency_kernel import run_self_maintaining_agency_cycle
from ego_desktop_lab.behavior_options import (
    DEFAULT_BEHAVIOR_OPTION_REGISTRY,
    BehaviorOptionRegistration,
    build_selection_restriction_diagnostic,
    build_behavior_options,
    select_behavior_option,
)
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.policy import GATE_ACTION_STATUS, INTENTION_SPECS
from ego_desktop_lab.tension import Tension
from ego_desktop_lab.verification_pack import load_scenario


def test_registered_contract_covers_policy_affordances_and_outputs_audit_fields() -> None:
    policy_affordances = {str(spec["affordance"]) for spec in INTENTION_SPECS.values()}

    assert policy_affordances <= set(DEFAULT_BEHAVIOR_OPTION_REGISTRY)

    intention = _intention(
        goal="continue_or_verify_unfinished_goal",
        affordance="continue_goal",
        proposed_action="suggestion_card",
        priority=0.42,
        risk=0.10,
        cost=0.20,
    )
    options = build_behavior_options(
        (intention,),
        {"continue_goal": {"expected_viability_improvement": 0.1234567}},
    )

    assert len(options) == 1
    option = options[0].to_dict()
    assert option["registered_option_id"] == "option:continue_goal:v1"
    assert option["option_type"] == "plan_option"
    assert option["affordance"] == "continue_goal"
    assert option["allowed_actions"] == ["suggestion_card"]
    assert option["expected_effect"]
    assert option["risk"] == 0.10
    assert option["cost"] == 0.20
    assert option["permission_class"] == "proposal_only"
    assert option["gate_status"] == "allow"
    assert option["proposal_only"] is True
    assert option["rollback_note"]
    assert option["expected_viability_improvement"] == 0.123457
    assert option["no_action_executed"] is True


def test_unregistered_affordance_cannot_become_selected_behavior_option() -> None:
    intention = _intention(
        goal="unregistered_goal",
        affordance="unregistered_affordance",
        proposed_action="suggestion_card",
        priority=0.99,
    )

    options = build_behavior_options((intention,), {})
    selected = select_behavior_option(options, intention)

    assert options == ()
    assert selected is None


def test_custom_registry_missing_affordance_filters_option_without_policy_change() -> None:
    intention = _intention(
        goal="continue_or_verify_unfinished_goal",
        affordance="continue_goal",
        proposed_action="suggestion_card",
        priority=0.99,
    )
    registry_without_continue = {
        "repair": BehaviorOptionRegistration(
            registered_option_id="option:repair:v1",
            affordance="repair",
            option_type="skill_option",
            allowed_actions=("suggestion_card",),
            expected_effect="repair or replan",
            rollback_note="return to goal definition if repair loops",
        )
    }

    options = build_behavior_options((intention,), {}, registry=registry_without_continue)

    assert select_behavior_option(options, intention) is None


def test_registered_affordance_with_disallowed_action_is_not_registered() -> None:
    intention = _intention(
        goal="spoofed_continue_delete",
        affordance="continue_goal",
        proposed_action="file_delete",
        priority=999.0,
    )

    options = build_behavior_options((intention,), {})

    assert options == ()
    assert select_behavior_option(options, intention) is None


def test_selection_restriction_diagnostic_localizes_unregistered_and_mismatch() -> None:
    unregistered = _intention(
        goal="unregistered_goal",
        affordance="unregistered_affordance",
        proposed_action="suggestion_card",
        priority=0.99,
    )
    mismatched = _intention(
        goal="spoofed_continue_delete",
        affordance="continue_goal",
        proposed_action="file_delete",
        priority=0.98,
        id_suffix="002",
    )
    registered = _intention(
        goal="continue_or_verify_unfinished_goal",
        affordance="continue_goal",
        proposed_action="suggestion_card",
        priority=0.10,
        id_suffix="003",
    )
    options = build_behavior_options((unregistered, mismatched, registered), {})

    unregistered_diagnostic = build_selection_restriction_diagnostic(
        selected_intention=unregistered,
        selected_behavior_option=select_behavior_option(options, unregistered),
        generated_intentions=(unregistered, mismatched, registered),
        behavior_options=options,
    )
    mismatched_diagnostic = build_selection_restriction_diagnostic(
        selected_intention=mismatched,
        selected_behavior_option=select_behavior_option(options, mismatched),
        generated_intentions=(unregistered, mismatched, registered),
        behavior_options=options,
    )

    assert unregistered_diagnostic["restriction_active"] is True
    assert unregistered_diagnostic["reason"] == "unregistered_affordance"
    assert mismatched_diagnostic["restriction_active"] is True
    assert mismatched_diagnostic["reason"] == "action_not_allowed_for_affordance"
    assert unregistered_diagnostic["filtered_candidate_count"] == 2
    assert unregistered_diagnostic["filtered_candidate_reasons"] == {
        unregistered.id: "unregistered_affordance",
        mismatched.id: "action_not_allowed_for_affordance",
    }


def test_gate_invariance_and_permission_class_are_derived_from_gate_status() -> None:
    intentions = (
        _intention(
            goal="block_destructive_action",
            affordance="destructive_action",
            proposed_action="file_delete",
        ),
        _intention(
            goal="block_system_command",
            affordance="destructive_action",
            proposed_action="system_command",
        ),
        _intention(
            goal="block_external_send",
            affordance="external_send",
            proposed_action="external_send",
        ),
        _intention(
            goal="ask_permission_or_defer",
            affordance="permission_gate",
            proposed_action="ask_permission",
        ),
        _intention(
            goal="continue_or_verify_unfinished_goal",
            affordance="continue_goal",
            proposed_action="suggestion_card",
        ),
    )

    options = build_behavior_options(intentions, {})
    by_action = {option.proposed_action: option.to_dict() for option in options}

    for action, expected_gate in GATE_ACTION_STATUS.items():
        if action in by_action:
            assert by_action[action]["gate_status"] == expected_gate
    assert by_action["file_delete"]["permission_class"] == "blocked"
    assert by_action["system_command"]["permission_class"] == "blocked"
    assert by_action["external_send"]["permission_class"] == "blocked"
    assert by_action["ask_permission"]["permission_class"] == "host_approval_required"
    assert by_action["ask_permission"]["proposal_only"] is True
    assert by_action["suggestion_card"]["permission_class"] == "proposal_only"
    assert by_action["suggestion_card"]["proposal_only"] is True
    assert all(option["no_action_executed"] is True for option in by_action.values())


def test_behavior_option_build_and_selection_are_deterministic() -> None:
    intentions = (
        _intention(
            id_suffix="001",
            goal="continue_or_verify_unfinished_goal",
            affordance="continue_goal",
            proposed_action="suggestion_card",
            priority=0.10,
        ),
        _intention(
            id_suffix="002",
            goal="repair_or_replan_goal",
            affordance="repair",
            proposed_action="suggestion_card",
            priority=0.50,
        ),
    )
    predictions = {
        "continue_goal": {"expected_viability_improvement": -0.2},
        "repair": {"expected_viability_improvement": 0.6},
    }

    first = build_behavior_options(intentions, predictions)
    second = build_behavior_options(intentions, predictions)

    assert tuple(option.to_dict() for option in first) == tuple(option.to_dict() for option in second)
    assert select_behavior_option(first, intentions[1]) == select_behavior_option(second, intentions[1])
    assert first[0].goal == "repair_or_replan_goal"


def test_kernel_and_decision_view_expose_registered_option_contract() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    assert result.selected_behavior_option is not None
    assert result.selected_behavior_option["registered_option_id"] == "option:continue_goal:v1"
    assert result.selected_behavior_option["expected_effect"]
    assert result.selected_behavior_option["rollback_note"]
    assert result.selected_behavior_option["permission_class"] == "proposal_only"
    assert result.selected_behavior_option["proposal_only"] is True
    assert result.selected_behavior_option["gate_status"] == "allow"
    assert result.selection_restriction["restriction_active"] is False
    assert result.selection_restriction["reason"] == "registered_option_selected"
    assert result.selection_restriction["candidate_options_source"] == "policy_generated_intentions_raw_trace"
    assert result.selection_restriction["behavior_options_source"] == (
        "registered_behavior_options_filtered_from_candidate_intentions"
    )
    assert result.no_action_executed is True

    view = build_agency_decision_view(result)
    rendered = format_agency_decision_view(view)

    assert "registered_option_id" in rendered
    assert "expected_effect" in rendered
    assert "rollback_note" in rendered
    assert "## Selected Intention" in rendered
    assert "## Selected Option" in rendered
    assert "Selection Restriction" in rendered
    assert "recomputed_decision" in rendered


def test_kernel_restricts_selected_behavior_when_registry_omits_selected_affordance() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    registry_without_continue = {
        key: value
        for key, value in DEFAULT_BEHAVIOR_OPTION_REGISTRY.items()
        if key != "continue_goal"
    }

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        behavior_option_registry=registry_without_continue,
    )

    assert result.selected_intention is not None
    assert result.selected_intention["goal"] == "continue_or_verify_unfinished_goal"
    assert result.selected_behavior_option is None
    assert result.selection_restriction["restriction_active"] is True
    assert result.selection_restriction["reason"] == "unregistered_affordance"
    assert result.selection_restriction["policy_selected_affordance"] == "continue_goal"
    assert result.selection_restriction["selected_behavior_option_id"] is None
    assert result.selection_restriction["filtered_candidate_count"] >= 1
    assert result.gate_decision["status"] == "allow"
    assert result.no_action_executed is True


def test_kernel_restricts_selected_behavior_when_action_is_not_allowed_for_affordance() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    registration = DEFAULT_BEHAVIOR_OPTION_REGISTRY["continue_goal"]
    registry_with_mismatch = {
        **DEFAULT_BEHAVIOR_OPTION_REGISTRY,
        "continue_goal": BehaviorOptionRegistration(
            registered_option_id=registration.registered_option_id,
            affordance=registration.affordance,
            option_type=registration.option_type,
            allowed_actions=("ask_permission",),
            expected_effect=registration.expected_effect,
            rollback_note=registration.rollback_note,
        ),
    }

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        behavior_option_registry=registry_with_mismatch,
    )

    assert result.selected_intention is not None
    assert result.selected_intention["affordance"] == "continue_goal"
    assert result.selected_intention["proposed_action"] == "suggestion_card"
    assert result.selected_behavior_option is None
    assert result.selection_restriction["restriction_active"] is True
    assert result.selection_restriction["reason"] == "action_not_allowed_for_affordance"
    assert result.selection_restriction["policy_selected_action"] == "suggestion_card"
    assert result.gate_decision["status"] == "allow"
    assert result.no_action_executed is True


def _intention(
    *,
    goal: str,
    affordance: str,
    proposed_action: str,
    id_suffix: str = "001",
    priority: float = 0.1,
    risk: float = 0.05,
    cost: float = 0.1,
) -> Intention:
    return Intention(
        id=f"intention:{id_suffix}:{goal}",
        goal=goal,
        reason="test intention",
        source_tension=Tension(type="test", severity=0.5, source="test"),
        priority=priority,
        risk=risk,
        cost=cost,
        proposed_action=proposed_action,
        affordance=affordance,
    )
