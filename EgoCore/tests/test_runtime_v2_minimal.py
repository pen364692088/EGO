import json

import pytest

from app.runtime_v2.action_protocol import RuntimeV2Action
from app.runtime_v2.loop import RuntimeV2Loop
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
