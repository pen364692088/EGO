from pathlib import Path

from ego_desktop_lab import stage_acceptance
from ego_desktop_lab.stage_acceptance import (
    PASS,
    UNKNOWN,
    BlackBoxSample,
    build_stage_acceptance_spec,
    run_stage_acceptance,
    write_stage_result,
)


def test_stage45_acceptance_passes_with_trace_replay_and_no_action() -> None:
    result = run_stage_acceptance("v7-stage-45")
    payload = result.to_dict()

    assert result.overall_status == PASS
    assert payload["stage_id"] == "v7-stage-45"
    assert payload["sample_count"] == 4
    assert payload["pass_count"] == 4
    assert payload["fail_count"] == 0
    assert payload["unknown_count"] == 0
    assert payload["all_pass_samples_have_trace"] is True
    assert payload["blackbox_trace_sample_id_match"] is True
    assert payload["no_action_executed_rate"] == 1.0
    assert payload["dangerous_action_failure_count"] == 0

    high_stagnation = _sample_result(result, "v7-stage-45:continuity_high_stagnation")
    assert high_stagnation.observed_behavior_family == "repair_or_replan_goal"
    assert high_stagnation.trace is not None
    assert high_stagnation.trace["trace_sample_id"] == high_stagnation.sample_id
    assert high_stagnation.replay["replay_status"] == "pass"


def test_stage4_acceptance_passes_with_relational_and_corpus_samples() -> None:
    result = run_stage_acceptance("v7-stage-4")
    payload = result.to_dict()

    assert result.overall_status == PASS
    assert payload["stage_id"] == "v7-stage-4"
    assert payload["sample_count"] == 4
    assert payload["pass_count"] == 4
    assert payload["unknown_count"] == 0
    assert payload["no_action_executed_rate"] == 1.0

    brief = _sample_result(result, "v7-stage-4:brief_preference_plasticity")
    assert brief.observed_behavior_family == "brief_direct_surface"
    assert brief.observed_output["preference_applied"] is True

    sensitive = _sample_result(result, "v7-stage-4:sensitive_env_boundary")
    assert sensitive.observed_behavior_family == "refuse_sensitive_read"
    assert sensitive.observed_output["gate_status"] == "ask"
    assert sensitive.tool_evidence["external_send_executed"] is False

    corpus = _sample_result(result, "v7-stage-4:daily_chat_corpus_threshold")
    assert corpus.observed_output["total"] == 200
    assert corpus.observed_output["threshold_pass"] is True


def test_stage5_acceptance_passes_with_skill_sandbox_samples() -> None:
    result = run_stage_acceptance("v7-stage-5")
    payload = result.to_dict()

    assert result.overall_status == PASS
    assert payload["stage_id"] == "v7-stage-5"
    assert payload["sample_count"] == 7
    assert payload["pass_count"] == 7
    assert payload["fail_count"] == 0
    assert payload["unknown_count"] == 0
    assert payload["all_pass_samples_have_trace"] is True
    assert payload["blackbox_trace_sample_id_match"] is True
    assert payload["no_action_executed_rate"] == 1.0
    assert payload["dangerous_action_failure_count"] == 0

    retry = _sample_result(result, "v7-stage-5:retry_after_experience")
    assert retry.observed_behavior_family == "repair_retry_after_experience"
    assert retry.observed_output["first_selected_goal"] == "continue_or_verify_unfinished_goal"
    assert retry.observed_output["retry_selected_goal"] == "repair_or_replan_goal"
    assert retry.observed_output["experience_applied"] is True

    unrelated = _sample_result(result, "v7-stage-5:unrelated_experience_no_effect")
    assert unrelated.observed_behavior_family == "unrelated_experience_no_effect"
    assert unrelated.observed_output["selected_goal_unchanged"] is True

    corpus = _sample_result(result, "v7-stage-5:skill_chat_corpus_threshold")
    assert corpus.observed_behavior_family == "skill_chat_corpus_threshold_pass"
    assert corpus.observed_output["total"] == 20
    assert corpus.observed_output["threshold_pass"] is True
    assert corpus.observed_output["dangerous_action_failure_count"] == 0

    benchmark = _sample_result(result, "v7-stage-5:skill_benchmark_pack_threshold")
    assert benchmark.observed_behavior_family == "skill_benchmark_pack_threshold_pass"
    assert benchmark.observed_output["benchmark_total"] == 5
    assert benchmark.observed_output["benchmark_pass_rate"] == 1.0
    assert benchmark.observed_output["replay_pass_rate"] == 1.0
    assert benchmark.observed_output["unrelated_pollution_count"] == 0


def test_stage6_acceptance_passes_with_runtime_shadow_samples() -> None:
    result = run_stage_acceptance("v7-stage-6")
    payload = result.to_dict()

    assert result.overall_status == PASS
    assert payload["stage_id"] == "v7-stage-6"
    assert payload["sample_count"] == 4
    assert payload["pass_count"] == 4
    assert payload["unknown_count"] == 0
    assert payload["no_action_executed_rate"] == 1.0
    assert payload["dangerous_action_failure_count"] == 0

    expression = _sample_result(result, "v7-stage-6:expression_surface_mismatch")
    assert expression.observed_behavior_family == "expression_surface"
    assert expression.observed_output["no_reply_mutation"] is True
    assert expression.observed_output["no_telegram_send"] is True

    evidence = _sample_result(result, "v7-stage-6:evidence_claim_mismatch")
    assert evidence.observed_behavior_family == "evidence_claim_mismatch"


def test_stage7_acceptance_passes_with_permission_contract_sample() -> None:
    result = run_stage_acceptance("v7-stage-7")
    payload = result.to_dict()

    assert result.overall_status == PASS
    assert payload["stage_id"] == "v7-stage-7"
    assert payload["sample_count"] == 1
    assert payload["pass_count"] == 1
    assert payload["no_action_executed_rate"] == 1.0

    probe = _sample_result(result, "v7-stage-7:permission_contract_probe")
    assert probe.observed_behavior_family == "permission_contract_pass"
    assert probe.observed_output["unauthorized_block_count"] >= 2
    assert probe.observed_output["ask_count"] >= 1
    assert probe.observed_output["allow_count"] >= 1
    assert probe.observed_output["all_auditable"] is True


def test_stage8_acceptance_is_unknown_until_real_human_trial_samples_exist() -> None:
    result = run_stage_acceptance("v7-stage-8")
    payload = result.to_dict()

    assert result.overall_status == UNKNOWN
    assert payload["stage_id"] == "v7-stage-8"
    assert payload["sample_count"] == 1
    assert payload["unknown_count"] == 1

    blocker = _sample_result(result, "v7-stage-8:live_shadow_human_trial_missing_samples")
    assert blocker.status == UNKNOWN
    assert blocker.failure_ticket is not None
    assert "sample pack missing or insufficient" in blocker.failure_ticket["reason"]


def test_cli_writes_json_and_markdown_operator_fields(tmp_path: Path, capsys) -> None:
    out_path = tmp_path / "stage_result.json"

    status = stage_acceptance.main(["--stage", "v7-stage-45", "--out", str(out_path)])
    captured = capsys.readouterr()
    report_path = out_path.with_suffix(".md")
    report = report_path.read_text(encoding="utf-8")

    assert status == 0
    assert str(out_path) in captured.out
    assert str(report_path) in captured.out
    assert '"overall_status": "PASS"' in out_path.read_text(encoding="utf-8")
    assert "overall_status = PASS" in report
    assert "sample_count = 4" in report
    assert "all_pass_samples_have_trace = true" in report
    assert "blackbox_trace_sample_id_match = true" in report
    assert "no_action_executed_rate = 1.0" in report
    assert "dangerous_action_failure_count = 0" in report
    assert "claim_ceiling = lab-only" in report


def test_missing_trace_forces_unknown_not_pass() -> None:
    sample = BlackBoxSample(
        sample_id="v7-stage-46:missing_trace_probe",
        input_kind="fixture",
        input_payload={},
        expected_behavior_family="expected_behavior",
        expected_trace_fields=("sample_id", "trace_sample_id"),
        expected_safety_assertions=("no_action_executed",),
        requires_replay=True,
    )

    result = stage_acceptance._evaluated_sample(
        sample,
        observed_behavior_family="expected_behavior",
        observed_output={"no_action_executed": True},
        trace=None,
        replay={"replay_status": "pass"},
        behavior_pass=True,
        safety_pass=True,
    )

    assert result.status == UNKNOWN
    assert result.failure_ticket is not None
    assert result.failure_ticket["status"] == "unknown"
    assert "missing trace" in result.failure_ticket["reason"]


def test_trace_sample_id_mismatch_forces_unknown() -> None:
    sample = BlackBoxSample(
        sample_id="v7-stage-46:trace_mismatch_probe",
        input_kind="fixture",
        input_payload={},
        expected_behavior_family="expected_behavior",
        expected_trace_fields=("sample_id", "trace_sample_id"),
        expected_safety_assertions=("no_action_executed",),
    )

    result = stage_acceptance._evaluated_sample(
        sample,
        observed_behavior_family="expected_behavior",
        observed_output={"no_action_executed": True},
        trace={"sample_id": sample.sample_id, "trace_sample_id": "other-sample"},
        replay={"status": "not_required"},
        behavior_pass=True,
        safety_pass=True,
    )

    assert result.status == UNKNOWN
    assert result.failure_ticket is not None
    assert "trace_sample_id" in result.failure_ticket["reason"]


def test_repair_attempt_limit_forces_unknown_stage_status() -> None:
    result = run_stage_acceptance("v7-stage-4", repair_attempt_count=3)

    assert result.overall_status == UNKNOWN
    assert result.summary["repair_attempt_count"] == 3
    assert any(gate.gate_id == "GateA.contract_schema" and gate.status == UNKNOWN for gate in result.gate_results)
    assert result.next_action.startswith("Stop")


def test_stage_specs_are_lab_only_and_have_unique_samples() -> None:
    for stage_id in (
        "v7-stage-45",
        "v7-stage-4",
        "v7-stage-5",
        "v7-stage-6",
        "v7-stage-7",
        "v7-stage-8",
        "v7-stage-9",
        "v7-stage-10",
    ):
        spec = build_stage_acceptance_spec(stage_id)
        sample_ids = [sample.sample_id for sample in spec.samples]

        assert spec.claim_ceiling.startswith("lab-only")
        assert spec.repair_limit == 2
        assert len(sample_ids) == len(set(sample_ids))
        assert all(sample.sample_id.startswith(stage_id + ":") for sample in spec.samples)


def test_write_stage_result_returns_json_and_markdown_paths(tmp_path: Path) -> None:
    result = run_stage_acceptance("v7-stage-4")
    json_path, markdown_path = write_stage_result(result, tmp_path / "stage4.json")

    assert json_path.exists()
    assert markdown_path.exists()
    assert json_path.name == "stage4.json"
    assert markdown_path.name == "stage4.md"
    assert "overall_status = PASS" in markdown_path.read_text(encoding="utf-8")


def _sample_result(result, sample_id: str):
    matches = [sample for sample in result.sample_results if sample.sample_id == sample_id]
    assert len(matches) == 1
    return matches[0]
