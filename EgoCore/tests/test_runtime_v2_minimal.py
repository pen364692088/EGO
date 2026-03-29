import json

import pytest

from app.runtime_v2.action_protocol import RuntimeV2Action
from app.runtime_v2.loop import RuntimeV2Loop
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.verifier import RuntimeV2Verifier


def test_action_protocol_parses_complete_json():
    action = RuntimeV2Action.from_model_output('{"type":"complete","summary":"done","verification":{"target":"/tmp/x"}}')
    assert action.type == "complete"
    assert action.summary == "done"
    assert action.verification["target"] == "/tmp/x"


def test_verifier_fails_when_target_missing(tmp_path):
    verifier = RuntimeV2Verifier()
    result = verifier.verify_complete({"target": str(tmp_path / 'missing.html')}, None)
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_runtime_v2_loop_runs_plan_act_complete(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    target = tmp_path / "hello.html"
    target.write_text("background: modern", encoding="utf-8")

    actions = iter([
        RuntimeV2Action.from_model_output(
            json.dumps({"type": "plan", "goal": "改配色", "steps": ["修改文件", "验证结果"]}, ensure_ascii=False)
        ),
        RuntimeV2Action.from_model_output(
            json.dumps(
                {
                    "type": "act",
                    "tool": "file",
                    "input": {"operation": "read", "path": str(target)},
                },
                ensure_ascii=False,
            )
        ),
        RuntimeV2Action.from_model_output(
            json.dumps(
                {
                    "type": "complete",
                    "summary": "已完成",
                    "verification": {"target": str(target), "expected": "modern"},
                },
                ensure_ascii=False,
            )
        ),
    ])

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(_tool, _tool_input):
        return {"success": True, "tool": "file", "stdout": "background: modern", "stderr": "", "exit_code": 0, "metadata": {}}

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)
    result = await loop.run_turn_typed("session:test", "请修改 hello.html 配色")
    assert result.status == "completed_verified"
    assert result.reply_text == "已完成"


def test_runtime_v2_loop_promotes_explicit_analyze_shell_read_to_file_read():
    loop = RuntimeV2Loop()
    target = r"D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md"
    state = RuntimeV2State(session_id="session:explicit-read")
    state.ingress_context = {
        "request_mode": "analyze",
        "runtime_action": "execute_task",
        "resolved_target": {
            "source": "explicit_path",
            "path": target,
            "filename": "PROJECT_MEMORY.md",
        },
    }
    action = RuntimeV2Action.from_model_output(
        json.dumps(
            {
                "type": "act",
                "tool": "shell",
                "input": {"command": f'type "{target}"'},
            },
            ensure_ascii=False,
        )
    )

    normalized = loop._normalize_action_for_host_contract(state, action)

    assert normalized.tool == "file"
    assert normalized.input == {"operation": "read", "path": target}
    assert normalized.raw["host_normalization"]["kind"] == "explicit_path_analyze_promoted_to_file_read"


@pytest.mark.asyncio
async def test_runtime_v2_loop_executes_explicit_analyze_with_file_tool(monkeypatch):
    loop = RuntimeV2Loop()
    target = r"D:\Project\AIProject\MyProject\Ego\PROJECT_MEMORY.md"
    state = loop.get_state("session:explicit-read-turn")
    state.ingress_context = {
        "request_mode": "analyze",
        "runtime_action": "execute_task",
        "resolved_target": {
            "source": "explicit_path",
            "path": target,
            "filename": "PROJECT_MEMORY.md",
        },
    }

    actions = iter(
        [
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "act",
                        "tool": "shell",
                        "input": {"command": f'type "{target}"'},
                    },
                    ensure_ascii=False,
                )
            ),
            RuntimeV2Action.from_model_output(
                json.dumps(
                    {
                        "type": "complete",
                        "summary": "已读取完成",
                        "verification": {"target": target, "expected": "项目记忆"},
                    },
                    ensure_ascii=False,
                )
            ),
        ]
    )

    async def fake_decide(_state):
        return next(actions)

    async def fake_execute(tool, tool_input):
        assert tool == "file"
        assert tool_input == {"operation": "read", "path": target}
        return {
            "success": True,
            "tool": "file",
            "stdout": "项目记忆",
            "stderr": "",
            "exit_code": 0,
            "metadata": {},
        }

    monkeypatch.setattr(loop, "_decide", fake_decide)
    monkeypatch.setattr(loop.tool_broker, "execute", fake_execute)
    monkeypatch.setattr(
        loop.verifier,
        "verify_complete",
        lambda verification, last_tool_result: {"passed": True, "reason": "stubbed"},
    )

    result = await loop.run_turn_typed("session:explicit-read-turn", f'看看这个文件 "{target}"')

    assert result.status == "completed_verified"
    assert result.reply_text == "已读取完成"
