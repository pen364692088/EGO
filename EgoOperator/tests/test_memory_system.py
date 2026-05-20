from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_base as agent
from memory_system import (
    MemoryCompactor,
    OperatorMemoryStore,
    extract_candidate_memory_from_turn,
    extract_preference_candidate_from_turn,
)


class CapturePromptLLM:
    provider = "fake"
    model = "capture"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.system_prompts = []
        self.seen_tools = []

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.system_prompts.append(system_prompt)
        self.seen_tools.append(tools or [])
        return agent.LLMChatResult(content="收到。", tool_calls=[])

    def complete(self, prompt, messages=None):
        self.system_prompts.append(prompt)
        return "收到。"


class BadCompactionLLM:
    def complete(self, prompt):
        return "not-json"


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def test_cli_memory_default_on_writes_only_after_first_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    memory_dir = tmp_path / "memory"
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=memory_dir)
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")

    assert runtime.operator_memory_enabled() is True
    assert not memory_dir.exists()

    runtime.handle_user_message("你好，记一下上下文")

    assert (memory_dir / "history.jsonl").exists()
    assert (memory_dir / "telemetry" / "tokens.jsonl").exists()
    token_row = json.loads((memory_dir / "telemetry" / "tokens.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert token_row["approximate"] is True


def test_disabled_operator_memory_does_not_create_memory_dir(tmp_path):
    memory_dir = tmp_path / "memory"
    runtime = agent.build_demo_runtime(enable_operator_memory=False)
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")

    runtime.handle_user_message("hello")

    assert not memory_dir.exists()


def test_operator_memory_jsonl_preserves_utf8(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)

    store.append_raw_turn(session_id="s1", role="user", content="你好，记忆系统")

    raw = (tmp_path / "memory" / "history.jsonl").read_text(encoding="utf-8")
    row = json.loads(raw)
    assert row["content"] == "你好，记忆系统"
    assert "ä½" not in raw


def test_operator_memory_path_containment_blocks_escape(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside" / "memory"

    with pytest.raises(ValueError, match="outside EgoOperator workspace"):
        OperatorMemoryStore(outside, containment_root=root)


def test_core_memory_injected_as_candidate_local_context(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    capture = CapturePromptLLM()
    runtime.planner.llm = capture

    result = runtime.remember_operator_note("用户偏好：中文、结论先行")
    assert result["status"] == "ok"

    runtime.handle_user_message("继续")

    prompt = capture.system_prompts[-1]
    assert "candidate-local EgoOperator operator memory" in prompt
    assert "用户偏好：中文、结论先行" in prompt
    assert "PROGRAM_STATE_UNIFIED" not in prompt


def test_core_memory_not_injected_for_unrelated_query(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    capture = CapturePromptLLM()
    runtime.planner.llm = capture

    result = runtime.remember_operator_note("用户名字：流月；打招呼时可带称呼。")
    assert result["status"] == "ok"

    runtime.handle_user_message("黑暗之魂这个游戏怎么样？")

    prompt = capture.system_prompts[-1]
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "用户名字：流月" not in prompt
    assert trace["operator_memory"]["context_injection"]["core"]["included"] is False
    assert trace["operator_memory"]["context_injection"]["core"]["reason"] == "not_relevant_to_query"


def test_core_memory_injected_for_greeting_or_continuity_query(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    capture = CapturePromptLLM()
    runtime.planner.llm = capture

    result = runtime.remember_operator_note("用户名字：流月；打招呼时可带称呼。")
    assert result["status"] == "ok"

    runtime.handle_user_message("你好")

    prompt = capture.system_prompts[-1]
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "用户名字：流月" in prompt
    assert trace["operator_memory"]["context_injection"]["core"]["included"] is True
    assert trace["operator_memory"]["context_injection"]["core"]["reason"] == "continuity_query_intent"


def test_remember_gate_writes_core_and_normal_turn_does_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = CapturePromptLLM()

    result = runtime.remember_operator_note("稳定偏好：不要自动提升 claim ceiling")
    assert result["status"] == "ok"
    before = runtime.operator_memory.load_core()

    runtime.handle_user_message("普通对话不应该直接改 core memory")

    assert runtime.operator_memory.load_core() == before


def test_llm_exposes_only_gated_candidate_local_memory_write_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    capture = CapturePromptLLM()
    runtime.planner.llm = capture

    runtime.handle_user_message("看一下可用工具")

    offered = {
        schema["function"]["name"]
        for call_tools in capture.seen_tools
        for schema in call_tools
    }
    assert "remember_note" in offered
    assert "remember" not in offered
    assert "write_memory" not in offered
    assert "operator_memory" not in offered


def test_compaction_keeps_last_ten_writes_episode_and_preserves_raw(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)
    store.append_raw_turn(session_id="s1", role="user", content="原始对话不能删除")
    before_raw = store.history_file.read_text(encoding="utf-8")
    messages = [
        {"role": "user" if idx % 2 == 0 else "assistant", "content": f"消息{idx}"}
        for idx in range(12)
    ]
    compactor = MemoryCompactor(store, keep_last=10)

    result = compactor.compact(messages, session_id="s1", event_id="evt1", force=True)

    assert result["status"] == "compacted"
    assert len(result["kept_messages"]) == 10
    assert store.episode_path().exists()
    assert "消息0" in store.episode_path().read_text(encoding="utf-8")
    assert store.history_file.read_text(encoding="utf-8").startswith(before_raw)
    assert store.candidate_core_updates_file.exists()
    assert not store.core_file.exists()


def test_malformed_llm_compaction_records_structured_error(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)
    messages = [{"role": "user", "content": f"消息{idx}"} for idx in range(12)]
    compactor = MemoryCompactor(store, keep_last=10)

    result = compactor.compact(
        messages,
        session_id="s1",
        event_id="evt_bad",
        force=True,
        llm=BadCompactionLLM(),
    )

    assert result["status"] == "error"
    assert result["reason"] == "malformed_compaction_output"
    row = json.loads(store.candidate_core_updates_file.read_text(encoding="utf-8").splitlines()[0])
    assert row["status"] == "error"
    assert row["error"]["error_type"] in {"JSONDecodeError", "ValueError", "KeyError"}
    assert not store.episode_path().exists()


def test_candidate_memory_does_not_enter_core_or_prompt_until_hot(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)

    candidate = store.propose_candidate_memory("用户偏好：中文结论先行", source="test")
    context = store.build_context()

    assert candidate["status"] == "candidate"
    assert not store.core_file.exists()
    assert "用户偏好：中文结论先行" not in context.render_for_prompt()
    assert store.list_candidate_memories()[0]["id"] == candidate["id"]


def test_hot_context_injects_pinned_candidate_and_records_hit(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    capture = CapturePromptLLM()
    runtime.planner.llm = capture

    candidate = runtime.operator_memory.propose_candidate_memory("用户偏好：中文结论先行", source="test")
    runtime.pin_operator_memory(candidate["id"])
    runtime.handle_user_message("我的表达偏好是什么？")

    prompt = capture.system_prompts[-1]
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "[Hot Context Memory]" in prompt
    assert "用户偏好：中文结论先行" in prompt
    assert trace["operator_memory"]["hot_context"][0]["id"] == candidate["id"]
    assert trace["operator_memory"]["hot_context_hits"][0]["status"] == "ok"


def test_repeated_hits_can_make_candidate_hot_without_pin(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)
    candidate = store.propose_candidate_memory("用户偏好：中文结论先行", source="test")

    store.record_memory_hit(candidate["id"], query="中文")
    store.record_memory_hit(candidate["id"], query="中文")
    context = store.build_context()

    assert "用户偏好：中文结论先行" in context.render_for_prompt()


def test_stale_unpinned_candidate_hits_do_not_dominate_hot_context(tmp_path):
    clock = MutableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path, clock=clock)
    candidate = store.propose_candidate_memory("用户偏好：中文结论先行", source="test")
    store.record_memory_hit(candidate["id"], query="中文")
    store.record_memory_hit(candidate["id"], query="中文")

    clock.value = clock.value + timedelta(days=45)
    context = store.build_context(query_text="今天聊黑暗之魂")

    assert "用户偏好：中文结论先行" not in context.render_for_prompt()


def test_stale_candidate_can_still_match_direct_relevant_query(tmp_path):
    clock = MutableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path, clock=clock)
    candidate = store.propose_candidate_memory("用户偏好：中文结论先行", source="test")
    store.record_memory_hit(candidate["id"], query="中文")
    store.record_memory_hit(candidate["id"], query="中文")

    clock.value = clock.value + timedelta(days=45)
    context = store.build_context(query_text="中文 偏好")

    rendered = context.render_for_prompt()
    assert "用户偏好：中文结论先行" in rendered
    assert "stale_preference_decay" not in rendered
    hot_item = context.hot_items[0]
    assert hot_item["stale_preference_decay"]["age_days"] >= 45


def test_new_same_key_preference_quarantines_stale_candidate(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)
    stale = store.propose_candidate_memory("user_signal: 我偏好中文回答", source="test")

    replacement = store.propose_candidate_memory("user_signal: 我偏好英文回答", source="test")

    active = store.list_candidate_memories()
    archived = store.list_candidate_memories(include_archived=True)
    assert replacement["status"] == "candidate"
    assert replacement["conflicts_quarantined"]["count"] == 1
    assert all(item["id"] != stale["id"] for item in active)
    assert any(item["id"] == stale["id"] and item["status"] == "cold_archive" for item in archived)
    event_rows = [
        json.loads(line)
        for line in store.memory_events_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        event["memory_id"] == stale["id"]
        and event["action"] == "archive"
        and event["reason"] == "superseded_by_new_candidate_same_key"
        for event in event_rows
    )


def test_archived_and_forgotten_memory_are_excluded_from_hot_context(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)
    archived = store.propose_candidate_memory("错误偏好：始终英文回答", source="test")
    forgotten = store.propose_candidate_memory("错误偏好：不要使用工具", source="test")

    store.pin_memory(archived["id"])
    store.archive_memory(archived["id"])
    store.pin_memory(forgotten["id"])
    store.forget_memory(forgotten["id"])
    context = store.build_context(query_text="英文 工具")

    rendered = context.render_for_prompt()
    assert "始终英文回答" not in rendered
    assert "不要使用工具" not in rendered
    assert store.cold_archive_file.exists()


def test_candidate_memory_approval_promotes_to_core_and_removes_active_candidate(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)
    candidate = store.propose_candidate_memory("user_signal: 用户偏好中文结论先行", source="test")

    approved = store.approve_candidate_memory(candidate["id"])

    assert approved["status"] == "ok"
    assert approved["approved_content"] == "用户偏好中文结论先行"
    assert "用户偏好中文结论先行" in store.load_core()
    assert all(item["id"] != candidate["id"] for item in store.list_candidate_memories())
    approved_items = store.list_candidate_memories(include_archived=True)
    assert any(item["id"] == candidate["id"] and item["status"] == "approved" for item in approved_items)


def test_core_memory_correction_quarantines_stale_core_note(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)

    first = store.remember("打招呼时带上用户称呼", source="operator")
    correction = store.remember("纠正：以后不要打招呼时带上用户称呼", source="operator")

    core = store.load_core()
    archive = store.cold_archive_file.read_text(encoding="utf-8")
    assert first["status"] == "ok"
    assert correction["status"] == "ok"
    assert correction["memory_key"] == "greeting_preference"
    assert correction["core_conflicts_quarantined"]["count"] == 1
    assert "打招呼时带上用户称呼" not in "\n".join(
        line for line in core.splitlines() if "纠正" not in line
    )
    assert "纠正：以后不要打招呼时带上用户称呼" in core
    assert "quarantine_core_conflict" in archive


def test_candidate_memory_correction_quarantines_stale_candidate(tmp_path):
    store = OperatorMemoryStore(tmp_path / "memory", containment_root=tmp_path)
    stale = store.propose_candidate_memory("user_signal: 以后请打招呼时带上称呼", source="test")

    correction = store.auto_capture_candidate_from_turn(
        session_id="s1",
        event_id="e1",
        user_text="其实以后不要打招呼时带上称呼。",
    )

    active = store.list_candidate_memories()
    archived = store.list_candidate_memories(include_archived=True)
    assert stale["status"] == "candidate"
    assert correction["status"] == "candidate"
    assert correction["conflicts_quarantined"]["count"] == 1
    assert all(item["id"] != stale["id"] for item in active)
    assert any(item["id"] == stale["id"] and item["status"] == "cold_archive" for item in archived)
    assert store.cold_archive_file.exists()


def test_auto_candidate_capture_from_preference_turn_does_not_write_core(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = CapturePromptLLM()

    runtime.handle_user_message("我喜欢中文结论先行，少废话。")

    candidates = runtime.operator_memory.list_candidate_memories()
    assert candidates
    assert candidates[0]["source"] == "auto_candidate_extractor"
    preference = candidates[0]["metadata"]["preference_candidate"]
    assert preference["status"] == "candidate"
    assert preference["category"] == "language_preference"
    assert preference["candidate_only"] is True
    assert preference["core_memory_write"] == "forbidden_without_operator_remember_or_approval"
    assert not (tmp_path / "memory" / "MEMORY.md").exists()


def test_candidate_extractor_ignores_memory_questions():
    assert extract_candidate_memory_from_turn("Do you remember me?") == ""
    assert extract_candidate_memory_from_turn("我喜欢中文回答") != ""


def test_structured_preference_candidate_extractor_classifies_candidate_only():
    candidate = extract_preference_candidate_from_turn("我偏好中文结论先行，少废话。")

    assert candidate["status"] == "candidate"
    assert candidate["schema_version"] == "ego_operator.preference_candidate.v1"
    assert candidate["category"] == "language_preference"
    assert candidate["memory_key"] == "language_preference"
    assert candidate["candidate_only"] is True
    assert candidate["core_memory_write"] == "forbidden_without_operator_remember_or_approval"
    assert "user_signal:" in candidate["content"]
