from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

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


class WrongRelativeFileProposalLLM:
    provider = "fake"
    model = "wrong-relative-file-proposal"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self, path: str = "../Test/index.html") -> None:
        self.path = path
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="我会先生成可审批写入 proposal。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_wrong_path",
                        name="propose_file_write",
                        arguments={
                            "path": self.path,
                            "content": "<!doctype html><html><head><title>T</title></head><body>ok</body></html>",
                            "reason": "operator requested a simple test page",
                            "create_parents": True,
                        },
                    )
                ],
            )
        return agent.LLMChatResult(content="已生成待审批写入 proposal，请使用 /approve 执行。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "已生成待审批写入 proposal。"


class WrongGlobThenWrongProposalLLM:
    provider = "fake"
    model = "wrong-glob-then-wrong-proposal"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="我先查看目标目录。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_wrong_glob",
                        name="glob_files",
                        arguments={"pattern": "../../Test/**/*", "max_results": 30},
                    )
                ],
            )
        if self.calls == 2:
            return agent.LLMChatResult(
                content="我会生成写入 proposal。",
                tool_calls=[
                    agent.LLMToolCall(
                        id="call_wrong_write_path",
                        name="propose_file_write",
                        arguments={
                            "path": "../Test/index.html",
                            "content": "<!doctype html><html><head><title>T</title></head><body>ok</body></html>",
                            "reason": "operator requested a simple test page",
                            "create_parents": True,
                        },
                    )
                ],
            )
        return agent.LLMChatResult(content="已生成待审批写入 proposal，请使用 /approve 执行。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "已生成待审批写入 proposal。"


class EmptyThenProposalLLM:
    provider = "fake"
    model = "empty-then-proposal"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(content="", tool_calls=[])
        joined = json.dumps(messages, ensure_ascii=False)
        assert "empty_response_repair" in joined
        return agent.LLMChatResult(
            content="空回复已修复，我会生成写入 proposal。",
            tool_calls=[
                agent.LLMToolCall(
                    id="call_after_empty_repair",
                    name="propose_file_write",
                    arguments={
                        "path": "test/index.html",
                        "content": "<!doctype html><html><head><title>T</title></head><body>ok</body></html>",
                        "reason": "operator requested a simple test page",
                        "create_parents": True,
                    },
                )
            ],
        )

    def complete(self, prompt, messages=None):
        return "已生成待审批写入 proposal。"


class AlwaysEmptyLLM:
    provider = "fake"
    model = "always-empty"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        return agent.LLMChatResult(content="   ", tool_calls=[])

    def complete(self, prompt, messages=None):
        return ""


class HallucinatedApprovalThenProposalLLM:
    provider = "fake"
    model = "hallucinated-approval-then-proposal"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content=(
                    "已生成待审批操作，当前不会继续调用工具。\n\n"
                    "Pending operation approval:\n"
                    "- id: proposal_0a1b2c3d4e5f\n"
                    "- action: write_file\n"
                    "- path: test/index.html\n\n"
                    "批准执行：\n- /approve proposal_0a1b2c3d4e5f"
                ),
                tool_calls=[],
            )
        joined = json.dumps(messages, ensure_ascii=False)
        assert "unbacked_approval_repair" in joined
        return agent.LLMChatResult(
            content="我会改为调用真实 proposal 工具。",
            tool_calls=[
                agent.LLMToolCall(
                    id="call_real_proposal_after_hallucination",
                    name="propose_file_write",
                    arguments={
                        "path": "test/index.html",
                        "content": "<!doctype html><html><head><title>T</title></head><body>ok</body></html>",
                        "reason": "operator requested a simple test page",
                        "create_parents": True,
                    },
                )
            ],
        )

    def complete(self, prompt, messages=None):
        return "已生成待审批写入 proposal。"


class HallucinatedApprovalTwiceThenProposalLLM:
    provider = "fake"
    model = "hallucinated-approval-twice-then-proposal"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls <= 2:
            fake_id = f"proposal_fake_attempt_{self.calls}"
            return agent.LLMChatResult(
                content=(
                    "已生成待审批操作，当前不会继续调用工具。\n\n"
                    "Pending operation approval:\n"
                    f"- id: {fake_id}\n"
                    "- action: write_file\n"
                    "- path: test/index.html\n\n"
                    "批准执行：\n"
                    f"- /approve {fake_id}"
                ),
                tool_calls=[],
            )
        joined = json.dumps(messages, ensure_ascii=False)
        assert "unbacked_approval_repair" in joined
        assert "Attempt 2/2" in joined
        return agent.LLMChatResult(
            content="我会改为调用真实 proposal 工具。",
            tool_calls=[
                agent.LLMToolCall(
                    id="call_real_proposal_after_second_hallucination",
                    name="propose_file_write",
                    arguments={
                        "path": "test/index.html",
                        "content": "<!doctype html><html><head><title>T</title></head><body>ok</body></html>",
                        "reason": "operator requested a simple test page",
                        "create_parents": True,
                    },
                )
            ],
        )

    def complete(self, prompt, messages=None):
        return "已生成待审批写入 proposal。"


class AlwaysHallucinatedApprovalLLM:
    provider = "fake"
    model = "always-hallucinated-approval"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        fake_id = "proposal_6f7e8d9c0b1a"
        return agent.LLMChatResult(
            content=(
                "已生成待审批操作，当前不会继续调用工具。\n\n"
                "Pending operation approval:\n"
                f"- id: {fake_id}\n"
                "- action: write_file\n"
                "- path: test/index.html\n\n"
                "批准执行：\n"
                f"- /approve {fake_id}"
            ),
            tool_calls=[],
        )

    def complete(self, prompt, messages=None):
        return "已生成待审批写入 proposal。"


class AllowedRootRefusalThenFallbackProposalLLM:
    provider = "fake"
    model = "allowed-root-refusal-then-fallback-proposal"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        if self.calls == 1:
            return agent.LLMChatResult(
                content="这个路径不在我的 workspace 内，我无法直接写入。我可以改在 workspace 的 Test/index.html 创建。",
                tool_calls=[],
            )
        joined = json.dumps(messages, ensure_ascii=False)
        assert "allowed_root_refusal_repair" in joined
        return agent.LLMChatResult(
            content="我会改为调用真实 proposal 工具。",
            tool_calls=[
                agent.LLMToolCall(
                    id="call_allowed_root_repair_proposal",
                    name="propose_file_write",
                    arguments={
                        "path": "Test/index.html",
                        "content": "<!doctype html><html><head><title>T</title></head><body>ok</body></html>",
                        "reason": "operator requested a simple test page under an allowed root",
                        "create_parents": True,
                    },
                )
            ],
        )

    def complete(self, prompt, messages=None):
        return "已生成待审批写入 proposal。"


class OutsideRootRefusalLLM:
    provider = "fake"
    model = "outside-root-refusal"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        return agent.LLMChatResult(
            content="这个路径不在我的 workspace 内，也不在允许范围内，无法写入。",
            tool_calls=[],
        )

    def complete(self, prompt, messages=None):
        return "无法写入。"


class RateLimitedLLM:
    provider = "fake"
    model = "rate-limited"
    last_usage = {}
    last_reasoning_tokens = None

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        raise RuntimeError("429 Client Error: Too Many Requests for url: https://openrouter.ai/api/v1/chat/completions")

    def complete(self, prompt, messages=None):
        raise RuntimeError("429 Client Error: Too Many Requests")


class StructuredProviderErrorLLM:
    provider = "openrouter"
    last_usage = {}
    last_reasoning_tokens = None
    last_fallback_used = False
    last_fallback_chain = []

    def __init__(self, error: agent.OpenRouterProviderError) -> None:
        self.error = error
        self.model = error.model
        self.configured_model = error.model
        self.last_provider_error = error.to_metadata()

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        raise self.error

    def complete(self, prompt, messages=None):
        raise self.error


class FakeHTTPResponse:
    def __init__(self, status_code: int, payload=None, headers=None, text: str = "", reason: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text
        self.reason = reason

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeRequests:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def post(self, url, *, headers=None, json=None, timeout=None, stream=False):
        self.calls.append({"url": url, "model": (json or {}).get("model"), "stream": stream})
        if not self.responses:
            raise AssertionError("unexpected extra request")
        return self.responses.pop(0)


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


class FileApprovalAwareLLM:
    provider = "fake"
    model = "file-approval-aware"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self, expected_path_fragment: str) -> None:
        self.expected_path_fragment = expected_path_fragment

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        joined = json.dumps(messages, ensure_ascii=False)
        if self.expected_path_fragment in joined and "path_written" in joined:
            return agent.LLMChatResult(content=f"好了，文件已创建：{self.expected_path_fragment}", tool_calls=[])
        return agent.LLMChatResult(content="还没看到文件写入结果。", tool_calls=[])

    def complete(self, prompt, messages=None):
        return "好了。"


class LoopingToolLLM:
    provider = "fake"
    model = "looping-tool"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.calls = 0
        self.system_messages_seen = 0

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.calls += 1
        self.system_messages_seen += len([
            message
            for message in messages
            if message.get("role") == "system" and "tool_loop_checkpoint" in str(message.get("content", ""))
        ])
        return agent.LLMChatResult(
            content="继续调用工具。",
            tool_calls=[
                agent.LLMToolCall(
                    id=f"call_time_{self.calls}",
                    name="current_time",
                    arguments={},
                )
            ],
        )

    def complete(self, prompt, messages=None):
        return "继续。"


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
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
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


def test_proposal_and_approval_update_in_session_commitment_memory(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)

    proposal = runtime.propose_file_write("test/commitment.html", "<h1>ok</h1>", reason="commitment smoke")
    proposal_id = proposal["proposal"]["proposal_id"]
    pending_memory = runtime.memory.render()

    assert "[operator_runtime_commitment]" in pending_memory
    assert proposal_id in pending_memory
    assert "pending_approval" in pending_memory
    assert runtime.commitments[proposal_id]["status"] == "pending_approval"

    approved = runtime.approve_pending_operation(proposal_id)
    completed_memory = runtime.memory.render()

    assert approved["status"] == "ok"
    assert "[operator_runtime_decision]" in completed_memory
    assert "operator_runtime_commitment_completion" in completed_memory
    assert "completed" in completed_memory
    assert runtime.commitments[proposal_id]["status"] == "completed"
    assert runtime.commitments[proposal_id]["execution"]["status"] == "ok"


def test_absolute_path_under_allowed_root_can_create_pending_file_write(tmp_path, monkeypatch):
    workspace = tmp_path / "Ego" / "EgoOperator"
    workspace.mkdir(parents=True)
    allowed_root = tmp_path / "MyProject"
    target = allowed_root / "Test" / "index.html"
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (workspace, allowed_root))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")

    proposal = runtime.propose_file_write(
        str(target),
        "<!doctype html><html><head><title>T</title></head><body>ok</body></html>",
        reason="external allowed root smoke",
    )
    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])

    assert proposal["status"] == "pending_approval"
    assert proposal["proposal"]["path"] == str(target.resolve())
    assert approved["status"] == "ok"
    assert target.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_file_path_intent_corrects_wrong_relative_proposal(tmp_path, monkeypatch):
    workspace = tmp_path / "MyProject" / "Ego" / "EgoOperator"
    allowed_root = tmp_path / "MyProject"
    intended_dir = allowed_root / "Test"
    wrong_dir = allowed_root / "Ego" / "Test"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (workspace, allowed_root))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = WrongRelativeFileProposalLLM("../Test/index.html")

    result = runtime.handle_user_message(f"在{intended_dir}下创建一个测试用的简单网页")
    proposal = runtime.list_pending_approvals()["items"][0]
    approved = runtime.approve_pending_operation(proposal["proposal_id"])

    assert result.external_result["status"] == "pending_approval"
    assert proposal["path"] == str((intended_dir / "index.html").resolve())
    assert proposal["resolved_path"] == str((intended_dir / "index.html").resolve())
    assert approved["status"] == "ok"
    assert (intended_dir / "index.html").exists()
    assert not (wrong_dir / "index.html").exists()

    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    path_intent = trace["tool_trace"][0]["tool_call"]["path_intent"]
    assert path_intent["status"] == "corrected"
    assert path_intent["intended_path"] == str(intended_dir.resolve())
    assert path_intent["proposed_path"] == str((wrong_dir / "index.html").resolve())
    assert path_intent["corrected_path"] == str((intended_dir / "index.html").resolve())


def test_file_path_intent_corrects_wrong_relative_glob_then_write_proposal(tmp_path, monkeypatch):
    workspace = tmp_path / "MyProject" / "Ego" / "EgoOperator"
    allowed_root = tmp_path / "MyProject"
    intended_dir = allowed_root / "Test"
    wrong_dir = allowed_root / "Ego" / "Test"
    intended_dir.mkdir(parents=True)
    (intended_dir / "CLAUDE.md").write_text("target marker", encoding="utf-8")
    workspace.mkdir(parents=True)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (workspace, allowed_root))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = WrongGlobThenWrongProposalLLM()

    result = runtime.handle_user_message(f"帮我在{intended_dir}下创建一个简单的测试网页")
    proposal = runtime.list_pending_approvals()["items"][0]

    assert result.external_result["status"] == "pending_approval"
    assert proposal["path"] == str((intended_dir / "index.html").resolve())
    assert not (wrong_dir / "index.html").exists()

    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    glob_trace = trace["tool_trace"][0]
    write_trace = trace["tool_trace"][1]
    assert glob_trace["tool_call"]["name"] == "glob_files"
    assert glob_trace["gate"]["reason"] == "tool_call_allowed"
    assert glob_trace["output"]["status"] == "ok"
    assert glob_trace["tool_call"]["arguments"]["pattern"] == str((intended_dir / "**" / "*").resolve())
    assert glob_trace["tool_call"]["path_intent"]["status"] == "corrected"
    assert "invalid_glob_pattern" not in json.dumps(glob_trace, ensure_ascii=False)
    assert write_trace["tool_call"]["name"] == "propose_file_write"
    assert write_trace["tool_call"]["arguments"]["path"] == str((intended_dir / "index.html").resolve())
    assert write_trace["tool_call"]["path_intent"]["status"] == "corrected"


def test_allowed_root_workspace_refusal_triggers_repair_and_preserves_target_path(tmp_path, monkeypatch):
    workspace = tmp_path / "MyProject" / "Ego" / "EgoOperator"
    allowed_root = tmp_path / "MyProject"
    intended_dir = allowed_root / "Test3"
    fallback_dir = workspace / "Test"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (workspace, allowed_root))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    llm = AllowedRootRefusalThenFallbackProposalLLM()
    runtime.planner.llm = llm

    result = runtime.handle_user_message(f"在{intended_dir}创建一个测试网页")
    pending = runtime.list_pending_approvals()["items"]

    assert llm.calls == 2
    assert result.external_result["status"] == "pending_approval"
    assert len(pending) == 1
    assert pending[0]["path"] == str((intended_dir / "index.html").resolve())
    assert pending[0]["resolved_path"] == str((intended_dir / "index.html").resolve())
    assert "workspace 的 Test/index.html" not in result.reply_text
    assert not (fallback_dir / "index.html").exists()

    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    write_trace = trace["tool_trace"][0]
    assert write_trace["tool_call"]["name"] == "propose_file_write"
    assert write_trace["tool_call"]["path_intent"]["status"] == "corrected"
    assert write_trace["tool_call"]["path_intent"]["intended_path"] == str(intended_dir.resolve())
    assert write_trace["tool_call"]["arguments"]["path"] == str((intended_dir / "index.html").resolve())


def test_outside_allowed_root_workspace_refusal_is_not_repaired(tmp_path, monkeypatch):
    workspace = tmp_path / "MyProject" / "Ego" / "EgoOperator"
    allowed_root = tmp_path / "MyProject"
    outside_dir = tmp_path / "Outside" / "Test3"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (workspace, allowed_root))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")
    llm = OutsideRootRefusalLLM()
    runtime.planner.llm = llm

    result = runtime.handle_user_message(f"在{outside_dir}创建一个测试网页")

    assert llm.calls == 1
    assert result.external_result["status"] == "sent"
    assert "不在我的 workspace" in result.reply_text
    assert runtime.list_pending_approvals()["count"] == 0
    assert not (outside_dir / "index.html").exists()


def test_windows_path_intent_extracts_as_wsl_normalized_allowed_path(monkeypatch):
    workspace = Path("/mnt/d/Project/AIProject/MyProject/Ego/EgoOperator")
    allowed_root = Path("/mnt/d/Project/AIProject/MyProject")
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (workspace, allowed_root))

    intents = agent._extract_local_path_intents(r"在D:\Project\AIProject\MyProject\Test下创建一个测试网页")

    assert len(intents) == 1
    assert intents[0].raw_path == r"D:\Project\AIProject\MyProject\Test"
    assert intents[0].resolved_path == "/mnt/d/Project/AIProject/MyProject/Test"
    assert intents[0].is_directory is True


def test_path_outside_allowed_roots_is_blocked(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    allowed_root = tmp_path / "allowed"
    outside = tmp_path / "outside" / "blocked.html"
    workspace.mkdir()
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (workspace, allowed_root))
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")

    blocked = runtime.propose_file_write(str(outside), "bad")

    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "path_outside_workspace"


def test_absolute_glob_under_allowed_root_returns_matches(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    allowed_root = tmp_path / "MyProject"
    target = allowed_root / "Test" / "index.html"
    target.parent.mkdir(parents=True)
    target.write_text("ok", encoding="utf-8")
    workspace.mkdir()
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (workspace, allowed_root))

    result = agent.glob_files_tool(str(allowed_root / "Test" / "*.html"))

    assert result["status"] == "ok"
    assert str(target.resolve()) in result["matches"]


def test_html_preflight_warnings_are_non_blocking(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)

    proposal = runtime.propose_file_write("test/bad.html", "<html><head></head>")

    assert proposal["status"] == "pending_approval"
    warnings = proposal["proposal"]["preflight_warnings"]
    assert "html_missing_doctype" in warnings
    assert "html_missing_body_tag" in warnings
    assert "preflight_warnings" in proposal["action_card"]


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
    assert "/approve" in result.reply_text
    assert "工具调用循环超过上限" not in result.reply_text


def test_pending_approval_finalizes_without_hitting_tool_loop_limit(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.planner.llm = ProposalThenFinalLLM()
    monkeypatch.setattr(agent, "DEFAULT_MAX_TOOL_LOOPS", 1)
    monkeypatch.setattr(agent, "DEFAULT_TOOL_LOOP_HARD_CAP", 3)

    result = runtime.handle_user_message("帮我创建 test/test_1.html")

    assert result.external_result["status"] == "pending_approval"
    assert "/approve" in result.reply_text
    assert "hard cap" not in result.reply_text
    assert "工具调用循环超过上限" not in result.reply_text


def test_empty_llm_response_triggers_repair_turn_and_can_generate_proposal(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    llm = EmptyThenProposalLLM()
    runtime.planner.llm = llm

    result = runtime.handle_user_message("帮我创建 test/index.html")

    assert llm.calls == 2
    assert result.external_result["status"] == "pending_approval"
    assert "待审批" in result.reply_text
    assert runtime.list_pending_approvals()["count"] == 1
    assistant_messages = [message for message in runtime.memory.as_messages() if message["role"] == "assistant"]
    assert assistant_messages
    assert all(str(message.get("content", "")).strip() for message in assistant_messages)


def test_consecutive_empty_llm_response_returns_non_empty_recovery_without_side_effect(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    llm = AlwaysEmptyLLM()
    runtime.planner.llm = llm

    result = runtime.handle_user_message("帮我创建 test/index.html")

    assert llm.calls == 2
    assert result.external_result["status"] == "llm_empty_response"
    assert "模型连续返回了空回复" in result.reply_text
    assert "没有执行文件创建或修改" in result.reply_text
    assert runtime.list_pending_approvals()["count"] == 0
    assert not (tmp_path / "test" / "index.html").exists()
    assistant_messages = [message for message in runtime.memory.as_messages() if message["role"] == "assistant"]
    assert assistant_messages
    assert all(str(message.get("content", "")).strip() for message in assistant_messages)


def test_hallucinated_approval_card_triggers_repair_and_real_proposal(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    llm = HallucinatedApprovalThenProposalLLM()
    runtime.planner.llm = llm

    result = runtime.handle_user_message("帮我创建 test/index.html")
    pending = runtime.list_pending_approvals()["items"]

    assert llm.calls == 2
    assert result.external_result["status"] == "pending_approval"
    assert len(pending) == 1
    assert pending[0]["proposal_id"] != "proposal_0a1b2c3d4e5f"
    assert pending[0]["path"] == "test/index.html"
    assert "/approve proposal_0a1b2c3d4e5f" not in result.reply_text
    assert f"/approve {pending[0]['proposal_id']}" in result.reply_text
    assert not (tmp_path / "test" / "index.html").exists()


def test_hallucinated_approval_card_auto_repairs_twice_before_real_proposal(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    llm = HallucinatedApprovalTwiceThenProposalLLM()
    runtime.planner.llm = llm

    result = runtime.handle_user_message("帮我创建 test/index.html")
    pending = runtime.list_pending_approvals()["items"]

    assert llm.calls == 3
    assert result.external_result["status"] == "pending_approval"
    assert len(pending) == 1
    assert pending[0]["proposal_id"] not in {"proposal_fake_attempt_1", "proposal_fake_attempt_2"}
    assert pending[0]["path"] == "test/index.html"
    assert "/approve proposal_fake_attempt_1" not in result.reply_text
    assert "/approve proposal_fake_attempt_2" not in result.reply_text
    assert f"/approve {pending[0]['proposal_id']}" in result.reply_text
    assert "请重试同一句请求" not in result.reply_text
    assert not (tmp_path / "test" / "index.html").exists()


def test_repeated_hallucinated_approval_card_returns_non_executable_recovery(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    llm = AlwaysHallucinatedApprovalLLM()
    runtime.planner.llm = llm

    result = runtime.handle_user_message("帮我创建 test/index.html")

    assert llm.calls == 3
    assert result.external_result["status"] == "unbacked_approval_auto_repair_exhausted"
    assert result.external_result["auto_repair_attempts"] == 2
    assert "没有对应的真实 proposal" in result.reply_text
    assert "已自动尝试修复：2 次" in result.reply_text
    assert "没有执行文件创建或修改" in result.reply_text
    assert "请重试同一句请求" not in result.reply_text
    assert "proposal_6f7e8d9c0b1a" in result.reply_text
    assert "/approve proposal_6f7e8d9c0b1a" not in result.reply_text
    assert runtime.list_pending_approvals()["count"] == 0
    assert not (tmp_path / "test" / "index.html").exists()


def test_provider_429_in_tool_loop_returns_chinese_error_not_nollm_fallback(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.planner.llm = RateLimitedLLM()

    result = runtime.handle_user_message("帮我创建 test/index.html")

    assert result.external_result["status"] == "llm_error"
    assert result.action.reason == "llm_tool_loop_provider_error"
    assert "429" in result.reply_text
    assert "模型/API" in result.reply_text
    assert "文件操作恢复" not in result.reply_text
    assert "没有执行外部副作用" in result.reply_text
    assert "非 free 模型" not in result.reply_text
    assert "I can help with that" not in result.reply_text
    assert runtime.list_pending_approvals()["count"] == 0
    assert not (tmp_path / "test" / "index.html").exists()
    assistant_messages = [message for message in runtime.memory.as_messages() if message["role"] == "assistant"]
    assert assistant_messages
    assert all(str(message.get("content", "")).strip() for message in assistant_messages)


def test_openrouter_429_error_preserves_retry_after_body_and_model(monkeypatch):
    fake_requests = FakeRequests([
        FakeHTTPResponse(
            429,
            {"error": {"message": "Provider rate limited upstream", "code": 429, "status": 429}},
            headers={"Retry-After": "60"},
        )
    ])
    monkeypatch.setattr(agent, "requests", fake_requests)
    llm = agent.OpenRouterLLM(agent.LLMConfig(api_key="sk-test", model="tencent/hy3-preview", stream=False))

    with pytest.raises(agent.OpenRouterProviderError) as exc_info:
        llm.chat([{"role": "user", "content": "你好"}], system_prompt="system", stream=False)

    error = exc_info.value
    metadata = error.to_metadata()
    assert error.status_code == 429
    assert error.model == "tencent/hy3-preview"
    assert error.retry_after == "60"
    assert "Provider rate limited upstream" in error.message
    assert metadata["status_code"] == 429
    assert metadata["retry_after"] == "60"
    assert "sk-test" not in json.dumps(metadata, ensure_ascii=False)


def test_openrouter_fallback_on_503_records_chain(monkeypatch):
    fake_requests = FakeRequests([
        FakeHTTPResponse(503, {"error": {"message": "provider unavailable", "code": 503}}, headers={"Retry-After": "10"}),
        FakeHTTPResponse(
            200,
            {
                "choices": [{"message": {"content": "备用模型回复", "tool_calls": []}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            },
        ),
    ])
    monkeypatch.setattr(agent, "requests", fake_requests)
    llm = agent.OpenRouterLLM(agent.LLMConfig(
        api_key="sk-test",
        model="primary/model",
        fallback_mode="on",
        fallback_models=("fallback/model",),
        stream=False,
    ))

    result = llm.chat([{"role": "user", "content": "你好"}], system_prompt="system", stream=False)

    assert result.content == "备用模型回复"
    assert [call["model"] for call in fake_requests.calls] == ["primary/model", "fallback/model"]
    assert llm.model == "fallback/model"
    assert llm.last_fallback_used is True
    assert llm.last_fallback_chain[0]["status"] == "error"
    assert llm.last_fallback_chain[0]["status_code"] == 503
    assert llm.last_fallback_chain[1] == {"model": "fallback/model", "status": "ok"}


def test_openrouter_fallback_on_429_records_chain(monkeypatch):
    fake_requests = FakeRequests([
        FakeHTTPResponse(429, {"error": {"message": "rate limited", "code": 429}}, headers={"Retry-After": "30"}),
        FakeHTTPResponse(200, {"choices": [{"message": {"content": "fallback ok", "tool_calls": []}}]}),
    ])
    monkeypatch.setattr(agent, "requests", fake_requests)
    llm = agent.OpenRouterLLM(agent.LLMConfig(
        api_key="sk-test",
        model="primary/model",
        fallback_mode="on",
        fallback_models=("fallback/model",),
        stream=False,
    ))

    result = llm.chat([{"role": "user", "content": "你好"}], system_prompt="system", stream=False)

    assert result.content == "fallback ok"
    assert [call["model"] for call in fake_requests.calls] == ["primary/model", "fallback/model"]
    assert llm.last_fallback_used is True
    assert llm.last_fallback_chain[0]["status_code"] == 429
    assert llm.last_fallback_chain[0]["retry_after"] == "30"
    assert llm.last_fallback_chain[1]["status"] == "ok"


def test_openrouter_does_not_fallback_on_400_401_or_403(monkeypatch):
    for status_code in (400, 401, 403):
        fake_requests = FakeRequests([
            FakeHTTPResponse(status_code, {"error": {"message": f"error {status_code}", "code": status_code}}),
            FakeHTTPResponse(200, {"choices": [{"message": {"content": "should not happen"}}]}),
        ])
        monkeypatch.setattr(agent, "requests", fake_requests)
        llm = agent.OpenRouterLLM(agent.LLMConfig(
            api_key="sk-test",
            model="primary/model",
            fallback_mode="on",
            fallback_models=("fallback/model",),
            stream=False,
        ))

        with pytest.raises(agent.OpenRouterProviderError) as exc_info:
            llm.chat([{"role": "user", "content": "你好"}], system_prompt="system", stream=False)

        assert exc_info.value.status_code == status_code
        assert [call["model"] for call in fake_requests.calls] == ["primary/model"]


def test_structured_paid_model_429_reply_has_diagnostics_without_free_model_advice(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    error = agent.OpenRouterProviderError(
        status_code=429,
        model="tencent/hy3-preview",
        message="Provider returned rate limit",
        response_body='{"error":{"message":"Provider returned rate limit","code":429}}',
        retry_after="45",
    )
    runtime.planner.llm = StructuredProviderErrorLLM(error)

    result = runtime.handle_user_message("你好")

    assert result.external_result["status"] == "llm_error"
    assert result.external_result["provider_error"]["status_code"] == 429
    assert result.external_result["provider_error"]["model"] == "tencent/hy3-preview"
    assert "文件操作恢复" not in result.reply_text
    assert "effective model：tencent/hy3-preview" in result.reply_text
    assert "Provider returned rate limit" in result.reply_text
    assert "Retry-After：45 秒" in result.reply_text
    assert "非 free 模型" not in result.reply_text
    assert "没有执行外部副作用" in result.reply_text


def test_structured_402_reply_points_to_credits_not_fallback(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    error = agent.OpenRouterProviderError(
        status_code=402,
        model="tencent/hy3-preview",
        message="Insufficient credits",
        response_body='{"error":{"message":"Insufficient credits","code":402}}',
    )
    runtime.planner.llm = StructuredProviderErrorLLM(error)

    result = runtime.handle_user_message("你好")

    assert result.external_result["provider_error"]["status_code"] == 402
    assert "402" in result.reply_text
    assert "credits" in result.reply_text
    assert "补足余额" in result.reply_text
    assert "开启 fallback" not in result.reply_text


def test_approved_file_write_result_is_available_to_next_turn(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    target = tmp_path / "external" / "index.html"
    monkeypatch.setattr(agent, "DEFAULT_AGENT_ALLOWED_ROOTS", (tmp_path,))
    proposal = runtime.propose_file_write(
        str(target),
        "<!doctype html><html><head><title>T</title></head><body>ok</body></html>",
        reason="external file",
    )

    approved = runtime.approve_pending_operation(proposal["proposal"]["proposal_id"])
    runtime.planner.llm = FileApprovalAwareLLM(str(target.resolve()))
    result = runtime.handle_user_message("好了吗")

    assert approved["status"] == "ok"
    assert target.exists()
    assert str(target.resolve()) in runtime.memory.render()
    assert str(target.resolve()) in result.reply_text


def test_tool_loop_soft_checkpoint_and_hard_cap_stop_runaway_llm(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch)
    llm = LoopingToolLLM()
    runtime.planner.llm = llm
    monkeypatch.setattr(agent, "DEFAULT_MAX_TOOL_LOOPS", 2)
    monkeypatch.setattr(agent, "DEFAULT_TOOL_LOOP_HARD_CAP", 5)

    result = runtime.handle_user_message("一直查时间")

    assert result.action.reason == "tool_loop_hard_cap"
    assert result.gate.reason == "tool_loop_hard_cap"
    assert "hard cap (5)" in result.reply_text
    assert result.external_result["tool_calls"] == 5
    assert llm.calls == 5
    assert llm.system_messages_seen >= 2


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
