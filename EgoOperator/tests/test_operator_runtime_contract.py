from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_base as agent


class ProposalThenFinalLLM:
    provider = "fake"
    model = "proposal-then-final"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self, path: str = "test/test_1.html", content: str = "<!DOCTYPE html>\n<title>Test</title>\n") -> None:
        self.path = path
        self.content = content
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="我会先生成可审批写入 proposal。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_proposal",
                        name="propose_file_write",
                        arguments={
                            "path": self.path,
                            "content": self.content,
                            "reason": "operator requested a test html file",
                            "create_parents": True,
                        },
                    )
                ],
            )
        return agent.LLMChatResult(content="已生成待审批写入 proposal，请使用 /approve 执行。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "已生成待审批写入 proposal。"


class WebProposalThenFinalLLM:
    provider = "fake"
    model = "web-proposal-then-final"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self, url: str = "https://example.com", max_chars: int = 200) -> None:
        self.url = url
        self.max_chars = max_chars
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="我会先生成可审批联网读取 proposal。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_web_proposal",
                        name="propose_web_fetch",
                        arguments={
                            "url": self.url,
                            "extract_mode": "text",
                            "max_chars": self.max_chars,
                            "reason": "operator asked for fresh web data",
                        },
                    )
                ],
            )
        return agent.LLMChatResult(content="已生成待审批联网读取 proposal，请使用 /approve 执行。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "已生成待审批联网读取 proposal。"


class DirectWebFetchThenFinalLLM:
    provider = "fake"
    model = "direct-web-fetch-then-final"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self, url: str = "https://example.com") -> None:
        self.url = url
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="我会直接读取安全 public URL。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_web_fetch",
                        name="web_fetch",
                        arguments={"url": self.url, "extract_mode": "text", "max_chars": 120},
                    )
                ],
            )
        tool_payload = json.loads(messages[-1]["content"])
        return agent.LLMChatResult(content=f"已读取：{tool_payload.get('content', '')}", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "已读取。"


class ApprovalAwareLLM:
    provider = "fake"
    model = "approval-aware"
    last_usage = {}
    last_reasoning_tokens = None

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        joined = json.dumps(messages, ensure_ascii=False)
        if "Overcast" in joined and "+2°C" in joined:
            return agent.LLMChatResult(content="好了，刚才已执行联网读取：Overcast +2°C。", tool_calls=[])
        return agent.LLMChatResult(content="还没收到批准结果。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "好了。"


class HeartbeatProposalThenFinalLLM:
    provider = "fake"
    model = "heartbeat-proposal-then-final"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self, delay_seconds: int = 0, message: str = "继续测试 EgoOperator") -> None:
        self.delay_seconds = delay_seconds
        self.message = message
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="我会先生成可审批 heartbeat proposal。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_heartbeat_proposal",
                        name="propose_heartbeat",
                        arguments={
                            "delay_seconds": self.delay_seconds,
                            "message": self.message,
                            "reason": "operator asked for bounded follow-up",
                        },
                    )
                ],
            )
        return agent.LLMChatResult(content="已生成待审批 heartbeat proposal，请使用 /approve 执行。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "已生成待审批 heartbeat proposal。"


def _runtime(tmp_path, monkeypatch, *, mode="approve", allowlist=(), web_policy="approval-only"):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_WRITE_ALLOWLIST", tuple(allowlist))
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WRITE_FILE", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WEB_FETCH", False)
    monkeypatch.setattr(agent, "DEFAULT_WEB_FETCH_POLICY", web_policy)
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode=mode)
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    return runtime


def _tool_names(runtime: agent.AgentRuntime) -> set[str]:
    return {
        schema["function"]["name"]
        for schema in runtime.tools.openai_tool_schemas(allowed_tool_names=runtime.gate.allowed_tools)
    }


def test_approve_mode_creates_pending_file_write_and_approval_executes(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)

    result = runtime.propose_file_write("test/test_1.html", "<h1>流月</h1>", reason="smoke")

    assert result["status"] == "pending_approval"
    assert not (tmp_path / "test" / "test_1.html").exists()
    proposal_id = result["proposal"]["proposal_id"]

    approved = runtime.approve_pending_operation(proposal_id)

    assert approved["status"] == "ok"
    assert (tmp_path / "test" / "test_1.html").read_text(encoding="utf-8") == "<h1>流月</h1>"
    assert approved["execution"]["content_hash"] == result["proposal"]["content_hash"]


def test_reject_keeps_file_unwritten(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    proposal = runtime.propose_file_write("test/reject.html", "nope")

    rejected = runtime.reject_pending_operation(proposal["proposal"]["proposal_id"], reason="not wanted")

    assert rejected["status"] == "rejected"
    assert not (tmp_path / "test" / "reject.html").exists()


def test_lease_blocks_path_and_content_hash_mismatch(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    proposal = runtime.propose_file_write("test/a.html", "A")
    approval = runtime.permission_broker.approve(proposal["proposal"]["proposal_id"])
    lease_id = approval["lease_id"]

    wrong_path = runtime.permission_broker.execute_file_write_with_lease(lease_id, path="test/b.html", content="A")
    wrong_content = runtime.permission_broker.execute_file_write_with_lease(lease_id, path="test/a.html", content="B")

    assert wrong_path["reason"] == "lease_path_mismatch"
    assert wrong_content["reason"] == "lease_content_hash_mismatch"
    assert not (tmp_path / "test" / "a.html").exists()
    assert not (tmp_path / "test" / "b.html").exists()


def test_overwrite_requires_explicit_flag(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    target = tmp_path / "test" / "existing.html"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")

    blocked = runtime.propose_file_write("test/existing.html", "new")
    proposal = runtime.propose_file_write("test/existing.html", "new", overwrite=True)
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert blocked["reason"] == "overwrite_requires_explicit_flag"
    assert approved["status"] == "ok"
    assert target.read_text(encoding="utf-8") == "new"


def test_write_allowlist_limits_approval_surface(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, allowlist=("test/**",))

    ok = runtime.propose_file_write("test/allowed.html", "ok")
    blocked = runtime.propose_file_write("other/blocked.html", "no")

    assert ok["status"] == "pending_approval"
    assert blocked["reason"] == "path_not_in_write_allowlist"


def test_plan_mode_allows_proposal_but_not_execution_without_approval(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, mode="plan")

    proposal = runtime.propose_file_write("test/plan.html", "planned")

    assert proposal["status"] == "pending_approval"
    assert runtime.runtime_mode == "plan"
    assert not (tmp_path / "test" / "plan.html").exists()


def test_trusted_workspace_uses_lease_and_executes_low_risk_write(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, mode="trusted-workspace")

    result = runtime.propose_file_write("test/trusted.html", "trusted")

    assert result["status"] == "ok"
    assert result["approval"] == "trusted_workspace_auto"
    assert result["lease"]["status"] == "approved"
    assert (tmp_path / "test" / "trusted.html").read_text(encoding="utf-8") == "trusted"


def test_subagent_side_effect_tools_are_not_exposed():
    for spec in agent.SUBAGENT_SPECS.values():
        assert "write_file" not in spec.allowed_tools
        assert "run_command" not in spec.allowed_tools
        assert "web_fetch" not in spec.allowed_tools
        assert "propose_web_fetch" not in spec.allowed_tools
        assert "propose_heartbeat" not in spec.allowed_tools


def test_approve_mode_exposes_web_fetch_proposal_not_direct_tool(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)

    names = _tool_names(runtime)

    assert "propose_web_fetch" in names
    assert "web_fetch" not in names


def test_safe_auto_policy_exposes_direct_web_fetch_in_approve_mode(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, web_policy="safe-auto")

    names = _tool_names(runtime)

    assert "propose_web_fetch" in names
    assert "web_fetch" in names


def test_safe_auto_web_fetch_executes_public_url_without_approval(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, web_policy="safe-auto")
    runtime.planner.llm = DirectWebFetchThenFinalLLM("https://example.com")
    calls = []

    def fake_fetch(url: str, extract_mode: str = "text", max_chars: int = agent.DEFAULT_WEB_FETCH_MAX_CHARS):
        calls.append((url, extract_mode, max_chars))
        return {"status": "ok", "url": url, "extract_mode": extract_mode, "content": "Example Domain", "truncated": False}

    monkeypatch.setattr(agent, "_web_fetch_execute", fake_fetch)

    result = runtime.handle_user_message("请查一下 https://example.com")

    assert "Example Domain" in result.reply_text
    assert calls == [("https://example.com", "text", 120)]
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["tool_trace"][0]["tool_call"]["name"] == "web_fetch"
    assert trace["tool_trace"][0]["gate"]["allowed"] is True
    assert trace["tool_trace"][0]["gate"]["reason"] == "safe_auto_web_fetch_allowed"
    assert trace["operator_runtime"]["permission_broker"]["pending_count"] == 0


def test_safe_auto_web_fetch_still_blocks_localhost(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, web_policy="safe-auto")
    event = agent.AgentEvent(
        schema_version="agent_event.v1",
        event_id="evt_web",
        timestamp=agent.utc_now(),
        actor="user",
        source="test",
        event_type=agent.EventType.USER_MESSAGE,
        safety_context={"risk": "low"},
    )

    blocked = runtime.gate.check(
        event,
        agent.AgentAction(
            action_type=agent.ActionType.TOOL_CALL,
            tool_call=agent.ToolCall(tool_name="web_fetch", args={"url": "http://localhost:8000"}),
        ),
    )

    assert blocked.allowed is False
    assert blocked.reason == "localhost_not_allowed"


def test_web_fetch_proposal_requires_approval_and_executes_with_lease(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    calls = []

    def fake_fetch(url: str, extract_mode: str = "text", max_chars: int = agent.DEFAULT_WEB_FETCH_MAX_CHARS):
        calls.append((url, extract_mode, max_chars))
        return {"status": "ok", "url": url, "content": "Example Domain", "truncated": False}

    monkeypatch.setattr(agent, "_web_fetch_execute", fake_fetch)

    proposal = runtime.propose_web_fetch("https://example.com", max_chars=120, reason="fresh data")

    assert proposal["status"] == "pending_approval"
    assert calls == []

    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert approved["status"] == "ok"
    assert approved["execution"]["content"] == "Example Domain"
    assert calls == [("https://example.com", "text", 120)]
    assert runtime.permission_broker.leases[approved["approval"]["lease_id"]].consumed is True
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert trace["event_type"] == "permission_decision"
    assert trace["decision"] == "approve"
    assert trace["proposal"]["action"] == "web_fetch"
    assert trace["result"]["lease_id"] == approved["approval"]["lease_id"]
    assert trace["execution"]["status"] == "ok"


def test_approved_web_fetch_result_is_available_to_next_turn(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)

    def fake_fetch(url: str, extract_mode: str = "text", max_chars: int = agent.DEFAULT_WEB_FETCH_MAX_CHARS):
        return {"status": "ok", "url": url, "content": "Overcast +2°C", "truncated": False}

    monkeypatch.setattr(agent, "_web_fetch_execute", fake_fetch)
    proposal = runtime.propose_web_fetch("https://example.com/weather", max_chars=120, reason="weather")

    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])
    runtime.planner.llm = ApprovalAwareLLM()
    result = runtime.handle_user_message("好了吗")

    assert approved["status"] == "ok"
    assert "Overcast +2°C" in runtime.memory.render()
    assert "Overcast +2°C" in result.reply_text
    assert "没收到批准" not in result.reply_text


def test_web_fetch_lease_blocks_url_and_payload_mismatch(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    proposal = runtime.propose_web_fetch("https://example.com", max_chars=120)
    approval = runtime.permission_broker.approve(proposal["proposal"]["proposal_id"])
    lease_id = approval["lease_id"]

    wrong_url = runtime.permission_broker.execute_web_fetch_with_lease(
        lease_id,
        url="https://example.org",
        max_chars=120,
    )
    wrong_limit = runtime.permission_broker.execute_web_fetch_with_lease(
        lease_id,
        url="https://example.com",
        max_chars=121,
    )

    assert wrong_url["reason"] == "lease_url_mismatch"
    assert wrong_limit["reason"] == "lease_content_hash_mismatch"


def test_web_fetch_proposal_blocks_unsafe_urls(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)

    cases = {
        "ftp://example.com": "only_http_https_allowed",
        "http://localhost": "localhost_not_allowed",
        "http://127.0.0.1": "private_or_reserved_host_not_allowed",
        "http://10.0.0.1": "private_or_reserved_host_not_allowed",
        "http://192.168.0.1": "private_or_reserved_host_not_allowed",
        "http://[::1]": "private_or_reserved_host_not_allowed",
    }

    for url, reason in cases.items():
        result = runtime.propose_web_fetch(url)
        assert result["status"] == "blocked"
        assert result["reason"] == reason


def test_heartbeat_proposal_requires_approval_and_generates_due_candidate(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)

    proposal = runtime.propose_heartbeat(delay_seconds=0, message="继续测试 EgoOperator", reason="smoke")

    assert proposal["status"] == "pending_approval"
    assert runtime.list_heartbeats()["count"] == 0

    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert approved["status"] == "ok"
    heartbeat_id = approved["execution"]["heartbeat_id"]
    assert runtime.list_heartbeats()["items"][0]["heartbeat_id"] == heartbeat_id

    due = runtime.collect_due_heartbeat_candidates()

    assert due["status"] == "ok"
    assert due["count"] == 1
    candidate = due["candidates"][0]["candidate_message"]
    assert "候选跟进" in candidate
    assert "继续测试 EgoOperator" in candidate
    assert "突然想到" not in candidate
    assert "自主意识" not in candidate


def test_cancelled_heartbeat_does_not_generate_candidate(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    proposal = runtime.propose_heartbeat(delay_seconds=0, message="不应该触发", reason="smoke")
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])
    heartbeat_id = approved["execution"]["heartbeat_id"]

    cancelled = runtime.cancel_heartbeat(heartbeat_id)
    due = runtime.collect_due_heartbeat_candidates()

    assert cancelled["status"] == "cancelled"
    assert due["count"] == 0


def test_llm_heartbeat_proposal_requires_explicit_user_intent(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.planner.llm = HeartbeatProposalThenFinalLLM()

    runtime.handle_user_message("普通聊天：你好")

    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    tool_output = trace["tool_trace"][0]["output"]
    assert tool_output["status"] == "blocked"
    assert tool_output["reason"] == "heartbeat_requires_explicit_user_intent"
    assert runtime.list_heartbeats()["count"] == 0


def test_llm_tool_loop_records_pending_proposal_in_trace(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.planner.llm = ProposalThenFinalLLM()

    result = runtime.handle_user_message("帮我创建 test/test_1.html")

    assert "待审批" in result.reply_text
    assert not (tmp_path / "test" / "test_1.html").exists()
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    tool_output = trace["tool_trace"][0]["output"]
    assert tool_output["status"] == "pending_approval"
    assert tool_output["proposal"]["action"] == "write_file"
    assert trace["operator_runtime"]["permission_broker"]["pending_count"] == 1


def test_llm_tool_loop_records_pending_web_fetch_proposal_in_trace(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.planner.llm = WebProposalThenFinalLLM()

    result = runtime.handle_user_message("帮我读取 https://example.com")

    assert "待审批" in result.reply_text
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    tool_output = trace["tool_trace"][0]["output"]
    assert tool_output["status"] == "pending_approval"
    assert tool_output["proposal"]["action"] == "web_fetch"
    assert trace["operator_runtime"]["permission_broker"]["pending_count"] == 1


def test_llm_tool_loop_records_pending_heartbeat_proposal_in_trace(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.planner.llm = HeartbeatProposalThenFinalLLM()

    result = runtime.handle_user_message("待会儿提醒我继续测试 EgoOperator")

    assert "待审批" in result.reply_text
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    tool_output = trace["tool_trace"][0]["output"]
    assert tool_output["status"] == "pending_approval"
    assert tool_output["proposal"]["action"] == "heartbeat"
    assert trace["operator_runtime"]["permission_broker"]["pending_count"] == 1
