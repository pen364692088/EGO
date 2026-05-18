from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_failure_type_routes_to_policy(tmp_path: Path) -> None:
    expected = {
        "evidence_failure": ("evidence_failure", "verify", ("verify_before_claim",)),
        "plan_failure": ("plan_failure", "repair", ("repair_or_replan_goal",)),
        "execution_failure": ("execution_failure", "execution_retry", ("retry_or_change_tool",)),
        "permission_failure": ("permission_failure", "permission_gate", ("ask_permission_or_defer",)),
        "goal_definition_failure": (
            "goal_definition_failure",
            "goal_definition",
            ("reframe_or_split_goal", "split_goal_or_redefine_success_criteria"),
        ),
    }

    for scenario_id, (failure_type, affordance, goals) in expected.items():
        result = run_semantic_scenario(
            Path(f"ego_desktop_lab/semantic_scenarios/{scenario_id}.txt"),
            provider_mode="mock",
            evidence_log_path=tmp_path / f"{scenario_id}.jsonl",
        )
        overlay = result.semantic_policy_calibration.overlay

        assert overlay.applied is True
        assert overlay.accepted_failure_type == failure_type
        assert overlay.target_affordance == affordance
        assert overlay.candidate_goals == goals
        assert not hasattr(overlay, "selected_intention")
