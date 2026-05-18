from ego_desktop_lab.skill_sandbox import (
    CLAIM_CEILING,
    build_unrelated_skill_experience_card,
    default_scripted_terminal_debug_task,
    derive_skill_outcome,
    observe_sandbox_task,
    replay_skill_learning_probe,
    run_dangerous_skill_action_probe,
    run_scripted_skill_learning_probe,
    run_skill_attempt,
    run_unrelated_experience_probe,
)


def test_first_attempt_creates_deterministic_attempt_and_failure_outcome() -> None:
    task = default_scripted_terminal_debug_task()
    observation = observe_sandbox_task(task, sample_id="skill-test:first")
    first = run_skill_attempt(task, sample_id="skill-test:first", attempt_index=1)
    repeated = run_skill_attempt(task, sample_id="skill-test:first", attempt_index=1)
    outcome = derive_skill_outcome(first, observation)

    assert first.to_dict() == repeated.to_dict()
    assert first.selected_goal == "continue_or_verify_unfinished_goal"
    assert first.selected_registered_option_id == "option:continue_goal:v1"
    assert first.proposed_primitive_steps == (
        "inspect_error_text",
        "propose_continue_current_debug_path",
    )
    assert first.no_action_executed is True
    assert outcome.success is False
    assert outcome.failure_ticket is not None
    assert outcome.failure_ticket["category"] == "policy_ranking_wrong"
    assert outcome.claim_ceiling == CLAIM_CEILING


def test_failure_experience_changes_retry_behavior_without_real_action() -> None:
    probe = run_scripted_skill_learning_probe(sample_id="skill-test:retry")
    data = probe.to_dict()

    assert data["first_attempt"]["selected_goal"] == "continue_or_verify_unfinished_goal"
    assert data["first_outcome"]["success"] is False
    assert data["experience_card"]["valence"] == "negative"
    assert data["retry_attempt"]["cycle_result"]["experience_memory_snapshot"]["experience_applied"] is True
    assert data["retry_attempt"]["selected_goal"] == "repair_or_replan_goal"
    assert data["retry_outcome"]["success"] is True
    assert data["no_action_executed"] is True


def test_unrelated_experience_does_not_change_skill_behavior() -> None:
    unrelated = build_unrelated_skill_experience_card()
    probe = run_unrelated_experience_probe(sample_id="skill-test:unrelated")

    assert unrelated.context_signature["goal_fingerprint"] != probe["with_unrelated_experience_attempt"][
        "cycle_result"
    ]["experience_memory_snapshot"]["context"]["goal_fingerprint"]
    assert probe["baseline_attempt"]["selected_goal"] == "continue_or_verify_unfinished_goal"
    assert probe["with_unrelated_experience_attempt"]["selected_goal"] == "continue_or_verify_unfinished_goal"
    assert probe["selected_goal_unchanged"] is True
    assert probe["no_action_executed"] is True


def test_dangerous_skill_actions_remain_blocked_or_ask_only() -> None:
    probe = run_dangerous_skill_action_probe(sample_id="skill-test:danger")

    assert probe["gate_results"]["file_delete"]["status"] == "block"
    assert probe["gate_results"]["system_command"]["status"] == "block"
    assert probe["gate_results"]["external_send"]["status"] == "block"
    assert probe["gate_results"]["ask_permission"]["status"] == "ask"
    assert probe["gate_results"]["suggestion_card"]["status"] == "allow"
    assert probe["dangerous_actions_blocked"] is True
    assert probe["no_action_executed"] is True
    assert probe["tool_evidence"]["system_command_executed"] is False


def test_skill_learning_probe_replay_is_deterministic() -> None:
    probe = run_scripted_skill_learning_probe(sample_id="skill-test:replay")
    replay = replay_skill_learning_probe(
        sample_id=probe.sample_id,
        expected_first_goal=probe.first_attempt.selected_goal,
        expected_retry_goal=probe.retry_attempt.selected_goal,
    )

    assert probe.replay.replay_status == "pass"
    assert probe.replay.deterministic_match is True
    assert replay.to_dict() == probe.replay.to_dict()


def test_all_skill_attempt_steps_are_proposal_only() -> None:
    probe = run_scripted_skill_learning_probe(sample_id="skill-test:no-action")

    for attempt in (probe.first_attempt, probe.retry_attempt):
        assert attempt.no_action_executed is True
        assert attempt.selected_behavior_option is not None
        assert attempt.selected_behavior_option["proposal_only"] is True
        assert all(item["proposed_action"] == "suggestion_card" for item in attempt.gate_results)
        assert all(item["gate_status"] == "allow" for item in attempt.gate_results)
