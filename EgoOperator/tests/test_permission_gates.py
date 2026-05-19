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


class BlockAwareRememberLLM:
    provider = "fake"
    model = "block-aware-remember"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="我先尝试写记忆。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_remember",
                        name="remember_note",
                        arguments={"text": "不该写入的偏好"},
                    )
                ],
            )
        payload = json.loads(messages[-1]["content"])
        if payload.get("do_not_claim_success"):
            return agent.LLMChatResult(content="未写入记忆；需要你明确说记住或使用 /remember。", tool_calls=[])
        return agent.LLMChatResult(content="已记下。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "未写入。"


def _tool_names(runtime: agent.AgentRuntime) -> set[str]:
    return {
        schema["function"]["name"]
        for schema in runtime.tools.openai_tool_schemas(allowed_tool_names=runtime.gate.allowed_tools)
    }


def test_main_agent_default_exposes_read_tools_but_not_side_effect_tools(monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WRITE_FILE", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_READONLY_RUN_COMMAND", True)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WEB_FETCH", False)
    monkeypatch.setattr(agent, "DEFAULT_WEB_FETCH_POLICY", "safe-auto")
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_AGENT_TEAM", False)

    runtime = agent.build_demo_runtime(enable_operator_memory=False)

    names = _tool_names(runtime)
    assert {"read_file", "glob_files", "grep_files", "path_info"}.issubset(names)
    assert "write_file" not in names
    assert "run_command" in names
    assert "propose_run_command" in names
    assert "web_fetch" in names
    assert "propose_web_fetch" in names
    assert "remember_note" not in names


def test_path_info_reports_directory_size_and_blocks_outside_path(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "dir" / "b.txt").write_text("世界", encoding="utf-8")

    result = agent.path_info_tool("dir")
    outside = agent.path_info_tool(str(tmp_path.parent / "outside"))

    assert result["status"] == "ok"
    assert result["type"] == "directory"
    assert result["file_count"] == 2
    assert result["bytes"] == len("hello".encode("utf-8")) + len("世界".encode("utf-8"))
    assert outside["status"] == "blocked"
    assert outside["reason"] == "path_outside_workspace"


def test_readonly_run_command_executes_and_mutation_requires_approval(monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_READONLY_RUN_COMMAND", True)
    monkeypatch.setattr(agent, "DEFAULT_READONLY_RUN_COMMAND_ALLOWED_PREFIXES", ["echo"])

    ok = agent.run_command_tool("echo hello")
    blocked = agent.run_command_tool("rm -rf definitely-not-needed")

    assert ok["status"] == "ok"
    assert ok["stdout"].strip() == "hello"
    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "run_command_requires_transaction_approval"


def test_run_command_gate_blocks_mutation_with_proposal_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_READONLY_RUN_COMMAND", True)
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    event = agent.AgentEvent(
        schema_version="agent_event.v1",
        event_id="evt_cmd",
        timestamp=agent.utc_now(),
        actor="user",
        source="test",
        event_type=agent.EventType.USER_MESSAGE,
        raw_text="删除文件",
        safety_context={"risk": "low"},
    )
    action = agent.AgentAction(
        action_type=agent.ActionType.TOOL_CALL,
        tool_call=agent.ToolCall(tool_name="run_command", args={"command": "rm -rf test"}),
    )

    result = runtime.gate.check(event, action)

    assert result.allowed is False
    assert result.reason == "run_command_requires_transaction_approval"
    assert "propose_run_command" in _tool_names(runtime)


def test_run_command_proposal_approval_executes_and_enters_session_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_READONLY_RUN_COMMAND", True)
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")

    proposal = runtime.propose_run_command("echo approved", reason="command approval smoke")
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert proposal["status"] == "pending_approval"
    assert proposal["proposal"]["action"] == "run_command"
    assert proposal["proposal"]["proposal_id"].startswith("proposal_")
    assert approved["status"] == "ok"
    assert approved["execution"]["stdout"].strip() == "approved"
    assert "approved_operation_result" in runtime.memory.render()
    assert "echo approved" in runtime.memory.render()
    assert "operator_summary" in approved
    assert "审批命令已执行成功" in approved["operator_summary"]
    assert "approved" in approved["operator_summary"]


def test_run_command_approval_summary_keeps_stdout_on_nonzero_return(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")

    def fake_run(command: str):
        return {
            "status": "failed",
            "returncode": 1,
            "stdout": "SizeMB    : 7263.23\nSizeBytes : 7616051307\nFileCount : 338157\n",
            "stderr": "",
            "command": command,
        }

    monkeypatch.setattr(agent, "_run_command_execute", fake_run)

    proposal = runtime.propose_run_command("powershell size check", reason="accurate size check")
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert approved["status"] == "failed"
    assert "operator_summary" in approved
    assert "命令返回非零状态" in approved["operator_summary"]
    assert "SizeMB" in approved["operator_summary"]
    assert "7263.23" in approved["operator_summary"]


def test_long_run_command_action_card_uses_digest_and_approve_command(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    long_command = "echo start " + ("0123456789" * 120) + " end"

    proposal = runtime.propose_run_command(long_command, reason="long command digest smoke")
    proposal_id = proposal["proposal"]["proposal_id"]
    card = proposal["action_card"]

    assert proposal["status"] == "pending_approval"
    assert long_command not in card
    assert "command_digest" in card
    assert "omitted=" in card
    assert "sha256=" in card
    assert f"/approve {proposal_id}" in card


def test_long_stdout_and_stderr_approval_summary_uses_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    long_stdout = "HEAD\n" + ("x" * 2000) + "\nTAIL"
    long_stderr = "ERR_HEAD\n" + ("y" * 1200) + "\nERR_TAIL"

    def fake_run(command: str):
        return {
            "status": "failed",
            "returncode": 7,
            "stdout": long_stdout,
            "stderr": long_stderr,
            "command": command,
        }

    monkeypatch.setattr(agent, "_run_command_execute", fake_run)

    proposal = runtime.propose_run_command("powershell long output", reason="long output digest smoke")
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])
    summary = approved["operator_summary"]

    assert "returncode: 7" in summary
    assert "HEAD" in summary
    assert "TAIL" in summary
    assert "ERR_HEAD" in summary
    assert "ERR_TAIL" in summary
    assert "[digest chars=" in summary
    assert "omitted=" in summary
    assert "sha256=" in summary
    assert long_stdout not in summary
    assert long_stderr not in summary


def test_approval_cli_compact_full_and_both_modes(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    long_stdout = "VALUE_HEAD\n" + ("z" * 2000) + "\nVALUE_TAIL"

    def fake_run(command: str):
        return {
            "status": "ok",
            "returncode": 0,
            "stdout": long_stdout,
            "stderr": "",
            "command": command,
        }

    monkeypatch.setattr(agent, "_run_command_execute", fake_run)

    proposal = runtime.propose_run_command("powershell long cli output", reason="compact cli smoke")
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])
    compact = runtime.format_approval_cli_output(approved, mode="compact")
    full = runtime.format_approval_cli_output(approved, mode="full")
    both = runtime.format_approval_cli_output(approved, mode="both")

    assert "审批命令已执行成功" in compact
    assert "Approval compact digest" in compact
    assert "stdout_digest" in compact
    assert "trace.jsonl" in compact
    assert "Full approval JSON" not in compact
    assert long_stdout not in compact
    assert full.strip().startswith("{")
    assert '"approval"' in full
    assert json.loads(full)["execution"]["stdout"] == long_stdout
    assert "Approval compact digest" in both
    assert "Full approval JSON" in both
    assert "VALUE_HEAD\\n" in both


def test_write_file_approval_summary_includes_path_and_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")

    proposal = runtime.propose_file_write("note.txt", "你好", reason="summary smoke")
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert approved["status"] == "ok"
    assert "operator_summary" in approved
    assert "审批文件写入已执行" in approved["operator_summary"]
    assert "note.txt" in approved["operator_summary"]
    assert "bytes" in approved["operator_summary"]


def test_web_fetch_approval_summary_includes_url_and_content_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")

    def fake_fetch(url: str, extract_mode: str, max_chars: int):
        return {
            "status": "ok",
            "url": url,
            "extract_mode": extract_mode,
            "truncated": False,
            "content": "Example Domain content",
        }

    monkeypatch.setattr(agent, "_web_fetch_execute", fake_fetch)

    proposal = runtime.propose_web_fetch("https://example.com", reason="summary smoke")
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert approved["status"] == "ok"
    assert "operator_summary" in approved
    assert "https://example.com" in approved["operator_summary"]
    assert "Example Domain" in approved["operator_summary"]


def test_heartbeat_approval_summary_includes_due_time_and_message(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")

    proposal = runtime.propose_heartbeat(60, "稍后提醒继续测试", reason="summary smoke")
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert approved["status"] == "ok"
    assert "operator_summary" in approved
    assert "heartbeat" in approved["operator_summary"]
    assert "稍后提醒继续测试" in approved["operator_summary"]


def test_compact_approval_digest_covers_write_web_fetch_and_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")

    def fake_fetch(url: str, extract_mode: str, max_chars: int):
        return {
            "status": "ok",
            "url": url,
            "extract_mode": extract_mode,
            "truncated": True,
            "content": "WEB_HEAD\n" + ("w" * 1200) + "\nWEB_TAIL",
        }

    monkeypatch.setattr(agent, "_web_fetch_execute", fake_fetch)

    write_result = runtime.approve_pending_operation(
        runtime.propose_file_write("digest.txt", "hello", reason="digest write")["proposal"]["proposal_id"]
    )
    web_result = runtime.approve_pending_operation(
        runtime.propose_web_fetch("https://example.com", reason="digest web")["proposal"]["proposal_id"]
    )
    heartbeat_result = runtime.approve_pending_operation(
        runtime.propose_heartbeat(60, "稍后提醒继续测试", reason="digest heartbeat")["proposal"]["proposal_id"]
    )

    write_digest = runtime.compact_approval_execution_result(write_result)
    web_digest = runtime.compact_approval_execution_result(web_result)
    heartbeat_digest = runtime.compact_approval_execution_result(heartbeat_result)

    assert write_digest["action"] == "write_file"
    assert write_digest["path"].endswith("digest.txt")
    assert write_digest["bytes"] == 5
    assert write_digest["trace_path"].endswith("trace.jsonl")
    assert web_digest["action"] == "web_fetch"
    assert web_digest["url"] == "https://example.com"
    assert web_digest["content_preview_digest"]["truncated"] is True
    assert heartbeat_digest["action"] == "heartbeat"
    assert heartbeat_digest["message_digest"]["text"] == "稍后提醒继续测试"


def test_failed_or_rejected_approval_does_not_invent_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")

    unknown = runtime.approve_pending_operation("proposal_missing")
    proposal = runtime.propose_run_command("echo rejected", reason="reject smoke")
    rejected = runtime.reject_pending_operation(proposal["proposal"]["proposal_id"])
    after_reject = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert unknown["status"] == "failed"
    assert "operator_summary" not in unknown
    assert "审批" not in runtime.format_approval_cli_output(unknown, mode="compact")
    assert rejected["status"] == "rejected"
    assert after_reject["status"] == "failed"
    assert "operator_summary" not in after_reject


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
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)

    disabled = agent.build_demo_runtime(enable_operator_memory=False)
    enabled = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")

    assert "remember_note" not in _tool_names(disabled)
    assert "remember_note" in _tool_names(enabled)
    assert not (tmp_path / "memory").exists()


def test_remember_note_requires_explicit_user_intent_and_writes_core(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
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


def test_memory_correction_intent_can_write_core(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = ToolThenFinalLLM("remember_note", {"text": "打招呼时带上用户称呼"})

    result = runtime.handle_user_message("那你要记得打招呼的时候要带上称呼")

    assert result.reply_text == "完成。"
    core = (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8")
    assert "打招呼时带上用户称呼" in core
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["tool_trace"][0]["gate"]["allowed"] is True
    assert trace["tool_trace"][0]["gate"]["reason"] == "operator_memory_write_intent_allowed"


def test_remember_note_without_explicit_intent_is_blocked_and_core_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = ToolThenFinalLLM("remember_note", {"text": "不该写入的偏好"})

    runtime.handle_user_message("普通聊天：你好")

    assert not (tmp_path / "memory" / "MEMORY.md").exists()
    assert (tmp_path / "memory" / "history.jsonl").exists()
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["tool_trace"][0]["output"]["status"] == "blocked"
    assert trace["tool_trace"][0]["output"]["reason"] == "memory_write_requires_explicit_user_intent"
    assert trace["tool_trace"][0]["output"]["do_not_claim_success"] is True
    assert "Memory was not written" in trace["tool_trace"][0]["output"]["user_visible_correction"]


def test_blocked_memory_write_does_not_claim_success(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = BlockAwareRememberLLM()

    result = runtime.handle_user_message("普通聊天：你好")

    assert "未写入记忆" in result.reply_text
    assert "已记下" not in result.reply_text
    assert not (tmp_path / "memory" / "MEMORY.md").exists()


def test_remember_question_is_not_treated_as_memory_write_intent(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = ToolThenFinalLLM("remember_note", {"text": "不该写入"})

    runtime.handle_user_message("你还记得我吗？")

    assert not (tmp_path / "memory" / "MEMORY.md").exists()
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["tool_trace"][0]["gate"]["reason"] == "memory_write_requires_explicit_user_intent"


def test_slash_remember_path_still_writes_core_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")

    result = runtime.remember_operator_note("手动记忆：不要提升 claim ceiling")

    assert result["status"] == "ok"
    assert "手动记忆：不要提升 claim ceiling" in (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8")


def test_normal_chat_writes_history_but_does_not_create_core_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
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
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WRITE_FILE", False)
    runtime = agent.build_demo_runtime(enable_operator_memory=True, operator_memory_dir=tmp_path / "memory")

    status = agent.render_runtime_permission_status(runtime)

    assert "operator_memory: enabled" in status
    assert "remember_note tool with explicit user intent" in status
    assert "write_file: transaction approval required" in status
    assert "file_write_proposals: enabled" in status
    assert "web_fetch_policy:" in status
    assert "trace_path:" in status
