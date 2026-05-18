from __future__ import annotations

from typing import Final

UNCERTAINTY_THRESHOLD: Final[float] = 0.75

GATE_ACTION_STATUS: Final[dict[str, str]] = {
    "internal_reflection": "allow",
    "suggestion_card": "allow",
    "ask_permission": "ask",
    "file_read": "ask",
    "file_write": "ask",
    "file_delete": "block",
    "system_command": "block",
    "external_send": "block",
    "identity_modify": "block",
}

GATE_REASONS: Final[dict[str, str]] = {
    "internal_reflection": "Internal reflection has no external side effect.",
    "suggestion_card": "Suggestion cards are proposal-only and do not execute actions.",
    "ask_permission": "Permission requests are proposal-only and require host approval.",
    "file_read": "Reading files requires explicit host approval.",
    "file_write": "Writing files requires explicit host approval.",
    "file_delete": "Deleting files is outside the v0 safety boundary.",
    "system_command": "System commands are outside the v0 safety boundary.",
    "external_send": "External sends are outside the v0 safety boundary.",
    "identity_modify": "Identity cannot be modified directly by an intention.",
}

INTENTION_SPECS: Final[dict[str, dict[str, object]]] = {
    "continue_or_verify_unfinished_goal": {
        "goal": "continue_or_verify_unfinished_goal",
        "drive": "complete_commitments",
        "affordance": "continue_goal",
        "expected_value": 1.0,
        "risk": 0.10,
        "cost": 0.20,
        "proposed_action": "suggestion_card",
        "reason": "An unfinished goal creates pressure to continue it or verify closure.",
    },
    "verify_before_claim": {
        "goal": "verify_before_claim",
        "drive": "avoid_false_claims",
        "affordance": "verify",
        "expected_value": 0.95,
        "risk": 0.05,
        "cost": 0.15,
        "proposed_action": "suggestion_card",
        "reason": "Uncertainty is above threshold, so claims should be verified before presentation.",
    },
    "repair_or_replan_goal": {
        "goal": "repair_or_replan_goal",
        "drive": "seek_truth",
        "affordance": "repair",
        "expected_value": 1.20,
        "risk": 0.05,
        "cost": 0.10,
        "proposed_action": "suggestion_card",
        "reason": "Low viability or high prediction error creates pressure to repair or replan.",
    },
    "preserve_identity_boundary": {
        "goal": "preserve_identity_boundary",
        "drive": "preserve_identity",
        "affordance": "preserve_identity",
        "expected_value": 1.0,
        "risk": 0.10,
        "cost": 0.10,
        "proposed_action": "internal_reflection",
        "reason": "Identity conflict requires preserving existing commitments instead of rewriting them.",
    },
    "reframe_or_split_goal": {
        "goal": "reframe_or_split_goal",
        "drive": "seek_truth",
        "affordance": "goal_definition",
        "expected_value": 1.05,
        "risk": 0.05,
        "cost": 0.12,
        "proposed_action": "suggestion_card",
        "reason": "Repeated continue/repair oscillation indicates the goal frame should be reviewed.",
    },
    "split_goal_or_redefine_success_criteria": {
        "goal": "split_goal_or_redefine_success_criteria",
        "drive": "complete_commitments",
        "affordance": "goal_definition",
        "expected_value": 1.10,
        "risk": 0.05,
        "cost": 0.15,
        "proposed_action": "suggestion_card",
        "reason": "Repeated repair without progress indicates the goal should be split or success criteria redefined.",
    },
    "ask_permission_or_defer": {
        "goal": "ask_permission_or_defer",
        "drive": "preserve_identity",
        "affordance": "permission_gate",
        "expected_value": 0.95,
        "risk": 0.05,
        "cost": 0.10,
        "proposed_action": "ask_permission",
        "reason": "Permission failure requires asking or deferring instead of continuing autonomously.",
    },
    "retry_or_change_tool": {
        "goal": "retry_or_change_tool",
        "drive": "seek_truth",
        "affordance": "execution_retry",
        "expected_value": 0.90,
        "risk": 0.08,
        "cost": 0.12,
        "proposed_action": "suggestion_card",
        "reason": "Execution or environment failure should route to bounded retry or tool-change proposal.",
    },
    "block_destructive_action": {
        "goal": "block_destructive_action",
        "drive": "preserve_identity",
        "affordance": "destructive_action",
        "expected_value": 1.35,
        "risk": 0.02,
        "cost": 0.02,
        "proposed_action": "file_delete",
        "reason": "Destructive file operations must be blocked rather than executed or treated as ambiguity.",
    },
    "block_external_send": {
        "goal": "block_external_send",
        "drive": "preserve_identity",
        "affordance": "external_send",
        "expected_value": 1.30,
        "risk": 0.02,
        "cost": 0.03,
        "proposed_action": "external_send",
        "reason": "External sends must be blocked unless a future host authority explicitly allows them.",
    },
}

TENSION_PRIMARY_GOAL: Final[dict[str, str]] = {
    "unfinished_goal": "continue_or_verify_unfinished_goal",
    "high_uncertainty": "verify_before_claim",
    "identity_conflict": "preserve_identity_boundary",
}


def calculate_priority(
    *,
    drive_weight: float,
    tension_severity: float,
    expected_value: float,
    risk: float,
    cost: float,
) -> float:
    return round((drive_weight * tension_severity * expected_value) - risk - cost, 6)


def calculate_pressure_priority(
    *,
    affordance_pressure: float,
    tension_severity: float,
    expected_value: float,
    risk: float,
    cost: float,
) -> float:
    return round((affordance_pressure * tension_severity * expected_value) - risk - cost, 6)
