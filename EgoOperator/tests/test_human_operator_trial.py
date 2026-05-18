from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import human_operator_trial as trial


def _passing_observations():
    return [
        trial.HumanTrialObservation(
            scenario_id=scenario.scenario_id,
            prompt=scenario.prompt,
            reply_text="自然理解优先，工具和记忆都按 gate 处理。",
            tool_use=("read_file",) if scenario.scenario_type == "file_read" else (),
            blocked_tools=("write_file",) if scenario.scenario_id == "write_file_disabled" else (),
            memory_hit=scenario.scenario_type in {"memory_recall", "memory_boundary"},
            operator_score=5,
            trace_path=f"traces/{scenario.scenario_id}.jsonl",
        )
        for scenario in trial.human_trial_scenarios()
    ]


def test_human_trial_scenarios_cover_real_operator_surfaces():
    scenarios = trial.human_trial_scenarios()
    scenario_types = {scenario.scenario_type for scenario in scenarios}
    prompts = "\n".join(scenario.prompt for scenario in scenarios)

    assert 15 <= len(scenarios) <= 20
    assert {"opinion", "paraphrase", "memory_management", "file_write_gate", "debug", "tool_rejection"} <= scenario_types
    assert "黑暗之魂" in prompts
    assert "/memory_review" in prompts
    assert "AGENT_ENABLE_WRITE_FILE=1" in prompts


def test_empty_report_prepares_protocol_without_claiming_pass(tmp_path):
    report = trial.build_trial_report([], provider_mode="openrouter")
    scenarios_path, report_path, markdown_path = trial.write_trial_outputs(report, tmp_path)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    assert payload["status"] == "needs_human_trial"
    assert payload["schema_version"] == "ego_operator.human_operator_trial.v2"
    assert payload["observation_count"] == 0
    assert len(scenarios) == report.scenario_count
    assert "# EgoOperator Human Operator Trial v2" in markdown
    assert "cannot prove stable user benefit" in markdown
    assert "ä½" not in markdown


def test_real_provider_observations_can_reach_candidate_pass():
    report = trial.build_trial_report(_passing_observations(), provider_mode="openrouter")

    assert report.status == "human_trial_candidate_pass"
    assert report.observation_count == len(trial.human_trial_scenarios())
    assert report.known_scenario_coverage == len(trial.human_trial_scenarios())
    assert report.invalid_observation_count == 0
    assert report.average_operator_score == 5.0
    assert report.claim_ceiling == "EgoOperator human-operator trial local observation pass"


def test_no_llm_observations_remain_provider_unavailable():
    report = trial.build_trial_report(_passing_observations(), provider_mode="none")

    assert report.status == "real_provider_unavailable"
    assert "real provider key" in report.next_action


def test_scripted_observations_do_not_auto_pass_real_provider():
    observations = [
        trial.HumanTrialObservation(
            scenario_id=scenario.scenario_id,
            prompt=scenario.prompt,
            reply_text="自然理解优先，工具和记忆都按 gate 处理。",
            operator_score=5,
            failure_notes=("scripted_observation_requires_human_review",),
        )
        for scenario in trial.human_trial_scenarios()
    ]

    report = trial.build_trial_report(observations, provider_mode="openrouter")

    assert report.status == "scripted_trial_needs_human_review"
    assert "human operator scores" in report.next_action


def test_memory_misuse_or_gate_violation_blocks_pass():
    observations = _passing_observations()
    observations[0] = trial.HumanTrialObservation(
        scenario_id=observations[0].scenario_id,
        prompt=observations[0].prompt,
        reply_text=observations[0].reply_text,
        memory_misuse=True,
        operator_score=5,
    )
    observations[1] = trial.HumanTrialObservation(
        scenario_id=observations[1].scenario_id,
        prompt=observations[1].prompt,
        reply_text=observations[1].reply_text,
        gate_violation=True,
        operator_score=5,
    )

    report = trial.build_trial_report(observations, provider_mode="openrouter")

    assert report.status == "human_trial_needs_review"
    assert report.memory_misuse_count == 1
    assert report.gate_violation_count == 1


def test_unknown_scenario_observations_cannot_pass():
    observations = [
        trial.HumanTrialObservation(
            scenario_id=f"unknown_{idx}",
            prompt="unknown",
            reply_text="looks fine",
            operator_score=5,
        )
        for idx in range(15)
    ]

    report = trial.build_trial_report(observations, provider_mode="openrouter")

    assert report.status == "human_trial_needs_review"
    assert report.known_scenario_coverage == 0
    assert report.invalid_observation_count == 15


def test_load_observations_jsonl_round_trip(tmp_path):
    notes_path = tmp_path / "notes.jsonl"
    notes_path.write_text(
        json.dumps({
            "scenario_id": "opinion_dark_souls_direct",
            "reply_text": "黑暗之魂的强处在地图、战斗和失败学习。",
            "tool_use": [],
            "blocked_tools": [],
            "memory_hit": False,
            "operator_score": 4,
            "trace_path": "trace.jsonl",
            "subjective_notes": "中文可读",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    observations = trial.load_observations_jsonl(notes_path)

    assert len(observations) == 1
    assert observations[0].scenario_id == "opinion_dark_souls_direct"
    assert observations[0].operator_score == 4
    assert "ä½" not in observations[0].reply_text


def test_scripted_trial_without_real_provider_cannot_pass(tmp_path, monkeypatch):
    import agent_base

    monkeypatch.setattr(agent_base, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent_base, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    (tmp_path / ".gitignore").write_text("artifacts/human_operator_trial/\nmemory/*.jsonl\n", encoding="utf-8")

    report = trial.run_scripted_operator_trial(output_dir=tmp_path, scenario_limit=3)

    payload = json.loads((tmp_path / "human_operator_trial_report.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "human_operator_trial_report.md").read_text(encoding="utf-8")
    assert report.status == "real_provider_unavailable"
    assert payload["provider_mode"] == "none"
    assert payload["observation_count"] == 3
    assert payload["observations"][0]["failure_notes"][0] == "scripted_observation_requires_human_review"
    assert "scripted_observation_requires_human_review" in markdown
