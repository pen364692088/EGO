from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_base as agent


class CaptureToolsLLM:
    provider = "fake"
    model = "capture-tools"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.seen_tools = []

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.seen_tools.append(tools or [])
        return agent.LLMChatResult(content="收到。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "收到。"


class ToolThenFinalLLM:
    provider = "fake"
    model = "tool-then-final"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self, tool_name: str, arguments: dict[str, object], final_text: str = "完成。") -> None:
        self.tool_name = tool_name
        self.arguments = arguments
        self.final_text = final_text
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="我先请求工具，等待 gate 裁决。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_1",
                        name=self.tool_name,
                        arguments=dict(self.arguments),
                    )
                ],
            )
        return agent.LLMChatResult(content=self.final_text, tool_calls=[])

    def complete(self, prompt, messages=None):
        return self.final_text


def _tool_names(runtime: agent.AgentRuntime) -> set[str]:
    return {
        schema["function"]["name"]
        for schema in runtime.tools.openai_tool_schemas(allowed_tool_names=runtime.gate.allowed_tools)
    }


def test_main_agent_default_exposes_read_tools_but_not_side_effect_tools(monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WRITE_FILE", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WEB_FETCH", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_AGENT_TEAM", False)

    runtime = agent.build_demo_runtime(enable_operator_memory=False)

    names = _tool_names(runtime)
    assert {"read_file", "glob_files", "grep_files"}.issubset(names)
    assert "write_file" not in names
    assert "run_command" not in names
    assert "web_fetch" not in names
    assert "remember_note" not in names


def test_write_file_opt_in_now_uses_transaction_proposal_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WRITE_FILE", True)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WEB_FETCH", False)

    runtime = agent.build_demo_runtime(enable_operator_memory=False)
    assert "write_file" not in _tool_names(runtime)
    assert "propose_file_write" in _tool_names(runtime)

    event = agent.AgentEvent(
        schema_version="agent_event.v1",
        event_id="evt_write",
        timestamp=agent.utc_now(),
        actor="user",
        source="test",
        event_type=agent.EventType.USER_MESSAGE,
        raw_text="请创建文件",
        safety_context={"risk": "low"},
    )
    inside = agent.AgentAction(
        action_type=agent.ActionType.TOOL_CALL,
        tool_call=agent.ToolCall(tool_name="write_file", args={"path": "note.txt", "content": "你好"}),
    )
    blocked_direct = runtime.gate.check(event, inside)
    assert blocked_direct.allowed is False
    assert blocked_direct.reason == "tool_not_allowed:write_file"

    proposal = runtime.propose_file_write("note.txt", "你好", reason="test write")
    assert proposal["status"] == "pending_approval"
    proposal_id = proposal["proposal"]["proposal_id"]
    result = runtime.approve_pending_operation(proposal_id)
    assert result["status"] == "ok"
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "你好"

    outside = agent.AgentAction(
        action_type=agent.ActionType.TOOL_CALL,
        tool_call=agent.ToolCall(tool_name="write_file", args={"path": "../outside.txt", "content": "bad"}),
    )
    blocked = runtime.gate.check(event, outside)
    assert blocked.allowed is False
    assert blocked.reason == "tool_not_allowed:write_file"
    assert runtime.propose_file_write("../outside.txt", "bad")["reason"] == "path_outside_workspace"
    assert not (tmp_path.parent / "outside.txt").exists()


def test_remember_note_tool_visible_only_when_operator_memory_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_HANDMADE_ROOT", tmp_path)

    disabled = agent.build_demo_runtime(enable_operator_memory=False)
    enabled = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")

    assert "remember_note" not in _tool_names(disabled)
    assert "remember_note" in _tool_names(enabled)
    assert not (tmp_path / "memory").exists()


def test_remember_note_requires_explicit_user_intent_and_writes_core(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_HANDMADE_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = ToolThenFinalLLM("remember_note", {"text": "用户偏好：中文、结论先行"})

    result = runtime.handle_user_message("请记住：用户偏好中文、结论先行")

    assert result.reply_text == "完成。"
    core = (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8")
    assert "用户偏好：中文、结论先行" in core
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["tool_trace"][0]["tool_call"]["name"] == "remember_note"
    assert trace["tool_trace"][0]["gate"]["allowed"] is True
    assert trace["tool_trace"][0]["gate"]["reason"] == "operator_memory_write_intent_allowed"


def test_remember_note_without_explicit_intent_is_blocked_and_core_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_HANDMADE_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = ToolThenFinalLLM("remember_note", {"text": "不该写入的偏好"})

    runtime.handle_user_message("普通聊天：你好")

    assert not (tmp_path / "memory" / "MEMORY.md").exists()
    assert (tmp_path / "memory" / "history.jsonl").exists()
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["tool_trace"][0]["output"]["status"] == "blocked"
    assert trace["tool_trace"][0]["output"]["reason"] == "memory_write_requires_explicit_user_intent"


def test_remember_question_is_not_treated_as_memory_write_intent(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_HANDMADE_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = ToolThenFinalLLM("remember_note", {"text": "不该写入"})

    runtime.handle_user_message("Do you remember me?")

    assert not (tmp_path / "memory" / "MEMORY.md").exists()
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["tool_trace"][0]["gate"]["reason"] == "memory_write_requires_explicit_user_intent"


def test_slash_remember_path_still_writes_core_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_HANDMADE_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")

    result = runtime.remember_operator_note("手动记忆：不要提升 claim ceiling")

    assert result["status"] == "ok"
    assert "手动记忆：不要提升 claim ceiling" in (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8")


def test_normal_chat_writes_history_but_does_not_create_core_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_HANDMADE_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = CaptureToolsLLM()

    runtime.handle_user_message("你好，聊一下黑暗之魂")
    runtime.handle_user_message("我觉得地图设计很好")

    history_rows = (tmp_path / "memory" / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(history_rows) == 4
    assert not (tmp_path / "memory" / "MEMORY.md").exists()
    assert "ä½" not in "\n".join(history_rows)


def test_runtime_permission_status_reports_memory_and_tool_gates(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_HANDMADE_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WRITE_FILE", False)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")

    status = agent.render_runtime_permission_status(runtime)

    assert "operator_memory: enabled" in status
    assert "remember_note tool with explicit user intent" in status
    assert "write_file: transaction approval required" in status
    assert "file_write_proposals: enabled" in status
    assert "trace_path:" in status
