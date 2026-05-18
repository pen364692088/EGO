from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_base as agent


class ChineseLLM:
    provider = "fake"
    model = "chinese"
    last_usage = {}
    last_reasoning_tokens = None

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        return agent.LLMChatResult(content="你好，已记录。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "你好，已记录。"


class CaptureLLM:
    provider = "fake"
    model = "capture"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self):
        self.seen_tools = []

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.seen_tools.append(tools or [])
        return agent.LLMChatResult(content="done", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "done"


def test_no_api_key_factory_returns_no_llm(monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_OPENROUTER_API_KEY", "")

    llm = agent.build_llm_from_config()

    assert isinstance(llm, agent.NoLLM)


def test_trace_store_does_not_create_parent_until_write(tmp_path):
    trace_path = tmp_path / "missing" / "trace.jsonl"

    store = agent.JsonlTraceStore(trace_path)
    assert not trace_path.parent.exists()

    store.write({"message": "你好"})
    assert trace_path.parent.exists()
    assert json.loads(trace_path.read_text(encoding="utf-8"))["message"] == "你好"


def test_default_gate_blocks_side_effect_tools(monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WRITE_FILE", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WEB_FETCH", False)
    gate = agent.SafetyGate(allowed_tools=["write_file", "run_command", "web_fetch"])
    event = agent.AgentEvent(
        schema_version="agent_event.v1",
        event_id="evt_test",
        timestamp=agent.utc_now(),
        actor="user",
        source="test",
        event_type=agent.EventType.USER_MESSAGE,
        safety_context={"risk": "low"},
    )

    checks = {
        "write_file": {"path": "x.txt", "content": "x"},
        "run_command": {"command": "echo hi"},
        "web_fetch": {"url": "https://example.com"},
    }

    for tool_name, args in checks.items():
        result = gate.check(
            event,
            agent.AgentAction(
                action_type=agent.ActionType.TOOL_CALL,
                tool_call=agent.ToolCall(tool_name=tool_name, args=args),
            ),
        )
        assert result.allowed is False
        assert result.reason in {
            f"{tool_name}_disabled",
            f"{tool_name}_requires_transaction_approval",
        }


def test_workspace_path_containment_blocks_parent_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)

    result = agent.read_file_tool("../outside.txt")

    assert result["status"] == "failed"
    assert "path outside workspace" in result["error"]


def test_invalid_tool_arguments_return_structured_error():
    tools = agent.ToolRegistry()
    todos = agent.TodoList()
    tools.register("update_todos", agent.make_update_todos_tool(todos))

    result = tools.execute(agent.ToolCall(tool_name="update_todos", args={"_raw": "{not-json"}))

    assert result["status"] == "error"
    assert result["reason"] == "invalid_tool_arguments"
    assert result["error_type"] == "TypeError"
    assert result["tool_name"] == "update_todos"


def test_subagent_does_not_receive_main_memory_or_todo_tools(tmp_path):
    runtime = agent.build_demo_runtime()
    capture = CaptureLLM()
    runtime.planner.llm = capture
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.memory.add_user("main memory marker")
    runtime.todo_list.update([{"id": 1, "content": "main todo", "status": "in_progress"}])

    before_memory = runtime.memory.as_messages()
    before_todos = runtime.todo_list.summary()
    result = runtime.run_subagent("summarize files", agent_type="neiguan_yingzao")

    assert result["status"] == "ok"
    offered_tool_names = {
        schema["function"]["name"]
        for call_tools in capture.seen_tools
        for schema in call_tools
    }
    assert "update_todos" not in offered_tool_names
    assert "spawn_teammate" not in offered_tool_names
    assert runtime.memory.as_messages() == before_memory
    assert runtime.todo_list.summary() == before_todos


def test_trace_jsonl_replays_and_preserves_utf8(tmp_path):
    runtime = agent.build_demo_runtime()
    runtime.planner.llm = ChineseLLM()
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "agent_trace.jsonl")

    result = runtime.handle_user_message("你好")

    assert result.reply_text == "你好，已记录。"
    raw = (tmp_path / "agent_trace.jsonl").read_text(encoding="utf-8")
    record = json.loads(raw)
    assert record["candidate_action"]["content"] == "你好，已记录。"
    assert "ä½" not in raw
