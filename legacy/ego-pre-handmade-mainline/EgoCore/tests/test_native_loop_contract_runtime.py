from __future__ import annotations

from pathlib import Path

from app.agent_core.native_loop import NativeToolCallingLoop
from app.llm_client import LLMResponse


class FakeLLMClient:
    def chat_with_tools(self, messages, tools, **kwargs):
        return LLMResponse(
            content="",
            model="fake",
            provider="fake",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "name": "file",
                    "arguments": {
                        "operation": "write",
                        "path": kwargs["messages_target_path"] if "messages_target_path" in kwargs else "",
                        "content": "<!DOCTYPE html><html><body>EgoCore</body></html>",
                    },
                }
            ],
        )

    def generate_with_messages(self, messages, **kwargs):
        return LLMResponse(
            content="页面已创建。",
            model="fake",
            provider="fake",
        )


def test_native_loop_returns_contract_and_verification(monkeypatch, tmp_path):
    target = tmp_path / "egocore_intro.html"

    client = FakeLLMClient()
    loop = NativeToolCallingLoop(llm_client=client)

    def fake_chat_with_tools(messages, tools, **kwargs):
        return LLMResponse(
            content="",
            model="fake",
            provider="fake",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "name": "file",
                    "arguments": {
                        "operation": "write",
                        "path": str(target),
                        "content": "<!DOCTYPE html><html><body>EgoCore</body></html>",
                    },
                }
            ],
        )

    monkeypatch.setattr(client, "chat_with_tools", fake_chat_with_tools)
    monkeypatch.setattr(
        "app.agent_core.contract_runtime.execute_tool",
        lambda *args, **kwargs: type(
            "ToolExecution",
            (),
            {
                "to_dict": lambda self: {
                    "success": True,
                    "output": "ok",
                    "error": None,
                    "status": "success",
                    "metadata": {"path": str(target)},
                    "execution_time_ms": 1.0,
                }
            },
        )(),
    )
    target.write_text("<!DOCTYPE html><html><body>EgoCore</body></html>", encoding="utf-8")

    result = loop.run_turn(
        session_key="telegram:dm:1",
        user_input=f"请在 {target} 创建介绍 EgoCore 的 html 页面",
        ingress_context={
            "runtime_action": "execute_task",
            "requested_output": {
                "effective_path": str(target),
                "target_path": str(target),
                "format": "html",
                "topic": "EgoCore",
            },
        },
        proto_self_context=None,
    )

    import asyncio

    result = asyncio.run(result)

    assert result.task_contract is not None
    assert result.next_step_decision is not None
    assert result.verification_result is not None
    assert result.verification_result["expected_signal_matched"] is True
    assert "页面已创建" in result.reply_text


def test_native_loop_reads_artifact_as_explicit_step(monkeypatch):
    client = FakeLLMClient()
    loop = NativeToolCallingLoop(llm_client=client)

    monkeypatch.setattr(
        loop.contract_runtime,
        "execute_artifact_read_step",
        lambda artifact_id: {
            "success": True,
            "output": "在D:\\Project\\AIProject\\MyProject\\Test下创建一个介绍EgoCore的html页面",
            "error": None,
            "metadata": {"artifact_id": artifact_id, "stage": "artifact_parse_completed"},
            "execution_time_ms": 1.0,
        },
    )
    monkeypatch.setattr(
        loop.contract_runtime,
        "execute_single_step_with_model",
        lambda **kwargs: (
            "页面已创建。",
            [
                {
                    "tool_name": "file",
                    "arguments": {"operation": "write", "path": "D:\\Project\\AIProject\\MyProject\\Test\\task_output.html"},
                    "result": {
                        "success": True,
                        "output": "ok",
                        "error": None,
                        "metadata": {"path": "D:\\Project\\AIProject\\MyProject\\Test\\task_output.html"},
                        "execution_time_ms": 1.0,
                    },
                }
            ],
            [],
            "stop",
        ),
    )

    import asyncio

    result = asyncio.run(
        loop.run_turn(
            session_key="telegram:dm:1",
            user_input="[用户发送了文件: 任务单.txt]",
            ingress_context={
                "runtime_action": "execute_task",
                "resolved_target": {
                    "artifact_id": "artifact://compacted/demo",
                    "artifact_ref": "artifact://compacted/demo",
                    "filename": "任务单.txt",
                },
            },
            proto_self_context=None,
        )
    )

    assert result.next_step_decision["action_type"] in {"call_tool", "reply"}
    assert result.tool_results[0]["tool_name"] == "read_artifact"
    assert len(result.tool_results) >= 2
    assert "页面已创建" in result.reply_text


def test_native_loop_preserves_state_when_planning_times_out_after_artifact_relock(tmp_path, monkeypatch):
    client = FakeLLMClient()
    loop = NativeToolCallingLoop(llm_client=client)
    target = tmp_path / "task_output.html"

    monkeypatch.setattr(
        loop.contract_runtime,
        "execute_artifact_read_step",
        lambda artifact_id: {
            "success": True,
            "output": f"在{target}创建一个参照bilili的html页面,只是看着像,不用做真正的功能.",
            "error": None,
            "metadata": {"artifact_id": artifact_id, "stage": "artifact_parse_completed"},
            "execution_time_ms": 1.0,
        },
    )

    def timeout_model_call(**kwargs):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(loop.contract_runtime, "execute_single_step_with_model", timeout_model_call)

    import asyncio

    result = asyncio.run(
        loop.run_turn(
            session_key="telegram:dm:1",
            user_input="[用户发送了文件: 任务单.txt]",
            ingress_context={
                "runtime_action": "execute_task",
                "requested_output": {
                    "effective_path": str(target),
                    "target_path": str(target),
                    "format": "html",
                },
                "resolved_target": {
                    "artifact_id": "artifact://compacted/demo",
                    "artifact_ref": "artifact://compacted/demo",
                    "filename": "任务单.txt",
                },
            },
            proto_self_context=None,
        )
    )

    assert result.finish_reason == "planning_timeout"
    assert result.status == "resumable_pause"
    assert result.tool_results[0]["tool_name"] == "read_artifact"
    assert result.next_step_decision["action_type"] == "call_tool"
    assert result.task_contract["target_path"] == str(target)
    assert result.verification_result["stop_reason"] == "planning_timeout"
    assert result.reply_text == ""
    assert result.checkpoint_payload["next_step"]["action_type"] == "call_tool"


def test_native_loop_emits_progress_phases_for_execute_task(monkeypatch, tmp_path):
    client = FakeLLMClient()
    loop = NativeToolCallingLoop(llm_client=client)
    target = tmp_path / "demo.txt"
    phases = []

    monkeypatch.setattr(
        loop.contract_runtime,
        "execute_single_step_with_model",
        lambda **kwargs: (
            "处理完成。",
            [
                {
                    "tool_name": "file",
                    "arguments": {"operation": "write", "path": str(target)},
                    "result": {
                        "success": True,
                        "output": "ok",
                        "error": None,
                        "metadata": {"path": str(target)},
                        "execution_time_ms": 1.0,
                    },
                }
            ],
            [],
            "stop",
        ),
    )

    async def capture_progress(phase: str, payload: dict) -> None:
        phases.append((phase, payload.get("tool_name")))

    import asyncio

    result = asyncio.run(
        loop.run_turn(
            session_key="telegram:dm:1",
            user_input=f"在 {target} 创建 demo.txt",
            ingress_context={
                "runtime_action": "execute_task",
                "requested_output": {
                    "effective_path": str(target),
                    "target_path": str(target),
                    "format": "txt",
                },
                "resolved_target": {
                    "path": str(target),
                    "filename": "demo.txt",
                    "source": "explicit_path",
                },
            },
            proto_self_context=None,
            progress_callback=capture_progress,
        )
    )

    assert result.status == "completed_verified"
    assert [phase for phase, _ in phases] == [
        "locking_goal",
        "reading_context",
        "executing_changes",
        "verifying",
    ]
    assert phases[2][1] == "file"
