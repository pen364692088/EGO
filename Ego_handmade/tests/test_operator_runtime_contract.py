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


def _runtime(tmp_path, monkeypatch, *, mode="approve", allowlist=()):
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_WRITE_ALLOWLIST", tuple(allowlist))
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WRITE_FILE", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_RUN_COMMAND", False)
    monkeypatch.setattr(agent, "DEFAULT_ENABLE_WEB_FETCH", False)
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode=mode)
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    return runtime


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
