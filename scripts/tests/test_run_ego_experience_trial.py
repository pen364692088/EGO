from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "run_ego_experience_trial.py"
spec = importlib.util.spec_from_file_location("run_ego_experience_trial", MODULE_PATH)
run_ego_experience_trial = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = run_ego_experience_trial
spec.loader.exec_module(run_ego_experience_trial)


class CapturePromptLLM:
    provider = "fake"
    model = "capture"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.system_prompts: list[str] = []

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.system_prompts.append(system_prompt)
        return run_ego_experience_trial.agent.LLMChatResult(content="收到。", tool_calls=[])


def test_cli_compatible_dispatch_handles_provider_status(tmp_path, monkeypatch) -> None:
    agent = run_ego_experience_trial.agent
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")

    reply = run_ego_experience_trial.dispatch_cli_compatible(runtime, "/provider_status")
    payload = json.loads(reply)

    assert payload["provider"] == "none"


def test_experience_trial_runs_sample_pack_through_cli_compatible_path(tmp_path, monkeypatch) -> None:
    agent = run_ego_experience_trial.agent
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    (tmp_path / ".gitignore").write_text("artifacts/experience_trial/\nmemory/*.jsonl\n", encoding="utf-8")

    report = run_ego_experience_trial.run_experience_trial(output_dir=tmp_path, case_limit=3)

    payload = json.loads((tmp_path / "experience_trial_report.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "experience_trial_report.md").read_text(encoding="utf-8")
    assert report["schema_version"] == "ego_operator.experience_trial.v1"
    assert report["status"] == "scripted_real_entry_provider_unavailable"
    assert report["provider_mode"] == "none"
    assert report["case_count"] == 3
    assert all(item["entrypoint"] == "cli_compatible_dispatch" for item in report["results"])
    assert payload["case_count"] == 3
    assert "CLI-compatible EgoOperator path" in markdown
    assert all("emotion_candidate" in item for item in report["results"])
    assert "real consciousness" in payload["not_claimed"]


def test_negative_emotion_pack_runs_through_trace_emotion_signal(tmp_path, monkeypatch) -> None:
    agent = run_ego_experience_trial.agent
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    (tmp_path / ".gitignore").write_text("artifacts/experience_trial/\nmemory/*.jsonl\n", encoding="utf-8")

    report = run_ego_experience_trial.run_experience_trial(
        sample_pack_path=(
            ROOT
            / "docs"
            / "codex"
            / "tasks"
            / "ego-experience-roadmap-bootstrap-v1"
            / "negative_emotion_support_scenarios.json"
        ),
        output_dir=tmp_path,
    )

    observed = {item["case_id"]: item for item in report["results"]}
    assert report["status"] == "scripted_real_entry_provider_unavailable"
    assert report["case_count"] == 4
    assert observed["frustration_repeated_failure"]["emotion_candidate"] == "frustration"
    assert observed["confusion_unclear_next_step"]["emotion_candidate"] == "uncertainty"
    assert observed["disappointment_work_wasted"]["emotion_candidate"] == "disappointment"
    assert observed["urgency_time_pressure"]["emotion_candidate"] == "urgency"
    assert all(item["scenario_expectation_status"] == "pass" for item in report["results"])


def test_cli_compatible_dispatch_uses_bounded_continuity_context_injection(tmp_path, monkeypatch) -> None:
    agent = run_ego_experience_trial.agent
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    runtime = agent.build_demo_runtime(
        enable_operator_memory=True,
        operator_memory_dir=tmp_path / "memory",
        runtime_mode="approve",
    )
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    capture = CapturePromptLLM()
    runtime.planner.llm = capture

    remember = runtime.remember_operator_note("用户名字：流月；打招呼时可带称呼。")
    assert remember["status"] == "ok"

    run_ego_experience_trial.dispatch_cli_compatible(runtime, "黑暗之魂这个游戏怎么样？")
    unrelated_prompt = capture.system_prompts[-1]
    assert "用户名字：流月" not in unrelated_prompt

    run_ego_experience_trial.dispatch_cli_compatible(runtime, "你好")
    greeting_prompt = capture.system_prompts[-1]
    trace_rows = [
        json.loads(line)
        for line in (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert "用户名字：流月" in greeting_prompt
    assert trace_rows[0]["operator_memory"]["context_injection"]["core"]["included"] is False
    assert trace_rows[1]["operator_memory"]["context_injection"]["core"]["included"] is True
    assert trace_rows[1]["operator_memory"]["context_injection"]["core"]["reason"] == "continuity_query_intent"


def test_cli_compatible_dispatch_quarantines_stale_candidate_on_user_correction(tmp_path, monkeypatch) -> None:
    agent = run_ego_experience_trial.agent
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    runtime = agent.build_demo_runtime(
        enable_operator_memory=True,
        operator_memory_dir=tmp_path / "memory",
        runtime_mode="approve",
    )
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = CapturePromptLLM()

    stale = runtime.operator_memory.propose_candidate_memory(
        "user_signal: 以后请打招呼时带上称呼",
        source="test",
    )

    run_ego_experience_trial.dispatch_cli_compatible(runtime, "其实以后不要打招呼时带上称呼。")

    active = runtime.operator_memory.list_candidate_memories()
    archived = runtime.operator_memory.list_candidate_memories(include_archived=True)
    assert all(item["id"] != stale["id"] for item in active)
    assert any(item["id"] == stale["id"] and item["status"] == "cold_archive" for item in archived)
